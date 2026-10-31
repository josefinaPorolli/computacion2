"""Modelos de datos de la API (Pydantic) y los estados de una tarea.

Pydantic valida lo que manda el cliente antes de que llegue a nuestro código
(clase 19): si alguien pide `hashear` sin `texto`, FastAPI responde 422 solo.
"""
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, HttpUrl


class Estado(str, Enum):
    PENDIENTE = 'pendiente'
    EJECUTANDO = 'ejecutando'
    COMPLETADA = 'completada'
    FALLIDA = 'fallida'
    CANCELADA = 'cancelada'

    @property
    def es_final(self) -> bool:
        return self in (Estado.COMPLETADA, Estado.FALLIDA, Estado.CANCELADA)


# ---------------------------------------------------------------------------
# Parámetros de cada tipo de tarea
# ---------------------------------------------------------------------------

class ParamsDescargar(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1, max_length=200)
    secuencial: bool = Field(
        default=False,
        description='Si es true descarga de a una (solo para la medición 1)')


class ParamsHashear(BaseModel):
    texto: str = Field(max_length=10_000)
    iteraciones: int = Field(ge=1, le=100_000_000)
    modo: Literal['proceso', 'thread', 'directo'] = Field(
        default='proceso',
        description="'proceso' (por defecto, ProcessPoolExecutor), 'thread' "
                    "(asyncio.to_thread) o 'directo' (en el event loop: lo "
                    "BLOQUEA, existe solo para la medición 2)")


class ParamsEsperar(BaseModel):
    segundos: float = Field(ge=0, le=3600)


# ---------------------------------------------------------------------------
# Cuerpo del POST /tareas: una unión discriminada por `tipo`
# ---------------------------------------------------------------------------

class _NuevaBase(BaseModel):
    timeout: float | None = Field(
        default=None, gt=0, le=24 * 3600,
        description='Segundos máximos de ejecución. Si se omite, usa el default')


class NuevaDescargar(_NuevaBase):
    tipo: Literal['descargar']
    parametros: ParamsDescargar


class NuevaHashear(_NuevaBase):
    tipo: Literal['hashear']
    parametros: ParamsHashear


class NuevaEsperar(_NuevaBase):
    tipo: Literal['esperar']
    parametros: ParamsEsperar


# Pydantic mira `tipo` y valida `parametros` con el modelo que corresponde.
TareaNueva = Annotated[
    Union[NuevaDescargar, NuevaHashear, NuevaEsperar],
    Field(discriminator='tipo'),
]


# ---------------------------------------------------------------------------
# Lo que devuelve la API
# ---------------------------------------------------------------------------

class TareaSalida(BaseModel):
    id: int
    tipo: str
    estado: Estado
    parametros: dict[str, Any]
    timeout: float
    creada: str
    iniciada: str | None = None
    finalizada: str | None = None
    espera_en_cola: float | None = Field(
        default=None, description='Segundos entre creada e iniciada')
    duracion: float | None = Field(
        default=None, description='Segundos de ejecución')
    progreso: float | None = None
    worker: int | None = None
    resultado: Any = None
    error: str | None = None
