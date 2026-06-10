from __future__ import annotations

import asyncio
from collections import deque

from .models import RawAlarmMessage


class RawMessageBuffer:
    def __init__(self, maxlen: int = 200) -> None:
        self._messages: deque[RawAlarmMessage] = deque(maxlen=maxlen)
        self._lock = asyncio.Lock()

    async def append(self, message: RawAlarmMessage) -> RawAlarmMessage:
        async with self._lock:
            self._messages.appendleft(message)
        return message

    async def list(self, limit: int = 100) -> list[RawAlarmMessage]:
        async with self._lock:
            return list(self._messages)[:limit]
