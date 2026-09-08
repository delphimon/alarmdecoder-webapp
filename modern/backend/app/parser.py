from __future__ import annotations

import re

from .models import PanelEvent


QUOTED_TEXT_RE = re.compile(r'"([^"]*)"')
ZONE_RE = re.compile(r"\b(?:ZONE|ZN|FAULT|ALARM)\s*0*(\d{1,3})\b", re.IGNORECASE)
AD2_KEYPAD_RE = re.compile(
    r"^\[(?P<flags>[^\]]+)\],(?P<beeps>\d{3}),\[(?P<metadata>[^\]]*)\],\"(?P<text>.*)\"$"
)


def parse_alarmdecoder_line(line: str) -> list[PanelEvent]:
    """Parse one read-only AlarmDecoder line into domain events.

    The parser is deliberately tolerant: every non-empty line is preserved as a
    raw diagnostic event, and malformed or unknown protocol lines become
    unknown_message events instead of exceptions.
    """

    raw = line.strip("\r\n")
    if not raw:
        return []

    events = [PanelEvent(type="raw_message", message=raw, data={"raw": raw})]

    parsed = _parse_keypad_message(raw)
    text = parsed["display_text"]
    semantic_count = 0

    if text:
        display_event = _panel_display_event(text, raw, parsed)
        events.append(display_event)
        semantic_count += 1
        semantic_events = _semantic_events(text)
        events.extend(semantic_events)
        semantic_count += len(semantic_events)
    else:
        protocol_event = _parse_non_keypad_message(raw)
        if protocol_event is not None:
            events.append(protocol_event)
            semantic_count += 1

    if semantic_count == 0:
        events.append(
            PanelEvent(
                type="unknown_message",
                message="Unrecognized AlarmDecoder message",
                data={"raw": raw},
            )
        )

    return events


def _parse_keypad_message(raw: str) -> dict[str, object]:
    match = AD2_KEYPAD_RE.match(raw)
    if match:
        display_text = match.group("text")
        flags_str = match.group("flags")
        return {
            "display_text": display_text,
            "flags": flags_str,
            "parsed_flags": _parse_keypad_flags(flags_str),
            "metadata": match.group("metadata"),
            "beeps": _coerce_beeps(match.group("beeps")),
            "format": "keypad",
        }

    quoted = QUOTED_TEXT_RE.findall(raw)
    if quoted:
        return {
            "display_text": quoted[-1],
            "flags": None,
            "parsed_flags": {},
            "metadata": None,
            "beeps": _extract_beeps(raw),
            "format": "quoted",
        }

    return {
        "display_text": "",
        "flags": None,
        "parsed_flags": {},
        "metadata": None,
        "beeps": _extract_beeps(raw),
        "format": "unknown",
    }


def _parse_keypad_flags(flags_str: str) -> dict:
    """Parse the AlarmDecoder bracket-encoded flag string into named booleans.

    The AlarmDecoder flag string captured between the first pair of square
    brackets is a 20-character sequence where each position is either '1'
    (bit set) or '0'/'.' (bit clear).  Positions 5-7 encode the beep count
    as a 3-digit decimal substring (e.g. '003').

    Position map (0-indexed):
        0  ready
        1  armed_away
        2  armed_stay
        3  backlight
        4  programming_mode
        5-7  beeps (3-character decimal string)
        8  zone_bypassed
        9  ac_power
        10 chime
        11 alarm_occurred
        12 alarm_sounding
        13 battery_low
        14 entry_delay_off
        15 fire
        16 check_zones
        17 perimeter_only
        18 system_fault
        19 panel_type_dsc
    """
    if not flags_str or len(flags_str) < 20:
        return {}

    def bit(pos: int) -> bool:
        return flags_str[pos] == "1"

    try:
        beep_count = int(flags_str[5:8])
    except ValueError:
        beep_count = 0

    return {
        "ready": bit(0),
        "armed_away": bit(1),
        "armed_stay": bit(2),
        "backlight": bit(3),
        "programming_mode": bit(4),
        "beeps": beep_count,
        "zone_bypassed": bit(8),
        "ac_power": bit(9),
        "chime": bit(10),
        "alarm_occurred": bit(11),
        "alarm_sounding": bit(12),
        "battery_low": bit(13),
        "entry_delay_off": bit(14),
        "fire": bit(15),
        "check_zones": bit(16),
        "perimeter_only": bit(17),
        "system_fault": bit(18),
        "panel_type_dsc": bit(19),
    }


