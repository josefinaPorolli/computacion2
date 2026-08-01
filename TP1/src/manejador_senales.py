"""
manejador_senales.py — Handlers de señales para el monitor.

Patrón self-pipe:
  1. Handler escribe un byte en un pipe (operación async-signal-safe)
  2. Loop principal lee el pipe y ejecuta la acción real

Señales manejadas:
  SIGINT  / SIGTERM → shutdown limpio
  SIGHUP            → recargar config.json
  SIGUSR1           → dump del snapshot a JSON
  SIGUSR2           → toggle verbose
"""

import os
import signal
import json
import time


# Extremos del self-pipe
_pipe_r, _pipe_w = os.pipe()

# Mapa de byte → señal
_BYTE_SIGINT  = b'I'
_BYTE_SIGTERM = b'T'
_BYTE_SIGHUP  = b'H'
_BYTE_SIGUSR1 = b'1'
_BYTE_SIGUSR2 = b'2'


# ---------------------------------------------------------------------------
# Handlers — solo escriben un byte en el pipe (async-signal-safe)
# ---------------------------------------------------------------------------

def _handler_sigint(signum, frame):
    os.write(_pipe_w, _BYTE_SIGINT)

def _handler_sigterm(signum, frame):
    os.write(_pipe_w, _BYTE_SIGTERM)

def _handler_sighup(signum, frame):
    os.write(_pipe_w, _BYTE_SIGHUP)

def _handler_sigusr1(signum, frame):
    os.write(_pipe_w, _BYTE_SIGUSR1)

def _handler_sigusr2(signum, frame):
    os.write(_pipe_w, _BYTE_SIGUSR2)


def instalar_handlers():
    """
    Instala los handlers en el proceso principal.
    Llamar desde main.py antes de lanzar los procesos hijos.
    """
    signal.signal(signal.SIGINT,  _handler_sigint)
    signal.signal(signal.SIGTERM, _handler_sigterm)
    signal.signal(signal.SIGHUP,  _handler_sighup)
    signal.signal(signal.SIGUSR1, _handler_sigusr1)
    signal.signal(signal.SIGUSR2, _handler_sigusr2)

    # Hacemos el extremo de lectura no bloqueante
    import fcntl
    flags = fcntl.fcntl(_pipe_r, fcntl.F_GETFL)
    fcntl.fcntl(_pipe_r, fcntl.F_SETFL, flags | os.O_NONBLOCK)


# ---------------------------------------------------------------------------
# Acciones reales — se ejecutan en el loop principal
# ---------------------------------------------------------------------------

def accion_shutdown(evento_stop, procesos):
    """SIGINT / SIGTERM — apaga todo limpiamente."""
    print("\n[señales] Shutdown limpio...")
    evento_stop.set()


def accion_recargar_config(intervalos, config_path='config.json'):
    """SIGHUP — recarga intervalos desde config.json."""
    try:
        with open(config_path) as f:
            config = json.load(f)

        nuevos = config.get('intervalos', {})
        for vista, valor in nuevos.items():
            if vista in intervalos:
                intervalos[vista].value = float(valor)
                print(f"[señales] Intervalo {vista} → {valor}s")

        print("[señales] Config recargada")
    except Exception as e:
        print(f"[señales] Error recargando config: {e}")


def accion_dump_snapshot(snapshot):
    """SIGUSR1 — guarda el snapshot a un archivo JSON."""
    timestamp = int(time.time())
    filename  = f"dump_{timestamp}.json"

    try:
        # Convertimos el snapshot a algo serializable
        datos = {}
        for clave in snapshot.keys():
            try:
                valor = snapshot[clave]
                # Intentamos serializar — algunos valores pueden no ser serializables
                json.dumps(valor)
                datos[clave] = valor
            except (TypeError, ValueError):
                datos[clave] = str(valor)

        with open(filename, 'w') as f:
            json.dump(datos, f, indent=2, default=str)

        print(f"[señales] Snapshot guardado en {filename}")
    except Exception as e:
        print(f"[señales] Error guardando dump: {e}")


def accion_toggle_verbose(snapshot):
    """SIGUSR2 — toggle modo verbose en el snapshot."""
    actual = snapshot.get('verbose', False)
    snapshot['verbose'] = not actual
    print(f"[señales] Verbose: {'ON' if not actual else 'OFF'}")


# ---------------------------------------------------------------------------
# Loop de señales — llamar desde main.py
# ---------------------------------------------------------------------------

def procesar_senales(evento_stop, procesos, intervalos, snapshot,
                     config_path='config.json'):
    """
    Lee el pipe y ejecuta la acción correspondiente.
    Llamar periódicamente desde el loop principal de main.py.
    """
    try:
        byte = os.read(_pipe_r, 1)
    except BlockingIOError:
        return  # No hay señales pendientes

    if byte in (_BYTE_SIGINT, _BYTE_SIGTERM):
        accion_shutdown(evento_stop, procesos)
    elif byte == _BYTE_SIGHUP:
        accion_recargar_config(intervalos, config_path)
    elif byte == _BYTE_SIGUSR1:
        accion_dump_snapshot(snapshot)
    elif byte == _BYTE_SIGUSR2:
        accion_toggle_verbose(snapshot)