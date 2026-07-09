"""
analizadores/fds.py — Lista los file descriptors abiertos de cada proceso.

Fuente: /proc/<pid>/fd/ — carpeta con symlinks, uno por FD abierto.
Cada symlink apunta a qué tiene abierto el proceso en ese FD.
"""

import os
import time
import multiprocessing as mp
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import pid_existe


def inferir_tipo(destino):
    """
    Dado el destino de un symlink de FD, infiere qué tipo de archivo es.

    Ejemplos de destinos:
      /home/joc/archivo.txt   → 'archivo'
      socket:[12345]          → 'socket'
      pipe:[67890]            → 'pipe'
      /dev/pts/0              → 'tty'
      /dev/null               → 'dispositivo'
      anon_inode:[eventfd]    → 'anon'
    """
    if destino.startswith('socket:'):
        return 'socket'
    elif destino.startswith('pipe:'):
        return 'pipe'
    elif destino.startswith('anon_inode:'):
        return 'anon'
    elif destino.startswith('/dev/pts'):
        return 'tty'
    elif destino.startswith('/dev/'):
        return 'dispositivo'
    elif destino.startswith('/'):
        return 'archivo'
    else:
        return 'otro'


def leer_fds(pid):
    """
    Lee todos los FDs abiertos de un proceso.

    Devuelve una lista de dicts, cada uno con:
      - fd: número del file descriptor
      - destino: a qué apunta el symlink
      - tipo: inferido del destino

    O None si el proceso no existe o no tenemos permiso.
    """
    fd_path = f'/proc/{pid}/fd'

    try:
        entradas = os.listdir(fd_path)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    fds = []
    for entrada in entradas:
        if not entrada.isdigit():
            continue

        symlink = f'{fd_path}/{entrada}'
        try:
            destino = os.readlink(symlink)
        except (FileNotFoundError, PermissionError, OSError):
            continue

        fds.append({
            'fd':      int(entrada),
            'destino': destino,
            'tipo':    inferir_tipo(destino),
        })

    # Ordenamos por número de FD para que sea más legible
    fds.sort(key=lambda x: x['fd'])
    return fds


def analizar_fds(pid):
    """
    Reúne todos los datos de FDs de un proceso.
    Devuelve un dict, o None si el proceso desapareció.
    """
    if not pid_existe(pid):
        return None

    fds = leer_fds(pid)
    if fds is None:
        return None

    # Contamos cuántos hay de cada tipo
    conteo = {}
    for fd in fds:
        tipo = fd['tipo']
        conteo[tipo] = conteo.get(tipo, 0) + 1

    return {
        'pid':    pid,
        'total':  len(fds),
        'fds':    fds,
        'conteo': conteo,
    }


def fds(queue_pids, snapshot, intervalo_val, evento_stop):
    """
    Proceso analizador de file descriptors.

    Parámetros:
      queue_pids   — Queue donde el recolector manda listas de PIDs
      snapshot     — Manager.dict compartido donde escribimos resultados
      intervalo_val— multiprocessing.Value con el intervalo actual
      evento_stop  — Event para shutdown limpio
    """
    print(f"[fds] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop.is_set():
            print("[fds] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue

        resultados = {}
        for pid in pids:
            datos = analizar_fds(pid)
            if datos is not None:
                resultados[pid] = datos

        snapshot['fds'] = resultados
        time.sleep(intervalo_val.value)

    print("[fds] Terminado")