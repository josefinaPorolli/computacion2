"""
main.py temporal — prueba el recolector corriendo como proceso hijo.
"""
import time
import multiprocessing as mp
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from recolector import recolector


def main():
    print(f"[main] Arrancando (PID {os.getpid()})")

    # Creamos los objetos de comunicación
    queue_pids  = mp.Queue()
    evento_stop = mp.Event()

    # Lanzamos el recolector como proceso hijo
    proceso = mp.Process(
        target=recolector,
        args=(queue_pids, 2.0, evento_stop),
        name="recolector"
    )
    proceso.start()
    print(f"[main] Recolector lanzado (PID {proceso.pid})")

    # Leemos 3 snapshots de la queue y los mostramos
    for i in range(3):
        pids = queue_pids.get()  # espera hasta que haya algo
        print(f"\n[main] Snapshot #{i+1}: {len(pids)} PIDs")
        print(f"  Primeros 5: {sorted(pids)[:5]}")
        print(f"  Últimos 5:  {sorted(pids)[-5:]}")

    # Le decimos al recolector que pare
    print("\n[main] Mandando señal de stop...")
    evento_stop.set()
    proceso.join(timeout=5)
    print("[main] Listo")


if __name__ == "__main__":
    main()