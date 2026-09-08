from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


PanelType = Literal["ADEMCO", "DSC"]
ConnectionStatus = Literal["idle", "connecting", "connected", "disconnected", "reconnecting", "error"]
ArmMode = Literal["disarmed", "away", "stay", "unknown"]
PowerStatus = Literal["AC", "BATTERY", "UNKNOWN"]
DomainEventType = Literal[
    "raw_message",
    "unknown_message",
    "connection_status",
    "device_open",
    "device_close",
    "panel_display",
    "panel_ready",
    "panel_armed",
    "panel_disarmed",
    "alarm_active",
    "fire_alarm",
    "panic_alarm",
    "chime_changed",
    "power_changed",
    "low_battery",
    "trouble",
    "bypass",
    "boot",
    "config_received",
    "relay_changed",
    "zone_fault",
    "zone_restore",
    "command_sent",
    "arm",
    "disarm",
    "fire",
    "panic",
    "panel_message",
    "alarm",
    "lrr",
    "rfx",
    "exp",
    "aui",
]


class PanelState(BaseModel):
    connected: bool = False
    connection_status: ConnectionStatus = "idle"
    panel_type: PanelType = "ADEMCO"
    display_line1: str = "ALARMDECODER"
    display_line2: str = "CONNECTING..."
    armed: bool = False
    armed_stay: bool = False
    armed_mode: ArmMode = "disarmed"
    ready: bool = True
    chime: bool = True
    alarming: bool = False
    bypassed: bool = False
    fire_detected: bool = False
    battery_trouble: bool = False
    battery_low: bool = False
    check_zones: bool = False
    trouble: bool = False
    trouble_text: str | None = None
    panic: bool = False
    power: PowerStatus = "AC"
    relay_status: dict[str, bool] = Field(default_factory=dict)
    beeps: int = Field(default=0, ge=0, le=7)
    cursor_location: int | None = None
    faulted_zones: list[int] = Field(default_factory=list)

    last_message: str = "ALARMDECODER    CONNECTING..."
    last_raw_message: str | None = None
    last_command: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PanelEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: DomainEventType | str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class KeypadCommand(BaseModel):
    keys: str = Field(min_length=1, max_length=64)
    dangerous_confirmed: bool = False


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    id: int | None = None
    username: str
    role: Literal["admin", "operator", "viewer"]
    disabled: bool = False


class AuthStatus(BaseModel):
    authenticated: bool
    auth_required: bool
    csrf_token: str | None = None
    user: UserPublic | None = None


class LoginResponse(BaseModel):
    user: UserPublic
    csrf_token: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["admin", "operator", "viewer"] = "viewer"


class UpdateUserRequest(BaseModel):
    role: Literal["admin", "operator", "viewer"] | None = None
    disabled: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class SettingItem(BaseModel):
    key: str
    value: str


class SettingsUpdate(BaseModel):
    settings: list[SettingItem]


class ZoneInfo(BaseModel):
    id: int
    name: str = ""
    enabled: bool = True


class ZonesUpdate(BaseModel):
    zones: list[ZoneInfo]


class NotificationConfig(BaseModel):
    id: int | None = None
    provider: Literal["webhook", "smtp", "test"] = "webhook"
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class NotificationTestRequest(BaseModel):
    provider: Literal["webhook", "smtp", "test"] = "test"
    config: dict[str, Any] = Field(default_factory=dict)


class SetupStatus(BaseModel):
    setup_required: bool
    users_exist: bool
    adapter: str
    panel_type: PanelType


class SetupCompleteRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    panel_type: PanelType = "ADEMCO"
    adapter: str = "fake"
    ser2sock_host: str | None = None
    ser2sock_port: int | None = None
    serial_path: str | None = None
    serial_baudrate: int | None = None


class CustomButtonPublic(BaseModel):
    id: int
    label: str
    dangerous: bool = False
    enabled: bool = True
    sort_order: int = 0


class CustomButtonCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=1, max_length=128)
    dangerous: bool = False
    enabled: bool = True
    sort_order: int = 0


class CustomButtonUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    command: str | None = Field(default=None, min_length=1, max_length=128)
    dangerous: bool | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class CustomButtonSendRequest(BaseModel):
    dangerous_confirmed: bool = False


class ApiTokenPublic(BaseModel):
    id: int
    name: str
    username: str
    token_prefix: str
    role: Literal["admin", "operator", "viewer"]
    disabled: bool = False
    created_at: datetime
    last_used_at: datetime | None = None


class ApiTokenCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "operator", "viewer"] = "viewer"


class ApiTokenCreateResponse(BaseModel):
    token: str
    record: ApiTokenPublic


class SettingsImportRequest(BaseModel):
    data: dict[str, Any]
    dry_run: bool = True


class AuditEntry(BaseModel):
    id: int
    timestamp: datetime
    actor: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)


class RawAlarmMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: str


class ConnectionDiagnostics(BaseModel):
    adapter: str
    host: str | None = None
    port: int | None = None
    read_only: bool
    status: ConnectionStatus
    connected: bool
    reconnect_attempts: int = 0
    last_connected_at: datetime | None = None
    last_disconnected_at: datetime | None = None
    last_error: str | None = None


class StateEnvelope(BaseModel):
    state: PanelState
    events: list[PanelEvent]
    raw_messages: list[RawAlarmMessage] = Field(default_factory=list)


class WebSocketMessage(BaseModel):
    type: Literal["snapshot", "state", "event"]
    state: PanelState | None = None
    event: PanelEvent | None = None
    events: list[PanelEvent] | None = None
    raw_messages: list[RawAlarmMessage] | None = None