def _panel_display_event(text: str, raw: str, parsed: dict[str, object]) -> PanelEvent:
    padded = text[:32].ljust(32)
    line1, line2 = _split_lcd(padded)
    normalized = _normalize_display_text(text)
    return PanelEvent(
        type="panel_display",
        message=normalized or text.strip(),
        data={
            "text": padded,
            "line1": line1,
            "line2": line2,
            "display_text": text,
            "normalized": normalized,
            "beeps": parsed.get("beeps", 0),
            "flags": parsed.get("flags"),
            "parsed_flags": parsed.get("parsed_flags", {}),
            "metadata": parsed.get("metadata"),
            "format": parsed.get("format"),
            "raw": raw,
        },
    )



def _semantic_events(text: str) -> list[PanelEvent]:
    normalized = _normalize_display_text(text)
    upper = normalized.upper()
    events: list[PanelEvent] = []
    zone = _extract_zone(upper)

    ready = _ready_status(upper)
    if ready is not None:
        events.append(
            PanelEvent(
                type="panel_ready",
                message="Panel ready" if ready else "Panel not ready",
                data={"ready": ready, "text": normalized},
            )
        )

    arm_mode = _arm_mode(upper)
    if arm_mode in {"away", "stay", "unknown"}:
        events.append(
            PanelEvent(
                type="panel_armed",
                message=f"Panel armed {arm_mode}",
                data={"mode": arm_mode, "text": normalized},
            )
        )
    elif arm_mode == "disarmed":
        events.append(
            PanelEvent(
                type="panel_disarmed",
                message="Panel disarmed",
                data={"text": normalized},
            )
        )

    if "CHIME" in upper:
        enabled = not any(token in upper for token in ("CHIME OFF", "OFF"))
        events.append(
            PanelEvent(
                type="chime_changed",
                message=f"Chime {'enabled' if enabled else 'disabled'}",
                data={"enabled": enabled, "text": normalized},
            )
        )

    if "BYPASS" in upper:
        events.append(
            PanelEvent(
                type="bypass",
                message=normalized,
                data={"active": "RESTORE" not in upper and "CLEAR" not in upper, "zone": zone, "text": normalized},
            )
        )

    if "RELAY" in upper:
        relay_match = re.search(r"RELAY\s*0*(\d{1,2}).*\b(ON|OFF)\b", upper)
        if relay_match:
            events.append(
                PanelEvent(
                    type="relay_changed",
                    message=normalized,
                    data={"relay": relay_match.group(1), "active": relay_match.group(2) == "ON", "text": normalized},
                )
            )

    if _is_fire_alarm(upper):
        active = "RESTORE" not in upper and "RESTORED" not in upper
        events.append(
            PanelEvent(
                type="fire_alarm",
                message="Fire alarm active" if active else "Fire alarm restored",
                data={"active": active, "zone": zone, "text": normalized},
            )
        )

    if _is_panic_alarm(upper):
        active = "RESTORE" not in upper and "RESTORED" not in upper
        events.append(
            PanelEvent(
                type="panic_alarm",
                message="Panic alarm active" if active else "Panic alarm restored",
                data={"active": active, "text": normalized},
            )
        )

    if _is_burglary_alarm(upper):
        active = "RESTORE" not in upper and "RESTORED" not in upper
        events.append(
            PanelEvent(
                type="alarm_active",
                message="Alarm active" if active else "Alarm restored",
                data={"active": active, "zone": zone, "text": normalized},
            )
        )

    power = _power_status(upper)
    if power is not None:
        events.append(
            PanelEvent(
                type="power_changed",
                message=f"Panel power changed to {power}",
                data={"power": power, "text": normalized},
            )
        )

    low_battery = _low_battery_status(upper)
    if low_battery is not None:
        events.append(
            PanelEvent(
                type="low_battery",
                message="Low battery detected" if low_battery else "Low battery restored",
                data={"active": low_battery, "text": normalized},
            )
        )

    zone_event = _zone_event(upper, zone)
    if zone_event is not None:
        events.append(zone_event)

    trouble = _trouble_status(upper)
    if trouble is not None:
        events.append(
            PanelEvent(
                type="trouble",
                message=normalized,
                data={"active": trouble, "text": normalized},
            )
        )

    return events


