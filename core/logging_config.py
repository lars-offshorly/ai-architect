from __future__ import annotations

import logging
import sys
from typing import Optional

from .settings import get_settings


_state = {"configured": False}
_LOGGER_ROOT = "ai_architect"


class SessionLoggerAdapter(logging.LoggerAdapter):
    def process(
        self,
        msg: object,
        kwargs: dict[str, object],
    ) -> tuple[object, dict[str, object]]:
        session_id = self.extra.get("session_id")
        prefix = f"[session:{session_id}] " if session_id else ""
        return f"{prefix}{msg}", kwargs


class ContextLoggerAdapter(SessionLoggerAdapter):
    def process(
        self,
        msg: object,
        kwargs: dict[str, object],
    ) -> tuple[object, dict[str, object]]:
        message, metadata = super().process(msg, kwargs)
        user_id = self.extra.get("user_id")
        prefix = f"[user:{user_id}] " if user_id else ""
        return f"{prefix}{message}", metadata


def _resolve_log_level() -> int:
    settings = get_settings()
    configured_level = settings.LOG_LEVEL.upper()
    return int(getattr(logging, configured_level, logging.INFO))


def configure_logging(level: Optional[int] = None) -> None:
    if _state["configured"]:
        return

    log_level = level if level is not None else _resolve_log_level()
    root_logger = logging.getLogger(_LOGGER_ROOT)
    root_logger.setLevel(log_level)
    root_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    _state["configured"] = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    configure_logging()
    if name is None:
        return logging.getLogger(_LOGGER_ROOT)

    if name.startswith(_LOGGER_ROOT):
        return logging.getLogger(name)

    return logging.getLogger(f"{_LOGGER_ROOT}.{name}")


def get_session_logger(
    name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> logging.LoggerAdapter:
    logger = get_logger(name)
    return SessionLoggerAdapter(logger, {"session_id": session_id})


def get_context_logger(
    name: Optional[str] = None,
    workflow_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> logging.LoggerAdapter:
    logger = get_logger(name)
    return ContextLoggerAdapter(
        logger,
        {
            "session_id": workflow_id,
            "user_id": user_id,
        },
    )
