"""
analizadores/memoria.py — Extrae datos de memoria de cada proceso.

Datos que produce:
  - VmSize, VmRSS, VmData, VmStk, VmExe, VmLib, VmHWM, VmSwap (de status)
  - minor/major page faults (de stat)
  - segmentos de memoria agrupados (de maps)
"""

import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import leer_stat, leer_status, pid_existe


def leer_maps(pid):
    """
    Lee y parsea /proc/<pid>/maps.

    Cada línea tiene formato:
      dirección_inicio-dirección_fin permisos offset dev inode pathname

    Ejemplo:
      7f8b4a000000-7f8b4a200000 r-xp 00000000 fd:01 123  /usr/lib/libc.so.6
      7fff12345000-7fff12367000 rw-p 00000000 00:00 0     [stack]

    Agrupamos los segmentos en categorías y sumamos su tamaño total.
    Devuelve un dict con el tamaño en kB de cada categoría, o None si falla.
    """
    try:
        with open(f'/proc/{pid}/maps') as f:
            lineas = f.readlines()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None

    segmentos = {
        'texto':      0,  # r-xp: código ejecutable
        'datos':      0,  # rw-p sin nombre especial: datos
        'heap':       0,  # [heap]
        'stack':      0,  # [stack]
        'librerias':  0,  # archivos .so
        'otro':       0,  # lo que no entra en ninguna categoría
    }

    for linea in lineas:
        partes = linea.split()
        if len(partes) < 5:
            continue

        # Calculamos el tamaño del segmento desde el rango de direcciones
        rango      = partes[0]
        permisos   = partes[1]
        pathname   = partes[4] if len(partes) >= 5 else ''

        try:
            inicio, fin = rango.split('-')
            tamanio_bytes = int(fin, 16) - int(inicio, 16)
            tamanio_kb    = tamanio_bytes // 1024
        except (ValueError, IndexError):
            continue

        # Clasificamos el segmento
        if pathname == '[heap]':
            segmentos['heap'] += tamanio_kb
        elif pathname == '[stack]':
            segmentos['stack'] += tamanio_kb
        elif pathname.endswith('.so') or '.so.' in pathname:
            segmentos['librerias'] += tamanio_kb
        elif 'x' in permisos and pathname:
            segmentos['texto'] += tamanio_kb
        elif 'w' in permisos and pathname:
            segmentos['datos'] += tamanio_kb
        else:
            segmentos['otro'] += tamanio_kb

    return segmentos


def analizar_memoria(pid):
    """
    Reúne todos los datos de memoria de un proceso.
    Devuelve un dict, o None si el proceso desapareció.
    """
    status = leer_status(pid)
    if status is None:
        return None

    stat = leer_stat(pid)
    if stat is None:
        return None

    maps = leer_maps(pid)

    return {
        'pid':      pid,
        # De status — memoria en kB
        'vm_size':  status.get('VmSize', 0),
        'vm_rss':   status.get('VmRSS', 0),
        'vm_data':  status.get('VmData', 0),
        'vm_stk':   status.get('VmStk', 0),
        'vm_exe':   status.get('VmExe', 0),
        'vm_lib':   status.get('VmLib', 0),
        'vm_hwm':   status.get('VmHWM', 0),
        'vm_swap':  status.get('VmSwap', 0),
        # De stat — page faults
        'minflt':   stat.get('minflt', 0),
        'majflt':   stat.get('majflt', 0),
        # De maps — segmentos agrupados en kB
        'segmentos': maps or {},
    }


def memoria(queue_pids, queue_agregador, intervalo_val, evento_stop):
    """
    Proceso analizador de memoria.

    Parámetros:
      queue_pids   — Queue donde el recolector manda listas de PIDs
      queue_agregador — Queue donde enviamos los resultados
      intervalo_val— multiprocessing.Value con el intervalo actual
      evento_stop  — Event para shutdown limpio
    """
    print(f"[memoria] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop.is_set():
            print("[memoria] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue

        resultados = {}
        for pid in pids:
            datos = analizar_memoria(pid)
            if datos is not None:
                resultados[pid] = datos

        queue_agregador.put(('memoria', resultados))
        time.sleep(intervalo_val.value)

    print("[memoria] Terminado")