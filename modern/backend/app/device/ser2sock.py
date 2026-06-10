from __future__ import annotations

import asyncio
import ssl
from contextlib import suppress
from datetime import datetime, timezone

from ..config import AppConfig
from ..models import ConnectionDiagnostics, PanelEvent
from ..parser import parse_alarmdecoder_line
from .base import EventHandler


class ReadOnlyAdapterError(RuntimeError):
    pass


class Ser2SockAlarmDecoderDevice:
    """Read-only ser2sock TCP adapter.

    Safety invariant: this class never writes to the TCP stream. It only opens a
    connection and reads line-oriented AlarmDecoder output.
    """

    def __init__(self, config: AppConfig, emit: EventHandler) -> None:
        self._config = config
        self._emit = emit
        self._running = False
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.read_only = config.read_only or not config.allow_commands
        self.status = "idle"
        self.reconnect_attempts = 0
        self.last_connected_at: datetime | None = None
        self.last_disconnected_at: datetime | None = None
        self.last_error: str | None = None

    async def open(self) -> None:
        self._running = True

    async def close(self) -> None:
        self._running = False
        await self._close_writer()
        await self._emit_status("disconnected", "ser2sock adapter stopped")

    async def run(self) -> None:
        delay = self._config.reconnect_initial_delay_seconds

        while self._running:
            await self._emit_status(
                "connecting" if self.reconnect_attempts == 0 else "reconnecting",
                f"Connecting to ser2sock at {self._config.ser2sock_host}:{self._config.ser2sock_port}",
            )

            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self._config.ser2sock_host,
                    self._config.ser2sock_port,
                    ssl=ssl.create_default_context() if self._config.ser2sock_tls else None,
                )
                self.reconnect_attempts = 0
                delay = self._config.reconnect_initial_delay_seconds
                self.last_connected_at = datetime.now(timezone.utc)
                await self._emit_status("connected", "ser2sock connected")
                await self._emit(PanelEvent(type="device_open", message="ser2sock AlarmDecoder stream connected"))

                await self._read_loop()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                await self._emit_status("error", f"ser2sock error: {exc}")
            finally:
                await self._close_writer()
                if self._running:
                    self.last_disconnected_at = datetime.now(timezone.utc)
                    await self._emit(PanelEvent(type="device_close", message="ser2sock AlarmDecoder stream disconnected"))
                    await self._emit_status("reconnecting", f"Reconnecting in {delay:.1f}s")
                    self.reconnect_attempts += 1
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._config.reconnect_max_delay_seconds)

    async def send_keys(self, keys: str) -> None:
        if self.read_only:
            raise ReadOnlyAdapterError("Selected adapter is read-only; keypad commands are disabled.")
        if self._writer is None:
            raise RuntimeError("ser2sock is not connected.")

        self._writer.write(keys.encode("ascii", errors="ignore") + b"\n")
        await self._writer.drain()

    def diagnostics(self) -> ConnectionDiagnostics:
        return ConnectionDiagnostics(
            adapter="ser2sock",
            host=self._config.ser2sock_host,
            port=self._config.ser2sock_port,
            read_only=self.read_only,
            status=self.status,
            connected=self.status == "connected",
            reconnect_attempts=self.reconnect_attempts,
            last_connected_at=self.last_connected_at,
            last_disconnected_at=self.last_disconnected_at,
            last_error=self.last_error,
        )

    async def _read_loop(self) -> None:
        if self._reader is None:
            return

        while self._running:
            line = await self._reader.readline()
            if not line:
                return
            raw = line.decode("utf-8", errors="replace").strip("\r\n")
            for event in parse_alarmdecoder_line(raw):
                await self._emit(event)

    async def _emit_status(self, status: str, message: str) -> None:
        self.status = status
        await self._emit(
            PanelEvent(
                type="connection_status",
                message=message,
                data={
                    "status": status,
                    "adapter": "ser2sock",
                    "host": self._config.ser2sock_host,
                    "port": self._config.ser2sock_port,
                    "read_only": self.read_only,
                    "allow_commands": self._config.allow_commands,
                    "reconnect_attempts": self.reconnect_attempts,
                    "last_error": self.last_error,
                },
            )
        )

    async def _close_writer(self) -> None:
        if self._writer is None:
            return

        self._writer.close()
        with suppress(Exception):
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
