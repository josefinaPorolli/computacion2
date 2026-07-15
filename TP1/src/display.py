"""
display.py — TUI del monitor usando rich.

Estructura:
  - Proceso display: loop principal que renderiza la pantalla
  - Thread de teclado: escucha teclas y actualiza el estado

Zonas de la pantalla:
  1. Barra superior: stats del sistema
  2. Lista de procesos: navegable con ↑↓
  3. Panel de detalle: cambia según vista activa
  4. Barra inferior: keybindings
"""

import os
import sys
import time
import threading
import multiprocessing as mp
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich import box


# ---------------------------------------------------------------------------
# Estado compartido entre loop principal y thread de teclado
# ---------------------------------------------------------------------------

class EstadoDisplay:
    def __init__(self):
        self.lock            = threading.Lock()
        self.vista_activa    = 'resumen'
        self.indice_lista    = 0
        self.pid_seleccionado = None
        self.filtro_cmd      = None
        self.filtro_usuario  = None
        self.orden           = 'cpu'
        self.corriendo       = True
        self.modo_verbose    = False

    def get(self, attr):
        with self.lock:
            return getattr(self, attr)

    def set(self, attr, valor):
        with self.lock:
            setattr(self, attr, valor)


# ---------------------------------------------------------------------------
# Mapa de teclas → vistas
# ---------------------------------------------------------------------------

VISTAS = {
    '1': 'resumen',    'r': 'resumen',
    '2': 'memoria',    'm': 'memoria',
    '3': 'fds',        'f': 'fds',
    '4': 'threads',    't': 'threads',
    '5': 'senales',    's': 'senales',
    '6': 'scheduling', 'p': 'scheduling',
    '7': 'sistema',    'g': 'sistema',
}

ORDENES = ['cpu', 'rss', 'pid']


# ---------------------------------------------------------------------------
# Helpers de renderizado
# ---------------------------------------------------------------------------

def fmt_kb(kb):
    """Convierte kB a formato legible."""
    if kb >= 1024 * 1024:
        return f"{kb / 1024 / 1024:.1f}GB"
    elif kb >= 1024:
        return f"{kb / 1024:.1f}MB"
    return f"{kb}kB"


def fmt_estado(estado):
    """Colorea el estado del proceso."""
    colores = {'R': 'green', 'S': 'blue', 'D': 'red', 'T': 'yellow', 'Z': 'magenta'}
    color = colores.get(estado, 'white')
    return f"[{color}]{estado}[/{color}]"


def obtener_procesos_filtrados(snapshot, estado):
    """
    Obtiene la lista de procesos del snapshot, aplicando filtros y orden.
    """
    datos = snapshot.get('resumen', {})
    if not datos:
        return []

    procs = list(datos.values())

    # Aplicar filtros
    if estado.get('filtro_cmd'):
        filtro = estado.get('filtro_cmd').lower()
        procs = [p for p in procs if filtro in p.get('nombre', '').lower()
                 or filtro in p.get('cmdline', '').lower()]

    if estado.get('filtro_usuario'):
        filtro = estado.get('filtro_usuario').lower()
        procs = [p for p in procs if filtro in p.get('usuario', '').lower()]

    # Ordenar
    orden = estado.get('orden')
    if orden == 'cpu':
        procs.sort(key=lambda p: p.get('cpu', 0), reverse=True)
    elif orden == 'rss':
        procs.sort(key=lambda p: p.get('rss', 0), reverse=True)
    elif orden == 'pid':
        procs.sort(key=lambda p: p.get('pid', 0))

    return procs


# ---------------------------------------------------------------------------
# Renderizado de cada zona
# ---------------------------------------------------------------------------

