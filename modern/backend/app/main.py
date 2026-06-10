from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import json
from datetime import datetime, timezone
from secrets import token_urlsafe

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import (
    authenticate_user,
    auth_status,
    clear_session_cookie,
    create_access_token,
    create_user,
    get_user,
    hash_api_token,
    hash_password,
    optional_current_user,
    require_csrf,
    require_current_user,
    require_role,
    set_session_cookie,
    set_csrf_cookie,
    user_public,
    verify_password,
)
from .device.ser2sock import ReadOnlyAdapterError
from .db import ApiTokenRecord, AppSettingRecord, AuditLogRecord, CustomButtonRecord, EventRecord, NotificationSettingRecord, RawMessageRecord, UserRecord, ZoneRecord
from .logging_config import configure_logging, log_startup_config
from .models import (
    AuditEntry,
    AuthStatus,
    ConnectionDiagnostics,
    CreateUserRequest,
    ApiTokenCreateRequest,
    ApiTokenCreateResponse,
    ApiTokenPublic,
    ChangePasswordRequest,
    CustomButtonCreate,
    CustomButtonPublic,
    CustomButtonSendRequest,
    CustomButtonUpdate,
    KeypadCommand,
    LoginRequest,
    LoginResponse,
    NotificationTestRequest,
    NotificationConfig,
    PanelEvent,
    PanelState,
    RawAlarmMessage,
    SettingItem,
    SettingsImportRequest,
    SettingsUpdate,
    SetupCompleteRequest,
    SetupStatus,
    StateEnvelope,
    UpdateUserRequest,
    UserPublic,
    ZoneInfo,
    ZonesUpdate,
)
from .notifications import SMTPNotificationProvider, TestNotificationProvider, WebhookNotificationProvider
from .runtime import AlarmRuntime


runtime = AlarmRuntime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = runtime
    configure_logging()
    log_startup_config(runtime.config)
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(
    title="AlarmDecoder Modern",
    description="First vertical slice with fake AlarmDecoder adapter.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "adapter": runtime.config.adapter, "read_only": str(runtime.config.read_only).lower()}


@app.get("/ready")
async def ready() -> dict[str, object]:
    database_ok = True
    try:
        runtime.database.users_exist()
    except Exception:
        database_ok = False
    return {
        "status": "ready" if database_ok else "degraded",
        "adapter": runtime.config.adapter,
        "connection_status": runtime.state.connection_status,
        "read_only": runtime.config.read_only,
        "allow_commands": runtime.config.allow_commands,
        "database_ok": database_ok,
    }


@app.get("/api/auth/me", response_model=AuthStatus)
async def get_auth_status(request: Request, response: Response) -> AuthStatus:
    status_payload = auth_status(request)
    if status_payload.authenticated and status_payload.csrf_token is None:
        status_payload.csrf_token = set_csrf_cookie(response)
    return status_payload


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: Request, response: Response, credentials: LoginRequest) -> LoginResponse:
    with runtime.database.session_factory() as session:
        user = authenticate_user(session, credentials.username, credentials.password)
    if user is None:
        runtime.database.audit(credentials.username, "login_failed", {"username": credentials.username})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    token = create_access_token(user.username, user.role, runtime.config.session_secret, runtime.config.access_token_minutes)
    set_session_cookie(response, token)
    csrf_token = set_csrf_cookie(response)
    runtime.database.audit(user.username, "login_success", {"username": user.username})
    return LoginResponse(user=user_public(user), csrf_token=csrf_token)


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response, user: UserRecord | None = Depends(optional_current_user)) -> dict[str, str]:
    require_csrf(request)
    clear_session_cookie(response)
    runtime.database.audit(user.username if user else "anonymous", "logout")
    return {"status": "ok"}


@app.post("/api/account/password")
async def change_password(request: Request, payload: ChangePasswordRequest, user: UserRecord = Depends(require_current_user)) -> dict[str, str]:
    require_csrf(request)
    with runtime.database.session_factory() as session:
        target = get_user(session, user.username)
        if target is None or not verify_password(payload.current_password, target.password_hash):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is invalid.")
        target.password_hash = hash_password(payload.new_password)
        session.commit()
    runtime.database.audit(user.username, "password_changed")
    return {"status": "ok"}


