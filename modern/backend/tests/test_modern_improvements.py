from __future__ import annotations

import pytest

from app.commands import CommandTranslator
from app.crypto import decrypt_value, encrypt_value
from app.parser import _parse_keypad_flags
from app.passkeys import (
    PasskeyLoginFinishRequest,
    PasskeyRegisterFinishRequest,
    create_authentication_options,
    create_registration_options,
    verify_authentication,
    verify_registration,
)


def test_bitfield_flag_parsing() -> None:
    # 20-char flag string:
    # 0: ready=1, 1: armed_away=0, 2: armed_stay=0, 3: backlight=1, 4: prog=0,
    # 5-7: beeps='003', 8: bypass=0, 9: ac=1, 10: chime=1, 11: alarm=0,
    # 12: sounding=0, 13: bat_low=0, 14: entry_off=0, 15: fire=0, 16: check=0,
    # 17: perim=0, 18: fault=0, 19: dsc=0
    raw_flags = "10010003011000000000"
    flags = _parse_keypad_flags(raw_flags)
    assert flags["ready"] is True
    assert flags["armed_away"] is False
    assert flags["armed_stay"] is False
    assert flags["backlight"] is True
    assert flags["beeps"] == 3
    assert flags["ac_power"] is True
    assert flags["chime"] is True
    assert flags["fire"] is False
    assert flags["panel_type_dsc"] is False

    # Armed away flag string
    armed_flags = "01000002010000000000"
    flags_armed = _parse_keypad_flags(armed_flags)
    assert flags_armed["ready"] is False
    assert flags_armed["armed_away"] is True
    assert flags_armed["armed_stay"] is False
    assert flags_armed["beeps"] == 2


def test_crypto_encryption_and_decryption() -> None:
    secret = "my-test-session-secret-which-is-long"
    token = encrypt_value("4321", secret)
    assert token != "4321"
    assert decrypt_value(token, secret) == "4321"

    with pytest.raises(ValueError):
        decrypt_value(token, "wrong-secret-which-is-also-long-enough")


def test_command_translator_honeywell() -> None:
    translator = CommandTranslator()
    assert translator.translate("AWAY", pin="1234", panel_type="ADEMCO") == "12342"
    assert translator.translate("STAY", pin="1234", panel_type="ADEMCO") == "12343"
    assert translator.translate("DISARM", pin="1234", panel_type="ADEMCO") == "12341"
    assert translator.translate("CHIME", pin="1234", panel_type="ADEMCO") == "12349"
    assert translator.translate("F1", pin="1234", panel_type="ADEMCO") == "\x01\x01\x01"
    assert translator.translate("FIRE", pin="1234", panel_type="ADEMCO") == "\x01\x01\x01"


def test_command_translator_dsc() -> None:
    translator = CommandTranslator()
    assert translator.translate("AWAY", pin="5678", panel_type="DSC") == "5678"
    assert translator.translate("STAY", pin="5678", panel_type="DSC") == "5678*"
    assert translator.translate("DISARM", pin="5678", panel_type="DSC") == "5678"


def test_command_translator_fake_passthrough() -> None:
    translator = CommandTranslator()
    assert translator.translate("AWAY", pin="1234", panel_type="ADEMCO", is_fake_adapter=True) == "AWAY"


class MockDatabase:
    def __init__(self):
        self.creds = {}

    def add_passkey(self, credential_id: str, username: str, name: str, public_key: str, aaguid=None):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        cred = SimpleNamespace(
            id=credential_id,
            username=username,
            name=name,
            public_key=public_key,
            sign_count=0,
            aaguid=aaguid,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
        )
        self.creds[credential_id] = cred
        return cred

    def get_passkey(self, credential_id: str):
        return self.creds.get(credential_id)

    def update_passkey_usage(self, credential_id: str, sign_count: int):
        if credential_id in self.creds:
            self.creds[credential_id].sign_count = sign_count


