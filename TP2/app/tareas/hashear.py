"""Tarea `hashear`: SHA-256 aplicado N veces. CPU-bound puro.

El problema: un `for` de millones de hashes no tiene ningún `await`, así que
si corre dentro de una corrutina, el event loop queda congelado hasta que
termine. Nadie más es atendido: ni un GET, ni un timeout, ni una cancelación.

La solución: mandar el cálculo a un ProcessPoolExecutor con
`loop.run_in_executor` (clase 21). La corrutina hace `await` del resultado,
y mientras tanto el loop sigue atendiendo a todos.

¿Por qué procesos y no threads? Por el GIL (clase 10): un thread de Python
que hace cálculo puro no deja correr bytecode a los demás threads, así que
dos hashes en threads no son más rápidos que uno. Cada proceso tiene su
propio intérprete y su propio GIL: corren en paralelo de verdad, uno por
núcleo. El modo 'thread' existe para poder compararlo.

Detalle de diseño: el cálculo se manda en BLOQUES (por defecto 100.000
iteraciones, ~0,1 s). Entre bloque y bloque hay un `await`, y eso permite:
  - cancelar o cortar por timeout una tarea en curso: el CancelledError entra
    en el próximo await. A lo sumo se desperdicia el bloque que ya estaba
    corriendo en el otro proceso (no hay forma segura de interrumpirlo).
  - informar el progreso.
El costo es pequeño: por bloque viajan 32 bytes pickleados de ida y de vuelta.
"""
import asyncio
import hashlib


def hash_iterado(estado: bytes, vueltas: int) -> bytes:
    """El trabajo pesado. Función de módulo para que se pueda picklear
    y mandar a otro proceso (las lambdas y funciones anidadas no)."""
    h = estado
    for _ in range(vueltas):
        h = hashlib.sha256(h).digest()
    return h


async def ejecutar(params: dict, ctx) -> dict:
    texto: str = params['texto']
    total: int = params['iteraciones']
    modo: str = params.get('modo', 'proceso')

    h = texto.encode()

    if modo == 'directo':
        # MAL A PROPÓSITO: calcula dentro del event loop y lo bloquea.
        # Existe solo para la medición 2. No hay ningún await en el medio,
        # así que no se puede cancelar ni cortar por timeout.
        h = hash_iterado(h, total)
        return {'hash': h.hex(), 'iteraciones': total, 'modo': modo}

    loop = asyncio.get_running_loop()
    bloque = ctx.config.hash_bloque
    hechas = 0
    while hechas < total:
        n = min(bloque, total - hechas)
        if modo == 'thread':
            h = await asyncio.to_thread(hash_iterado, h, n)
        else:
            h = await loop.run_in_executor(ctx.pool_cpu, hash_iterado, h, n)
        hechas += n
        ctx.progreso(hechas / total)

    return {'hash': h.hex(), 'iteraciones': total, 'modo': modo}
