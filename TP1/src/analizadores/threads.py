"""
analizadores/threads.py — Lista los threads (LWPs) de cada proceso.

Fuente: /proc/<pid>/task/ — una subcarpeta por thread.
Cada thread tiene su propio stat, status y comm.
"""

import os
import time
import multiprocessing as mp
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import pid_existe

JIFFIES_POR_SEG = os.sysconf('SC_CLK_TCK')


def leer_thread_stat(pid, tid):
    """
    Lee /proc/<pid>/task/<tid>/stat — igual que stat de proceso
    pero para un thread específico.
    Devuelve dict con estado, utime, stime o None si falla.
    """
    try:
        with open(f'/proc/{pid}/task/{tid}/stat') as f:
            contenido = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    inicio_nombre = contenido.index('(')
    fin_nombre    = contenido.rindex(')')
    resto = contenido[fin_nombre + 2:].split()

    try:
        return {
            'estado': resto[0],       # campo 3
            'utime':  int(resto[11]), # campo 14
            'stime':  int(resto[12]), # campo 15
        }
    except (IndexError, ValueError):
        return None


def leer_thread_comm(pid, tid):
    """
    Lee /proc/<pid>/task/<tid>/comm — nombre del thread.
    Devuelve string o None si falla.
    """
    try:
        with open(f'/proc/{pid}/task/{tid}/comm') as f:
            return f.read().strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def leer_thread_status(pid, tid):
    """
    Lee /proc/<pid>/task/<tid>/status para obtener context switches.
    Devuelve dict o None si falla.
    """
    try:
        with open(f'/proc/{pid}/task/{tid}/status') as f:
            lineas = f.readlines()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    datos = {}
    for linea in lineas:
        if ':' not in linea:
            continue
        clave, _, valor = linea.partition(':')
        datos[clave.strip()] = valor.strip()

    return {
        'vol_ctx':   int(datos.get('voluntary_ctxt_switches', 0)),
        'invol_ctx': int(datos.get('nonvoluntary_ctxt_switches', 0)),
    }


def listar_threads(pid):
    """
    Lista los TIDs de un proceso leyendo /proc/<pid>/task/.
    Devuelve lista de ints o None si falla.
    """
    try:
        return [int(t) for t in os.listdir(f'/proc/{pid}/task') if t.isdigit()]
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


def analizar_threads(pid, lecturas_anteriores):
    """
    Reúne todos los datos de threads de un proceso.
    Devuelve un dict con la lista de threads, o None si el proceso desapareció.
    """
    if not pid_existe(pid):
        return None

    tids = listar_threads(pid)
    if tids is None:
        return None

    threads = []
    ahora = time.time()

    for tid in tids:
        stat   = leer_thread_stat(pid, tid)
        if stat is None:
            continue

        comm   = leer_thread_comm(pid, tid)
        status = leer_thread_status(pid, tid)

        # Calculamos CPU% del thread igual que para procesos
        utime_ahora = stat['utime']
        stime_ahora = stat['stime']
        clave = (pid, tid)

        if clave in lecturas_anteriores:
            utime_antes, stime_antes, ts_antes = lecturas_anteriores[clave]
            delta_tiempo  = ahora - ts_antes
            delta_jiffies = (utime_ahora + stime_ahora) - (utime_antes + stime_antes)
            cpu = round((delta_jiffies / JIFFIES_POR_SEG / delta_tiempo) * 100, 1) \
                  if delta_tiempo > 0 else 0.0
        else:
            cpu = 0.0

        lecturas_anteriores[clave] = (utime_ahora, stime_ahora, ahora)

        threads.append({
            'tid':       tid,
            'nombre':    comm or f'thread-{tid}',
            'estado':    stat['estado'],
            'cpu':       cpu,
            'vol_ctx':   status['vol_ctx']   if status else 0,
            'invol_ctx': status['invol_ctx'] if status else 0,
        })

    threads.sort(key=lambda t: t['cpu'], reverse=True)

    return {
        'pid':     pid,
        'total':   len(threads),
        'threads': threads,
    }


def threads(queue_pids, snapshot, intervalo_val, evento_stop):
    """
    Proceso analizador de threads.
    """
    print(f"[threads] Arrancando (PID {mp.current_process().pid})")

    lecturas_anteriores = {}

    while True:
        if evento_stop.is_set():
            print("[threads] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue

        resultados = {}
        for pid in pids:
            datos = analizar_threads(pid, lecturas_anteriores)
            if datos is not None:
                resultados[pid] = datos

        # Limpiamos lecturas de threads que ya no existen
        pids_set = set(pids)
        lecturas_anteriores = {
            (p, t): v for (p, t), v in lecturas_anteriores.items()
            if p in pids_set
        }

        snapshot['threads'] = resultados
        time.sleep(intervalo_val.value)

    print("[threads] Terminado")