def test_passkey_flow() -> None:
    db = MockDatabase()

    # 1. Registration begin
    reg_opts = create_registration_options("alice", rp_id="localhost")
    assert reg_opts.challenge
    assert reg_opts.user["name"] == "alice"

    # 2. Registration finish
    import base64
    import json
    client_data = json.dumps({"challenge": reg_opts.challenge, "origin": "http://localhost:8000"}).encode()
    client_data_b64 = base64.urlsafe_b64encode(client_data).decode().rstrip("=")

    finish_req = PasskeyRegisterFinishRequest(
        id="cred-123",
        rawId="cred-123",
        name="MacBook TouchID",
        clientDataJSON=client_data_b64,
        attestationObject="mock-attestation-blob",
    )
    result = verify_registration(finish_req, db)
    assert result.id == "cred-123"
    assert result.username == "alice"

    # 3. Authentication begin
    auth_opts = create_authentication_options(rp_id="localhost")
    assert auth_opts.challenge

    # 4. Authentication finish
    auth_client_data = json.dumps({"challenge": auth_opts.challenge, "origin": "http://localhost:8000"}).encode()
    auth_client_b64 = base64.urlsafe_b64encode(auth_client_data).decode().rstrip("=")

    auth_req = PasskeyLoginFinishRequest(
        id="cred-123",
        rawId="cred-123",
        clientDataJSON=auth_client_b64,
        authenticatorData="mock-auth-data",
        signature="mock-sig",
    )
    authenticated_user = verify_authentication(auth_req, db)
    assert authenticated_user == "alice"


@pytest.mark.asyncio
async def test_initial_panel_state_not_fake_adapter():
    from app.state import initial_panel_state
    state = initial_panel_state()
    assert state.display_line1 == "ALARMDECODER"
    assert state.display_line2 == "CONNECTING..."
    assert "FAKE ADAPTER" not in state.last_message


@pytest.mark.asyncio
async def test_apply_settings_from_db_overrides_config():
    from app.config import AppConfig
    from app.runtime import AlarmRuntime
    from app.models import SettingItem

    config = AppConfig(
        adapter="fake",
        ser2sock_host="alarmdecoder.local",
        ser2sock_port=10000,
        read_only=True,
        allow_commands=False,
        auth_required=False,
        database_url="sqlite:///:memory:",
        session_secret="0123456789012345678901234567890123456789",
    )
    runtime = AlarmRuntime(config)
    runtime.database.init()

    # Pre-condition
    assert runtime.config.ser2sock_host == "alarmdecoder.local"

    # Save ad2iot.local in database
    runtime.database.upsert_settings({
        "adapter": "ser2sock",
        "ser2sock_host": "ad2iot.local",
        "ser2sock_port": "10001",
    })

    # Apply settings from DB
    runtime.apply_settings_from_db()

    assert runtime.config.adapter == "ser2sock"
    assert runtime.config.ser2sock_host == "ad2iot.local"
    assert runtime.config.ser2sock_port == 10001


@pytest.mark.asyncio
async def test_database_delete_zone():
    from app.config import AppConfig
    from app.db import Database

    config = AppConfig(
        adapter="fake",
        ser2sock_host="127.0.0.1",
        ser2sock_port=10000,
        read_only=True,
        database_url="sqlite:///:memory:",
        session_secret="0123456789012345678901234567890123456789",
    )
    db = Database(config)
    db.init()

    # Add zone
    db.upsert_zones([{"id": 1, "name": "Front Door", "enabled": True}, {"id": 2, "name": "Back Door", "enabled": True}])
    zones = db.list_zones()
    assert len(zones) == 2

    # Delete zone 1
    deleted = db.delete_zone(1)
    assert deleted is True

    zones = db.list_zones()
    assert len(zones) == 1
    assert zones[0].id == 2

    # Delete non-existent zone returns False
    assert db.delete_zone(99) is False