@app.get("/api/setup/status", response_model=SetupStatus)
async def setup_status() -> SetupStatus:
    users_exist = runtime.database.users_exist()
    panel_type = runtime.config.panel_type if runtime.config.panel_type in {"ADEMCO", "DSC"} else "ADEMCO"
    return SetupStatus(
        setup_required=not users_exist,
        users_exist=users_exist,
        adapter=runtime.config.adapter,
        panel_type=panel_type,
    )


@app.post("/api/setup/complete", response_model=UserPublic)
async def setup_complete(request: Request, payload: SetupCompleteRequest) -> UserPublic:
    if runtime.database.users_exist():
        user = optional_current_user(request)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        require_csrf(request)
        actor = user.username
    else:
        actor = payload.username

    with runtime.database.session_factory() as session:
        created = create_user(session, payload.username, payload.password, "admin")
        public = user_public(created)

    settings = {
        "adapter": payload.adapter,
        "panel_type": payload.panel_type,
    }
    if payload.ser2sock_host:
        settings["ser2sock_host"] = payload.ser2sock_host
    if payload.ser2sock_port is not None:
        settings["ser2sock_port"] = str(payload.ser2sock_port)
    if payload.serial_path:
        settings["serial_path"] = payload.serial_path
    if payload.serial_baudrate is not None:
        settings["serial_baudrate"] = str(payload.serial_baudrate)
    runtime.database.upsert_settings(settings)
    runtime.database.audit(actor, "setup_completed", {"adapter": payload.adapter, "panel_type": payload.panel_type})
    return public


@app.get("/api/state", response_model=PanelState)
async def get_state() -> PanelState:
    return runtime.state


@app.get("/api/events", response_model=list[PanelEvent])
async def get_events(limit: int = 50) -> list[PanelEvent]:
    return await runtime.events.list(limit=limit)


@app.get("/api/snapshot", response_model=StateEnvelope)
async def get_snapshot() -> StateEnvelope:
    snapshot = await runtime.snapshot()
    return StateEnvelope(**snapshot)


@app.post("/api/keypad/command", response_model=PanelState)
async def send_keypad_command(request: Request, command: KeypadCommand, user: UserRecord | None = Depends(optional_current_user)) -> PanelState:
    require_csrf(request)
    try:
        return await runtime.send_keys(command, user)
    except ReadOnlyAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/api/custom-buttons", response_model=list[CustomButtonPublic])
async def get_custom_buttons(user: UserRecord = Depends(require_current_user)) -> list[CustomButtonPublic]:
    return [_custom_button_public(record) for record in runtime.database.list_custom_buttons(user.username)]


@app.post("/api/custom-buttons", response_model=CustomButtonPublic)
async def post_custom_button(request: Request, payload: CustomButtonCreate, user: UserRecord = Depends(require_role("operator", "admin"))) -> CustomButtonPublic:
    require_csrf(request)
    record = runtime.database.upsert_custom_button(
        username=user.username,
        label=payload.label,
        command_value=payload.command,
        dangerous=payload.dangerous,
        enabled=payload.enabled,
        sort_order=payload.sort_order,
    )
    runtime.database.audit(user.username, "custom_button_created", {"button_id": record.id, "label": record.label, "dangerous": record.dangerous})
    return _custom_button_public(record)


