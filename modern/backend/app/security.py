from __future__ import annotations

import re


REDACTED_COMMAND = "<redacted-command>"


def redact_command(value: str | None) -> str:
    if not value:
        return REDACTED_COMMAND
    normalized = re.sub(r"\s+", "", value)
    return f"{REDACTED_COMMAND}:{len(normalized)}"


def command_metadata(value: str) -> dict[str, object]:
    normalized = re.sub(r"\s+", "", value)
    return {
        "redacted": redact_command(normalized),
        "length": len(normalized),
        "has_digits": any(char.isdigit() for char in normalized),
        "has_function_keys": bool(re.search(r"F[1-4]", normalized.upper())),
    }
