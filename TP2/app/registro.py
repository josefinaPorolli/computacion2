"""El registro de tareas: el estado de todo el sistema, en memoria.

Es un dict común, sin Lock. ¿Por qué no hace falta? Porque lo tocan solamente
corrutinas que corren en UN thread (el del event loop), y ninguno de los
métodos de acá tiene un `await` adentro: cada método se ejecuta de punta a
punta sin que el loop pueda meter otra corrutina en el medio (clase 20, "por
qué no hacen falta locks"). El código que corre en otros threads o procesos
(el hash) nunca toca el registro: recibe datos y devuelve datos.
"""
import itertools
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .modelos import Estado


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts).isoformat(timespec='milliseconds') if ts else None


@dataclass
class Tarea:
    id: int
    tipo: str
    parametros: dict[str, Any]
    timeout: float
    estado: Estado = Estado.PENDIENTE
    creada: float = field(default_factory=time.time)
    iniciada: float | None = None
    finalizada: float | None = None
    progreso: float | None = None
    worker: int | None = None
    resultado: Any = None
    error: str | None = None

    @property
    def espera_en_cola(self) -> float | None:
        return round(self.iniciada - self.creada, 4) if self.iniciada else None

    @property
    def duracion(self) -> float | None:
        if self.iniciada and self.finalizada:
            return round(self.finalizada - self.iniciada, 4)
        return None

    def a_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'tipo': self.tipo,
            'estado': self.estado.value,
            'parametros': self.parametros,
            'timeout': self.timeout,
            'creada': _iso(self.creada),
            'iniciada': _iso(self.iniciada),
            'finalizada': _iso(self.finalizada),
            'espera_en_cola': self.espera_en_cola,
            'duracion': self.duracion,
            'progreso': self.progreso,
            'worker': self.worker,
            'resultado': self.resultado,
            'error': self.error,
        }


class Registro:
    """Guarda las tareas y hace las transiciones de estado.

    Todas las transiciones pasan por acá, así hay un solo lugar donde se
    avisa a los suscriptores (WebSocket) y se mantienen las estadísticas.
    """

    def __init__(self, al_cambiar: Callable[[Tarea], None] | None = None):
        self._tareas: dict[int, Tarea] = {}
        self._ids = itertools.count(1)
        self._al_cambiar = al_cambiar or (lambda t: None)

    # --- consultas -------------------------------------------------------

    def obtener(self, tid: int) -> Tarea | None:
        return self._tareas.get(tid)

    def listar(self, estado: Estado | None = None, limite: int = 100,
               id_desde: int = 0) -> list[Tarea]:
        """Paginación por cursor: tareas con id >= id_desde. (El dict
        conserva el orden de inserción, que es el orden de los ids.)"""
        items = (t for t in self._tareas.values()
                 if t.id >= id_desde and (estado is None or t.estado == estado))
        return list(itertools.islice(items, limite))

    def todas(self) -> list[Tarea]:
        return list(self._tareas.values())

    # --- transiciones ----------------------------------------------------

    def crear(self, tipo: str, parametros: dict, timeout: float) -> Tarea:
        t = Tarea(id=next(self._ids), tipo=tipo, parametros=parametros,
                  timeout=timeout)
        self._tareas[t.id] = t
        self._al_cambiar(t)
        return t

    def descartar(self, tid: int) -> None:
        """Saca una tarea recién creada que no se pudo encolar (cola llena)."""
        self._tareas.pop(tid, None)

    def iniciar(self, t: Tarea, worker: int) -> None:
        t.estado = Estado.EJECUTANDO
        t.iniciada = time.time()
        t.worker = worker
        self._al_cambiar(t)

    def progresar(self, t: Tarea, fraccion: float) -> None:
        t.progreso = round(fraccion, 4)

    def terminar(self, t: Tarea, estado: Estado, resultado: Any = None,
                 error: str | None = None) -> None:
        """Pasa a un estado final. Si ya estaba en uno, no hace nada."""
        if t.estado.es_final:
            return
        t.estado = estado
        t.finalizada = time.time()
        t.resultado = resultado
        t.error = error
        if estado == Estado.COMPLETADA:
            t.progreso = 1.0
        self._al_cambiar(t)

    # --- estadísticas ----------------------------------------------------

    def estadisticas(self) -> dict[str, Any]:
        por_estado = {e.value: 0 for e in Estado}
        duraciones: dict[str, list[float]] = {}
        esperas: list[float] = []
        for t in self._tareas.values():
            por_estado[t.estado.value] += 1
            if t.estado == Estado.COMPLETADA and t.duracion is not None:
                duraciones.setdefault(t.tipo, []).append(t.duracion)
            if t.espera_en_cola is not None:
                esperas.append(t.espera_en_cola)

        def prom(xs):
            return round(sum(xs) / len(xs), 4) if xs else None

        todas = [d for ds in duraciones.values() for d in ds]
        return {
            'total': len(self._tareas),
            'por_estado': por_estado,
            'duracion_promedio': prom(todas),
            'duracion_promedio_por_tipo': {k: prom(v) for k, v in duraciones.items()},
            'espera_en_cola_promedio': prom(esperas),
        }
