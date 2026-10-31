"""Tarea `descargar`: baja una lista de URLs concurrentemente. I/O-bound.

Usa httpx en modo asíncrono (no `requests`, que es sincrónico y bloquearía
el event loop mientras espera la red). Elegimos httpx sobre aiohttp porque:
  - su API es casi la de requests, y es la que usamos en las clases 19 y 20;
  - tiene timeouts por fase (conexión, lectura) y límites de conexiones;
  - el mismo cliente sirve para los tests (ASGITransport / MockTransport).

Un solo AsyncClient compartido (creado al arrancar) reusa conexiones TCP con
keep-alive (clase 19) en vez de abrir una por pedido.

Concurrencia: cada URL es una tarea dentro de un TaskGroup (clase 21). Si la
tarea entera se cancela (DELETE o timeout), el TaskGroup cancela a todas las
hijas y espera a que terminen: no quedan corrutinas huérfanas. Un Semaphore
acota cuántas descargas corren a la vez (para no agotar descriptores).

Una URL que falla NO cancela a las demás: el error se captura y queda en el
resultado de esa URL. Si fallan todas, la tarea termina como `fallida`.
"""
import asyncio
import time


class DescargaFallida(Exception):
    pass


async def bajar_una(url: str, ctx, sem: asyncio.Semaphore) -> dict:
    async with sem:
        t0 = time.perf_counter()
        try:
            # stream: leemos el cuerpo por pedazos, sin cargarlo entero en
            # memoria. El `async with` garantiza que, pase lo que pase
            # (incluida una cancelación a mitad de la descarga), la respuesta
            # se cierra y la conexión vuelve al pool o se descarta.
            async with ctx.http.stream('GET', url) as r:
                tam = 0
                async for pedazo in r.aiter_bytes():
                    tam += len(pedazo)
                    if tam > ctx.config.max_bytes_descarga:
                        raise DescargaFallida(
                            f'supera el máximo de {ctx.config.max_bytes_descarga} bytes')
            return {'url': url, 'estado_http': r.status_code, 'bytes': tam,
                    'segundos': round(time.perf_counter() - t0, 4)}
        except asyncio.CancelledError:
            raise                       # SIEMPRE relanzarla
        except Exception as e:          # error de red, DNS, tamaño, etc.
            return {'url': url, 'estado_http': None, 'bytes': 0,
                    'segundos': round(time.perf_counter() - t0, 4),
                    'error': f'{type(e).__name__}: {e}'}


async def ejecutar(params: dict, ctx) -> dict:
    urls = [str(u) for u in params['urls']]
    sem = asyncio.Semaphore(ctx.config.descargas_simultaneas)
    t0 = time.perf_counter()
    hechas = 0

    async def una(url):
        nonlocal hechas
        res = await bajar_una(url, ctx, sem)
        hechas += 1
        ctx.progreso(hechas / len(urls))
        return res

    if params.get('secuencial'):
        # Solo para la medición 1: un for con await adentro espera a cada
        # descarga antes de empezar la siguiente. Tarda la SUMA.
        resultados = [await una(u) for u in urls]
    else:
        # Todas a la vez: tarda lo que la más lenta.
        async with asyncio.TaskGroup() as grupo:
            hijas = [grupo.create_task(una(u)) for u in urls]
        resultados = [h.result() for h in hijas]

    ok = [r for r in resultados if 'error' not in r]
    if not ok:
        raise DescargaFallida(f'fallaron las {len(urls)} URLs: '
                              f'{resultados[0]["error"]}')
    return {
        'modo': 'secuencial' if params.get('secuencial') else 'concurrente',
        'total_segundos': round(time.perf_counter() - t0, 4),
        'ok': len(ok),
        'con_error': len(resultados) - len(ok),
        'bytes_totales': sum(r['bytes'] for r in ok),
        'urls': resultados,
    }
