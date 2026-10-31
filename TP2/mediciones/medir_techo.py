#!/usr/bin/env python3
"""Medición 3: el techo del pool. Subir la cantidad de tareas simultáneas
hasta que los tiempos se degraden.

Parte A (esperar, I/O simulado): N tareas de 1 s lanzadas de golpe. Con W
workers, deberían tardar ceil(N / W) segundos: hasta N = W, todo en ~1 s;
después, escalones. El techo lo pone la cantidad de workers.

Parte B (hashear, CPU): N hashes iguales lanzados de golpe. El techo lo pone
la cantidad de procesos del executor (= núcleos): pasado ese número, cada
tarea extra se suma al tiempo total.

Uso:
    python mediciones/medir_techo.py
    python mediciones/medir_techo.py --a 1 2 4 8 16 32 --b 1 2 4 8
"""
import argparse
import asyncio
import math
import statistics
from concurrent.futures import ProcessPoolExecutor

from comun import ahora, cliente, crear_o_none, esperar_vacio

CONEXIONES = 100


async def _postear_async(api, n, tipo, params):
    # El cliente también tiene límites: con miles de pedidos esperando en el
    # pool de conexiones de httpx, el cuello de botella pasa a ser el propio
    # cliente. El semáforo deja como mucho CONEXIONES pedidos en vuelo.
    sem = asyncio.Semaphore(CONEXIONES)
    async with cliente(api) as c:
        async def uno():
            async with sem:
                return await crear_o_none(c, tipo, timeout=600, **params)
        return await asyncio.gather(*(uno() for _ in range(n)))


def _postear(api, n, tipo, params):
    """Corre en un proceso aparte: su propio event loop, su propio cliente."""
    return asyncio.run(_postear_async(api, n, tipo, params))


async def postear(api, n, tipo, params, procesos):
    """Reparte n POSTs entre `procesos` procesos cliente (clase 22). Generar
    carga con Python también consume CPU: con un solo proceso cliente, el
    que se satura es el cliente y no el servidor."""
    if procesos <= 1:
        return await _postear_async(api, n, tipo, params)
    partes = [n // procesos + (i < n % procesos) for i in range(procesos)]
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(procesos) as pool:
        listas = await asyncio.gather(*(
            loop.run_in_executor(pool, _postear, api, k, tipo, params)
            for k in partes if k))
    return [i for lista in listas for i in lista]


async def ronda(c, n, tipo, procesos=1, **params):
    t0 = ahora()
    ids = await postear(str(c.base_url).rstrip('/'), n, tipo, params, procesos)
    t_post = ahora() - t0
    rechazadas = ids.count(None)
    ids = [i for i in ids if i is not None]
    await esperar_vacio(c, cada=0.02)
    total = ahora() - t0
    pedidos = set(ids)
    tareas = (await c.get('/tareas', params={'limite': 10_000,
                                              'id_desde': min(ids)})).json()
    tareas = [t for t in tareas if t['id'] in pedidos]
    esperas = [t['espera_en_cola'] for t in tareas]
    duraciones = [t['duracion'] for t in tareas]
    ok = sum(t['estado'] == 'completada' for t in tareas)
    return (total, t_post, statistics.mean(esperas), statistics.mean(duraciones),
            ok, rechazadas)


async def main(args):
    async with cliente(args.api) as c:
        pool = (await c.get('/estadisticas')).json()['pool']
        W, P = pool['workers_total'], pool['procesos_cpu']

        print(f'\n=== Medición 3A: N tareas `esperar` de {args.segundos} s '
              f'({W} workers, {args.procesos} proceso(s) cliente) ===')
        print(f'  {"N":>6}{"total":>9}{"ideal":>8}{"espera cola":>13}'
              f'{"ejecución":>11}{"POSTs":>9}{"ok":>7}{"rechaz.":>9}')
        for n in args.a:
            total, tp, esp, dur, ok, rech = await ronda(
                c, n, 'esperar', procesos=args.procesos, segundos=args.segundos)
            ideal = math.ceil(ok / W) * args.segundos   # sobre las aceptadas
            print(f'  {n:>6}{total:>8.2f}s{ideal:>7.0f}s{esp:>12.2f}s'
                  f'{dur:>10.2f}s{tp:>8.2f}s{ok:>7}{rech:>9}')

        print(f'\n=== Medición 3B: N hashes de {args.iteraciones:,} iteraciones '
              f'({P} procesos CPU, {W} workers) ===')
        print(f'  {"N":>6}{"total":>9}{"por tarea":>11}{"espera cola":>13}{"ok":>5}')
        for n in args.b:
            total, tp, esp, dur, ok, _ = await ronda(c, n, 'hashear', texto='x',
                                                     iteraciones=args.iteraciones)
            print(f'  {n:>6}{total:>8.2f}s{dur:>10.2f}s{esp:>12.2f}s{ok:>5}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default='http://localhost:8000')
    p.add_argument('--segundos', type=float, default=1.0)
    p.add_argument('--iteraciones', type=int, default=1_500_000)
    p.add_argument('--a', type=int, nargs='+', default=[1, 2, 4, 8, 16, 32, 64])
    p.add_argument('--procesos', type=int, default=1,
                   help='procesos cliente para generar las POSTs de la parte A')
    p.add_argument('--b', type=int, nargs='+', default=[1, 2, 3, 4, 6, 8])
    asyncio.run(main(p.parse_args()))
