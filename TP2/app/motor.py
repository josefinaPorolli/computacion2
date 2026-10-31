"""El motor: la cola de tareas y el pool de workers.

Es el patrón productor-consumidor de la clase 11, pero con corrutinas:

    POST /tareas  --put_nowait-->  asyncio.Queue  --get-->  N workers

  - El productor es el endpoint POST: crea la tarea en el registro, pone su id
    en la cola y responde ENSEGUIDA, sin esperar a que se ejecute.
  - Los consumidores son N corrutinas `_worker` (bucles infinitos) que sacan
    ids de la cola y los ejecutan.

Cómo se ejecuta cada tarea: el worker NO la corre directamente, sino que crea
una asyncio.Task hija (la "ejecución") y la espera. Así tenemos un objeto al
que llamarle .cancel() desde DELETE /tareas/{id} sin matar al worker, que
queda libre para la siguiente tarea.

    worker ──create_task──> ejecución (con asyncio.timeout adentro)
       │                         │
       └── await ejecución <─────┘   resultado / excepción / CancelledError
"""
import asyncio
import logging
from typing import Any

from .config import Config
from .modelos import Estado
from .registro import Registro, Tarea
from .tareas import EJECUTORES, Contexto

log = logging.getLogger(__name__)


class ColaLlena(Exception):
    pass


class NoAcepta(Exception):
    pass