def render_barra_superior(snapshot):
    """Barra superior con stats del sistema."""
    sis = snapshot.get('sistema', {})
    if not sis:
        return Panel("Cargando...", style="bold")

    cpu  = sis.get('cpu', {})
    mem  = sis.get('memoria', {})
    load = sis.get('loadavg', {})

    mem_usada = mem.get('total', 0) - mem.get('disponible', 0)

    texto = (
        f"[bold cyan]CPU[/bold cyan] "
        f"usr:[green]{cpu.get('user', 0):.1f}%[/green] "
        f"sys:[yellow]{cpu.get('system', 0):.1f}%[/yellow] "
        f"idle:[white]{cpu.get('idle', 0):.1f}%[/white] "
        f"iowait:[red]{cpu.get('iowait', 0):.1f}%[/red]  "
        f"[bold cyan]MEM[/bold cyan] "
        f"[green]{fmt_kb(mem_usada)}[/green]/[white]{fmt_kb(mem.get('total', 0))}[/white]  "
        f"[bold cyan]Load[/bold cyan] "
        f"{load.get('load1', 0):.2f} {load.get('load5', 0):.2f} {load.get('load15', 0):.2f}  "
        f"[bold cyan]Up[/bold cyan] {sis.get('uptime_str', '?')}  "
        f"[bold cyan]Procs[/bold cyan] {sis.get('total_procs', 0)}"
    )
    return Panel(Text.from_markup(texto), box=box.SIMPLE)


