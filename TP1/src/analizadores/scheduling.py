"""
analizadores/scheduling.py — Lee datos de scheduling de cada proceso.

Fuentes:
  - /proc/<pid>/stat: nice, priority, policy, rt_priority, sid, pgid, utime, stime
  - /proc/<pid>/status: Cpus_allowed_list, context switches
"""

import os
import time
import multiprocessing as mp
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import leer_stat, leer_status, pid_existe


# Mapa de número de política → nombre legible
POLITICAS = {
    0: 'SCHED_OTHER',
    1: 'SCHED_FIFO',
    2: 'SCHED_RR',
    3: 'SCHED_BATCH',
    5: 'SCHED_IDLE',
}


def analizar_scheduling(pid):
    """
    Reúne todos los datos de scheduling de un proceso.
    Devuelve un dict, o None si el proceso desapareció.
    """
    if not pid_existe(pid):
        return None

    stat = leer_stat(pid)
    if stat is None:
        return None

    status = leer_status(pid)
    if status is None:
        return None

    policy_num = stat.get('policy', 0)

    return {
        'pid':          pid,
        # De stat
        'nice':         stat.get('nice', 0),
        'priority':     stat.get('priority', 0),
        'policy_num':   policy_num,
        'policy':       POLITICAS.get(policy_num, f'SCHED_{policy_num}'),
        'rt_priority':  stat.get('rt_priority', 0),
        'sid':          stat.get('sid', 0),
        'pgid':         stat.get('pgid', 0),
        'utime':        stat.get('utime', 0),
        'stime':        stat.get('stime', 0),
        # De status
        'cpu_affinity': status.get('Cpus_allowed_list', '0'),
        'vol_ctx':      status.get('voluntary_ctxt_switches', 0),
        'invol_ctx':    status.get('nonvoluntary_ctxt_switches', 0),
    }


def scheduling(queue_pids, queue_agregador, intervalo_val, evento_stop):
    """
    Proceso analizador de scheduling.
    """
    print(f"[scheduling] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop.is_set():
            print("[scheduling] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue

        resultados = {}
        for pid in pids:
            datos = analizar_scheduling(pid)
            if datos is not None:
                resultados[pid] = datos

        queue_agregador.put(('scheduling', resultados))
        time.sleep(intervalo_val.value)

    print("[scheduling] Terminado")