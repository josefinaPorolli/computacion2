"""Fixtures: levantan la app completa (con su lifespan) en memoria.

httpx.ASGITransport le habla a la app sin abrir sockets. El lifespan (cola,
workers, pool de procesos) se arranca a mano con `app.router.lifespan_context`,
porque ASGITransport no lo dispara solo.
"""
import sys
from pathlib import Path

import httpx
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest_asyncio.fixture
async def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv('DIR_VOLCADOS', str(tmp_path))
    monkeypatch.setenv('WORKERS', '3')
    monkeypatch.setenv('PROCESOS_CPU', '1')
    monkeypatch.setenv('GRACIA_APAGADO', '1')
    from app.main import app
    from lento.servidor import app as app_lento

    async with app.router.lifespan_context(app):
        # Las descargas van al servidor lento, también en memoria.
        await app.state.motor.http.aclose()
        app.state.motor.http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_lento), base_url='http://lento')
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte,
                                     base_url='http://test') as c:
            c.app = app
            yield c
