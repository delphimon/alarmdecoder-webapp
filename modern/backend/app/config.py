from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    adapter: str
    ser2sock_host: str
    ser2sock_port: int
    read_only: bool
    ser2sock_tls: bool = False
    serial_path: str = "/dev/ttyUSB0"
    serial_baudrate: int = 115200
    panel_type: str = "ADEMCO"
    allow_commands: bool = False
    auth_required: bool = False
    database_url: str = "sqlite:///:memory:"
    session_secret: str = "dev-only-change-me"
    access_token_minutes: int = 480
    command_cooldown_seconds: float = 1.5
    raw_retention_days: int = 14
    event_retention_days: int = 90
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None
    reconnect_initial_delay_seconds: float = 0.25
    reconnect_max_delay_seconds: float = 8.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        adapter = os.getenv("ALARMDECODER_ADAPTER", "fake").strip().lower()
        read_only_default = adapter != "fake"
        default_db_path = Path(os.getenv("ALARMDECODER_DATA_DIR", ".")).joinpath("alarmdecoder-modern.db")
        return cls(
            adapter=adapter,
            ser2sock_host=os.getenv("ALARMDECODER_SER2SOCK_HOST", "alarmdecoder.local").strip(),
            ser2sock_port=int(os.getenv("ALARMDECODER_SER2SOCK_PORT", "10000")),
            ser2sock_tls=_env_bool("ALARMDECODER_SER2SOCK_TLS", False),
            serial_path=os.getenv("ALARMDECODER_SERIAL_PATH", "/dev/ttyUSB0").strip(),
            serial_baudrate=int(os.getenv("ALARMDECODER_SERIAL_BAUDRATE", "115200")),
            panel_type=os.getenv("ALARMDECODER_PANEL_TYPE", "ADEMCO").strip().upper(),
            read_only=_env_bool("ALARMDECODER_READ_ONLY", read_only_default),
            allow_commands=_env_bool("ALARMDECODER_ALLOW_COMMANDS", adapter == "fake"),
            auth_required=_env_bool("ALARMDECODER_AUTH_REQUIRED", adapter != "fake"),
            database_url=os.getenv("ALARMDECODER_DATABASE_URL", f"sqlite:///{default_db_path}").strip(),
            session_secret=os.getenv("ALARMDECODER_SESSION_SECRET", "dev-only-change-me"),
            access_token_minutes=int(os.getenv("ALARMDECODER_ACCESS_TOKEN_MINUTES", "480")),
            command_cooldown_seconds=float(os.getenv("ALARMDECODER_COMMAND_COOLDOWN_SECONDS", "1.5")),
            raw_retention_days=int(os.getenv("ALARMDECODER_RAW_RETENTION_DAYS", "14")),
            event_retention_days=int(os.getenv("ALARMDECODER_EVENT_RETENTION_DAYS", "90")),
            bootstrap_admin_username=os.getenv("ALARMDECODER_BOOTSTRAP_ADMIN_USERNAME"),
            bootstrap_admin_password=os.getenv("ALARMDECODER_BOOTSTRAP_ADMIN_PASSWORD"),
        )

    def safe_public_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "ser2sock_host": self.ser2sock_host,
            "ser2sock_port": self.ser2sock_port,
            "ser2sock_tls": self.ser2sock_tls,
            "serial_path": self.serial_path,
            "serial_baudrate": self.serial_baudrate,
            "panel_type": self.panel_type,
            "read_only": self.read_only,
            "allow_commands": self.allow_commands,
            "auth_required": self.auth_required,
            "database_url": _redact_database_url(self.database_url),
            "reconnect_initial_delay_seconds": self.reconnect_initial_delay_seconds,
            "reconnect_max_delay_seconds": self.reconnect_max_delay_seconds,
            "command_cooldown_seconds": self.command_cooldown_seconds,
            "raw_retention_days": self.raw_retention_days,
            "event_retention_days": self.event_retention_days,
        }


def _redact_database_url(url: str) -> str:
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://<redacted>@{rest.split('@', 1)[1]}"
