from __future__ import annotations

from app.models import PanelEvent, PanelState
from app.parser import parse_alarmdecoder_line
from app.state import reduce_panel_state


def _apply_line(state: PanelState, line: str) -> PanelState:
    for event in parse_alarmdecoder_line(line):
        state = reduce_panel_state(state, event)
    return state


def test_state_tracks_disarmed_ready_fault_and_restore() -> None:
    state = PanelState()

    state = _apply_line(
        state,
        '[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "',
    )
    assert state.armed is False
    assert state.armed_mode == "disarmed"
    assert state.ready is True

    state = _apply_line(
        state,
        '[00000001000000003A--],003,[0000000000000000],"FAULT 01        FRONT DOOR      "',
    )
    assert state.ready is False
    assert state.faulted_zones == [1]

    state = _apply_line(
        state,
        '[10000001000000003A--],001,[0000000000000000],"ZONE 01 RESTORE FRONT DOOR      "',
    )
    assert state.ready is True
    assert state.faulted_zones == []


def test_state_tracks_arm_modes_and_disarm_transition() -> None:
    state = PanelState()

    state = _apply_line(
        state,
        '[01000001000000003A--],000,[0000000000000000],"****ARMED AWAY****Exit Now      "',
    )
    assert state.armed is True
    assert state.armed_mode == "away"
    assert state.armed_stay is False

    state = _apply_line(
        state,
        '[01000001000000003A--],000,[0000000000000000],"****ARMED STAY****Instant       "',
    )
    assert state.armed is True
    assert state.armed_mode == "stay"
    assert state.armed_stay is True

    state = _apply_line(
        state,
        '[10000001000000003A--],001,[0000000000000000],"****DISARMED****  Ready to Arm  "',
    )
    assert state.armed is False
    assert state.armed_mode == "disarmed"


def test_state_tracks_alarm_trouble_and_raw_diagnostics() -> None:
    state = PanelState()

    state = _apply_line(
        state,
        '[00000001000000003A--],007,[0000000000000000],"ALARM 01        FRONT DOOR      "',
    )
    assert state.alarming is True
    assert state.beeps == 7
    assert state.last_raw_message is not None

    state = _apply_line(
        state,
        '[00000001000000003A--],007,[0000000000000000],"FIRE ALARM      SMOKE DETECTOR  "',
    )
    assert state.fire_detected is True

    state = _apply_line(
        state,
        '[00000001000000003A--],007,[0000000000000000],"PANIC ALARM     CHECK PANEL     "',
    )
    assert state.panic is True
    assert state.trouble is True

    state = _apply_line(
        state,
        '[00000001000000003A--],002,[0000000000000000],"AC LOSS         CHECK SYSTEM    "',
    )
    assert state.power == "BATTERY"
    assert state.trouble is True

    state = _apply_line(
        state,
        '[00000001000000003A--],002,[0000000000000000],"LOW BATTERY     CHECK SYSTEM    "',
    )
    assert state.battery_trouble is True


def test_legacy_fake_adapter_events_remain_compatible() -> None:
    state = reduce_panel_state(PanelState(), PanelEvent(type="arm", message="System armed away", data={"stay": False}))
    assert state.armed is True
    assert state.armed_mode == "away"

    state = reduce_panel_state(state, PanelEvent(type="disarm", message="System disarmed"))
    assert state.armed is False
    assert state.armed_mode == "disarmed"
