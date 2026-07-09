"""
main.py temporal — todos los analizadores juntos.
"""
import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from recolector import recolector
from analizadores.resumen    import resumen
from analizadores.memoria    import memoria
from analizadores.fds        import fds
from analizadores.threads    import threads
from analizadores.senales    import senales
from analizadores.scheduling import scheduling
from analizadores.sistema    import sistema


def main():
    print(f"[main] Arrancando (PID {os.getpid()})")

    manager     = mp.Manager()
    snapshot    = manager.dict()
    evento_stop = mp.Event()

    queue_resumen    = mp.Queue(maxsize=1)
    queue_memoria    = mp.Queue(maxsize=1)
    queue_fds        = mp.Queue(maxsize=1)
    queue_threads    = mp.Queue(maxsize=1)
    queue_senales    = mp.Queue(maxsize=1)
    queue_scheduling = mp.Queue(maxsize=1)
    queue_sistema    = mp.Queue(maxsize=1)

    intervalo_resumen    = mp.Value('d', 2.0)
    intervalo_memoria    = mp.Value('d', 3.0)
    intervalo_fds        = mp.Value('d', 5.0)
    intervalo_threads    = mp.Value('d', 2.0)
    intervalo_senales    = mp.Value('d', 10.0)
    intervalo_scheduling = mp.Value('d', 10.0)
    intervalo_sistema    = mp.Value('d', 2.0)

    procesos = [
        mp.Process(target=recolector, name="recolector",
                   args=([queue_resumen, queue_memoria, queue_fds,
                          queue_threads, queue_senales,
                          queue_scheduling, queue_sistema], 2.0, evento_stop)),
        mp.Process(target=resumen,     name="resumen",
                   args=(queue_resumen, snapshot, intervalo_resumen, evento_stop)),
        mp.Process(target=memoria,     name="memoria",
                   args=(queue_memoria, snapshot, intervalo_memoria, evento_stop)),
        mp.Process(target=fds,         name="fds",
                   args=(queue_fds, snapshot, intervalo_fds, evento_stop)),
        mp.Process(target=threads,     name="threads",
                   args=(queue_threads, snapshot, intervalo_threads, evento_stop)),
        mp.Process(target=senales,     name="senales",
                   args=(queue_senales, snapshot, intervalo_senales, evento_stop)),
        mp.Process(target=scheduling,  name="scheduling",
                   args=(queue_scheduling, snapshot, intervalo_scheduling, evento_stop)),
        mp.Process(target=sistema,     name="sistema",
                   args=(queue_sistema, snapshot, intervalo_sistema, evento_stop)),
    ]

    for p in procesos:
        p.start()
        print(f"[main] {p.name} PID: {p.pid}")

    time.sleep(6)

    # Mostramos el snapshot de sistema
    datos_sis = snapshot.get('sistema', {})
    if datos_sis:
        cpu = datos_sis['cpu']
        mem = datos_sis['memoria']
        load = datos_sis['loadavg']
        est  = datos_sis['estados']

        print(f"\n=== Sistema global ===")
        print(f"  Uptime:   {datos_sis['uptime_str']}")
        print(f"  CPU:      user={cpu['user']}%  system={cpu['system']}%  "
              f"idle={cpu['idle']}%  iowait={cpu['iowait']}%")
        print(f"  Load avg: {load['load1']}  {load['load5']}  {load['load15']}")
        print(f"\n  Memoria (kB):")
        print(f"    Total:      {mem['total']:>10}")
        print(f"    Disponible: {mem['disponible']:>10}")
        print(f"    Libre:      {mem['libre']:>10}")
        print(f"    Buffers:    {mem['buffers']:>10}")
        print(f"    Cached:     {mem['cached']:>10}")
        print(f"    Swap total: {mem['swap_total']:>10}")
        print(f"    Swap libre: {mem['swap_libre']:>10}")
        print(f"\n  Procesos: {datos_sis['total_procs']} total, "
              f"{datos_sis['total_threads']} threads")
        print(f"    R={est['R']} S={est['S']} D={est['D']} "
              f"T={est['T']} Z={est['Z']}")

    print("\n[main] Parando todo...")
    evento_stop.set()
    for p in procesos:
        p.join(timeout=5)
    manager.shutdown()
    print("[main] Listo")


if __name__ == "__main__":
    main()