"""Configuración del servicio, leída de variables de entorno.

Todo tiene un valor por defecto razonable, así que el servicio arranca sin
configurar nada. En docker-compose.yml se pueden cambiar sin tocar código.
"""
import os
from dataclasses import dataclass, field


def _entero(nombre: str, defecto: int) -> int:
    return int(os.environ.get(nombre, defecto))


def _real(nombre: str, defecto: float) -> float:
    return float(os.environ.get(nombre, defecto))


@dataclass(frozen=True)
class Config:
    # Cantidad de corrutinas worker que consumen de la cola.
    workers: int = field(default_factory=lambda: _entero('WORKERS', 4))

    # Procesos del ProcessPoolExecutor para las tareas CPU-bound.
    # Por defecto, uno por núcleo: más no sirve (clase 9, "¿cuántos workers?").
    procesos_cpu: int = field(
        default_factory=lambda: _entero('PROCESOS_CPU', os.cpu_count() or 1))

    # Tamaño máximo de la cola: es el backpressure (clase 21).
    cola_max: int = field(default_factory=lambda: _entero('COLA_MAX', 1000))

    # Timeout por defecto de cada tarea, en segundos.
    timeout_defecto: float = field(
        default_factory=lambda: _real('TIMEOUT_DEFECTO', 60.0))

    # Cuánto esperamos a las tareas en curso al apagar, en segundos.
    gracia_apagado: float = field(
        default_factory=lambda: _real('GRACIA_APAGADO', 10.0))

    # Dónde se guardan los volcados estado_<timestamp>.json.
    dir_volcados: str = field(
        default_factory=lambda: os.environ.get('DIR_VOLCADOS', 'volcados'))

    # Iteraciones de SHA-256 por bloque mandado al executor (ver tareas/hashear.py).
    hash_bloque: int = field(
        default_factory=lambda: _entero('HASH_BLOQUE', 100_000))

    # Descargas simultáneas como máximo dentro de UNA tarea `descargar`.
    descargas_simultaneas: int = field(
        default_factory=lambda: _entero('DESCARGAS_SIMULTANEAS', 20))

    # Tope de bytes por URL: más que esto, se corta y se reporta error.
    max_bytes_descarga: int = field(
        default_factory=lambda: _entero('MAX_BYTES_DESCARGA', 50 * 1024 * 1024))

    # Habilita `hashear` con modo 'directo' (bloquea el event loop A PROPÓSITO).
    # Apagado por defecto: solo se prende para correr la medición 2.
    permitir_modo_directo: bool = field(
        default_factory=lambda: os.environ.get('PERMITIR_MODO_DIRECTO', '0') == '1')

    # Timeout de red de cada pedido HTTP individual, en segundos.
    timeout_http: float = field(
        default_factory=lambda: _real('TIMEOUT_HTTP', 15.0))