from __future__ import annotations

import logging
import sys


def _configure_root_logger(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(numeric_level)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    _configure_root_logger(level)
    return logging.getLogger(name)


def get_session_logger(name: str, session_id: str) -> logging.LoggerAdapter:  # type: ignore[type-arg]
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, {"session_id": session_id})
