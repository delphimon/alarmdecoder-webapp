from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from .db import UserRecord
from .device.ser2sock import ReadOnlyAdapterError
from .models import KeypadCommand, PanelEvent, PanelState
from .security import command_metadata, redact_command


DANGEROUS_COMMANDS = {"AWAY", "STAY", "DISARM", "CODE_OFF", "F1", "F2", "F3", "F4", "FIRE", "PANIC"}


class CommandService:
    def __init__(self, runtime: object) -> None:
        self.runtime = runtime
        self._last_command_at: datetime | None = None

    async def submit(self, command: KeypadCommand, user: UserRecord | None) -> PanelState:
        runtime = self.runtime
        config = runtime.config
        adapter = runtime.adapter

        if config.read_only or getattr(adapter, "read_only", False):
            await runtime.audit("anonymous" if user is None else user.username, "command_rejected_read_only", command_metadata(command.keys))
            raise ReadOnlyAdapterError("Selected adapter is read-only; keypad commands are disabled.")

        if not config.allow_commands:
            await runtime.audit("anonymous" if user is None else user.username, "command_rejected_disabled", command_metadata(command.keys))
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command mode is not enabled.")

        auth_required = config.auth_required or runtime.database.users_exist() or config.adapter != "fake"
        if auth_required and user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if user is not None and user.role not in {"operator", "admin"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator role required.")

        normalized = command.keys.strip().upper()
        if normalized in DANGEROUS_COMMANDS and not command.dangerous_confirmed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command requires explicit confirmation.")

        now = datetime.now(timezone.utc)
        if self._last_command_at is not None:
            elapsed = (now - self._last_command_at).total_seconds()
            if elapsed < config.command_cooldown_seconds:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Command cooldown active.")

        self._last_command_at = now
        await adapter.send_keys(command.keys)
        await runtime.audit(
            "anonymous" if user is None else user.username,
            "command_sent",
            command_metadata(command.keys),
        )
        await runtime.handle_event(
            PanelEvent(
                type="command_sent",
                message="Keypad command submitted",
                data={"keys": redact_command(command.keys), **command_metadata(command.keys)},
            )
        )
        return runtime.state
