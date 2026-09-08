from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.auth import create_user
from app.config import AppConfig
from app.db import AuditLogRecord, EventRecord
from app.device.ser2sock import ReadOnlyAdapterError
from app.models import KeypadCommand
from app.runtime import AlarmRuntime


def _config(**overrides) -> AppConfig:
    values = {
        "adapter": "fake",
        "ser2sock_host": "127.0.0.1",
        "ser2sock_port": 1,
        "read_only": False,
        "allow_commands": True,
        "auth_required": False,
        "database_url": "sqlite:///:memory:",
        "session_secret": "test-secret",
        "command_cooldown_seconds": 0,
        "reconnect_initial_delay_seconds": 0.02,
        "reconnect_max_delay_seconds": 0.05,
    }
    values.update(overrides)
    return AppConfig(**values)


@pytest.mark.asyncio
async def test_commands_rejected_when_allow_commands_is_false() -> None:
    runtime = AlarmRuntime(_config(allow_commands=False))
    await runtime.start()
    try:
        with pytest.raises(HTTPException) as exc:
            await runtime.send_keys(KeypadCommand(keys="1234"), user=None)
        assert exc.value.status_code == 409
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_read_only_wins_over_allow_commands() -> None:
    runtime = AlarmRuntime(_config(read_only=True, allow_commands=True))
    await runtime.start()
    try:
        with pytest.raises(ReadOnlyAdapterError):
            await runtime.send_keys(KeypadCommand(keys="1234", dangerous_confirmed=True), user=None)
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_dangerous_commands_require_confirmation() -> None:
    runtime = AlarmRuntime(_config())
    await runtime.start()
    try:
        with pytest.raises(HTTPException) as exc:
            await runtime.send_keys(KeypadCommand(keys="AWAY"), user=None)
        assert exc.value.status_code == 409
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_submitted_alarm_codes_are_not_logged_or_persisted() -> None:
    runtime = AlarmRuntime(_config())
    await runtime.start()
    try:
        await runtime.send_keys(KeypadCommand(keys="1234", dangerous_confirmed=True), user=None)
        assert "1234" not in runtime.state.last_message
        assert "1234" not in str(runtime.state.last_command)

        with runtime.database.session_factory() as session:
            event_blob = "\n".join(
                f"{record.message} {record.data_json}" for record in session.query(EventRecord).all()
            )
            audit_blob = "\n".join(
                f"{record.action} {record.details_json}" for record in session.query(AuditLogRecord).all()
            )

        assert "1234" not in event_blob
        assert "1234" not in audit_blob
        assert "<redacted-command>" in event_blob
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_ser2sock_command_mode_writes_only_when_explicitly_enabled() -> None:
    received = bytearray()
    connected = asyncio.Event()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connected.set()
        writer.write(b'[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(16), timeout=1)
        received.extend(data)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    runtime = AlarmRuntime(
        _config(
            adapter="ser2sock",
            ser2sock_port=port,
            read_only=False,
            allow_commands=True,
            auth_required=True,
        )
    )

    try:
        await runtime.start()
        with runtime.database.session_factory() as session:
            user = create_user(session, "operator", "secret", "operator")
        await asyncio.wait_for(connected.wait(), timeout=1)
        await runtime.send_keys(KeypadCommand(keys="1234", dangerous_confirmed=True), user=user)
        await asyncio.sleep(0.05)
        assert received == b"1234"
    finally:
        await runtime.stop()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_single_keystrokes_bypass_cooldown_for_pin_entry() -> None:
    runtime = AlarmRuntime(
        _config(
            adapter="fake",
            read_only=False,
            allow_commands=True,
            auth_required=False,
            command_cooldown_seconds=10.0,
        )
    )
    try:
        await runtime.start()
        # Rapid keypad entry (e.g. typing a PIN + function digit) must not be throttled by 10s cooldown
        for digit in ["1", "2", "3", "4", "2"]:
            state = await runtime.send_keys(KeypadCommand(keys=digit, dangerous_confirmed=False), user=None)
            assert state is not None
        assert runtime.state.armed is True
    finally:
        await runtime.stop()
