from __future__ import annotations

import asyncio
from collections import deque

from .models import PanelEvent


class InMemoryEventLog:
    def __init__(self, maxlen: int = 200) -> None:
        self._events: deque[PanelEvent] = deque(maxlen=maxlen)
        self._lock = asyncio.Lock()

    async def append(self, event: PanelEvent) -> PanelEvent:
        async with self._lock:
            self._events.appendleft(event)
        return event

    async def list(self, limit: int = 50) -> list[PanelEvent]:
        async with self._lock:
            return list(self._events)[:limit]
