"""
analizadores/sistema.py — Stats globales del sistema.
"""

import os
import time
import multiprocessing as mp
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def leer_cpu_global():
    try:
        with open('/proc/stat') as f:
            for linea in f:
                if linea.startswith('cpu '):
                    partes = linea.split()
                    return {
                        'user':    int(partes[1]),
                        'nice':    int(partes[2]),
                        'system':  int(partes[3]),
                        'idle':    int(partes[4]),
                        'iowait':  int(partes[5]),
                        'irq':     int(partes[6]),
                        'softirq': int(partes[7]),
                        'total':   sum(int(x) for x in partes[1:]),
                    }
    except (FileNotFoundError, ValueError):
        pass
    return None


def leer_meminfo():
    try:
        with open('/proc/meminfo') as f:
            lineas = f.readlines()
    except FileNotFoundError:
        return None

    datos = {}
    for linea in lineas:
        if ':' not in linea:
            continue
        clave, _, valor = linea.partition(':')
        try:
            datos[clave.strip()] = int(valor.strip().split()[0])
        except (ValueError, IndexError):
            datos[clave.strip()] = 0

    return {
        'total':      datos.get('MemTotal', 0),
        'libre':      datos.get('MemFree', 0),
        'buffers':    datos.get('Buffers', 0),
        'cached':     datos.get('Cached', 0),
        'disponible': datos.get('MemAvailable', 0),
        'swap_total': datos.get('SwapTotal', 0),
        'swap_libre': datos.get('SwapFree', 0),
    }


def leer_loadavg():
    try:
        with open('/proc/loadavg') as f:
            partes = f.read().split()
        return {
            'load1':  float(partes[0]),
            'load5':  float(partes[1]),
            'load15': float(partes[2]),
        }
    except (FileNotFoundError, ValueError, IndexError):
        return {'load1': 0.0, 'load5': 0.0, 'load15': 0.0}


def leer_uptime():
    try:
        with open('/proc/uptime') as f:
            return float(f.read().split()[0])
    except (FileNotFoundError, ValueError, IndexError):
        return 0.0


def formatear_uptime(segundos):
    dias    = int(segundos // 86400)
    horas   = int((segundos % 86400) // 3600)
    minutos = int((segundos % 3600) // 60)
    segs    = int(segundos % 60)
    partes  = []
    if dias:    partes.append(f"{dias}d")
    if horas:   partes.append(f"{horas}h")
    if minutos: partes.append(f"{minutos}m")
    partes.append(f"{segs}s")
    return ' '.join(partes)


def sistema(queue_pids, queue_agregador, intervalo_val, evento_stop):
    print(f"[sistema] Arrancando (PID {mp.current_process().pid})")
    cpu_anterior = None

    while True:
        if evento_stop.is_set():
            print("[sistema] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            pids = []

        cpu_actual = leer_cpu_global()
        cpu_pct = {'user': 0.0, 'system': 0.0, 'idle': 100.0, 'iowait': 0.0}

        if cpu_actual and cpu_anterior:
            delta_total = cpu_actual['total'] - cpu_anterior['total']
            if delta_total > 0:
                cpu_pct = {
                    'user':   round((cpu_actual['user']   - cpu_anterior['user'])   / delta_total * 100, 1),
                    'system': round((cpu_actual['system'] - cpu_anterior['system']) / delta_total * 100, 1),
                    'idle':   round((cpu_actual['idle']   - cpu_anterior['idle'])   / delta_total * 100, 1),
                    'iowait': round((cpu_actual['iowait'] - cpu_anterior['iowait']) / delta_total * 100, 1),
                }

        cpu_anterior = cpu_actual

        uptime_seg = leer_uptime()

        queue_agregador.put(('sistema', {
            'cpu':           cpu_pct,
            'memoria':       leer_meminfo(),
            'loadavg':       leer_loadavg(),
            'uptime_seg':    uptime_seg,
            'uptime_str':    formatear_uptime(uptime_seg),
            'total_procs':   len(pids),
        }))

        time.sleep(intervalo_val.value)

    print("[sistema] Terminado")