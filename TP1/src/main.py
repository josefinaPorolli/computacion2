"""
main.py — Entry point del monitor de procesos.
"""
import os
import sys
import time
import threading
import multiprocessing as mp
import readchar
sys.path.insert(0, os.path.dirname(__file__))

from recolector              import recolector
from agregador               import agregador
from display                 import display
from manejador_senales       import instalar_handlers, procesar_senales
from analizadores.resumen    import resumen
from analizadores.memoria    import memoria
from analizadores.fds        import fds
from analizadores.threads    import threads
from analizadores.senales    import senales
from analizadores.scheduling import scheduling
from analizadores.sistema    import sistema


def thread_teclas(queue_teclas, evento_stop):
    """
    Thread que lee teclas y las manda al display via queue.
    Corre en un thread separado para no bloquear el loop principal.

    Nota sobre ESC: readchar.readkey() al leer un ESC hace una segunda
    lectura BLOQUEANTE para ver si es el inicio de una secuencia (flecha,
    etc.). Como un ESC suelto no manda ningún byte más, esa lectura queda
    esperando hasta que se presiona la SIGUIENTE tecla, y readkey() termina
    devolviendo el ESC pegado con esa tecla siguiente (ej: '\\x1bh' si
    después tipeaste 'h'). Por eso más abajo detectamos ese caso y lo
    separamos en dos eventos: primero el ESC, y después la tecla que vino
    a continuación (para no perderla).
    """
    tecla_backspace = getattr(readchar.key, 'BACKSPACE', '\x7f')
    tecla_esc       = getattr(readchar.key, 'ESC', '\x1b')

    def despachar(ch):
        if ch == readchar.key.UP:
            queue_teclas.put('UP')
        elif ch == readchar.key.DOWN:
            queue_teclas.put('DOWN')
        elif ch in (readchar.key.ENTER, '\r', '\n'):
            queue_teclas.put('ENTER')
        elif ch in (tecla_backspace, '\x08'):
            queue_teclas.put('BACKSPACE')
        elif ch == tecla_esc:
            queue_teclas.put('ESC')
        elif ch.startswith('\x1b') and len(ch) > 1:
            # ESC "atrapado" junto con la tecla siguiente: separamos ambos
            # eventos en vez de descartar la tecla que vino después.
            queue_teclas.put('ESC')
            despachar(ch[1:])
        else:
            queue_teclas.put(ch)

    while not evento_stop.is_set():
        try:
            ch = readchar.readkey()
            despachar(ch)
        except Exception:
            pass


def cargar_config(path='config.json'):
    """Lee config.json y devuelve los intervalos. Si falla, usa defaults."""
    defaults = {
        'resumen': 2.0, 'memoria': 3.0, 'fds': 5.0,
        'threads': 2.0, 'senales': 10.0, 'scheduling': 10.0, 'sistema': 2.0,
    }
    try:
        import json
        with open(path) as f:
            config = json.load(f)
        intervalos = config.get('intervalos', {})
        for k in defaults:
            if k in intervalos:
                defaults[k] = float(intervalos[k])
        print(f"[main] Config cargada desde {path}")
    except Exception as e:
        print(f"[main] config.json no encontrado o inválido ({e}), usando defaults")
    return defaults


def main():
    import signal as _signal

    manager     = mp.Manager()
    snapshot    = manager.dict()
    evento_stop = mp.Event()

    # Instalamos handlers ANTES de lanzar hijos
    instalar_handlers()

    # SIGWINCH — repintar pantalla al redimensionar terminal
    # rich.Live lo maneja automáticamente, solo necesitamos no ignorarlo
    _signal.signal(_signal.SIGWINCH, _signal.SIG_DFL)

    queue_resumen    = mp.Queue(maxsize=1)
    queue_memoria    = mp.Queue(maxsize=1)
    queue_fds        = mp.Queue(maxsize=1)
    queue_threads    = mp.Queue(maxsize=1)
    queue_senales    = mp.Queue(maxsize=1)
    queue_scheduling = mp.Queue(maxsize=1)
    queue_sistema    = mp.Queue(maxsize=1)
    queue_agregador  = mp.Queue()
    queue_teclas     = mp.Queue()

    # Leemos intervalos desde config.json
    cfg = cargar_config()
    intervalos = {k: mp.Value('d', v) for k, v in cfg.items()}

    procesos = [
        mp.Process(target=recolector, name="recolector",
                   args=([queue_resumen, queue_memoria, queue_fds,
                          queue_threads, queue_senales,
                          queue_scheduling, queue_sistema], 2.0, evento_stop)),
        mp.Process(target=agregador, name="agregador",
                   args=(queue_agregador, snapshot, evento_stop)),
        mp.Process(target=resumen, name="resumen",
                   args=(queue_resumen, queue_agregador, intervalos['resumen'], evento_stop)),
        mp.Process(target=memoria, name="memoria",
                   args=(queue_memoria, queue_agregador, intervalos['memoria'], evento_stop)),
        mp.Process(target=fds, name="fds",
                   args=(queue_fds, queue_agregador, intervalos['fds'], evento_stop)),
        mp.Process(target=threads, name="threads",
                   args=(queue_threads, queue_agregador, intervalos['threads'], evento_stop)),
        mp.Process(target=senales, name="senales",
                   args=(queue_senales, queue_agregador, intervalos['senales'], evento_stop)),
        mp.Process(target=scheduling, name="scheduling",
                   args=(queue_scheduling, queue_agregador, intervalos['scheduling'], evento_stop)),
        mp.Process(target=sistema, name="sistema",
                   args=(queue_sistema, queue_agregador, intervalos['sistema'], evento_stop, snapshot)),
        mp.Process(target=display, name="display",
                   args=(snapshot, intervalos, evento_stop, queue_teclas)),
    ]

    for p in procesos:
        p.start()

    # Thread de teclado — separado para no bloquear el loop de señales
    t_teclas = threading.Thread(
        target=thread_teclas,
        args=(queue_teclas, evento_stop),
        daemon=True,
        name="teclas"
    )
    t_teclas.start()

    # Loop principal — solo procesa señales
    try:
        while not evento_stop.is_set():
            procesar_senales(evento_stop, procesos, intervalos, snapshot)
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        evento_stop.set()
        # Esperamos que cada proceso termine limpiamente
        for p in procesos:
            if p.is_alive():
                p.join(timeout=3)
            # Si sigue vivo después del timeout, lo terminamos a la fuerza
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
            # Si todavía sigue (improbable), kill
            if p.is_alive():
                p.kill()
        try:
            manager.shutdown()
        except Exception:
            pass
        print("\n[main] Monitor terminado")


if __name__ == "__main__":
    main()