def test_api_delete_zone():
    from fastapi.testclient import TestClient
    from app.main import app, runtime

    with TestClient(app) as client:
        # Create an admin user
        with runtime.database.session_factory() as session:
            from app.auth import create_user
            try:
                create_user(session, "test_admin", "AdminPass123!", "admin")
            except ValueError:
                pass

        # Login to get cookie and CSRF token
        login_res = client.post("/api/auth/login", json={"username": "test_admin", "password": "AdminPass123!"})
        assert login_res.status_code == 200
        csrf_token = login_res.json()["csrf_token"]

        # Create zone 10
        runtime.database.upsert_zones([{"id": 10, "name": "Garage Door", "enabled": True}])
        assert any(z.id == 10 for z in runtime.database.list_zones())

        # Delete zone 10 via API
        del_res = client.delete("/api/zones/10", headers={"X-CSRF-Token": csrf_token})
        assert del_res.status_code == 200
        assert del_res.json() == {"deleted": True}
        assert not any(z.id == 10 for z in runtime.database.list_zones())


@pytest.mark.asyncio
async def test_runtime_zone_restore_synthesis_on_panel_ready() -> None:
    from app.config import AppConfig
    from app.runtime import AlarmRuntime
    from app.parser import parse_alarmdecoder_line

    config = AppConfig(
        adapter="fake",
        ser2sock_host="127.0.0.1",
        ser2sock_port=10000,
        read_only=True,
        database_url="sqlite:///:memory:",
        session_secret="0123456789012345678901234567890123456789",
    )
    runtime = AlarmRuntime(config)
    await runtime.start()

    try:
        # 1. Door opened: FAULT 01
        line_fault = '[00000311100000000A--],001,[f71f80001001030038020000020000],"FAULT 01 GARAGE ENTRY DOOR "'
        for ev in parse_alarmdecoder_line(line_fault):
            await runtime.handle_event(ev)

        assert runtime.state.ready is False
        assert runtime.state.faulted_zones == [1]

        # 2. Door closed: Panel becomes ready with DISARMED BYPASS READY TO ARM (no explicit zone restore text)
        line_ready = '[10000011100000003A--],001,[f71f80001001801c38020000020000],"DISARMED BYPASS READY TO ARM "'
        for ev in parse_alarmdecoder_line(line_ready):
            await runtime.handle_event(ev)

        assert runtime.state.ready is True
        assert runtime.state.faulted_zones == []

        # Verify a zone_restore event was synthesized and added to the event log
        events = await runtime.events.list()
        restore_events = [e for e in events if e.type == "zone_restore" and e.data.get("zone") == 1]
        assert len(restore_events) >= 1
        assert "Zone 1 restored" in restore_events[0].message
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_multi_zone_expiration() -> None:
    from app.config import AppConfig
    from app.runtime import AlarmRuntime
    from app.models import PanelEvent

    config = AppConfig(
        adapter="fake",
        ser2sock_host="127.0.0.1",
        ser2sock_port=10000,
        read_only=True,
        database_url="sqlite:///:memory:",
        session_secret="0123456789012345678901234567890123456789",
    )
    runtime = AlarmRuntime(config)
    await runtime.start()

    try:
        # Fault zone 1 and zone 2
        await runtime.handle_event(PanelEvent(type="zone_fault", message="Zone 1 faulted", data={"zone": 1}))
        await runtime.handle_event(PanelEvent(type="zone_fault", message="Zone 2 faulted", data={"zone": 2}))
        assert runtime.state.faulted_zones == [1, 2]

        # Simulate time passing for Zone 1: set its last_seen to 20 seconds ago
        runtime._zone_last_seen[1] = runtime._zone_last_seen[1] - 20.0

        # Now an ongoing fault message arrives only for Zone 2 (Zone 1 closed)
        await runtime.handle_event(
            PanelEvent(type="panel_display", message="FAULT 02 BACK PATIO DOOR", data={"text": "FAULT 02 BACK PATIO DOOR", "parsed_flags": {"ready": False}})
        )

        # Zone 1 should have expired and restored; Zone 2 should still be faulted
        assert runtime.state.faulted_zones == [2]
        events = await runtime.events.list()
        restore_events = [e for e in events if e.type == "zone_restore" and e.data.get("zone") == 1]
        assert len(restore_events) >= 1
    finally:
        await runtime.stop()

