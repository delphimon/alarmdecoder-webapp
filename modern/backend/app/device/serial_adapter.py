from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Callable

from ..config import AppConfig
from ..models import ConnectionDiagnostics, PanelEvent
from ..parser import parse_alarmdecoder_line
from .base import EventHandler
from .ser2sock import ReadOnlyAdapterError


SerialFactory = Callable[[str, int], Any]


class SerialAlarmDecoderDevice:
    """Line-oriented AlarmDecoder serial adapter for AD2USB/AD2PI/AD2SERIAL.

    The adapter mirrors the ser2sock safety model: it defaults to read-only for
    real hardware and only writes when both READ_ONLY=false and
    ALLOW_COMMANDS=true are explicitly configured.
    """

    def __init__(self, config: AppConfig, emit: EventHandler, serial_factory: SerialFactory | None = None) -> None:
        self._config = config
        self._emit = emit
        self._serial_factory = serial_factory or _open_pyserial
        self._running = False
        self._serial: Any | None = None
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
        await self._close_serial()
        await self._emit_status("disconnected", "serial adapter stopped")

    async def run(self) -> None:
        delay = self._config.reconnect_initial_delay_seconds

        while self._running:
            await self._emit_status(
                "connecting" if self.reconnect_attempts == 0 else "reconnecting",
                f"Opening AlarmDecoder serial device {self._config.serial_path}",
            )
            try:
                self._serial = await asyncio.to_thread(
                    self._serial_factory,
                    self._config.serial_path,
                    self._config.serial_baudrate,
                )
                self.reconnect_attempts = 0
                delay = self._config.reconnect_initial_delay_seconds
                self.last_connected_at = datetime.now(timezone.utc)
                await self._emit_status("connected", "serial AlarmDecoder connected")
                await self._emit(PanelEvent(type="device_open", message="serial AlarmDecoder stream connected"))
                await self._read_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                await self._emit_status("error", f"serial adapter error: {exc}")
            finally:
                await self._close_serial()
                if self._running:
                    self.last_disconnected_at = datetime.now(timezone.utc)
                    await self._emit(PanelEvent(type="device_close", message="serial AlarmDecoder stream disconnected"))
                    await self._emit_status("reconnecting", f"Reopening serial device in {delay:.1f}s")
                    self.reconnect_attempts += 1
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._config.reconnect_max_delay_seconds)

    async def send_keys(self, keys: str) -> None:
        if self.read_only:
            raise ReadOnlyAdapterError("Selected adapter is read-only; keypad commands are disabled.")
        if self._serial is None:
            raise RuntimeError("serial AlarmDecoder is not connected.")

        payload = keys.encode("ascii", errors="ignore") + b"\n"
        await asyncio.to_thread(self._serial.write, payload)
        if hasattr(self._serial, "flush"):
            await asyncio.to_thread(self._serial.flush)

    def diagnostics(self) -> ConnectionDiagnostics:
        return ConnectionDiagnostics(
            adapter=self._config.adapter,
            host=self._config.serial_path,
            port=self._config.serial_baudrate,
            read_only=self.read_only,
            status=self.status,
            connected=self.status == "connected",
            reconnect_attempts=self.reconnect_attempts,
            last_connected_at=self.last_connected_at,
            last_disconnected_at=self.last_disconnected_at,
            last_error=self.last_error,
        )

    async def _read_loop(self) -> None:
        if self._serial is None:
            return

        while self._running:
            line = await asyncio.to_thread(self._serial.readline)
            if not line:
                await asyncio.sleep(0.05)
                continue
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
                    "adapter": self._config.adapter,
                    "path": self._config.serial_path,
                    "baudrate": self._config.serial_baudrate,
                    "read_only": self.read_only,
                    "allow_commands": self._config.allow_commands,
                    "reconnect_attempts": self.reconnect_attempts,
                    "last_error": self.last_error,
                },
            )
        )

    async def _close_serial(self) -> None:
        if self._serial is None:
            return
        serial_obj = self._serial
        self._serial = None
        if hasattr(serial_obj, "close"):
            with suppress(Exception):
                await asyncio.to_thread(serial_obj.close)


def _open_pyserial(path: str, baudrate: int) -> Any:
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pyserial is required for ALARMDECODER_ADAPTER=serial") from exc

    return serial.serial_for_url(path, baudrate=baudrate, timeout=0.25, write_timeout=1.0)
