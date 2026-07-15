"""
agregador.py — Único proceso que escribe en el snapshot global.

Recibe mensajes de todos los analizadores via queue_agregador.
Cada mensaje es una tupla: ('nombre_seccion', datos)

El agregador:
  1. Escribe los datos en snapshot['nombre_seccion']
  2. Agrega timestamp de última actualización
  3. Mantiene top 3 por CPU y memoria actualizados
"""

import time
import multiprocessing as mp


def agregador(queue_agregador, snapshot, evento_stop):
    """
    Parámetros:
      queue_agregador — Queue donde los analizadores mandan sus resultados
      snapshot        — Manager.dict compartido, único lugar donde escribimos
      evento_stop     — Event para shutdown limpio
    """
    print(f"[agregador] Arrancando (PID {mp.current_process().pid})")

    while True:
        if evento_stop.is_set():
            # Vaciamos lo que quede en la queue antes de salir
            while not queue_agregador.empty():
                try:
                    seccion, datos = queue_agregador.get_nowait()
                    snapshot[seccion] = datos
                except Exception:
                    break
            print("[agregador] Stopping...")
            break

        try:
            seccion, datos = queue_agregador.get(timeout=1.0)
        except Exception:
            continue

        # Escribimos la sección con timestamp
        snapshot[seccion] = datos
        snapshot[f'{seccion}_ts'] = time.time()

        # Top 3 por CPU y memoria — solo cuando llegan datos de resumen
        if seccion == 'resumen' and isinstance(datos, dict):
            procs = list(datos.values())

            top_cpu = sorted(procs, key=lambda p: p.get('cpu', 0), reverse=True)[:3]
            top_mem = sorted(procs, key=lambda p: p.get('rss', 0), reverse=True)[:3]

            snapshot['top_cpu'] = [
                {'pid': p['pid'], 'nombre': p['nombre'], 'cpu': p['cpu']}
                for p in top_cpu
            ]
            snapshot['top_mem'] = [
                {'pid': p['pid'], 'nombre': p['nombre'], 'rss': p['rss']}
                for p in top_mem
            ]

    print("[agregador] Terminado")