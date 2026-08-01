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
    """
    while not evento_stop.is_set():
        try:
            ch = readchar.readkey()
            if ch == readchar.key.UP:
                queue_teclas.put('UP')
            elif ch == readchar.key.DOWN:
                queue_teclas.put('DOWN')
            elif ch in (readchar.key.ENTER, '\r', '\n'):
                queue_teclas.put('ENTER')
            elif ch == 'q':
                queue_teclas.put('q')
                evento_stop.set()
                break
            else:
                queue_teclas.put(ch)
        except Exception:
            pass


def main():
    manager     = mp.Manager()
    snapshot    = manager.dict()
    evento_stop = mp.Event()

    # Instalamos handlers ANTES de lanzar hijos
    instalar_handlers()

    queue_resumen    = mp.Queue(maxsize=1)
    queue_memoria    = mp.Queue(maxsize=1)
    queue_fds        = mp.Queue(maxsize=1)
    queue_threads    = mp.Queue(maxsize=1)
    queue_senales    = mp.Queue(maxsize=1)
    queue_scheduling = mp.Queue(maxsize=1)
    queue_sistema    = mp.Queue(maxsize=1)
    queue_agregador  = mp.Queue()
    queue_teclas     = mp.Queue()

    intervalos = {
        'resumen':    mp.Value('d', 2.0),
        'memoria':    mp.Value('d', 3.0),
        'fds':        mp.Value('d', 5.0),
        'threads':    mp.Value('d', 2.0),
        'senales':    mp.Value('d', 10.0),
        'scheduling': mp.Value('d', 10.0),
        'sistema':    mp.Value('d', 2.0),
    }

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
                   args=(queue_sistema, queue_agregador, intervalos['sistema'], evento_stop)),
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
        for p in procesos:
            if p.is_alive():
                p.join(timeout=3)
            if p.is_alive():
                p.terminate()
        manager.shutdown()
        print("\n[main] Monitor terminado")


if __name__ == "__main__":
    main()