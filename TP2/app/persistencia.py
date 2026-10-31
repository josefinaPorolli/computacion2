"""Persistencia mínima: volcar el estado a JSON al apagar y reportar el
volcado anterior al arrancar.

Escribir un archivo es I/O bloqueante (el sistema operativo no ofrece una
versión "async" de write() para archivos comunes). Para no frenar el event
loop, las funciones sincrónicas de acá se llaman con `asyncio.to_thread`.

La escritura es atómica: se escribe a un archivo temporal y después se
renombra con os.replace(). Si el proceso muere a mitad de camino, queda el
temporal, nunca un JSON cortado por la mitad.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def volcar(directorio: str, datos: dict[str, Any]) -> Path:
    d = Path(directorio)
    d.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    destino = d / f'estado_{marca}.json'
    temporal = destino.with_suffix('.json.tmp')
    with open(temporal, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, destino)
    return destino


def ultimo_volcado(directorio: str) -> tuple[Path, dict[str, Any]] | None:
    """Devuelve (ruta, contenido) del volcado más reciente, o None."""
    d = Path(directorio)
    if not d.is_dir():
        return None
    candidatos = sorted(d.glob('estado_*.json'))   # el nombre ordena por fecha
    for ruta in reversed(candidatos):
        try:
            with open(ruta, encoding='utf-8') as f:
                return ruta, json.load(f)
        except (OSError, json.JSONDecodeError):
            continue                               # corrupto: probar el anterior
    return None
