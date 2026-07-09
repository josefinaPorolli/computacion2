"""
main.py temporal — prueba todos los analizadores hasta ahora.
"""
import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from recolector import recolector
from analizadores.resumen   import resumen
from analizadores.memoria   import memoria
from analizadores.fds       import fds
from analizadores.threads   import threads
from analizadores.senales   import senales


def main():
    print(f"[main] Arrancando (PID {os.getpid()})")

    manager     = mp.Manager()
    snapshot    = manager.dict()
    evento_stop = mp.Event()

    queue_resumen  = mp.Queue(maxsize=1)
    queue_memoria  = mp.Queue(maxsize=1)
    queue_fds      = mp.Queue(maxsize=1)
    queue_threads  = mp.Queue(maxsize=1)
    queue_senales  = mp.Queue(maxsize=1)

    intervalo_resumen  = mp.Value('d', 2.0)
    intervalo_memoria  = mp.Value('d', 3.0)
    intervalo_fds      = mp.Value('d', 5.0)
    intervalo_threads  = mp.Value('d', 2.0)
    intervalo_senales  = mp.Value('d', 10.0)

    procesos = [
        mp.Process(target=recolector, name="recolector",
                   args=([queue_resumen, queue_memoria, queue_fds,
                          queue_threads, queue_senales], 2.0, evento_stop)),
        mp.Process(target=resumen,  name="resumen",
                   args=(queue_resumen, snapshot, intervalo_resumen, evento_stop)),
        mp.Process(target=memoria,  name="memoria",
                   args=(queue_memoria, snapshot, intervalo_memoria, evento_stop)),
        mp.Process(target=fds,      name="fds",
                   args=(queue_fds, snapshot, intervalo_fds, evento_stop)),
        mp.Process(target=threads,  name="threads",
                   args=(queue_threads, snapshot, intervalo_threads, evento_stop)),
        mp.Process(target=senales,  name="senales",
                   args=(queue_senales, snapshot, intervalo_senales, evento_stop)),
    ]

    for p in procesos:
        p.start()
        print(f"[main] {p.name} PID: {p.pid}")

    time.sleep(6)

    # Mostramos las señales del proceso con más señales capturadas
    datos_senales = snapshot.get('senales', {})
    if datos_senales:
        # Buscamos el proceso con más señales capturadas (tiene handlers propios)
        top = max(datos_senales.values(),
                  key=lambda p: len(p['capturadas']), default=None)
        if top:
            print(f"\n=== Señales de PID {top['pid']} ===")
            print(f"  Bloqueadas  ({len(top['bloqueadas']):>2}): {', '.join(top['bloqueadas']) or 'ninguna'}")
            print(f"  Ignoradas   ({len(top['ignoradas']):>2}): {', '.join(top['ignoradas']) or 'ninguna'}")
            print(f"  Capturadas  ({len(top['capturadas']):>2}): {', '.join(top['capturadas']) or 'ninguna'}")
            print(f"  Pendientes  ({len(top['pendientes']):>2}): {', '.join(top['pendientes']) or 'ninguna'}")
            print(f"\n  Máscaras raw:")
            print(f"    SigBlk: {top['raw']['blk']}")
            print(f"    SigIgn: {top['raw']['ign']}")
            print(f"    SigCgt: {top['raw']['cgt']}")

    print("\n[main] Parando todo...")
    evento_stop.set()
    for p in procesos:
        p.join(timeout=5)
    manager.shutdown()
    print("[main] Listo")


if __name__ == "__main__":
    main()