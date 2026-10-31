"""Los tipos de tarea.

Cada tipo es una corrutina `async def ejecutar(params, ctx) -> resultado`.
Para agregar un tipo nuevo alcanza con escribir el módulo, registrarlo en
EJECUTORES y agregar su modelo de parámetros en modelos.py.
"""
from dataclasses import dataclass
from concurrent.futures import Executor
from typing import Any, Awaitable, Callable

import httpx

from ..config import Config


@dataclass
class Contexto:
    """Lo que una tarea necesita del sistema, sin acceso al registro."""
    config: Config
    http: httpx.AsyncClient          # un cliente compartido: reusa conexiones
    pool_cpu: Executor               # el ProcessPoolExecutor, creado una vez
    progreso: Callable[[float], None]


Ejecutor = Callable[[dict[str, Any], Contexto], Awaitable[Any]]

from . import descargar, esperar, hashear  # noqa: E402

EJECUTORES: dict[str, Ejecutor] = {
    'descargar': descargar.ejecutar,
    'hashear': hashear.ejecutar,
    'esperar': esperar.ejecutar,
}
