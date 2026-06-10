from __future__ import annotations

from pathlib import Path

from app.parser import parse_alarmdecoder_line


FIXTURE = Path(__file__).parent / "fixtures" / "ser2sock-readonly-capture.txt"


def _fixture_lines() -> list[str]:
    return [line for line in FIXTURE.read_text().splitlines() if line.strip()]


def _events_from_fixture():
    return [event for line in _fixture_lines() for event in parse_alarmdecoder_line(line)]


def test_fixture_lines_are_preserved_as_raw_messages() -> None:
    lines = _fixture_lines()
    raw_events = [event for event in _events_from_fixture() if event.type == "raw_message"]

    assert len(raw_events) == len(lines)
    assert raw_events[0].data["raw"] == lines[0]


def test_parser_extracts_keypad_display_text() -> None:
    events = _events_from_fixture()

    display = next(event for event in events if event.type == "panel_display")

    assert display.data["line1"] == "****DISARMED****"
    assert "Ready to Arm" in display.data["line2"]
    assert display.data["beeps"] == 1


def test_parser_identifies_state_patterns_in_fixture() -> None:
    events = _events_from_fixture()

    assert any(event.type == "panel_ready" and event.data["ready"] is True for event in events)
    assert any(event.type == "panel_ready" and event.data["ready"] is False for event in events)
    assert any(event.type == "panel_armed" and event.data["mode"] == "away" for event in events)
    assert any(event.type == "panel_armed" and event.data["mode"] == "stay" for event in events)
    assert any(event.type == "panel_disarmed" for event in events)
    assert any(event.type == "alarm_active" and event.data["active"] is True for event in events)
    assert any(event.type == "fire_alarm" and event.data["active"] is True for event in events)
    assert any(event.type == "panic_alarm" and event.data["active"] is True for event in events)
    assert any(event.type == "chime_changed" and event.data["enabled"] is True for event in events)
    assert any(event.type == "chime_changed" and event.data["enabled"] is False for event in events)
    assert any(event.type == "power_changed" and event.data["power"] == "BATTERY" for event in events)
    assert any(event.type == "power_changed" and event.data["power"] == "AC" for event in events)
    assert any(event.type == "low_battery" and event.data["active"] is True for event in events)
    assert any(event.type == "zone_fault" and event.data["zone"] == 1 for event in events)
    assert any(event.type == "zone_restore" and event.data["zone"] == 1 for event in events)


def test_unknown_and_malformed_messages_do_not_crash() -> None:
    cases = [
        "",
        "[partial keypad message",
        '[10000001000000003A--],abc,[metadata],"bad beeps"',
        "garbled partial message without keypad fields",
        "\x00\x01not alarmdecoder",
    ]

    for case in cases:
        events = parse_alarmdecoder_line(case)
        if not case:
            assert events == []
        else:
            assert events[0].type == "raw_message"

    unknown_events = parse_alarmdecoder_line("[partial keypad message")
    assert any(event.type == "unknown_message" for event in unknown_events)


def test_non_keypad_families_emit_structured_events() -> None:
    for raw, event_type, family in [
        ("!LRR:012,003,ARM", "lrr", "LRR"),
        ("!RFX:0123456,80", "rfx", "RFX"),
        ("!EXP:01,FAULT", "exp", "EXP"),
        ("!AUI:01,READY", "aui", "AUI"),
    ]:
        events = parse_alarmdecoder_line(raw)
        event = next(item for item in events if item.type == event_type)
        assert event.data["family"] == family
        assert event.data["raw"] == raw
        assert event.data["fields"]


def test_parser_identifies_bypass_relay_boot_and_config() -> None:
    bypass = parse_alarmdecoder_line('[10000001000000003A--],000,[0000000000000000],"BYPASS ZONE 001 FRONT DOOR      "')
    assert any(event.type == "bypass" and event.data["zone"] == 1 for event in bypass)

    relay = parse_alarmdecoder_line('[10000001000000003A--],000,[0000000000000000],"RELAY 01 ON                     "')
    assert any(event.type == "relay_changed" and event.data["relay"] == "1" and event.data["active"] is True for event in relay)

    assert any(event.type == "boot" for event in parse_alarmdecoder_line("!BOOT:ready"))
    assert any(event.type == "config_received" for event in parse_alarmdecoder_line("!CONFIG:ADDRESS=18"))
