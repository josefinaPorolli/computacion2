"""
recolector.py — Lista PIDs activos y los distribuye a los analizadores.

Ahora acepta una lista de queues y manda los PIDs a todas.
"""

import time
import multiprocessing as mp
from procfs import listar_pids


def recolector(queues, intervalo=2.0, evento_stop=None):
    """
    Parámetros:
      queues       — lista de Queues, una por analizador
      intervalo    — cada cuántos segundos listamos /proc
      evento_stop  — Event para shutdown limpio
    """
    print(f"[recolector] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop and evento_stop.is_set():
            print("[recolector] Stopping...")
            break

        pids = listar_pids()

        # Mandamos la lista a TODAS las queues
        for queue in queues:
            try:
                queue.put(pids, timeout=1.0)
            except Exception:
                pass  # Si alguna queue está llena, la salteamos

        time.sleep(intervalo)

    print("[recolector] Terminado")