from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.auth import create_access_token, create_user
from app.config import AppConfig
from app.db import EventRecord, RawMessageRecord
from app.main import app
from app.runtime import AlarmRuntime
import app.main as main_module


def _config(**overrides) -> AppConfig:
    values = {
        "adapter": "fake",
        "ser2sock_host": "127.0.0.1",
        "ser2sock_port": 1,
        "read_only": False,
        "allow_commands": True,
        "auth_required": True,
        "database_url": "sqlite:///:memory:",
        "session_secret": "test-secret",
        "command_cooldown_seconds": 0,
        "raw_retention_days": 1,
        "event_retention_days": 1,
    }
    values.update(overrides)
    return AppConfig(**values)


def _client_with_runtime() -> tuple[TestClient, AlarmRuntime]:
    runtime = AlarmRuntime(_config())
    main_module.runtime = runtime
    app.state.runtime = runtime
    client = TestClient(app)
    client.__enter__()
    return client, runtime


def _bearer(runtime: AlarmRuntime, username: str, role: str) -> dict[str, str]:
    with runtime.database.session_factory() as session:
        create_user(session, username, "password123", role)
    token = create_access_token(username, role, runtime.config.session_secret, 30)
    return {"Authorization": f"Bearer {token}"}


def test_admin_apis_and_history_are_db_backed() -> None:
    client, runtime = _client_with_runtime()
    try:
        headers = _bearer(runtime, "admin", "admin")
        response = client.put("/api/settings", json={"settings": [{"key": "raw_retention_days", "value": "7"}]}, headers=headers)
        assert response.status_code == 200
        assert response.json()[0]["key"] == "raw_retention_days"

        response = client.put("/api/zones", json={"zones": [{"id": 1, "name": "Front Door", "enabled": True}]}, headers=headers)
        assert response.status_code == 200
        assert response.json()[0]["name"] == "Front Door"

        response = client.post("/api/admin/users", json={"username": "viewer", "password": "password123", "role": "viewer"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["role"] == "viewer"

        response = client.get("/api/history/events", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        client.__exit__(None, None, None)


def test_viewer_cannot_send_commands_or_manage_admin_resources() -> None:
    client, runtime = _client_with_runtime()
    try:
        headers = _bearer(runtime, "viewer", "viewer")
        response = client.post("/api/keypad/command", json={"keys": "1234", "dangerous_confirmed": True}, headers=headers)
        assert response.status_code == 403
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403
    finally:
        client.__exit__(None, None, None)


def test_cookie_auth_mutations_require_csrf() -> None:
    client, runtime = _client_with_runtime()
    try:
        with runtime.database.session_factory() as session:
            create_user(session, "admin", "password123", "admin")
        response = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
        assert response.status_code == 200
        response = client.put("/api/settings", json={"settings": [{"key": "a", "value": "b"}]})
        assert response.status_code == 403
        csrf = client.cookies.get("ad2_csrf")
        response = client.put(
            "/api/settings",
            json={"settings": [{"key": "a", "value": "b"}]},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
    finally:
        client.__exit__(None, None, None)


def test_retention_prunes_old_records() -> None:
    runtime = AlarmRuntime(_config())
    runtime.database.init()
    old = datetime.now(timezone.utc) - timedelta(days=3)
    with runtime.database.session_factory() as session:
        session.add(EventRecord(id="old-event", timestamp=old, type="trouble", message="old", data_json="{}"))
        session.add(RawMessageRecord(id="old-raw", timestamp=old, raw="old"))
        session.commit()

    runtime.database.prune_retention()

    with runtime.database.session_factory() as session:
        assert session.get(EventRecord, "old-event") is None
        assert session.get(RawMessageRecord, "old-raw") is None


def test_notification_config_redacts_secrets_and_sends_safe_payload() -> None:
    client, runtime = _client_with_runtime()
    try:
        headers = _bearer(runtime, "admin", "admin")
        response = client.put(
            "/api/admin/notifications",
            json=[{"provider": "webhook", "enabled": True, "config": {"url": "http://127.0.0.1:9/hook", "secret": "1234"}}],
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()[0]["config"]["secret"] == "<redacted>"
        with runtime.database.session_factory() as session:
            stored = session.query(main_module.NotificationSettingRecord).first()
            assert stored is not None
            assert "1234" not in stored.config_json
    finally:
        client.__exit__(None, None, None)


def test_alembic_initial_migration_creates_schema(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("ALARMDECODER_DATABASE_URL", f"sqlite:///{db_path}")
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    runtime = AlarmRuntime(_config(database_url=f"sqlite:///{db_path}"))
    assert runtime.database.users_exist() is False


def test_setup_export_import_and_api_tokens() -> None:
    client, runtime = _client_with_runtime()
    try:
        response = client.get("/api/setup/status")
        assert response.status_code == 200
        assert response.json()["setup_required"] is True

        response = client.post(
            "/api/setup/complete",
            json={"username": "admin", "password": "password123", "panel_type": "ADEMCO", "adapter": "fake"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

        headers = {"Authorization": f"Bearer {create_access_token('admin', 'admin', runtime.config.session_secret, 30)}"}
        response = client.post(
            "/api/admin/api-tokens",
            json={"username": "admin", "name": "tests", "role": "viewer"},
            headers=headers,
        )
        assert response.status_code == 200
        token = response.json()["token"]
        assert token.startswith("ad2_")

        response = client.get("/api/state", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

        response = client.get("/api/admin/export", headers=headers)
        assert response.status_code == 200
        exported = response.json()
        assert exported["version"] == 1

        response = client.post("/api/admin/import", json={"data": exported, "dry_run": True}, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "dry-run"
    finally:
        client.__exit__(None, None, None)


def test_custom_buttons_send_by_id_and_do_not_expose_command_value() -> None:
    client, runtime = _client_with_runtime()
    try:
        headers = _bearer(runtime, "operator", "operator")
        response = client.post(
            "/api/custom-buttons",
            json={"label": "Arm test", "command": "1234", "dangerous": False},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["label"] == "Arm test"
        assert "1234" not in str(body)

        button_id = body["id"]
        response = client.get("/api/custom-buttons", headers=headers)
        assert response.status_code == 200
        assert "1234" not in str(response.json())

        response = client.post(f"/api/custom-buttons/{button_id}/send", json={"dangerous_confirmed": False}, headers=headers)
        assert response.status_code == 200

        events = client.get("/api/events", headers=headers).json()
        assert "1234" not in str(events)
    finally:
        client.__exit__(None, None, None)
