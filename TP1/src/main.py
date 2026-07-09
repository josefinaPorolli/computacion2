"""
main.py temporal — prueba recolector + resumen + memoria + fds juntos.
"""
import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from recolector import recolector
from analizadores.resumen import resumen
from analizadores.memoria import memoria
from analizadores.fds import fds


def main():
    print(f"[main] Arrancando (PID {os.getpid()})")

    manager     = mp.Manager()
    snapshot    = manager.dict()
    evento_stop = mp.Event()

    queue_resumen = mp.Queue(maxsize=1)
    queue_memoria = mp.Queue(maxsize=1)
    queue_fds     = mp.Queue(maxsize=1)

    intervalo_resumen = mp.Value('d', 2.0)
    intervalo_memoria = mp.Value('d', 3.0)
    intervalo_fds     = mp.Value('d', 5.0)

    procesos = [
        mp.Process(target=recolector, name="recolector",
                   args=([queue_resumen, queue_memoria, queue_fds], 2.0, evento_stop)),
        mp.Process(target=resumen, name="resumen",
                   args=(queue_resumen, snapshot, intervalo_resumen, evento_stop)),
        mp.Process(target=memoria, name="memoria",
                   args=(queue_memoria, snapshot, intervalo_memoria, evento_stop)),
        mp.Process(target=fds, name="fds",
                   args=(queue_fds, snapshot, intervalo_fds, evento_stop)),
    ]

    for p in procesos:
        p.start()
        print(f"[main] {p.name} PID: {p.pid}")

    time.sleep(6)

    # Mostramos los 5 procesos con más FDs abiertos
    datos_fds = snapshot.get('fds', {})
    if datos_fds:
        top5 = sorted(datos_fds.values(), key=lambda p: p['total'], reverse=True)[:5]
        print(f"\n=== Top 5 procesos por FDs abiertos ===")
        print(f"{'PID':>6}  {'TOTAL':>5}  {'ARCHIVOS':>8}  {'SOCKETS':>7}  {'PIPES':>5}  {'TTY':>3}")
        print("-" * 50)
        for p in top5:
            c = p['conteo']
            print(f"{p['pid']:>6}  {p['total']:>5}  "
                  f"{c.get('archivo', 0):>8}  "
                  f"{c.get('socket', 0):>7}  "
                  f"{c.get('pipe', 0):>5}  "
                  f"{c.get('tty', 0):>3}")

        # Mostramos el detalle del proceso con más FDs
        top1 = top5[0]
        print(f"\n=== Detalle FDs de PID {top1['pid']} ===")
        for fd in top1['fds'][:10]:  # primeros 10
            print(f"  fd {fd['fd']:>3}  [{fd['tipo']:<11}]  {fd['destino'][:50]}")
        if len(top1['fds']) > 10:
            print(f"  ... y {len(top1['fds']) - 10} más")

    print("\n[main] Parando todo...")
    evento_stop.set()
    for p in procesos:
        p.join(timeout=5)
    manager.shutdown()
    print("[main] Listo")


if __name__ == "__main__":
    main()