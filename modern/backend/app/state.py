from __future__ import annotations

from datetime import datetime, timezone

from .models import PanelEvent, PanelState


def _split_lcd(text: str) -> tuple[str, str]:
    padded = text[:32].ljust(32)
    return padded[:16].rstrip(), padded[16:32].rstrip()


def reduce_panel_state(state: PanelState, event: PanelEvent) -> PanelState:
    next_state = state.model_copy(deep=True)
    data = event.data

    if event.type == "raw_message":
        next_state.last_raw_message = str(data.get("raw", event.message))
    elif event.type == "device_open":
        next_state.connected = True
        next_state.connection_status = "connected"
    elif event.type == "device_close":
        next_state.connected = False
        next_state.connection_status = "disconnected"
    elif event.type == "connection_status":
        status = data.get("status", next_state.connection_status)
        if status in {"idle", "connecting", "connected", "disconnected", "reconnecting", "error"}:
            next_state.connection_status = status
            next_state.connected = status == "connected"
            if not next_state.connected and (next_state.last_message.startswith("ALARMDECODER") or not next_state.last_message):
                next_state.display_line1 = "ALARMDECODER"
                next_state.display_line2 = (status.upper() + "...").ljust(16)[:16]
    elif event.type in {"panel_display", "panel_message"}:
        text = str(data.get("text", event.message))
        next_state.display_line1, next_state.display_line2 = _split_lcd(text)
        next_state.last_message = text
        next_state.beeps = int(data.get("beeps", 0))
        next_state.cursor_location = data.get("cursor_location")

        flags = data.get("parsed_flags") or {}
        if flags:
            next_state.ready = bool(flags.get("ready", next_state.ready))
            next_state.armed = bool(flags.get("armed_away", False) or flags.get("armed_stay", False))
            next_state.armed_stay = bool(flags.get("armed_stay", False))
            next_state.armed_mode = "stay" if next_state.armed_stay else ("away" if next_state.armed else "disarmed")
            next_state.chime = bool(flags.get("chime", next_state.chime))
            next_state.bypassed = bool(flags.get("zone_bypassed", next_state.bypassed))
            next_state.fire_detected = bool(flags.get("fire", next_state.fire_detected))
            next_state.battery_low = bool(flags.get("battery_low", next_state.battery_low))
            next_state.battery_trouble = next_state.battery_low
            next_state.check_zones = bool(flags.get("check_zones", next_state.check_zones))
            next_state.alarming = bool(flags.get("alarm_sounding", next_state.alarming))
            if "ac_power" in flags:
                next_state.power = "AC" if flags["ac_power"] else "BATTERY"
            if flags.get("beeps"):
                next_state.beeps = int(flags["beeps"])
        else:
            if "ready" in data:
                next_state.ready = bool(data["ready"])
            if "armed" in data:
                next_state.armed = bool(data["armed"])
            if "armed_stay" in data:
                next_state.armed_stay = bool(data["armed_stay"])
                next_state.armed_mode = "stay" if next_state.armed_stay else ("away" if next_state.armed else "disarmed")
            if "chime" in data:
                next_state.chime = bool(data["chime"])

        # When the panel is ready, all monitored zones are closed
        if next_state.ready and next_state.faulted_zones:
            next_state.faulted_zones = []

    elif event.type == "panel_ready":
        next_state.ready = bool(data.get("ready", next_state.ready))
        if next_state.ready and next_state.faulted_zones:
            next_state.faulted_zones = []
    elif event.type == "panel_armed":
        mode = str(data.get("mode", "unknown"))
        next_state.armed = True
        next_state.armed_mode = mode if mode in {"away", "stay", "unknown"} else "unknown"
        next_state.armed_stay = next_state.armed_mode == "stay"
        next_state.alarming = False
        next_state.panic = False
    elif event.type == "panel_disarmed":
        next_state.armed = False
        next_state.armed_stay = False
        next_state.armed_mode = "disarmed"
        next_state.alarming = False
        next_state.panic = False
    elif event.type == "command_sent":
        next_state.last_command = str(data.get("keys", ""))
        next_state.beeps = int(data.get("beeps", 1))
    elif event.type == "arm":
        stay = bool(data.get("stay", False))
        next_state.armed = True
        next_state.armed_stay = stay
        next_state.armed_mode = "stay" if stay else "away"
        next_state.ready = False
        next_state.alarming = False
        next_state.display_line1 = "ARMED STAY" if stay else "ARMED AWAY"
        next_state.display_line2 = "EXIT NOW" if not stay else "INSTANT"
        next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 2
    elif event.type == "disarm":
        next_state.armed = False
        next_state.armed_stay = False
        next_state.armed_mode = "disarmed"
        next_state.alarming = False
        next_state.panic = False
        next_state.fire_detected = False
        next_state.ready = len(next_state.faulted_zones) == 0
        next_state.display_line1 = "DISARMED"
        next_state.display_line2 = "READY" if next_state.ready else "CHECK ZONES"
        next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 1
    elif event.type == "chime_changed":
        next_state.chime = bool(data.get("enabled", not next_state.chime))
        next_state.beeps = 1
    elif event.type == "zone_fault":
        zone = int(data.get("zone", 0))
        if zone and zone not in next_state.faulted_zones:
            next_state.faulted_zones.append(zone)
            next_state.faulted_zones.sort()
        next_state.ready = False
        # Only overwrite LCD display text if it's currently empty
        if not next_state.last_message or not next_state.last_message.strip():
            next_state.display_line1 = f"FAULT ZONE {zone}"
            next_state.display_line2 = str(data.get("name", f"Zone {zone}"))[:16]
            next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 3 if next_state.chime else 0
    elif event.type == "zone_restore":
        zone = int(data.get("zone", 0))
        if zone:
            next_state.faulted_zones = [z for z in next_state.faulted_zones if z != zone]
        else:
            next_state.faulted_zones = []
        next_state.ready = len(next_state.faulted_zones) == 0 and not next_state.armed
        # Only overwrite LCD display text if it's currently showing a fault or empty
        if not next_state.last_message or "FAULT" in next_state.last_message.upper():
            next_state.display_line1 = "SYSTEM READY" if next_state.ready else "ZONE RESTORED"
            next_state.display_line2 = f"ZONE {zone}" if not next_state.ready else "ALL ZONES OK"
            next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 1
    elif event.type in {"alarm", "alarm_active"}:
        zone = data.get("zone", "?")
        active = bool(data.get("active", True))
        next_state.alarming = active
        next_state.display_line1 = "ALARM"
        next_state.display_line2 = f"ZONE {zone}"
        next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 7 if active else 1
    elif event.type in {"fire", "fire_alarm"}:
        next_state.fire_detected = bool(data.get("active", True))
        next_state.display_line1 = "FIRE ALARM" if next_state.fire_detected else "FIRE RESTORED"
        next_state.display_line2 = "VERIFY PANEL"
        next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 7 if next_state.fire_detected else 1
    elif event.type in {"panic", "panic_alarm"}:
        next_state.panic = bool(data.get("active", True))
        next_state.display_line1 = "PANIC" if next_state.panic else "PANIC RESTORED"
        next_state.display_line2 = "VERIFY PANEL" if event.type == "panic_alarm" else "SENT"
        next_state.last_message = f"{next_state.display_line1:<16}{next_state.display_line2:<16}"
        next_state.beeps = 7 if next_state.panic else 1
    elif event.type == "power_changed":
        power = data.get("power", next_state.power)
        if power in {"AC", "BATTERY", "UNKNOWN"}:
            next_state.power = power
        if next_state.power == "AC":
            next_state.trouble = False if next_state.trouble_text in {"AC LOSS", "NO AC"} else next_state.trouble
        next_state.beeps = 2
    elif event.type == "low_battery":
        next_state.battery_trouble = bool(data.get("active", True))
        next_state.trouble = next_state.battery_trouble
        next_state.trouble_text = "Low battery" if next_state.battery_trouble else None
        next_state.beeps = 2
    elif event.type == "trouble":
        next_state.trouble = bool(data.get("active", True))
        next_state.trouble_text = str(data.get("text", event.message)) if next_state.trouble else None
    elif event.type == "bypass":
        next_state.bypassed = bool(data.get("active", True))
    elif event.type == "relay_changed":
        relay = str(data.get("relay", ""))
        if relay:
            next_state.relay_status[relay] = bool(data.get("active", False))

    next_state.updated_at = datetime.now(timezone.utc)
    return next_state


def initial_panel_state() -> PanelState:
    return PanelState(
        display_line1="ALARMDECODER",
        display_line2="CONNECTING...",
        last_message="ALARMDECODER    CONNECTING...",
    )
