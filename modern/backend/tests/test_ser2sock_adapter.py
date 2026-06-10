from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.runtime import AlarmRuntime
from app.main import app
import app.main as main_module


async def _unused_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.close()
    await writer.wait_closed()


async def _start_server(
    handler: Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]],
) -> tuple[asyncio.AbstractServer, int]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    socket = server.sockets[0]
    return server, socket.getsockname()[1]


def _ser2sock_config(port: int) -> AppConfig:
    return AppConfig(
        adapter="ser2sock",
        ser2sock_host="127.0.0.1",
        ser2sock_port=port,
        read_only=True,
        reconnect_initial_delay_seconds=0.02,
        reconnect_max_delay_seconds=0.05,
    )


@pytest.mark.asyncio
async def test_ser2sock_read_only_adapter_sends_zero_bytes() -> None:
    received = bytearray()
    got_connection = asyncio.Event()
    got_raw_message = asyncio.Event()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        got_connection.set()
        writer.write(b'[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "\n')
        await writer.drain()
        try:
            data = await asyncio.wait_for(reader.read(16), timeout=0.15)
            received.extend(data)
        except TimeoutError:
            pass
        writer.close()
        await writer.wait_closed()

    server, port = await _start_server(handler)
    runtime = AlarmRuntime(_ser2sock_config(port))
    original_handle_event = runtime.handle_event

    async def handle_event(event):
        await original_handle_event(event)
        if event.type == "raw_message":
            got_raw_message.set()

    runtime.adapter._emit = handle_event

    try:
        await runtime.start()
        await asyncio.wait_for(got_connection.wait(), timeout=1)
        await asyncio.wait_for(got_raw_message.wait(), timeout=1)
        await asyncio.sleep(0.2)
        assert received == b""
        raw_messages = await runtime.raw_messages.list()
        assert raw_messages
        assert "DISARMED" in raw_messages[0].raw
    finally:
        await runtime.stop()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_ser2sock_adapter_reconnects_after_disconnect() -> None:
    connections = 0
    second_connection = asyncio.Event()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        writer.write(b'[10000001000000003A--],000,[0000000000000000],"SYSTEM READY    TEST SERVER"\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        if connections >= 2:
            second_connection.set()

    server, port = await _start_server(handler)
    runtime = AlarmRuntime(_ser2sock_config(port))

    try:
        await runtime.start()
        await asyncio.wait_for(second_connection.wait(), timeout=2)
        diagnostics = await runtime.connection_diagnostics()
        assert diagnostics.reconnect_attempts >= 0
        assert connections >= 2
    finally:
        await runtime.stop()
        server.close()
        await server.wait_closed()


def test_keypad_command_endpoint_rejects_when_read_only() -> None:
    main_module.runtime = AlarmRuntime(_ser2sock_config(port=1))
    with TestClient(app) as client:
        response = client.post("/api/keypad/command", json={"keys": "AWAY"})

    assert response.status_code == 409
    assert "read-only" in response.json()["detail"]