def render_lista_procesos(snapshot, estado, altura=15):
    """Lista de procesos navegable."""
    procs = obtener_procesos_filtrados(snapshot, estado)
    indice = estado.get('indice_lista')
    pid_sel = estado.get('pid_seleccionado')

    tabla = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    tabla.add_column("PID",     width=7,  justify="right")
    tabla.add_column("NOMBRE",  width=16)
    tabla.add_column("USR",     width=8)
    tabla.add_column("EST",     width=3,  justify="center")
    tabla.add_column("CPU%",    width=6,  justify="right")
    tabla.add_column("RSS",     width=8,  justify="right")
    tabla.add_column("THR",     width=4,  justify="right")
    tabla.add_column("COMANDO", min_width=20)

    # Mostramos solo los procesos que entran en pantalla
    inicio = max(0, indice - altura // 2)
    fin    = min(len(procs), inicio + altura)
    visibles = procs[inicio:fin]

    for i, p in enumerate(visibles):
        idx_real  = inicio + i
        es_cursor = (idx_real == indice)
        es_pin    = (p.get('pid') == pid_sel)

        estilo = ""
        if es_cursor:
            estilo = "on dark_blue"
        elif es_pin:
            estilo = "on dark_green"

        prefijo = "▶ " if es_cursor else ("📌" if es_pin else "  ")

        tabla.add_row(
            str(p.get('pid', '')),
            p.get('nombre', '')[:15],
            p.get('usuario', '')[:8],
            Text.from_markup(fmt_estado(p.get('estado', '?'))),
            f"{p.get('cpu', 0):.1f}",
            fmt_kb(p.get('rss', 0)),
            str(p.get('threads', 1)),
            (prefijo + p.get('cmdline', '')[:40]),
            style=estilo,
        )

    titulo = f"Procesos ({len(procs)})"
    if estado.get('filtro_cmd'):
        titulo += f" [filtro: {estado.get('filtro_cmd')}]"
    if estado.get('filtro_usuario'):
        titulo += f" [usuario: {estado.get('filtro_usuario')}]"

    return Panel(tabla, title=titulo, box=box.ROUNDED)


def render_panel_detalle(snapshot, estado):
    """Panel de detalle según la vista activa."""
    vista = estado.get('vista_activa')
    procs = obtener_procesos_filtrados(snapshot, estado)
    indice = estado.get('indice_lista')
    pid_sel = estado.get('pid_seleccionado')

    # Obtenemos el PID a mostrar
    if pid_sel:
        pid = pid_sel
    elif procs and 0 <= indice < len(procs):
        pid = procs[indice].get('pid')
    else:
        pid = None

    if vista == 'sistema':
        return render_vista_sistema(snapshot)
    elif pid is None:
        return Panel("Sin proceso seleccionado", title=vista)
    elif vista == 'resumen':
        return render_vista_resumen(snapshot, pid)
    elif vista == 'memoria':
        return render_vista_memoria(snapshot, pid)
    elif vista == 'fds':
        return render_vista_fds(snapshot, pid)
    elif vista == 'threads':
        return render_vista_threads(snapshot, pid)
    elif vista == 'senales':
        return render_vista_senales(snapshot, pid)
    elif vista == 'scheduling':
        return render_vista_scheduling(snapshot, pid)
    else:
        return Panel("Vista desconocida", title=vista)


def render_vista_resumen(snapshot, pid):
    datos = snapshot.get('resumen', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos para PID {pid}", title="Resumen")

    texto = (
        f"[cyan]PID:[/cyan]      {datos['pid']}\n"
        f"[cyan]Nombre:[/cyan]   {datos['nombre']}\n"
        f"[cyan]Comando:[/cyan]  {datos.get('cmdline', '')[:60]}\n"
        f"[cyan]Estado:[/cyan]   {datos['estado']}\n"
        f"[cyan]PPID:[/cyan]     {datos['ppid']}\n"
        f"[cyan]Usuario:[/cyan]  {datos['usuario']} (UID {datos['uid']})\n"
        f"[cyan]CPU%:[/cyan]     {datos['cpu']:.1f}%\n"
        f"[cyan]RSS:[/cyan]      {fmt_kb(datos['rss'])}\n"
        f"[cyan]VSZ:[/cyan]      {fmt_kb(datos['vsz'])}\n"
        f"[cyan]Threads:[/cyan]  {datos['threads']}\n"
    )
    return Panel(Text.from_markup(texto), title=f"Resumen — PID {pid}", box=box.ROUNDED)


def render_vista_memoria(snapshot, pid):
    datos = snapshot.get('memoria', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos de memoria para PID {pid}", title="Memoria")

    texto = (
        f"[cyan]VmSize:[/cyan]  {fmt_kb(datos['vm_size']):<10} (virtual total)\n"
        f"[cyan]VmRSS:[/cyan]   {fmt_kb(datos['vm_rss']):<10} (en RAM)\n"
        f"[cyan]VmHWM:[/cyan]   {fmt_kb(datos['vm_hwm']):<10} (pico histórico)\n"
        f"[cyan]VmSwap:[/cyan]  {fmt_kb(datos['vm_swap']):<10} (en swap)\n"
        f"[cyan]VmData:[/cyan]  {fmt_kb(datos['vm_data']):<10} (datos)\n"
        f"[cyan]VmStk:[/cyan]   {fmt_kb(datos['vm_stk']):<10} (stack)\n"
        f"[cyan]VmExe:[/cyan]   {fmt_kb(datos['vm_exe']):<10} (ejecutable)\n"
        f"[cyan]VmLib:[/cyan]   {fmt_kb(datos['vm_lib']):<10} (librerías)\n"
        f"[cyan]Minflt:[/cyan]  {datos['minflt']:<10} (page faults menores)\n"
        f"[cyan]Majflt:[/cyan]  {datos['majflt']:<10} (page faults mayores)\n"
    )

    if datos.get('segmentos'):
        texto += "\n[bold]Segmentos:[/bold]\n"
        for nombre, kb in datos['segmentos'].items():
            texto += f"  {nombre:<12} {fmt_kb(kb)}\n"

    return Panel(Text.from_markup(texto), title=f"Memoria — PID {pid}", box=box.ROUNDED)


def render_vista_fds(snapshot, pid):
    datos = snapshot.get('fds', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos de FDs para PID {pid}", title="File Descriptors")

    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    tabla.add_column("FD",      width=5,  justify="right")
    tabla.add_column("TIPO",    width=12)
    tabla.add_column("DESTINO", min_width=30)

    for fd in datos.get('fds', [])[:20]:
        tabla.add_row(
            str(fd['fd']),
            fd['tipo'],
            fd['destino'][:60],
        )

    conteo = datos.get('conteo', {})
    resumen = "  ".join(f"{k}:{v}" for k, v in conteo.items())
    titulo = f"FDs — PID {pid} ({datos['total']} total: {resumen})"
    return Panel(tabla, title=titulo, box=box.ROUNDED)


def render_vista_threads(snapshot, pid):
    datos = snapshot.get('threads', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos de threads para PID {pid}", title="Threads")

    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    tabla.add_column("TID",       width=8,  justify="right")
    tabla.add_column("NOMBRE",    width=20)
    tabla.add_column("EST",       width=3,  justify="center")
    tabla.add_column("CPU%",      width=6,  justify="right")
    tabla.add_column("VOL_CTX",   width=9,  justify="right")
    tabla.add_column("INVOL_CTX", width=10, justify="right")

    for t in datos.get('threads', [])[:15]:
        tabla.add_row(
            str(t['tid']),
            t['nombre'][:19],
            Text.from_markup(fmt_estado(t['estado'])),
            f"{t['cpu']:.1f}",
            str(t['vol_ctx']),
            str(t['invol_ctx']),
        )

    return Panel(tabla, title=f"Threads — PID {pid} ({datos['total']} total)", box=box.ROUNDED)


def render_vista_senales(snapshot, pid):
    datos = snapshot.get('senales', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos de señales para PID {pid}", title="Señales")

    def fmt_lista(lst):
        return ', '.join(lst) if lst else '[dim]ninguna[/dim]'

    texto = (
        f"[cyan]Bloqueadas  ({len(datos['bloqueadas']):>2}):[/cyan] {fmt_lista(datos['bloqueadas'])}\n"
        f"[cyan]Ignoradas   ({len(datos['ignoradas']):>2}):[/cyan] {fmt_lista(datos['ignoradas'])}\n"
        f"[cyan]Capturadas  ({len(datos['capturadas']):>2}):[/cyan] {fmt_lista(datos['capturadas'])}\n"
        f"[cyan]Pendientes  ({len(datos['pendientes']):>2}):[/cyan] {fmt_lista(datos['pendientes'])}\n"
        f"\n[bold]Máscaras raw:[/bold]\n"
        f"  SigBlk: {datos['raw']['blk']}\n"
        f"  SigIgn: {datos['raw']['ign']}\n"
        f"  SigCgt: {datos['raw']['cgt']}\n"
    )
    return Panel(Text.from_markup(texto), title=f"Señales — PID {pid}", box=box.ROUNDED)


def render_vista_scheduling(snapshot, pid):
    datos = snapshot.get('scheduling', {}).get(pid)
    if not datos:
        return Panel(f"Sin datos de scheduling para PID {pid}", title="Scheduling")

    texto = (
        f"[cyan]Policy:[/cyan]    {datos['policy']}\n"
        f"[cyan]Nice:[/cyan]      {datos['nice']}\n"
        f"[cyan]Priority:[/cyan]  {datos['priority']}\n"
        f"[cyan]RT Prio:[/cyan]   {datos['rt_priority']}\n"
        f"[cyan]Affinity:[/cyan]  {datos['cpu_affinity']}\n"
        f"[cyan]SID:[/cyan]       {datos['sid']}\n"
        f"[cyan]PGID:[/cyan]      {datos['pgid']}\n"
        f"[cyan]Vol ctx:[/cyan]   {datos['vol_ctx']}\n"
        f"[cyan]Invol ctx:[/cyan] {datos['invol_ctx']}\n"
        f"[cyan]utime:[/cyan]     {datos['utime']}\n"
        f"[cyan]stime:[/cyan]     {datos['stime']}\n"
    )
    return Panel(Text.from_markup(texto), title=f"Scheduling — PID {pid}", box=box.ROUNDED)


def render_vista_sistema(snapshot):
    sis = snapshot.get('sistema', {})
    if not sis:
        return Panel("Sin datos del sistema", title="Sistema Global")

    cpu  = sis.get('cpu', {})
    mem  = sis.get('memoria', {})
    load = sis.get('loadavg', {})

    top_cpu = snapshot.get('top_cpu', [])
    top_mem = snapshot.get('top_mem', [])

    texto = (
        f"[bold cyan]CPU Global[/bold cyan]\n"
        f"  user={cpu.get('user',0):.1f}%  system={cpu.get('system',0):.1f}%  "
        f"idle={cpu.get('idle',0):.1f}%  iowait={cpu.get('iowait',0):.1f}%\n\n"
        f"[bold cyan]Memoria[/bold cyan]\n"
        f"  Total:      {fmt_kb(mem.get('total',0))}\n"
        f"  Disponible: {fmt_kb(mem.get('disponible',0))}\n"
        f"  Libre:      {fmt_kb(mem.get('libre',0))}\n"
        f"  Swap:       {fmt_kb(mem.get('swap_total',0) - mem.get('swap_libre',0))} / {fmt_kb(mem.get('swap_total',0))}\n\n"
        f"[bold cyan]Load Average[/bold cyan]\n"
        f"  {load.get('load1',0):.2f}  {load.get('load5',0):.2f}  {load.get('load15',0):.2f}\n\n"
        f"[bold cyan]Top 3 CPU[/bold cyan]\n"
    )
    for p in top_cpu:
        texto += f"  {p['pid']:>6} {p['nombre']:<16} {p['cpu']:.1f}%\n"

    texto += f"\n[bold cyan]Top 3 Memoria[/bold cyan]\n"
    for p in top_mem:
        texto += f"  {p['pid']:>6} {p['nombre']:<16} {fmt_kb(p['rss'])}\n"

    return Panel(Text.from_markup(texto), title="Sistema Global", box=box.ROUNDED)


def render_barra_inferior(estado):
    """Barra inferior con keybindings."""
    vista = estado.get('vista_activa')
    orden = estado.get('orden')

    vistas_str = "[1]Res [2]Mem [3]FDs [4]Thr [5]Sig [6]Sch [7]Sis"
    keys_str   = "↑↓:navegar  Enter:pin  /:cmd  u:usuario  c:orden  q:salir  h:ayuda"
    orden_str  = f"orden:[cyan]{orden}[/cyan]"
    vista_str  = f"vista:[cyan]{vista}[/cyan]"

    texto = f"{vistas_str}  |  {orden_str}  {vista_str}  |  {keys_str}"
    return Panel(Text.from_markup(texto), box=box.SIMPLE)


# ---------------------------------------------------------------------------
# Composición de la pantalla completa
# ---------------------------------------------------------------------------

def render_pantalla(snapshot, estado):
    """Arma el layout completo."""
    layout = Layout()
    layout.split_column(
        Layout(name="superior", size=3),
        Layout(name="lista",    size=18),
        Layout(name="detalle",  minimum_size=8),
        Layout(name="inferior", size=3),
    )

    layout["superior"].update(render_barra_superior(snapshot))
    layout["lista"].update(render_lista_procesos(snapshot, estado))
    layout["detalle"].update(render_panel_detalle(snapshot, estado))
    layout["inferior"].update(render_barra_inferior(estado))

    return layout


# ---------------------------------------------------------------------------
# Thread de teclado
# ---------------------------------------------------------------------------

def thread_teclado(estado, snapshot, intervalos):
    """
    Lee teclas del usuario y actualiza el estado.
    Corre en un thread separado dentro del proceso display.
    """
    import tty
    import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        while estado.get('corriendo'):
            ch = sys.stdin.read(1)

            if ch == 'q':
                estado.set('corriendo', False)

            elif ch in VISTAS:
                estado.set('vista_activa', VISTAS[ch])

            elif ch == 'c':
                # Ciclar entre órdenes
                orden_actual = estado.get('orden')
                idx = ORDENES.index(orden_actual) if orden_actual in ORDENES else 0
                estado.set('orden', ORDENES[(idx + 1) % len(ORDENES)])

            elif ch == '\r':  # Enter — pin del proceso
                procs = obtener_procesos_filtrados(snapshot, estado)
                indice = estado.get('indice_lista')
                if procs and 0 <= indice < len(procs):
                    pid = procs[indice].get('pid')
                    # Toggle: si ya estaba pineado lo des-pinea
                    if estado.get('pid_seleccionado') == pid:
                        estado.set('pid_seleccionado', None)
                    else:
                        estado.set('pid_seleccionado', pid)

            elif ch == '\x1b':  # secuencia de escape (flechas)
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    procs = obtener_procesos_filtrados(snapshot, estado)
                    indice = estado.get('indice_lista')
                    if ch3 == 'A':  # ↑
                        estado.set('indice_lista', max(0, indice - 1))
                    elif ch3 == 'B':  # ↓
                        estado.set('indice_lista', min(len(procs) - 1, indice + 1))

            elif ch == '/':
                # Filtro por comando — leemos el texto
                tty.setcbreak(fd)
                sys.stdout.write('\nFiltrar por comando: ')
                sys.stdout.flush()
                filtro = ''
                while True:
                    c = sys.stdin.read(1)
                    if c == '\r' or c == '\n':
                        break
                    elif c == '\x7f':  # backspace
                        filtro = filtro[:-1]
                    else:
                        filtro += c
                estado.set('filtro_cmd', filtro if filtro else None)
                estado.set('indice_lista', 0)
                tty.setraw(fd)

            elif ch == 'u':
                # Filtro por usuario
                tty.setcbreak(fd)
                sys.stdout.write('\nFiltrar por usuario: ')
                sys.stdout.flush()
                filtro = ''
                while True:
                    c = sys.stdin.read(1)
                    if c == '\r' or c == '\n':
                        break
                    elif c == '\x7f':
                        filtro = filtro[:-1]
                    else:
                        filtro += c
                estado.set('filtro_usuario', filtro if filtro else None)
                estado.set('indice_lista', 0)
                tty.setraw(fd)

            elif ch == '+':
                vista = estado.get('vista_activa')
                if vista in intervalos:
                    intervalos[vista].value = min(60.0, intervalos[vista].value + 0.5)

            elif ch == '-':
                vista = estado.get('vista_activa')
                if vista in intervalos:
                    # Respetamos el mínimo del config
                    intervalos[vista].value = max(0.5, intervalos[vista].value - 0.5)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ---------------------------------------------------------------------------
# Proceso display principal
# ---------------------------------------------------------------------------

def display(snapshot, intervalos, evento_stop):
    """
    Proceso display principal.

    Parámetros:
      snapshot   — Manager.dict con todos los datos
      intervalos — dict de multiprocessing.Value con intervalos por vista
      evento_stop— Event para shutdown limpio
    """
    print(f"[display] Arrancando (PID {mp.current_process().pid})")

    estado = EstadoDisplay()
    console = Console()

    # Lanzamos el thread de teclado
    t_teclado = threading.Thread(
        target=thread_teclado,
        args=(estado, snapshot, intervalos),
        daemon=True,
        name="teclado"
    )
    t_teclado.start()

    # Loop principal de renderizado
    with Live(console=console, refresh_per_second=4, screen=True) as live:
        while estado.get('corriendo') and not evento_stop.is_set():
            try:
                pantalla = render_pantalla(snapshot, estado)
                live.update(pantalla)
            except Exception as e:
                live.update(Panel(f"Error renderizando: {e}", style="red"))
            time.sleep(0.25)

    evento_stop.set()
    print("[display] Terminado")