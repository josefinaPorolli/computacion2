"""
recolector.py — Lista PIDs activos y los distribuye a los analizadores.

Es el primer proceso hijo que arranca main.py.
No analiza nada: solo toma una foto de /proc cada N segundos
y la manda a todos los analizadores via Queue.
"""

import time
import multiprocessing as mp
from procfs import listar_pids


def recolector(queue_pids, intervalo=2.0, evento_stop=None):
    """
    Proceso recolector.

    Parámetros:
      queue_pids   — Queue compartida donde ponemos la lista de PIDs
      intervalo    — cada cuántos segundos listamos /proc
      evento_stop  — Event de multiprocessing para saber cuándo parar
    """
    print(f"[recolector] Arrancando (PID {mp.current_process().pid})")

    while True:
        # ¿Nos pidieron parar?
        if evento_stop and evento_stop.is_set():
            print("[recolector] Stopping...")
            break

        # Tomamos la foto de PIDs activos
        pids = listar_pids()

        # La mandamos a la queue para que los analizadores la consuman
        # El put() es no bloqueante con timeout para no colgarnos
        try:
            queue_pids.put(pids, timeout=1.0)
        except Exception:
            pass  # Si la queue está llena, descartamos y seguimos

        time.sleep(intervalo)

    print("[recolector] Terminado")