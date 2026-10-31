"""El apagado ordenado: espera a las tareas cortas, cancela las largas,
marca las pendientes y deja el volcado JSON."""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark = pytest.mark.asyncio


async def test_apagado_vuelca_estado(tmp_path, monkeypatch):
    monkeypatch.setenv('DIR_VOLCADOS', str(tmp_path))
    monkeypatch.setenv('WORKERS', '2')
    monkeypatch.setenv('PROCESOS_CPU', '1')
    monkeypatch.setenv('GRACIA_APAGADO', '1')
    from app.main import app

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url='http://t') as c:
            for s in (0.3, 30, 30):          # corta, larga, y una en cola
                await c.post('/tareas', json={'tipo': 'esperar',
                                              'parametros': {'segundos': s}})
            await asyncio.sleep(0.1)
    # al salir del bloque corrió el apagado

    volcados = list(tmp_path.glob('estado_*.json'))
    assert len(volcados) == 1
    tareas = {t['id']: t for t in json.loads(volcados[0].read_text())['tareas']}
    estados = sorted(t['estado'] for t in tareas.values())
    assert estados == ['cancelada', 'cancelada', 'completada']
    assert any('apagado' in (t['error'] or '') for t in tareas.values())
