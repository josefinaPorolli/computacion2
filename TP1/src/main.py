"""
main.py temporal — prueba recolector + analizador de resumen juntos.
"""
import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from recolector import recolector
from analizadores.resumen import resumen


def main():
    print(f"[main] Arrancando (PID {os.getpid()})")

    # El Manager crea el dict compartido entre procesos
    manager     = mp.Manager()
    snapshot    = manager.dict()

    # Queue para que el recolector le mande PIDs al analizador
    # maxsize=1: si el analizador no consumió el anterior, descartamos
    queue_resumen = mp.Queue(maxsize=1)

    # Value compartido para el intervalo del analizador (ajustable en runtime)
    intervalo_resumen = mp.Value('d', 2.0)  # 'd' = double

    # Event para shutdown limpio
    evento_stop = mp.Event()

    # Lanzamos los procesos
    p_recolector = mp.Process(
        target=recolector,
        args=(queue_resumen, 2.0, evento_stop),
        name="recolector"
    )
    p_resumen = mp.Process(
        target=resumen,
        args=(queue_resumen, snapshot, intervalo_resumen, evento_stop),
        name="resumen"
    )

    p_recolector.start()
    p_resumen.start()
    print(f"[main] Recolector PID: {p_recolector.pid}")
    print(f"[main] Resumen    PID: {p_resumen.pid}")

    # Esperamos 3 ciclos y mostramos el snapshot
    for i in range(3):
        time.sleep(3)
        datos = snapshot.get('resumen', {})
        print(f"\n=== Snapshot #{i+1}: {len(datos)} procesos ===")

        # Mostramos los 5 procesos con más CPU
        top5 = sorted(datos.values(), key=lambda p: p['cpu'], reverse=True)[:5]
        print(f"{'PID':>6} {'NOMBRE':<16} {'EST':>3} {'CPU%':>6} {'RSS(kB)':>8} {'THREADS':>7}  COMANDO")
        print("-" * 70)
        for p in top5:
            print(f"{p['pid']:>6} {p['nombre']:<16} {p['estado']:>3} "
                  f"{p['cpu']:>6.1f} {p['rss']:>8} {p['threads']:>7}  "
                  f"{p['cmdline'][:30]}")

    # Shutdown limpio
    print("\n[main] Parando todo...")
    evento_stop.set()
    p_recolector.join(timeout=5)
    p_resumen.join(timeout=5)
    manager.shutdown()
    print("[main] Listo")


if __name__ == "__main__":
    main()