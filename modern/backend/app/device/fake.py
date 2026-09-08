from __future__ import annotations

import asyncio
from contextlib import suppress

from ..models import PanelEvent
from ..security import redact_command
from .base import EventHandler


class FakeAlarmDecoderAdapter:
    """Deterministic in-memory adapter for development before serial support exists."""

    def __init__(self, emit: EventHandler) -> None:
        self._emit = emit
        self._running = False
        self._chime = True
        self._scenario_step = 0
        self.read_only = False
        self._key_buffer = ""

    async def open(self) -> None:
        self._running = True
        await self._emit(PanelEvent(type="connection_status", message="Fake adapter connected", data={"status": "connected"}))
        await self._emit(PanelEvent(type="device_open", message="Fake AlarmDecoder connected"))
        await self._emit(
            PanelEvent(
                type="panel_message",
                message="SYSTEM READY",
                data={
                    "text": "SYSTEM READY    FAKE ADAPTER",
                    "ready": True,
                    "armed": False,
                    "chime": self._chime,
                    "beeps": 1,
                },
            )
        )

    async def close(self) -> None:
        self._running = False
        await self._emit(PanelEvent(type="connection_status", message="Fake adapter disconnected", data={"status": "disconnected"}))
        await self._emit(PanelEvent(type="device_close", message="Fake AlarmDecoder disconnected"))

    async def run(self) -> None:
        while self._running:
            await asyncio.sleep(10)
            await self._emit_next_scenario_event()

    async def send_keys(self, keys: str) -> None:
        normalized = keys.strip().upper()
        if normalized in {"AWAY", "ARM_AWAY"}:
            await self._emit(PanelEvent(type="arm", message="System armed away", data={"stay": False}))
        elif normalized in {"STAY", "ARM_STAY"}:
            await self._emit(PanelEvent(type="arm", message="System armed stay", data={"stay": True}))
        elif normalized in {"DISARM", "CODE_OFF"}:
            await self._emit(PanelEvent(type="disarm", message="System disarmed"))
        elif normalized == "CHIME":
            self._chime = not self._chime
            await self._emit(
                PanelEvent(
                    type="chime_changed",
                    message=f"Chime {'enabled' if self._chime else 'disabled'}",
                    data={"enabled": self._chime},
                )
            )
        elif normalized in {"PANIC", "F2"}:
            await self._emit(PanelEvent(type="panic", message="Panic command sent"))
        elif normalized in {"FIRE", "F1"}:
            await self._emit(PanelEvent(type="fire", message="Fire alarm simulated", data={"active": True}))
        elif normalized == "FAULT":
            await self._emit(PanelEvent(type="zone_fault", message="Zone 1 faulted", data={"zone": 1, "name": "Front Door"}))
        elif normalized == "RESTORE":
            await self._emit(PanelEvent(type="zone_restore", message="Zone 1 restored", data={"zone": 1, "name": "Front Door"}))
        else:
            self._key_buffer = (self._key_buffer + normalized)[-10:]
            if len(self._key_buffer) >= 5 and self._key_buffer[:-1].isdigit():
                action_key = self._key_buffer[-1]
                self._key_buffer = ""
                if action_key == "2":
                    await self._emit(PanelEvent(type="arm", message="System armed away", data={"stay": False}))
                    return
                elif action_key == "3":
                    await self._emit(PanelEvent(type="arm", message="System armed stay", data={"stay": True}))
                    return
                elif action_key == "1":
                    await self._emit(PanelEvent(type="disarm", message="System disarmed"))
                    return
                elif action_key == "9":
                    self._chime = not self._chime
                    await self._emit(
                        PanelEvent(
                            type="chime_changed",
                            message=f"Chime {'enabled' if self._chime else 'disabled'}",
                            data={"enabled": self._chime},
                        )
                    )
                    return

            await self._emit(
                PanelEvent(
                    type="panel_message",
                    message="Keys accepted",
                    data={
                        "text": f"KEYS ACCEPTED   {redact_command(normalized)}"[:32],
                        "ready": True,
                        "chime": self._chime,
                        "beeps": 1,
                    },
                )
            )

    async def _emit_next_scenario_event(self) -> None:
        scenario = self._scenario_step % 6
        self._scenario_step += 1

        if scenario == 0:
            await self._emit(PanelEvent(type="zone_fault", message="Front Door faulted", data={"zone": 1, "name": "Front Door"}))
        elif scenario == 1:
            await self._emit(PanelEvent(type="zone_restore", message="Front Door restored", data={"zone": 1, "name": "Front Door"}))
        elif scenario == 2:
            await self._emit(PanelEvent(type="power_changed", message="Panel switched to battery", data={"power": "BATTERY"}))
        elif scenario == 3:
            await self._emit(PanelEvent(type="power_changed", message="Panel AC power restored", data={"power": "AC"}))
        elif scenario == 4:
            await self._emit(
                PanelEvent(
                    type="panel_message",
                    message="Periodic ready update",
                    data={
                        "text": "SYSTEM READY    CHIME ON",
                        "ready": True,
                        "armed": False,
                        "chime": self._chime,
                        "beeps": 0,
                    },
                )
            )
        else:
            await self._emit(PanelEvent(type="lrr", message="LRR sample event", data={"partition": 1, "code": "602"}))


async def cancel_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