@app.patch("/api/custom-buttons/{button_id}", response_model=CustomButtonPublic)
async def patch_custom_button(button_id: int, request: Request, payload: CustomButtonUpdate, user: UserRecord = Depends(require_role("operator", "admin"))) -> CustomButtonPublic:
    require_csrf(request)
    existing = runtime.database.get_custom_button(button_id)
    if existing is None or (existing.owner_username != user.username and user.role != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom button not found.")
    record = runtime.database.upsert_custom_button(
        username=existing.owner_username,
        label=payload.label if payload.label is not None else existing.label,
        command_value=payload.command if payload.command is not None else existing.command_value,
        dangerous=payload.dangerous if payload.dangerous is not None else existing.dangerous,
        enabled=payload.enabled if payload.enabled is not None else existing.enabled,
        sort_order=payload.sort_order if payload.sort_order is not None else existing.sort_order,
        button_id=button_id,
    )
    runtime.database.audit(user.username, "custom_button_updated", {"button_id": button_id, "label": record.label, "dangerous": record.dangerous})
    return _custom_button_public(record)


@app.delete("/api/custom-buttons/{button_id}")
async def delete_custom_button(button_id: int, request: Request, user: UserRecord = Depends(require_role("operator", "admin"))) -> dict[str, str]:
    require_csrf(request)
    existing = runtime.database.get_custom_button(button_id)
    if existing is None or (existing.owner_username != user.username and user.role != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom button not found.")
    runtime.database.delete_custom_button(button_id)
    runtime.database.audit(user.username, "custom_button_deleted", {"button_id": button_id})
    return {"status": "deleted"}


@app.post("/api/custom-buttons/{button_id}/send", response_model=PanelState)
async def send_custom_button(button_id: int, request: Request, payload: CustomButtonSendRequest, user: UserRecord = Depends(require_role("operator", "admin"))) -> PanelState:
    require_csrf(request)
    existing = runtime.database.get_custom_button(button_id)
    if existing is None or not existing.enabled or (existing.owner_username != user.username and user.role != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom button not found.")
    return await runtime.send_keys(KeypadCommand(keys=existing.command_value, dangerous_confirmed=payload.dangerous_confirmed), user)


@app.get("/api/diagnostics/connection", response_model=ConnectionDiagnostics)
async def get_connection_diagnostics() -> ConnectionDiagnostics:
    return await runtime.connection_diagnostics()


@app.get("/api/diagnostics/raw-messages", response_model=list[RawAlarmMessage])
async def get_raw_messages(limit: int = 100) -> list[RawAlarmMessage]:
    return await runtime.raw_messages.list(limit=limit)


@app.get("/api/diagnostics/events", response_model=list[PanelEvent])
async def get_diagnostic_events(limit: int = 100) -> list[PanelEvent]:
    return await runtime.events.list(limit=limit)


@app.get("/api/history/events", response_model=list[PanelEvent])
async def get_history_events(limit: int = 50, offset: int = 0, type: str | None = None) -> list[PanelEvent]:
    return [_event_from_record(record) for record in runtime.database.list_events(limit=limit, offset=offset, type=type)]


@app.get("/api/history/raw-messages", response_model=list[RawAlarmMessage])
async def get_history_raw_messages(limit: int = 50, offset: int = 0) -> list[RawAlarmMessage]:
    return [_raw_from_record(record) for record in runtime.database.list_raw_messages(limit=limit, offset=offset)]


@app.get("/api/settings", response_model=list[SettingItem])
async def get_settings(_: UserRecord = Depends(require_role("admin"))) -> list[SettingItem]:
    return [_setting_from_record(record) for record in runtime.database.list_settings()]


@app.put("/api/settings", response_model=list[SettingItem])
async def put_settings(request: Request, update: SettingsUpdate, user: UserRecord = Depends(require_role("admin"))) -> list[SettingItem]:
    require_csrf(request)
    records = runtime.database.upsert_settings({item.key: item.value for item in update.settings})
    runtime.database.audit(user.username, "settings_updated", {"keys": [item.key for item in update.settings]})
    return [_setting_from_record(record) for record in records]


@app.get("/api/zones", response_model=list[ZoneInfo])
async def get_zones() -> list[ZoneInfo]:
    return [_zone_from_record(record) for record in runtime.database.list_zones()]


@app.put("/api/zones", response_model=list[ZoneInfo])
async def put_zones(request: Request, update: ZonesUpdate, user: UserRecord = Depends(require_role("admin"))) -> list[ZoneInfo]:
    require_csrf(request)
    records = runtime.database.upsert_zones([zone.model_dump() for zone in update.zones])
    runtime.database.audit(user.username, "zones_updated", {"count": len(update.zones)})
    return [_zone_from_record(record) for record in records]


@app.get("/api/admin/users", response_model=list[UserPublic])
async def list_users(_: UserRecord = Depends(require_role("admin"))) -> list[UserPublic]:
    with runtime.database.session_factory() as session:
        return [user_public(user) for user in session.query(UserRecord).order_by(UserRecord.username).all()]


@app.post("/api/admin/users", response_model=UserPublic)
async def post_user(request: Request, payload: CreateUserRequest, user: UserRecord = Depends(require_role("admin"))) -> UserPublic:
    require_csrf(request)
    with runtime.database.session_factory() as session:
        created = create_user(session, payload.username, payload.password, payload.role)
        public = user_public(created)
    runtime.database.audit(user.username, "user_created", {"username": payload.username, "role": payload.role})
    return public


@app.patch("/api/admin/users/{username}", response_model=UserPublic)
async def patch_user(username: str, request: Request, payload: UpdateUserRequest, user: UserRecord = Depends(require_role("admin"))) -> UserPublic:
    require_csrf(request)
    with runtime.database.session_factory() as session:
        target = get_user(session, username)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        if payload.role is not None:
            target.role = payload.role
        if payload.disabled is not None:
            target.disabled = payload.disabled
        if payload.password is not None:
            target.password_hash = hash_password(payload.password)
        session.commit()
        session.refresh(target)
        public = user_public(target)
    runtime.database.audit(user.username, "user_updated", {"username": username})
    return public


@app.delete("/api/admin/users/{username}")
async def delete_user(username: str, request: Request, user: UserRecord = Depends(require_role("admin"))) -> dict[str, str]:
    require_csrf(request)
    if username == user.username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete the current user.")
    with runtime.database.session_factory() as session:
        target = get_user(session, username)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        session.delete(target)
        session.commit()
    runtime.database.audit(user.username, "user_deleted", {"username": username})
    return {"status": "deleted"}


@app.get("/api/admin/notifications", response_model=list[NotificationConfig])
async def get_notifications(_: UserRecord = Depends(require_role("admin"))) -> list[NotificationConfig]:
    return [_notification_from_record(record) for record in runtime.database.list_notifications()]


@app.put("/api/admin/notifications", response_model=list[NotificationConfig])
async def put_notifications(request: Request, configs: list[NotificationConfig], user: UserRecord = Depends(require_role("admin"))) -> list[NotificationConfig]:
    require_csrf(request)
    records = runtime.database.replace_notifications(
        [
            {
                "provider": config.provider,
                "enabled": config.enabled,
                "config_json": json.dumps(_redact_notification_config(config.config)),
            }
            for config in configs
        ]
    )
    runtime.reload_notifications()
    runtime.database.audit(user.username, "notifications_updated", {"count": len(configs)})
    return [_notification_from_record(record) for record in records]


@app.post("/api/admin/notifications/test")
async def test_notification(request: Request, payload: NotificationTestRequest, user: UserRecord = Depends(require_role("admin"))) -> dict[str, str]:
    require_csrf(request)
    event = PanelEvent(type="trouble", message="AlarmDecoder notification test", data={"test": True})
    if payload.provider == "webhook":
        url = str(payload.config.get("url", ""))
        if not url:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Webhook URL is required.")
        await WebhookNotificationProvider(url=url).send(event)
    elif payload.provider == "smtp":
        await SMTPNotificationProvider(
            host=str(payload.config.get("host", "")),
            sender=str(payload.config.get("sender", "")),
            recipient=str(payload.config.get("recipient", "")),
        ).send(event)
    else:
        sent: list[PanelEvent] = []
        await TestNotificationProvider(sent).send(event)
    runtime.database.audit(user.username, "notification_test_sent", {"provider": payload.provider})
    return {"status": "sent"}


@app.get("/api/admin/api-tokens", response_model=list[ApiTokenPublic])
async def list_api_tokens(_: UserRecord = Depends(require_role("admin"))) -> list[ApiTokenPublic]:
    with runtime.database.session_factory() as session:
        records = session.query(ApiTokenRecord).order_by(ApiTokenRecord.created_at.desc()).all()
        return [_api_token_public(record, session.get(UserRecord, record.user_id)) for record in records]


@app.post("/api/admin/api-tokens", response_model=ApiTokenCreateResponse)
async def create_api_token(request: Request, payload: ApiTokenCreateRequest, user: UserRecord = Depends(require_role("admin"))) -> ApiTokenCreateResponse:
    require_csrf(request)
    raw_token = f"ad2_{token_urlsafe(32)}"
    with runtime.database.session_factory() as session:
        target = get_user(session, payload.username)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        record = ApiTokenRecord(
            user_id=target.id,
            name=payload.name,
            token_hash=hash_api_token(raw_token),
            token_prefix=raw_token[:12],
            role=payload.role,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        public = _api_token_public(record, target)
    runtime.database.audit(user.username, "api_token_created", {"username": payload.username, "name": payload.name, "role": payload.role})
    return ApiTokenCreateResponse(token=raw_token, record=public)


@app.delete("/api/admin/api-tokens/{token_id}")
async def delete_api_token(token_id: int, request: Request, user: UserRecord = Depends(require_role("admin"))) -> dict[str, str]:
    require_csrf(request)
    with runtime.database.session_factory() as session:
        record = session.get(ApiTokenRecord, token_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found.")
        session.delete(record)
        session.commit()
    runtime.database.audit(user.username, "api_token_deleted", {"token_id": token_id})
    return {"status": "deleted"}


@app.get("/api/audit", response_model=list[AuditEntry])
async def get_audit(limit: int = 100, offset: int = 0, _: UserRecord = Depends(require_role("admin"))) -> list[AuditEntry]:
    return [_audit_from_record(record) for record in runtime.database.list_audit(limit=limit, offset=offset)]


@app.get("/api/admin/export")
async def export_settings(_: UserRecord = Depends(require_role("admin"))) -> dict[str, object]:
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "settings": [_setting_from_record(record).model_dump() for record in runtime.database.list_settings()],
        "zones": [_zone_from_record(record).model_dump() for record in runtime.database.list_zones()],
        "notifications": [_notification_from_record(record).model_dump() for record in runtime.database.list_notifications()],
    }


@app.post("/api/admin/import")
async def import_settings(request: Request, payload: SettingsImportRequest, user: UserRecord = Depends(require_role("admin"))) -> dict[str, object]:
    require_csrf(request)
    data = payload.data
    summary = {
        "settings": len(data.get("settings", [])) if isinstance(data.get("settings"), list) else 0,
        "zones": len(data.get("zones", [])) if isinstance(data.get("zones"), list) else 0,
        "notifications": len(data.get("notifications", [])) if isinstance(data.get("notifications"), list) else 0,
    }
    if payload.dry_run:
        return {"status": "dry-run", "summary": summary}

    settings = data.get("settings", [])
    zones = data.get("zones", [])
    notifications = data.get("notifications", [])
    if isinstance(settings, list):
        runtime.database.upsert_settings({str(item["key"]): str(item.get("value", "")) for item in settings if isinstance(item, dict) and "key" in item})
    if isinstance(zones, list):
        runtime.database.upsert_zones([item for item in zones if isinstance(item, dict) and "id" in item])
    if isinstance(notifications, list):
        runtime.database.replace_notifications(
            [
                {
                    "provider": str(item.get("provider", "webhook")),
                    "enabled": bool(item.get("enabled", False)),
                    "config_json": json.dumps(_redact_notification_config(item.get("config", {}))),
                }
                for item in notifications
                if isinstance(item, dict)
            ]
        )
        runtime.reload_notifications()
    runtime.database.audit(user.username, "settings_imported", summary)
    return {"status": "imported", "summary": summary}


@app.get("/api/config/effective")
async def get_effective_config() -> dict[str, object]:
    return runtime.config.safe_public_dict()


@app.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    await runtime.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        runtime.disconnect(websocket)


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


def _event_from_record(record: EventRecord) -> PanelEvent:
    return PanelEvent(
        id=record.id,
        timestamp=record.timestamp,
        type=record.type,
        message=record.message,
        data=json.loads(record.data_json or "{}"),
    )


def _raw_from_record(record: RawMessageRecord) -> RawAlarmMessage:
    return RawAlarmMessage(id=record.id, timestamp=record.timestamp, raw=record.raw)


def _setting_from_record(record: AppSettingRecord) -> SettingItem:
    return SettingItem(key=record.key, value=record.value)


def _zone_from_record(record: ZoneRecord) -> ZoneInfo:
    return ZoneInfo(id=record.id, name=record.name, enabled=record.enabled)


def _notification_from_record(record: NotificationSettingRecord) -> NotificationConfig:
    return NotificationConfig(
        id=record.id,
        provider=record.provider,
        enabled=record.enabled,
        config=json.loads(record.config_json or "{}"),
    )


def _audit_from_record(record: AuditLogRecord) -> AuditEntry:
    return AuditEntry(
        id=record.id,
        timestamp=record.timestamp,
        actor=record.actor,
        action=record.action,
        details=json.loads(record.details_json or "{}"),
    )


def _custom_button_public(record: CustomButtonRecord) -> CustomButtonPublic:
    return CustomButtonPublic(
        id=record.id,
        label=record.label,
        dangerous=record.dangerous,
        enabled=record.enabled,
        sort_order=record.sort_order,
    )


def _api_token_public(record: ApiTokenRecord, user: UserRecord | None) -> ApiTokenPublic:
    username = user.username if user else "unknown"
    return ApiTokenPublic(
        id=record.id,
        name=record.name,
        username=username,
        token_prefix=record.token_prefix,
        role=record.role,
        disabled=record.disabled,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
    )


def _redact_notification_config(config: dict) -> dict:
    safe = dict(config)
    for key in ("password", "token", "secret", "authorization"):
        if key in safe:
            safe[key] = "<redacted>"
    return safe
