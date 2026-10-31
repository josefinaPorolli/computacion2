"""Servidor HTTP de prueba con demoras controladas.

Para medir concurrencia de descargas hace falta que cada descarga tarde un
tiempo conocido. Con sitios reales los números dependen de la red del día;
con este servidor son reproducibles. En docker-compose corre como el
servicio `lento` (puerto 9000).

    GET /bytes/{n}?demora=0.5   espera `demora` segundos y manda n bytes
    GET /estado/{codigo}        responde con ese código HTTP

Uso fuera de Docker:
    python -m lento.servidor
"""
import asyncio
import os

from fastapi import FastAPI, Query, Response
from fastapi.responses import StreamingResponse

app = FastAPI(title='Servidor lento de pruebas')

PEDAZO = 64 * 1024


@app.get('/bytes/{n}')
async def bytes_lentos(n: int, demora: float = Query(default=0.0, ge=0, le=120)):
    await asyncio.sleep(demora)           # no bloquea: atiende a otros mientras

    async def cuerpo():
        enviados = 0
        while enviados < n:
            k = min(PEDAZO, n - enviados)
            yield b'x' * k
            enviados += k

    return StreamingResponse(cuerpo(), media_type='application/octet-stream',
                             headers={'Content-Length': str(n)})


@app.get('/estado/{codigo}')
async def estado(codigo: int):
    return Response(status_code=codigo)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 9000)),
                log_level='warning')