class Motor:
    def __init__(self, config: Config, registro: Registro, http, pool_cpu):
        self.config = config
        self.registro = registro
        self.http = http
        self.pool_cpu = pool_cpu
        # asyncio.Queue y no queue.Queue: get() es una corrutina que SUSPENDE
        # al worker sin bloquear el thread. queue.Queue.get() bloquearía el
        # único thread que tenemos, y con él al servidor entero.
        self.cola: asyncio.Queue[int] = asyncio.Queue(maxsize=config.cola_max)
        self.workers: dict[int, asyncio.Task] = {}
        self.en_curso: dict[int, asyncio.Task] = {}     # id tarea -> ejecución
        self.aceptando = False
        self.apagando = False

    # ------------------------------------------------------------------
    # Arranque
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        for wid in range(self.config.workers):
            self._lanzar_worker(wid)
        self.aceptando = True
        log.info('motor iniciado: %d workers, cola máx %d, %d procesos CPU',
                 self.config.workers, self.config.cola_max,
                 self.config.procesos_cpu)

    def _lanzar_worker(self, wid: int) -> None:
        w = asyncio.create_task(self._worker(wid), name=f'worker-{wid}')
        w.add_done_callback(lambda tarea, wid=wid: self._worker_termino(wid, tarea))
        self.workers[wid] = w

    def _worker_termino(self, wid: int, w: asyncio.Task) -> None:
        """Supervisor: si un worker muere por un bug (no por apagado), lo
        reemplaza. Sin esto, cada excepción no capturada achicaría el pool
        en silencio hasta dejarlo en cero (clase 22: "el bug silencioso")."""
        if w.cancelled() or self.apagando:
            return
        exc = w.exception()
        log.error('worker %d murió inesperadamente (%r); se lo reemplaza', wid, exc)
        self._lanzar_worker(wid)

    # ------------------------------------------------------------------
    # Productor: encolar
    # ------------------------------------------------------------------

    def encolar(self, tipo: str, parametros: dict, timeout: float | None) -> Tarea:
        if not self.aceptando:
            raise NoAcepta('el servidor se está apagando')
        t = self.registro.crear(tipo, parametros,
                                timeout or self.config.timeout_defecto)
        try:
            # put_nowait y no `await put()`: el POST tiene que responder ya.
            # Si la cola está llena preferimos decir 503 a dejar al cliente
            # colgado esperando lugar (eso es el backpressure de maxsize).
            self.cola.put_nowait(t.id)
        except asyncio.QueueFull:
            self.registro.descartar(t.id)
            raise ColaLlena(f'la cola está llena ({self.config.cola_max})')
        return t

    # ------------------------------------------------------------------
    # Consumidores: los workers
    # ------------------------------------------------------------------

    async def _worker(self, wid: int) -> None:
        while True:
            tid = await self.cola.get()          # suspende, no bloquea
            try:
                await self._procesar(wid, tid)
            except asyncio.CancelledError:
                raise                            # nos están apagando
            except Exception:
                # Un error en NUESTRO código (no en la tarea, ese se captura
                # en _procesar). Se loguea y el worker sigue vivo.
                log.exception('error interno procesando la tarea %s', tid)
            finally:
                self.cola.task_done()            # SIEMPRE, o join() no vuelve

    async def _procesar(self, wid: int, tid: int) -> None:
        t = self.registro.obtener(tid)
        if t is None or t.estado != Estado.PENDIENTE:
            return                               # la cancelaron mientras esperaba

        self.registro.iniciar(t, wid)
        ejecucion = asyncio.create_task(self._ejecutar(t), name=f'tarea-{tid}')
        self.en_curso[tid] = ejecucion
        try:
            resultado = await ejecucion
        except asyncio.CancelledError:
            # ¿A quién cancelaron? cancelling() > 0 significa que alguien
            # llamó .cancel() sobre ESTE worker (apagado). Si no, fue un
            # DELETE sobre la ejecución, y el worker tiene que seguir.
            a_mi = asyncio.current_task().cancelling() > 0
            motivo = ('cancelada por apagado del servidor'
                      if a_mi or self.apagando else 'cancelada por el usuario')
            self.registro.terminar(t, Estado.CANCELADA, error=motivo)
            if a_mi:
                raise           # relanzar: el worker tiene que terminar
        except TimeoutError:
            self.registro.terminar(t, Estado.FALLIDA,
                                   error=f'timeout: superó los {t.timeout} s')
        except Exception as e:
            # La tarea lanzó una excepción: la tarea falla, el worker no.
            self.registro.terminar(t, Estado.FALLIDA,
                                   error=f'{type(e).__name__}: {e}')
        else:
            self.registro.terminar(t, Estado.COMPLETADA, resultado=resultado)
        finally:
            self.en_curso.pop(tid, None)

    async def _ejecutar(self, t: Tarea) -> Any:
        ctx = Contexto(
            config=self.config, http=self.http, pool_cpu=self.pool_cpu,
            progreso=lambda f: self.registro.progresar(t, f),
        )
        ejecutor = EJECUTORES[t.tipo]
        # asyncio.timeout cancela la ejecución cuando vence el plazo y
        # convierte ese CancelledError en TimeoutError (clase 20).
        async with asyncio.timeout(t.timeout):
            return await ejecutor(t.parametros, ctx)

    # ------------------------------------------------------------------
    # Cancelación
    # ------------------------------------------------------------------

    async def cancelar(self, tid: int, espera: float = 2.0) -> Tarea | None:
        """Cancela una tarea pendiente o en ejecución.

        - Pendiente: se marca cancelada. Su id sigue en la cola, pero cuando
          un worker lo saque va a ver que ya no está pendiente y lo salteará.
        - Ejecutando: .cancel() sobre su ejecución. Eso inyecta CancelledError
          en el await donde esté parada; los `async with` / `finally` de la
          tarea liberan lo que tenían (conexiones, semáforos). Esperamos un
          poco a que termine de limpiar para devolver el estado final.
        """
        t = self.registro.obtener(tid)
        if t is None:
            return None
        if t.estado == Estado.PENDIENTE:
            self.registro.terminar(t, Estado.CANCELADA,
                                   error='cancelada por el usuario (en cola)')
        elif t.estado == Estado.EJECUTANDO and (ej := self.en_curso.get(tid)):
            ej.cancel()
            # asyncio.wait no cancela lo que espera si vence el plazo: solo
            # deja de esperar. La cancelación sigue su curso igual.
            await asyncio.wait({ej}, timeout=espera)
        return t

    # ------------------------------------------------------------------
    # Estado para /estadisticas
    # ------------------------------------------------------------------

    def estado_pool(self) -> dict[str, Any]:
        return {
            'workers_total': len(self.workers),
            'workers_ocupados': len(self.en_curso),
            'en_cola': self.cola.qsize(),
            'cola_max': self.config.cola_max,
            'procesos_cpu': self.config.procesos_cpu,
            'aceptando': self.aceptando,
        }

    # ------------------------------------------------------------------
    # Apagado ordenado
    # ------------------------------------------------------------------

    async def apagar(self) -> None:
        """1) dejar de aceptar, 2) descartar lo que nunca arrancó,
        3) esperar con límite a lo que está corriendo, 4) cancelar lo que
        quede, 5) cancelar los workers y esperar a que salgan."""
        self.aceptando = False
        self.apagando = True

        # 2) Lo que sigue en la cola no se va a ejecutar nunca: lo marcamos.
        descartadas = 0
        while True:
            try:
                tid = self.cola.get_nowait()
            except asyncio.QueueEmpty:
                break
            t = self.registro.obtener(tid)
            if t and t.estado == Estado.PENDIENTE:
                self.registro.terminar(t, Estado.CANCELADA,
                                       error='no llegó a ejecutarse: apagado del servidor')
                descartadas += 1
            self.cola.task_done()

        # 3) Esperar a las que están corriendo, como mucho `gracia` segundos.
        corriendo = set(self.en_curso.values())
        log.info('apagando: %d en curso, %d pendientes descartadas; espero hasta %.0f s',
                 len(corriendo), descartadas, self.config.gracia_apagado)
        if corriendo:
            hechas, quedan = await asyncio.wait(corriendo,
                                                timeout=self.config.gracia_apagado)
            # 4) Las que no llegaron, se cancelan.
            if quedan:
                log.warning('cancelando %d tareas que no terminaron a tiempo', len(quedan))
                for ej in quedan:
                    ej.cancel()
                await asyncio.gather(*quedan, return_exceptions=True)

        # 5) Los workers están parados en cola.get(): los cancelamos y
        # esperamos a que salgan, para no dejar corrutinas huérfanas.
        for w in self.workers.values():
            w.cancel()
        await asyncio.gather(*self.workers.values(), return_exceptions=True)
        log.info('motor detenido')
