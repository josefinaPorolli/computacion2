"""Funciones compartidas por los scripts de medición (cliente HTTP de la API)."""
import asyncio
import time

import httpx

FINALES = {'completada', 'fallida', 'cancelada'}


async def crear(c: httpx.AsyncClient, tipo: str, timeout: float | None = None,
                **parametros) -> int:
    cuerpo = {'tipo': tipo, 'parametros': parametros}
    if timeout:
        cuerpo['timeout'] = timeout
    r = await c.post('/tareas', json=cuerpo)
    r.raise_for_status()
    return r.json()['id']


async def esperar_final(c: httpx.AsyncClient, tid: int, cada: float = 0.05) -> dict:
    while True:
        t = (await c.get(f'/tareas/{tid}')).json()
        if t['estado'] in FINALES:
            return t
        await asyncio.sleep(cada)


async def esperar_vacio(c: httpx.AsyncClient, cada: float = 0.05) -> None:
    """Espera a que no quede nada pendiente ni ejecutando."""
    while True:
        e = (await c.get('/estadisticas')).json()['por_estado']
        if e['pendiente'] == 0 and e['ejecutando'] == 0:
            return
        await asyncio.sleep(cada)


async def crear_o_none(c: httpx.AsyncClient, tipo: str, **kw) -> int | None:
    """Como crear(), pero devuelve None si el servidor rechaza (503) o corta."""
    try:
        return await crear(c, tipo, **kw)
    except (httpx.HTTPStatusError, httpx.TransportError):
        return None


def cliente(api: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=api, timeout=120,
                             limits=httpx.Limits(max_connections=200))


def ahora() -> float:
    return time.perf_counter()
