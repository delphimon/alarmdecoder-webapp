from __future__ import annotations

import json
import logging

from .config import AppConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def log_startup_config(config: AppConfig) -> None:
    logger = logging.getLogger("alarmdecoder.startup")
    logger.info("effective_config %s", config.safe_public_dict())
    if config.adapter != "fake" and not config.read_only and config.allow_commands:
        logger.warning("hardware command mode is enabled")
    if config.session_secret == "dev-only-change-me" and config.auth_required:
        logger.warning("default session secret is configured while auth is required")
