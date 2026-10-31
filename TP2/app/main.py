"""Punto de entrada: la API HTTP (FastAPI) y el ciclo de vida del servicio.

Correr:
    python -m app.main                 # o: docker compose up --build
Documentación interactiva:
    http://localhost:8000/docs

Todos los endpoints son `async def` y ninguno hace nada bloqueante: solo
tocan el registro en memoria o hacen `await` de cosas que ceden el control.
"""
import asyncio
import logging
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import PlainTextResponse

from . import persistencia
from .config import Config
from .eventos import Difusor
from .modelos import Estado, TareaNueva, TareaSalida
from .motor import ColaLlena, Motor, NoAcepta
from .registro import Registro
from .tareas.hashear import hash_iterado

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s %(levelname)-7s %(name)s: %(message)s',
)
log = logging.getLogger('app')


# ---------------------------------------------------------------------------
# Ciclo de vida: lo que se crea al arrancar y se libera al apagar
# ---------------------------------------------------------------------------

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    config = Config()

    # Persistencia: si hay un volcado de una corrida anterior, reportarlo.
    previo = await asyncio.to_thread(persistencia.ultimo_volcado, config.dir_volcados)
    if previo:
        ruta, datos = previo
        log.info('volcado previo encontrado: %s (%s, %d tareas, por estado: %s)',
                 ruta, datos.get('volcado_en'), len(datos.get('tareas', [])),
                 datos.get('estadisticas', {}).get('por_estado'))
    else:
        log.info('no hay volcados previos en %s/', config.dir_volcados)

    difusor = Difusor()
    registro = Registro(al_cambiar=lambda t: difusor.publicar(
        {'id': t.id, 'tipo': t.tipo, 'estado': t.estado.value,
         'worker': t.worker, 'error': t.error}))

    # El pool de procesos se crea UNA vez (clase 22: "crear el pool una vez").
    # 'spawn' arranca cada proceso con un intérprete limpio, igual en Linux,
    # macOS y Windows (clase 8). Por eso el arranque del servidor está
    # protegido con `if __name__ == '__main__'` (ver al final).
    pool_cpu = ProcessPoolExecutor(
        max_workers=config.procesos_cpu,
        mp_context=multiprocessing.get_context('spawn'))
    # Precalentar: que los procesos ya existan antes del primer pedido.
    loop = asyncio.get_running_loop()
    await asyncio.gather(*(loop.run_in_executor(pool_cpu, hash_iterado, b'', 1)
                           for _ in range(config.procesos_cpu)))

    http = httpx.AsyncClient(
        timeout=config.timeout_http, follow_redirects=True,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20))

    motor = Motor(config, registro, http, pool_cpu)
    motor.iniciar()

    app.state.config = config
    app.state.registro = registro
    app.state.motor = motor
    app.state.difusor = difusor

    try:
        yield                     # <-- acá el servidor atiende pedidos
    finally:
        # Llegamos acá cuando uvicorn recibió SIGTERM o SIGINT y ya dejó de
        # aceptar conexiones nuevas (ver README, "apagado ordenado").
        log.info('apagado ordenado en curso')
        await motor.apagar()
        datos = {
            'volcado_en': datetime.now().isoformat(timespec='seconds'),
            'estadisticas': registro.estadisticas(),
            'tareas': [t.a_dict() for t in registro.todas()],
        }
        ruta = await asyncio.to_thread(persistencia.volcar, config.dir_volcados, datos)
        log.info('estado volcado en %s (%d tareas)', ruta, len(datos['tareas']))
        await http.aclose()
        # shutdown() espera a los procesos: es bloqueante, va a un thread.
        await asyncio.to_thread(pool_cpu.shutdown, wait=True, cancel_futures=True)
        log.info('recursos liberados, chau')


app = FastAPI(
    title='Plataforma de Tareas Distribuidas',
    description='TP2 de Computación II — UM 2026. FastAPI + asyncio.Queue + '
                'pool de workers + ProcessPoolExecutor.',
    version='1.0.0',
    lifespan=ciclo_de_vida,
)


def _motor(request: Request) -> Motor:
    return request.app.state.motor


# ---------------------------------------------------------------------------
# Endpoints obligatorios
# ---------------------------------------------------------------------------

@app.get('/')
async def raiz():
    return {'servicio': 'plataforma de tareas', 'docs': '/docs',
            'tipos': ['descargar', 'hashear', 'esperar']}


@app.post('/tareas', response_model=TareaSalida, status_code=202)
async def crear_tarea(nueva: TareaNueva, request: Request, response: Response):
    """Encola y responde YA. 202 Accepted = "lo recibí, lo voy a hacer"."""
    try:
        t = _motor(request).encolar(nueva.tipo,
                                    nueva.parametros.model_dump(mode='json'),
                                    nueva.timeout)
    except ColaLlena as e:
        raise HTTPException(status_code=503, detail=str(e),
                            headers={'Retry-After': '1'})
    except NoAcepta as e:
        raise HTTPException(status_code=503, detail=str(e))
    response.headers['Location'] = f'/tareas/{t.id}'
    return t.a_dict()


