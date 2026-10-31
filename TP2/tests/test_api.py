"""Tests con pytest-asyncio. Foco en lo que pide la consigna: que el POST no
espere, que la concurrencia sea real, y que la cancelación sea limpia.

Correr:  pytest -v
"""
import asyncio
import time

import pytest

pytestmark = pytest.mark.asyncio


async def crear(c, tipo, timeout=None, **parametros):
    cuerpo = {'tipo': tipo, 'parametros': parametros}
    if timeout:
        cuerpo['timeout'] = timeout
    r = await c.post('/tareas', json=cuerpo)
    assert r.status_code == 202, r.text
    return r.json()['id']


async def esperar_final(c, tid, limite=10.0):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        t = (await c.get(f'/tareas/{tid}')).json()
        if t['estado'] in ('completada', 'fallida', 'cancelada'):
            return t
        await asyncio.sleep(0.02)
    raise AssertionError(f'la tarea {tid} no terminó: {t}')


async def esperar_estado(c, tid, estado, limite=5.0):
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if (await c.get(f'/tareas/{tid}')).json()['estado'] == estado:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f'{tid} nunca llegó a {estado}')


async def test_post_responde_inmediatamente(cliente):
    t0 = time.perf_counter()
    tid = await crear(cliente, 'esperar', segundos=2)
    assert time.perf_counter() - t0 < 0.2       # no esperó los 2 s
    assert (await cliente.get(f'/tareas/{tid}')).json()['estado'] in (
        'pendiente', 'ejecutando')


async def test_validacion(cliente):
    r = await cliente.post('/tareas', json={'tipo': 'hashear', 'parametros': {}})
    assert r.status_code == 422
    r = await cliente.post('/tareas', json={'tipo': 'volar', 'parametros': {}})
    assert r.status_code == 422
    assert (await cliente.get('/tareas/999')).status_code == 404


async def test_las_tres_tareas_completan(cliente):
    a = await crear(cliente, 'esperar', segundos=0.2)
    b = await crear(cliente, 'hashear', texto='hola', iteraciones=1000)
    c = await crear(cliente, 'descargar',
                    urls=['http://lento/bytes/1000?demora=0.1'])
    ta, tb, tc = [await esperar_final(cliente, x) for x in (a, b, c)]
    assert ta['estado'] == tb['estado'] == tc['estado'] == 'completada'
    import hashlib
    h = b'hola'
    for _ in range(1000):
        h = hashlib.sha256(h).digest()
    assert tb['resultado']['hash'] == h.hex()
    assert tc['resultado']['urls'][0]['bytes'] == 1000


async def test_descargas_concurrentes_tardan_lo_que_la_mas_lenta(cliente):
    urls = [f'http://lento/bytes/100?demora={d}' for d in (0.3, 0.5, 0.4, 0.2)]
    tid = await crear(cliente, 'descargar', urls=urls)
    t = await esperar_final(cliente, tid)
    assert t['estado'] == 'completada'
    assert t['resultado']['total_segundos'] < 0.9     # suma = 1.4, máx = 0.5


async def test_cancelar_en_ejecucion(cliente):
    tid = await crear(cliente, 'esperar', segundos=30)
    await esperar_estado(cliente, tid, 'ejecutando')
    t0 = time.perf_counter()
    r = await cliente.delete(f'/tareas/{tid}')
    assert r.status_code == 200
    assert r.json()['estado'] == 'cancelada'
    assert time.perf_counter() - t0 < 1
    # el worker sigue vivo y atiende otra tarea
    otra = await crear(cliente, 'esperar', segundos=0.1)
    assert (await esperar_final(cliente, otra))['estado'] == 'completada'
    assert cliente.app.state.motor.en_curso == {}      # nada quedó colgado


