from __future__ import annotations

import asyncio
from contextlib import suppress
from collections import deque

import pytest

from app.config import AppConfig
from app.device.ser2sock import ReadOnlyAdapterError
from app.device.serial_adapter import SerialAlarmDecoderDevice
from app.models import PanelEvent


class FakeSerial:
    def __init__(self, lines: list[bytes] | None = None) -> None:
        self.lines = deque(lines or [])
        self.writes: list[bytes] = []
        self.closed = False

    def readline(self) -> bytes:
        if self.lines:
            return self.lines.popleft()
        return b""

    def write(self, payload: bytes) -> int:
        self.writes.append(payload)
        return len(payload)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _config(read_only: bool = True, allow_commands: bool = False) -> AppConfig:
    return AppConfig(
        adapter="serial",
        ser2sock_host="127.0.0.1",
        ser2sock_port=10000,
        read_only=read_only,
        allow_commands=allow_commands,
        serial_path="loop://test",
        serial_baudrate=115200,
        reconnect_initial_delay_seconds=0.01,
        reconnect_max_delay_seconds=0.02,
    )


@pytest.mark.asyncio
async def test_serial_adapter_reads_lines_without_writing_in_read_only_mode() -> None:
    serial = FakeSerial(
        [b'[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "\n']
    )
    events: list[PanelEvent] = []
    got_raw = asyncio.Event()

    async def emit(event: PanelEvent) -> None:
        events.append(event)
        if event.type == "raw_message":
            got_raw.set()

    adapter = SerialAlarmDecoderDevice(_config(), emit, serial_factory=lambda _path, _baud: serial)

    await adapter.open()
    task = asyncio.create_task(adapter.run())
    try:
        await asyncio.wait_for(got_raw.wait(), timeout=1)
        with pytest.raises(ReadOnlyAdapterError):
            await adapter.send_keys("1234")
    finally:
        await adapter.close()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert serial.writes == []
    assert any(event.type == "panel_display" for event in events)


@pytest.mark.asyncio
async def test_serial_adapter_writes_only_when_command_mode_enabled() -> None:
    serial = FakeSerial()

    async def emit(_event: PanelEvent) -> None:
        return None

    adapter = SerialAlarmDecoderDevice(
        _config(read_only=False, allow_commands=True),
        emit,
        serial_factory=lambda _path, _baud: serial,
    )
    await adapter.open()
    task = asyncio.create_task(adapter.run())
    try:
        await asyncio.sleep(0.05)
        await adapter.send_keys("1234")
    finally:
        await adapter.close()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert serial.writes == [b"1234"]
