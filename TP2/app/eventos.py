"""Difusión de cambios de estado a los clientes del WebSocket /eventos (bonus).

Cada cliente conectado tiene su propia asyncio.Queue. Publicar es poner el
evento en todas las colas con put_nowait: nunca espera, así un cliente lento
no frena al resto del sistema. Si la cola de un cliente se llena (no está
leyendo), se le descarta el evento: preferimos perder notificaciones de un
cliente lento antes que acumular memoria sin límite.
"""
import asyncio
import logging
import time

log = logging.getLogger(__name__)


class Difusor:
    def __init__(self, tam_cola: int = 1000):
        self._suscriptores: set[asyncio.Queue] = set()
        self._tam_cola = tam_cola

    def suscribir(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._tam_cola)
        self._suscriptores.add(q)
        return q

    def desuscribir(self, q: asyncio.Queue) -> None:
        self._suscriptores.discard(q)

    @property
    def cantidad(self) -> int:
        return len(self._suscriptores)

    def publicar(self, evento: dict) -> None:
        evento = {'ts': time.time(), **evento}
        for q in self._suscriptores:
            try:
                q.put_nowait(evento)
            except asyncio.QueueFull:
                log.warning('suscriptor lento: se descarta un evento')
