"""Tarea `esperar`: duerme N segundos.

Sirve para probar cancelación, timeouts y ver el estado en vivo. Duerme con
`asyncio.sleep`, NUNCA con `time.sleep`: el primero suspende esta corrutina y
le devuelve el control al loop; el segundo frena el thread entero, y con él a
todas las corrutinas del servidor (clase 18).

Duerme en pasos de 1 s solo para poder informar el progreso: la cancelación
funcionaría igual con un único sleep largo, porque CancelledError se inyecta
en el await que esté esperando. (Primero eran pasos de 0,1 s; la medición 3
mostró que con miles de tareas esos despertares saturaban el event loop.)
"""
import asyncio
import time

PASO = 1.0


async def ejecutar(params: dict, ctx) -> dict:
    segundos = params['segundos']
    t0 = time.perf_counter()
    fin = t0 + segundos
    while (restante := fin - time.perf_counter()) > 0:
        await asyncio.sleep(min(PASO, restante))
        if segundos:
            ctx.progreso(min(1.0, (time.perf_counter() - t0) / segundos))
    return {'durmio': round(time.perf_counter() - t0, 4)}
