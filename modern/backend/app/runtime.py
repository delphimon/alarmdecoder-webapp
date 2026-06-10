from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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
from .state import reduce_panel_state


class AlarmRuntime:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.database = Database(self.config)
        panel_type = self.config.panel_type if self.config.panel_type in {"ADEMCO", "DSC"} else "ADEMCO"
        self.state = PanelState(panel_type=panel_type)
        self.events = InMemoryEventLog()
        self.raw_messages = RawMessageBuffer()
        self.adapter = self._build_adapter()
        self.command_service = CommandService(self)
        self.notifications = NotificationService()
        self._adapter_task: asyncio.Task | None = None
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.database.init()
        self._bootstrap_admin()
        self.database.prune_retention()
        self.reload_notifications()
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
            adapter="fake",
            read_only=self.config.read_only,
            status=self.state.connection_status,
            connected=self.state.connected,
        )

    async def handle_event(self, event: PanelEvent) -> None:
        async with self._lock:
            self.state = reduce_panel_state(self.state, event)
            if event.type == "raw_message":
                raw_message = RawAlarmMessage(
                    timestamp=event.timestamp,
                    raw=str(event.data.get("raw", event.message)),
                )
                await self.raw_messages.append(raw_message)
                self.database.append_raw_message(raw_message)
            await self.events.append(event)
            self.database.append_event(event)
            if event.type in {"zone_fault", "zone_restore"} and "zone" in event.data:
                self.database.ensure_zone(int(event.data["zone"]))

        await self.broadcast(WebSocketMessage(type="event", state=self.state, event=event))
        await self.notifications.handle_event(event)

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
