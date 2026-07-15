"""
analizadores/resumen.py — Extrae datos básicos de cada proceso.

Datos que produce:
  - pid, nombre, comando completo
  - estado (R/S/D/T/Z)
  - ppid, uid, usuario
  - CPU% (calculado entre dos lecturas)
  - memoria RSS
  - cantidad de threads
"""

import time
import multiprocessing as mp
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import leer_stat, leer_status, leer_cmdline, nombre_usuario

# Cuántos jiffies por segundo tiene este sistema
# Es una constante del kernel, casi siempre 100 pero mejor leerla
JIFFIES_POR_SEG = os.sysconf('SC_CLK_TCK')


def calcular_cpu(pid, stat_actual, lecturas_anteriores):
    """
    Calcula el CPU% de un proceso comparando dos lecturas de jiffies.

    stat_actual        — dict de leer_stat() leído ahora
    lecturas_anteriores — dict donde guardamos {pid: (utime, stime, timestamp)}

    Devuelve el CPU% como float, o 0.0 si es la primera lectura.
    """
    utime_ahora = stat_actual['utime']
    stime_ahora = stat_actual['stime']
    ahora       = time.time()

    if pid in lecturas_anteriores:
        utime_antes, stime_antes, timestamp_antes = lecturas_anteriores[pid]
        delta_tiempo  = ahora - timestamp_antes
        delta_jiffies = (utime_ahora + stime_ahora) - (utime_antes + stime_antes)

        if delta_tiempo > 0:
            cpu = (delta_jiffies / JIFFIES_POR_SEG / delta_tiempo) * 100
        else:
            cpu = 0.0
    else:
        cpu = 0.0  # Primera lectura, no tenemos con qué comparar

    # Guardamos la lectura actual para la próxima vez
    lecturas_anteriores[pid] = (utime_ahora, stime_ahora, ahora)

    return round(cpu, 1)


def analizar_proceso(pid, lecturas_anteriores):
    """
    Lee todos los datos de resumen de un proceso.
    Devuelve un dict con los datos, o None si el proceso desapareció.
    """
    stat   = leer_stat(pid)
    if stat is None:
        return None

    status = leer_status(pid)
    if status is None:
        return None

    cmdline = leer_cmdline(pid)

    # UID del proceso
    uid = status.get('Uid', {}).get('real', 0)

    return {
        'pid':      pid,
        'nombre':   stat['nombre'],
        'cmdline':  cmdline or f"[{stat['nombre']}]",
        'estado':   stat['estado'],
        'ppid':     stat['ppid'],
        'uid':      uid,
        'usuario':  nombre_usuario(uid),
        'cpu':      calcular_cpu(pid, stat, lecturas_anteriores),
        'rss':      status.get('VmRSS', 0),      # en kB
        'vsz':      status.get('VmSize', 0),     # en kB
        'threads':  status.get('Threads', 1),
    }


def resumen(queue_pids, queue_agregador, intervalo_val, evento_stop):
    """
    Proceso analizador de resumen.

    Parámetros:
      queue_pids   — Queue donde el recolector manda listas de PIDs
      queue_agregador — Queue donde enviamos los resultados
      intervalo_val— multiprocessing.Value con el intervalo actual (ajustable)
      evento_stop  — Event para shutdown limpio
    """
    print(f"[resumen] Arrancando (PID {mp.current_process().pid})")

    # Guardamos las lecturas anteriores de CPU localmente
    # (no necesitan compartirse, solo las usa este proceso)
    lecturas_anteriores = {}

    while True:
        if evento_stop.is_set():
            print("[resumen] Stopping...")
            break

        # Esperamos que el recolector nos mande PIDs
        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue  # timeout, volvemos a intentar

        # Analizamos cada PID
        resultados = {}
        for pid in pids:
            datos = analizar_proceso(pid, lecturas_anteriores)
            if datos is not None:
                resultados[pid] = datos

        # Limpiamos lecturas de PIDs que ya no existen
        pids_set = set(pids)
        lecturas_anteriores = {
            pid: v for pid, v in lecturas_anteriores.items()
            if pid in pids_set
        }

        # Escribimos en el snapshot global
        queue_agregador.put(('resumen', resultados))

        # Esperamos el intervalo antes de pedir más PIDs
        time.sleep(intervalo_val.value)

    print("[resumen] Terminado")