from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import time

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .config import AppConfig
from .auth import create_user
from .commands import CommandService
from .db import Database
from .device.fake import FakeAlarmDecoderAdapter, cancel_task
from .device.ser2sock import ReadOnlyAdapterError, Ser2SockAlarmDecoderDevice
from .device.serial_adapter import SerialAlarmDecoderDevice
from .event_log import InMemoryEventLog
from .models import ConnectionDiagnostics, PanelEvent, PanelState, RawAlarmMessage, WebSocketMessage
from .notifications import NotificationService
from .raw_messages import RawMessageBuffer
from .state import initial_panel_state, reduce_panel_state


class AlarmRuntime:
    def __init__(self, config: AppConfig | None = None) -> None:
        self._custom_config = config is not None
        self.config = config or AppConfig.from_env()
        self.database = Database(self.config)
        panel_type = self.config.panel_type if self.config.panel_type in {"ADEMCO", "DSC"} else "ADEMCO"
        self.state = initial_panel_state()
        self.state.panel_type = panel_type
        self.events = InMemoryEventLog()
        self.raw_messages = RawMessageBuffer()
        self.adapter = self._build_adapter()
        self.command_service = CommandService(self)
        self.notifications = NotificationService()
        self._zone_last_seen: dict[int, float] = {}
        self._adapter_task: asyncio.Task | None = None
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    def apply_settings_from_db(self) -> None:
        """Override config and state with any settings stored in the database."""
        try:
            db_settings = {s.key: s.value for s in self.database.list_settings()}
        except Exception:
            return

        if not db_settings:
            return

        updates: dict[str, object] = {}
        if "adapter" in db_settings and db_settings["adapter"]:
            updates["adapter"] = db_settings["adapter"]
        if "panel_type" in db_settings and db_settings["panel_type"]:
            pt = db_settings["panel_type"]
            updates["panel_type"] = pt
            self.state.panel_type = pt if pt in {"ADEMCO", "DSC"} else "ADEMCO"
        if "ser2sock_host" in db_settings and db_settings["ser2sock_host"]:
            updates["ser2sock_host"] = db_settings["ser2sock_host"].strip()
        if "ser2sock_port" in db_settings and db_settings["ser2sock_port"]:
            try:
                updates["ser2sock_port"] = int(db_settings["ser2sock_port"])
            except ValueError:
                pass
        if "ser2sock_tls" in db_settings:
            updates["ser2sock_tls"] = str(db_settings["ser2sock_tls"]).lower() in {"true", "1", "yes"}
        if "serial_path" in db_settings and db_settings["serial_path"]:
            updates["serial_path"] = db_settings["serial_path"].strip()
        if "serial_baudrate" in db_settings and db_settings["serial_baudrate"]:
            try:
                updates["serial_baudrate"] = int(db_settings["serial_baudrate"])
            except ValueError:
                pass
        if "raw_retention_days" in db_settings:
            try:
                updates["raw_retention_days"] = int(db_settings["raw_retention_days"])
            except ValueError:
                pass
        if "event_retention_days" in db_settings:
            try:
                updates["event_retention_days"] = int(db_settings["event_retention_days"])
            except ValueError:
                pass

        if updates:
            self.config = replace(self.config, **updates)

    async def reload_adapter(self) -> None:
        """Safely close existing adapter, rebuild, and start with current config."""
        if hasattr(self, "adapter") and self.adapter is not None:
            try:
                await self.adapter.close()
            except Exception:
                pass
        if self._adapter_task is not None:
            await cancel_task(self._adapter_task)
            self._adapter_task = None

        self.adapter = self._build_adapter()
        await self.adapter.open()
        self._adapter_task = asyncio.create_task(self.adapter.run())
        await self.broadcast(WebSocketMessage(type="snapshot", state=self.state))

    async def start(self) -> None:
        self.database.init()
        self._bootstrap_admin()
        self.database.prune_retention()
        if not self._custom_config:
            self.apply_settings_from_db()
            self.reload_notifications()
            self.adapter = self._build_adapter()
        await self.adapter.open()
        self._adapter_task = asyncio.create_task(self.adapter.run())

    async def stop(self) -> None:
        await self.adapter.close()
        await cancel_task(self._adapter_task)


    async def send_keys(self, command, user=None) -> PanelState:
        return await self.command_service.submit(command, user)

    async def snapshot(self) -> dict:
        return {
            "state": self.state,
            "events": await self.events.list(),
            "raw_messages": await self.raw_messages.list(),
        }

    async def connection_diagnostics(self) -> ConnectionDiagnostics:
        if hasattr(self.adapter, "diagnostics"):
            return self.adapter.diagnostics()

        return ConnectionDiagnostics(
            adapter=self.config.adapter,
            read_only=self.config.read_only,
            status=self.state.connection_status,
            connected=self.state.connected,
        )

    def _persist_event(self, event: PanelEvent) -> None:
        if event.type == "raw_message":
            raw_message = RawAlarmMessage(
                timestamp=event.timestamp,
                raw=str(event.data.get("raw", event.message)),
            )
            self.database.append_raw_message(raw_message)
        self.database.append_event(event)
        if event.type in {"zone_fault", "zone_restore"} and "zone" in event.data:
            self.database.ensure_zone(int(event.data["zone"]))

    async def handle_event(self, event: PanelEvent) -> None:
        restored_events: list[PanelEvent] = []
        now = time.monotonic()

        async with self._lock:
            prev_faulted = list(self.state.faulted_zones)

            if event.type == "zone_fault" and "zone" in event.data:
                try:
                    z_num = int(event.data["zone"])
                    self._zone_last_seen[z_num] = now
                except (ValueError, TypeError):
                    pass

            self.state = reduce_panel_state(self.state, event)

            # Zone timeout expiration:
            # When multiple zones fault and one closes while others remain open, the panel
            # stops including the closed zone in its scrolling fault display.
            if self.state.faulted_zones and event.type in {"panel_display", "panel_message", "zone_fault"}:
                active_zones: list[int] = []
                for z in self.state.faulted_zones:
                    last_seen = self._zone_last_seen.get(z, now)
                    if now - last_seen > 12.0:
                        restored_events.append(
                            PanelEvent(
                                type="zone_restore",
                                message=f"Zone {z} restored",
                                data={"zone": z, "text": "Zone fault cleared"},
                            )
                        )
                        self._zone_last_seen.pop(z, None)
                    else:
                        active_zones.append(z)
                self.state.faulted_zones = active_zones
                if not self.state.faulted_zones and not self.state.armed:
                    self.state.ready = True

            # If zones were cleared by panel transition to ready (or explicit clear), synthesize zone_restore
            if event.type != "zone_restore":
                curr_faulted = set(self.state.faulted_zones)
                for rz in prev_faulted:
                    if rz not in curr_faulted and not any(r.data.get("zone") == rz for r in restored_events):
                        restored_events.append(
                            PanelEvent(
                                type="zone_restore",
                                message=f"Zone {rz} restored",
                                data={"zone": rz, "text": self.state.last_message},
                            )
                        )
                        self._zone_last_seen.pop(rz, None)

            if event.type == "raw_message":
                raw_message = RawAlarmMessage(
                    timestamp=event.timestamp,
                    raw=str(event.data.get("raw", event.message)),
                )
                await self.raw_messages.append(raw_message)
            await self.events.append(event)

            for rev in restored_events:
                await self.events.append(rev)

        # Broadcast immediately so WebSocket clients receive updates with zero delay
        await self.broadcast(WebSocketMessage(type="event", state=self.state, event=event))
        await self.notifications.handle_event(event)
        await asyncio.to_thread(self._persist_event, event)

        for rev in restored_events:
            await self.broadcast(WebSocketMessage(type="event", state=self.state, event=rev))
            await self.notifications.handle_event(rev)
            await asyncio.to_thread(self._persist_event, rev)



    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        snapshot = WebSocketMessage(
            type="snapshot",
            state=self.state,
            events=await self.events.list(),
            raw_messages=await self.raw_messages.list(),
        )
        await websocket.send_json(snapshot.model_dump(mode="json"))

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, message: WebSocketMessage) -> None:
        if not self._clients:
            return

        payload = message.model_dump(mode="json")
        stale: list[WebSocket] = []
        for websocket in list(self._clients):
            if websocket.application_state != WebSocketState.CONNECTED:
                stale.append(websocket)
                continue

            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)

        for websocket in stale:
            self.disconnect(websocket)

    def _build_adapter(self):
        if self.config.adapter == "fake":
            return FakeAlarmDecoderAdapter(self.handle_event)
        if self.config.adapter == "ser2sock":
            return Ser2SockAlarmDecoderDevice(self.config, self.handle_event)
        if self.config.adapter in {"serial", "ad2usb", "ad2pi", "ad2serial"}:
            return SerialAlarmDecoderDevice(self.config, self.handle_event)
        raise ValueError(f"Unsupported ALARMDECODER_ADAPTER: {self.config.adapter}")

    async def audit(self, actor: str, action: str, details: dict[str, object] | None = None) -> None:
        self.database.audit(actor, action, details)

    def _bootstrap_admin(self) -> None:
        if not self.config.bootstrap_admin_username or not self.config.bootstrap_admin_password:
            return
        with self.database.session_factory() as session:
            try:
                create_user(
                    session,
                    self.config.bootstrap_admin_username,
                    self.config.bootstrap_admin_password,
                    "admin",
                )
                self.database.audit(self.config.bootstrap_admin_username, "bootstrap_admin_created", {"role": "admin"})
            except ValueError:
                return

    def reload_notifications(self) -> None:
        self.notifications.configure_from_records(self.database.list_notifications())