def _parse_non_keypad_message(raw: str) -> PanelEvent | None:
    upper = raw.upper()
    if upper.startswith("!BOOT") or "BOOT" in upper:
        return PanelEvent(type="boot", message="AlarmDecoder boot message", data={"raw": raw})
    if upper.startswith("!CONFIG") or upper.startswith("!VER") or upper.startswith("!ADDRESS"):
        return PanelEvent(type="config_received", message="AlarmDecoder configuration message", data=_structured_family_data(raw, raw[1:].split(":", 1)[0] if raw.startswith("!") else "CONFIG"))
    if raw.startswith("!LRR"):
        return PanelEvent(type="lrr", message="Long-range radio event", data=_structured_family_data(raw, "LRR"))
    if raw.startswith("!RFX"):
        return PanelEvent(type="rfx", message="Wireless receiver event", data=_structured_family_data(raw, "RFX"))
    if raw.startswith("!EXP"):
        return PanelEvent(type="exp", message="Zone expander event", data=_structured_family_data(raw, "EXP"))
    if raw.startswith("!AUI"):
        return PanelEvent(type="aui", message="AUI event", data=_structured_family_data(raw, "AUI"))
    return None


def _structured_family_data(raw: str, family: str) -> dict[str, object]:
    payload = raw[4:] if raw.startswith(f"!{family}") else raw
    parts = [part.strip() for part in payload.split(",") if part.strip()]
    fields: dict[str, object] = {}
    for index, part in enumerate(parts):
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key.strip().lower()] = value.strip()
        else:
            fields[f"field_{index + 1}"] = part
    return {"raw": raw, "family": family, "fields": fields}


def _ready_status(upper: str) -> bool | None:
    if "NOT READY" in upper:
        return False
    if any(token in upper for token in ("FAULT", "OPEN", "CHECK ")):
        return False
    if "READY TO ARM" in upper or "SYSTEM READY" in upper:
        return True
    if re.search(r"\bREADY\b", upper):
        return True
    return None


def _arm_mode(upper: str) -> str | None:
    if "DISARMED" in upper or "READY TO ARM" in upper:
        return "disarmed"
    if "ARMED" not in upper:
        return None
    if "AWAY" in upper:
        return "away"
    if "STAY" in upper:
        return "stay"
    return "unknown"


def _is_burglary_alarm(upper: str) -> bool:
    if "FIRE" in upper or "PANIC" in upper:
        return False
    return "ALARM" in upper or "BURGLARY" in upper


def _is_fire_alarm(upper: str) -> bool:
    return "FIRE" in upper and ("ALARM" in upper or "RESTORE" in upper or "RESTORED" in upper)


def _is_panic_alarm(upper: str) -> bool:
    return "PANIC" in upper and ("ALARM" in upper or "RESTORE" in upper or "RESTORED" in upper)


def _power_status(upper: str) -> str | None:
    if any(token in upper for token in ("AC LOSS", "NO AC", "AC FAIL", "POWER FAIL")):
        return "BATTERY"
    if any(token in upper for token in ("AC RESTORE", "AC RESTORED", "AC OK", "AC POWER")):
        return "AC"
    return None


def _low_battery_status(upper: str) -> bool | None:
    if "LOW BAT" not in upper and "LOWBAT" not in upper and "LOW BATTERY" not in upper:
        return None
    return not ("RESTORE" in upper or "RESTORED" in upper or "OK" in upper)


def _zone_event(upper: str, zone: int | None) -> PanelEvent | None:
    if zone is None:
        return None
    if any(token in upper for token in ("FAULT", "OPEN")):
        return PanelEvent(type="zone_fault", message=f"Zone {zone} faulted", data={"zone": zone})
    if any(token in upper for token in ("RESTORE", "RESTORED", "CLOSED")):
        return PanelEvent(type="zone_restore", message=f"Zone {zone} restored", data={"zone": zone})
    return None


def _trouble_status(upper: str) -> bool | None:
    if any(token in upper for token in ("RESTORE", "RESTORED", "AC OK")):
        return False
    if any(token in upper for token in ("LOW BAT", "LOWBAT", "AC LOSS", "NO AC", "AC FAIL", "CHECK ")):
        return True
    return None


def _split_lcd(text: str) -> tuple[str, str]:
    padded = text[:32].ljust(32)
    return padded[:16].rstrip(), padded[16:32].rstrip()


def _normalize_display_text(text: str) -> str:
    return " ".join(text.replace("*", " ").split())


def _extract_zone(text: str) -> int | None:
    match = ZONE_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def _extract_beeps(raw: str) -> int:
    parts = raw.split(",")
    if len(parts) > 1:
        return _coerce_beeps(parts[1])
    return 0


def _coerce_beeps(raw: str) -> int:
    try:
        return max(0, min(int(raw), 7))
    except ValueError:
        return 0