@app.get('/tareas', response_model=list[TareaSalida])
async def listar_tareas(
    request: Request,
    estado: Estado | None = Query(default=None, description='Filtrar por estado'),
    limite: int = Query(default=100, ge=1, le=10_000),
    id_desde: int = Query(default=0, ge=0, description='Solo ids >= este (paginar)'),
):
    return [t.a_dict() for t in request.app.state.registro.listar(estado, limite, id_desde)]


@app.get('/tareas/{tarea_id}', response_model=TareaSalida)
async def obtener_tarea(tarea_id: int, request: Request):
    t = request.app.state.registro.obtener(tarea_id)
    if t is None:
        raise HTTPException(status_code=404, detail='No existe esa tarea')
    return t.a_dict()


@app.delete('/tareas/{tarea_id}', response_model=TareaSalida)
async def cancelar_tarea(tarea_id: int, request: Request):
    """Cancela una tarea pendiente o en ejecución. Devuelve cómo quedó."""
    t = request.app.state.registro.obtener(tarea_id)
    if t is None:
        raise HTTPException(status_code=404, detail='No existe esa tarea')
    if t.estado.es_final:
        raise HTTPException(status_code=409,
                            detail=f'La tarea ya terminó: está {t.estado.value}')
    await _motor(request).cancelar(tarea_id)
    return t.a_dict()


@app.get('/estadisticas')
async def estadisticas(request: Request):
    return {**request.app.state.registro.estadisticas(),
            'pool': _motor(request).estado_pool(),
            'suscriptores_ws': request.app.state.difusor.cantidad}


# ---------------------------------------------------------------------------
# Bonus: métricas Prometheus y WebSocket de eventos
# ---------------------------------------------------------------------------

@app.get('/metrics', response_class=PlainTextResponse)
async def metricas(request: Request):
    """Formato de exposición de Prometheus, escrito a mano (es texto plano)."""
    est = request.app.state.registro.estadisticas()
    pool = _motor(request).estado_pool()
    lineas = ['# HELP tareas_total Tareas por estado.', '# TYPE tareas_total gauge']
    lineas += [f'tareas_total{{estado="{e}"}} {n}' for e, n in est['por_estado'].items()]
    lineas += ['# HELP tareas_duracion_promedio_segundos Duración media de las completadas.',
               '# TYPE tareas_duracion_promedio_segundos gauge']
    lineas += [f'tareas_duracion_promedio_segundos{{tipo="{k}"}} {v}'
               for k, v in est['duracion_promedio_por_tipo'].items()]
    lineas += ['# TYPE workers_ocupados gauge', f'workers_ocupados {pool["workers_ocupados"]}',
               '# TYPE workers_total gauge', f'workers_total {pool["workers_total"]}',
               '# TYPE cola_tamano gauge', f'cola_tamano {pool["en_cola"]}']
    return '\n'.join(lineas) + '\n'


@app.websocket('/eventos')
async def eventos(ws: WebSocket):
    """Manda un JSON por cada cambio de estado de cualquier tarea.

    Hay DOS corrutinas por cliente: una manda eventos y otra escucha si el
    cliente (o el servidor, al apagarse) cerró la conexión. Con una sola,
    el endpoint quedaba parado en `cola.get()` sin enterarse del cierre, y
    uvicorn lo esperaba para siempre al apagar: el apagado se colgaba y
    nunca se hacía el volcado. (Bug encontrado probando SIGTERM con un
    cliente conectado.)
    """
    await ws.accept()
    difusor: Difusor = ws.app.state.difusor
    cola = difusor.suscribir()

    async def mandar():
        while True:
            await ws.send_json(await cola.get())

    async def escuchar_cierre():
        while (await ws.receive())['type'] != 'websocket.disconnect':
            pass                          # ignoramos lo que mande el cliente

    tareas = {asyncio.create_task(mandar()), asyncio.create_task(escuchar_cierre())}
    try:
        # La primera que termine (normalmente, el cierre) gana...
        await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # ...y la otra se cancela y se espera: nada queda huérfano.
        for t in tareas:
            t.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        difusor.desuscribir(cola)


# ---------------------------------------------------------------------------
# Arranque. La guarda es OBLIGATORIA con 'spawn': cada proceso del pool
# re-importa este módulo, y sin ella cada uno levantaría otro servidor.
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=os.environ.get('HOST', '0.0.0.0'),
                port=int(os.environ.get('PORT', 8000)),
                # Red de seguridad: si alguna conexión no cierra, uvicorn no
                # la espera más de esto antes de pasar al apagado del motor.
                timeout_graceful_shutdown=5)
