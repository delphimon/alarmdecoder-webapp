from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from .db import UserRecord
from .device.ser2sock import ReadOnlyAdapterError
from .models import KeypadCommand, PanelEvent, PanelState
from .security import command_metadata, redact_command


DANGEROUS_COMMANDS = {"AWAY", "STAY", "DISARM", "CODE_OFF", "F1", "F2", "F3", "F4", "FIRE", "PANIC"}


class CommandTranslator:
    """Translates high-level panel commands to AlarmDecoder keystroke sequences."""

    HONEYWELL_SEQUENCES = {
        "AWAY": "{pin}2",
        "ARM_AWAY": "{pin}2",
        "STAY": "{pin}3",
        "ARM_STAY": "{pin}3",
        "DISARM": "{pin}1",
        "CODE_OFF": "{pin}1",
        "CHIME": "{pin}9",
        "CHIME_TOGGLE": "{pin}9",
    }

    DSC_SEQUENCES = {
        "AWAY": "{pin}",
        "ARM_AWAY": "{pin}",
        "STAY": "{pin}*",
        "ARM_STAY": "{pin}*",
        "DISARM": "{pin}",
        "CODE_OFF": "{pin}",
    }

    FUNCTION_KEYS = {
        "F1": "\x01\x01\x01",
        "FIRE": "\x01\x01\x01",
        "F2": "\x02\x02\x02",
        "POLICE": "\x02\x02\x02",
        "F3": "\x03\x03\x03",
        "AUX": "\x03\x03\x03",
        "F4": "\x04\x04\x04",
        "PANIC": "\x04\x04\x04",
    }

    def translate(self, command: str, pin: str | None, panel_type: str, is_fake_adapter: bool = False) -> str:
        upper = command.strip().upper()
        if is_fake_adapter:
            return command

        if upper in self.FUNCTION_KEYS:
            return self.FUNCTION_KEYS[upper]

        sequences = self.DSC_SEQUENCES if panel_type.upper() == "DSC" else self.HONEYWELL_SEQUENCES
        if upper in sequences:
            if not pin:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Panel PIN not configured in settings. Set your panel PIN before sending arm/disarm commands.",
                )
            return sequences[upper].format(pin=pin)

        return command


class CommandService:
    def __init__(self, runtime: object) -> None:
        self.runtime = runtime
        self._last_command_at: datetime | None = None
        self.translator = CommandTranslator()

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

        auth_required = config.auth_required or runtime.database.users_exist()
        if auth_required and user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if user is not None and user.role not in {"operator", "admin"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator role required.")

        raw_keys = command.keys.strip()
        is_single_key = len(raw_keys) == 1 and (raw_keys.isdigit() or raw_keys in {"*", "#"})

        normalized = raw_keys.upper()
        if normalized in DANGEROUS_COMMANDS and not command.dangerous_confirmed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Command requires explicit confirmation.")

        now = datetime.now(timezone.utc)
        if not is_single_key:
            if self._last_command_at is not None:
                elapsed = (now - self._last_command_at).total_seconds()
                if elapsed < config.command_cooldown_seconds:
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Command cooldown active.")
            self._last_command_at = now

        # Translate high-level commands using configured panel PIN if needed
        pin = None
        pin_token = runtime.database.get_setting("panel_pin")
        if pin_token:
            try:
                from .crypto import decrypt_value
                pin = decrypt_value(pin_token, config.session_secret)
            except Exception:
                pass

        keys_to_send = self.translator.translate(
            command.keys,
            pin=pin,
            panel_type=config.panel_type,
            is_fake_adapter=config.adapter == "fake",
        )

        await adapter.send_keys(keys_to_send)
        await runtime.audit(
            "anonymous" if user is None else user.username,
            "command_sent",
            command_metadata(keys_to_send),
        )
        await runtime.handle_event(
            PanelEvent(
                type="command_sent",
                message="Keypad command submitted",
                data={"keys": redact_command(keys_to_send), **command_metadata(keys_to_send)},
            )
        )
        return runtime.state

