#!/usr/bin/env python3
"""Medición 2: cuánto tarda un GET /tareas mientras corre un hash pesado.

Para cada modo de `hashear` (directo, thread, proceso) lanza un hash de
--iteraciones vueltas y, mientras corre, manda GET /tareas cada 50 ms
midiendo cuánto tarda cada respuesta.

  - directo : el cálculo corre DENTRO del event loop. El loop no puede
              atender nada: el primer GET espera a que termine el hash.
  - thread  : asyncio.to_thread. El loop sigue vivo, pero compite por el GIL
              con el thread que calcula.
  - proceso : run_in_executor con ProcessPoolExecutor. El cálculo corre en
              otro proceso, con su propio GIL: el loop queda libre.

El modo 'directo' está deshabilitado por defecto (la API responde 403),
así que para esta medición hay que levantar el servidor con:
    PERMITIR_MODO_DIRECTO=1 docker compose up --build

Uso:
    python mediciones/medir_bloqueo.py
    python mediciones/medir_bloqueo.py --iteraciones 8000000
"""
import argparse
import asyncio
import statistics

import httpx

from comun import FINALES, ahora, cliente, crear


async def sondear(c, tid, cada):
    latencias = []
    while True:
        t0 = ahora()
        await c.get('/tareas', params={'limite': 1})
        latencias.append((ahora() - t0) * 1000)
        t = (await c.get(f'/tareas/{tid}')).json()
        if t['estado'] in FINALES:
            return latencias, t
        await asyncio.sleep(cada)


async def main(args):
    print(f'\n=== Medición 2: GET /tareas durante un hash de {args.iteraciones:,} '
          f'iteraciones ===')
    print(f'  {"modo":<9}{"hash":>8}{"GETs":>7}{"mediana":>11}{"p95":>11}{"peor":>11}')
    async with cliente(args.api) as c:
        await c.get('/tareas')                       # calentar la conexión
        for modo in args.modos:
            try:
                tid = await crear(c, 'hashear', timeout=600, texto='computacion2',
                                  iteraciones=args.iteraciones, modo=modo)
            except httpx.HTTPStatusError as e:
                print(f'  {modo:<9}rechazado ({e.response.status_code}): '
                      f'{e.response.json()["detail"]}')
                continue
            lat, t = await sondear(c, tid, args.cada)
            p95 = statistics.quantiles(lat, n=20)[-1] if len(lat) >= 2 else lat[0]
            print(f'  {modo:<9}{t["duracion"]:>7.2f}s{len(lat):>7}'
                  f'{statistics.median(lat):>9.1f}ms{p95:>9.1f}ms{max(lat):>9.1f}ms')
            await asyncio.sleep(0.5)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default='http://localhost:8000')
    p.add_argument('--iteraciones', type=int, default=5_000_000)
    p.add_argument('--cada', type=float, default=0.05)
    p.add_argument('--modos', nargs='+', default=['directo', 'thread', 'proceso'])
    asyncio.run(main(p.parse_args()))