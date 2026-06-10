from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from ..models import PanelEvent


EventHandler = Callable[[PanelEvent], Awaitable[None]]


class AlarmDecoderAdapter(Protocol):
    read_only: bool

    async def open(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def send_keys(self, keys: str) -> None:
        ...

    async def run(self) -> None:
        ...
