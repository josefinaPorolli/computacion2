"""
analizadores/senales.py — Lee máscaras de señales de cada proceso.

Las máscaras vienen de /proc/<pid>/status como hex de 64 bits.
Cada bit representa una señal: bit 0 = señal 1 (SIGHUP), bit 1 = señal 2 (SIGINT), etc.
"""

import os
import time
import multiprocessing as mp
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from procfs import leer_status, pid_existe


# Mapa de número de señal → nombre
# Definido a mano para no depender de librerías externas
NOMBRES_SENALES = {
    1:  'SIGHUP',
    2:  'SIGINT',
    3:  'SIGQUIT',
    4:  'SIGILL',
    5:  'SIGTRAP',
    6:  'SIGABRT',
    7:  'SIGBUS',
    8:  'SIGFPE',
    9:  'SIGKILL',
    10: 'SIGUSR1',
    11: 'SIGSEGV',
    12: 'SIGUSR2',
    13: 'SIGPIPE',
    14: 'SIGALRM',
    15: 'SIGTERM',
    16: 'SIGSTKFLT',
    17: 'SIGCHLD',
    18: 'SIGCONT',
    19: 'SIGSTOP',
    20: 'SIGTSTP',
    21: 'SIGTTIN',
    22: 'SIGTTOU',
    23: 'SIGURG',
    24: 'SIGXCPU',
    25: 'SIGXFSZ',
    26: 'SIGVTALRM',
    27: 'SIGPROF',
    28: 'SIGWINCH',
    29: 'SIGIO',
    30: 'SIGPWR',
    31: 'SIGSYS',
}


def decodificar_mascara(hex_str):
    """
    Convierte una máscara hexadecimal de 64 bits en lista de nombres de señales.

    Ejemplo:
      '0000000000000002' → ['SIGINT']   (bit 1 seteado = señal 2)
      '0000000000000006' → ['SIGINT', 'SIGQUIT']  (bits 1 y 2)

    El bit N-1 representa la señal N.
    """
    try:
        mascara = int(hex_str, 16)
    except (ValueError, TypeError):
        return []

    senales = []
    for num_senal, nombre in NOMBRES_SENALES.items():
        # Chequeamos si el bit correspondiente está seteado
        if mascara & (1 << (num_senal - 1)):
            senales.append(nombre)

    return senales


def analizar_senales(pid):
    """
    Lee las máscaras de señales de un proceso.
    Devuelve un dict con las señales decodificadas, o None si falla.
    """
    if not pid_existe(pid):
        return None

    status = leer_status(pid)
    if status is None:
        return None

    return {
        'pid':      pid,
        # Máscara hex original (para mostrar en la TUI)
        'raw': {
            'blk': status.get('SigBlk', '0000000000000000'),
            'ign': status.get('SigIgn', '0000000000000000'),
            'cgt': status.get('SigCgt', '0000000000000000'),
            'pnd': status.get('SigPnd', '0000000000000000'),
            'shd': status.get('ShdPnd', '0000000000000000'),
        },
        # Señales decodificadas a nombres legibles
        'bloqueadas':  decodificar_mascara(status.get('SigBlk', '0')),
        'ignoradas':   decodificar_mascara(status.get('SigIgn', '0')),
        'capturadas':  decodificar_mascara(status.get('SigCgt', '0')),
        'pendientes':  decodificar_mascara(status.get('SigPnd', '0')),
        'pendientes_grp': decodificar_mascara(status.get('ShdPnd', '0')),
    }


def senales(queue_pids, queue_agregador, intervalo_val, evento_stop):
    """
    Proceso analizador de señales.
    """
    print(f"[senales] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop.is_set():
            print("[senales] Stopping...")
            break

        try:
            pids = queue_pids.get(timeout=2.0)
        except Exception:
            continue

        resultados = {}
        for pid in pids:
            datos = analizar_senales(pid)
            if datos is not None:
                resultados[pid] = datos

        queue_agregador.put(('senales', resultados))
        time.sleep(intervalo_val.value)

    print("[senales] Terminado")