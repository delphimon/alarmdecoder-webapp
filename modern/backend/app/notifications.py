from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
import logging
from typing import Protocol
from urllib import request

from .db import NotificationSettingRecord
from .models import PanelEvent


NOTIFIABLE_EVENTS = {
    "alarm_active",
    "fire_alarm",
    "panic_alarm",
    "panel_armed",
    "panel_disarmed",
    "trouble",
    "connection_status",
}


class NotificationProvider(Protocol):
    async def send(self, event: PanelEvent) -> None:
        ...


@dataclass
class TestNotificationProvider:
    sent: list[PanelEvent]

    async def send(self, event: PanelEvent) -> None:
        self.sent.append(event)


@dataclass
class WebhookNotificationProvider:
    url: str
    event_types: set[str] | None = None

    async def send(self, event: PanelEvent) -> None:
        if self.event_types and event.type not in self.event_types:
            return
        import json

        payload = json.dumps(
            {
                "type": event.type,
                "message": event.message,
                "timestamp": event.timestamp.isoformat(),
            }
        ).encode()

        def post() -> None:
            req = request.Request(self.url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            request.urlopen(req, timeout=5).close()

        await asyncio.to_thread(post)


@dataclass
class SMTPNotificationProvider:
    host: str
    sender: str
    recipient: str

    async def send(self, event: PanelEvent) -> None:
        import smtplib

        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = self.recipient
        message["Subject"] = f"AlarmDecoder {event.type.replace('_', ' ')}"
        message.set_content(f"{event.timestamp.isoformat()}\n{event.message}\n")

        def deliver() -> None:
            with smtplib.SMTP(self.host, timeout=5) as smtp:
                smtp.send_message(message)

        await asyncio.to_thread(deliver)


class NotificationService:
    def __init__(self, providers: list[NotificationProvider] | None = None) -> None:
        self.providers = providers or []
        self.logger = logging.getLogger("alarmdecoder.notifications")

    def configure_from_records(self, records: list[NotificationSettingRecord]) -> None:
        import json

        providers: list[NotificationProvider] = []
        for record in records:
            if not record.enabled:
                continue
            try:
                config = json.loads(record.config_json)
            except json.JSONDecodeError:
                self.logger.warning("invalid notification config for provider %s", record.provider)
                continue
            if record.provider == "webhook":
                url = str(config.get("url", ""))
                if not url:
                    continue
                event_types = config.get("event_types")
                providers.append(
                    WebhookNotificationProvider(
                        url=url,
                        event_types=set(event_types) if isinstance(event_types, list) else None,
                    )
                )
        self.providers = providers

    async def handle_event(self, event: PanelEvent) -> None:
        if event.type not in NOTIFIABLE_EVENTS:
            return
        for provider in self.providers:
            try:
                await provider.send(event)
            except Exception as exc:
                self.logger.warning("notification delivery failed: %s", exc)