async def test_cancelar_descarga_a_mitad_libera_todo(cliente):
    urls = ['http://lento/bytes/100?demora=30' for _ in range(5)]
    tid = await crear(cliente, 'descargar', urls=urls)
    await esperar_estado(cliente, tid, 'ejecutando')
    await asyncio.sleep(0.2)
    antes = len(asyncio.all_tasks())
    r = await cliente.delete(f'/tareas/{tid}')
    assert r.json()['estado'] == 'cancelada'
    await asyncio.sleep(0.1)
    # las 5 hijas del TaskGroup ya no existen
    assert len(asyncio.all_tasks()) <= antes - 5


async def test_cancelar_hash_en_proceso(cliente):
    tid = await crear(cliente, 'hashear', texto='x', iteraciones=50_000_000)
    await esperar_estado(cliente, tid, 'ejecutando')
    await asyncio.sleep(0.3)
    r = await cliente.delete(f'/tareas/{tid}')
    assert r.json()['estado'] == 'cancelada'
    assert r.json()['progreso'] < 0.5


async def test_cancelar_pendiente(cliente):
    largas = [await crear(cliente, 'esperar', segundos=5) for _ in range(3)]
    tid = await crear(cliente, 'esperar', segundos=0.1)     # queda en cola
    assert (await cliente.get(f'/tareas/{tid}')).json()['estado'] == 'pendiente'
    r = await cliente.delete(f'/tareas/{tid}')
    assert r.json()['estado'] == 'cancelada'
    # cancelar algo terminado es un conflicto
    assert (await cliente.delete(f'/tareas/{tid}')).status_code == 409
    for x in largas:
        await cliente.delete(f'/tareas/{x}')


async def test_timeout_pasa_a_fallida(cliente):
    tid = await crear(cliente, 'esperar', timeout=0.3, segundos=10)
    t = await esperar_final(cliente, tid)
    assert t['estado'] == 'fallida'
    assert 'timeout' in t['error']
    assert t['duracion'] < 1


async def test_excepcion_en_tarea_no_mata_al_worker(cliente, monkeypatch):
    from app import tareas

    async def explota(params, ctx):
        raise ValueError('boom')

    monkeypatch.setitem(tareas.EJECUTORES, 'esperar', explota)
    tid = await crear(cliente, 'esperar', segundos=1)
    t = await esperar_final(cliente, tid)
    assert t['estado'] == 'fallida' and 'boom' in t['error']
    monkeypatch.undo()
    workers = cliente.app.state.motor.workers.values()
    assert all(not w.done() for w in workers)


async def test_hash_con_executor_no_bloquea_la_api(cliente):
    tid = await crear(cliente, 'hashear', texto='x', iteraciones=3_000_000)
    await esperar_estado(cliente, tid, 'ejecutando')
    peor = 0.0
    while (await cliente.get(f'/tareas/{tid}')).json()['estado'] == 'ejecutando':
        t0 = time.perf_counter()
        await cliente.get('/tareas')
        peor = max(peor, time.perf_counter() - t0)
        await asyncio.sleep(0.05)
    assert peor < 0.2


async def test_filtro_y_estadisticas(cliente):
    tid = await crear(cliente, 'esperar', segundos=0)
    await esperar_final(cliente, tid)
    r = await cliente.get('/tareas', params={'estado': 'completada'})
    assert [t['id'] for t in r.json()] == [tid]
    est = (await cliente.get('/estadisticas')).json()
    assert est['por_estado']['completada'] == 1
    assert est['pool']['workers_total'] == 3
    assert 'tareas_total{estado="completada"} 1' in (await cliente.get('/metrics')).text


async def test_modo_directo_deshabilitado_por_defecto(cliente):
    r = await cliente.post('/tareas', json={
        'tipo': 'hashear',
        'parametros': {'texto': 'x', 'iteraciones': 10, 'modo': 'directo'}})
    assert r.status_code == 403
    assert (await cliente.get('/tareas')).json() == []     # no se creó nada


async def test_cola_llena_devuelve_503(cliente):
    motor = cliente.app.state.motor
    motor.cola = asyncio.Queue(maxsize=1)      # cola diminuta para el test
    motor.cola.put_nowait(-1)                  # ocupada
    r = await cliente.post('/tareas', json={'tipo': 'esperar',
                                            'parametros': {'segundos': 0}})
    assert r.status_code == 503