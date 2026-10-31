#!/usr/bin/env python3
"""Medición 1: 20 descargas secuenciales contra 20 concurrentes.

Manda dos tareas `descargar` con las mismas 20 URLs: una con
"secuencial": true (un for con await adentro) y otra normal (TaskGroup).
Reporta el tiempo de cada una medido por el servidor y el speedup.

Por defecto usa el servidor `lento` del docker-compose, que demora cada
respuesta un tiempo conocido: así el resultado es reproducible.

Uso (con docker compose up corriendo):
    python mediciones/medir_io.py
    python mediciones/medir_io.py --lento http://localhost:9000   # API fuera de Docker
    python mediciones/medir_io.py --reales                       # sitios de internet
"""
import argparse
import asyncio
import random

from comun import cliente, crear, esperar_final

REALES = [
    'https://www.python.org', 'https://docs.python.org/3/', 'https://pypi.org',
    'https://www.wikipedia.org', 'https://github.com', 'https://www.um.edu.ar',
    'https://fastapi.tiangolo.com', 'https://www.python-httpx.org',
    'https://www.debian.org', 'https://www.kernel.org', 'https://www.gnu.org',
    'https://www.mozilla.org', 'https://www.docker.com', 'https://www.w3.org',
    'https://www.ietf.org', 'https://www.iana.org', 'https://www.apache.org',
    'https://www.postgresql.org', 'https://www.sqlite.org', 'https://www.rust-lang.org',
]


async def main(args):
    if args.reales:
        urls = REALES[:args.n]
        demoras = None
    else:
        rnd = random.Random(args.semilla)
        demoras = [round(rnd.uniform(0.2, 1.0), 2) for _ in range(args.n)]
        urls = [f'{args.lento}/bytes/{args.bytes}?demora={d}&i={i}'
                for i, d in enumerate(demoras)]

    async with cliente(args.api) as c:
        res = {}
        for modo, secuencial in (('secuencial', True), ('concurrente', False)):
            tid = await crear(c, 'descargar', timeout=300, urls=urls,
                              secuencial=secuencial)
            t = await esperar_final(c, tid)
            if t['estado'] != 'completada':
                raise SystemExit(f'la tarea {modo} terminó {t["estado"]}: {t["error"]}')
            res[modo] = t['resultado']

    seq = res['secuencial']['total_segundos']
    con = res['concurrente']['total_segundos']
    print(f'\n=== Medición 1: {args.n} descargas ===')
    if demoras:
        print(f'URLs del servidor lento, {args.bytes} bytes c/u, demoras entre '
              f'0.2 y 1.0 s (semilla {args.semilla})')
        print(f'  suma de las demoras : {sum(demoras):6.2f} s   <- lo esperable secuencial')
        print(f'  la demora más larga : {max(demoras):6.2f} s   <- lo esperable concurrente')
    else:
        lentas = sorted(u['segundos'] for u in res['concurrente']['urls'])
        print(f'Sitios reales. La URL más lenta (concurrente): {lentas[-1]:.2f} s')
    print(f'  secuencial          : {seq:6.2f} s')
    print(f'  concurrente         : {con:6.2f} s')
    print(f'  speedup             : {seq / con:6.1f}x')
    errores = res['concurrente']['con_error']
    if errores:
        print(f'  ({errores} URLs con error)')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default='http://localhost:8000')
    p.add_argument('--lento', default='http://lento:9000',
                   help='URL base del servidor lento VISTA DESDE LA API')
    p.add_argument('--n', type=int, default=20)
    p.add_argument('--bytes', type=int, default=200_000)
    p.add_argument('--semilla', type=int, default=2026)
    p.add_argument('--reales', action='store_true')
    asyncio.run(main(p.parse_args()))
