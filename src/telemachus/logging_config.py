"""Structured logging configuration for Telemachus.

Provides JSON-formatted structured logging with file rotation
and configurable log levels.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from typing import Any

from telemachus.config import TelemachusConfig


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        extra = getattr(record, "extra", None)
        if extra and isinstance(extra, dict):
            log_entry["extra"] = extra

        return json.dumps(log_entry, default=str)


class PlainFormatter(logging.Formatter):
    """Standard human-readable log formatter."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )


def setup_logging(config: TelemachusConfig) -> logging.Logger:
    """Initialize structured logging for the Telemachus system.

    Configures the root 'telemachus' logger with both console (plain text)
    and file (JSON) handlers. File logs rotate based on size.

    Args:
        config: Validated TelemachusConfig instance.

    Returns:
        The root 'telemachus' logger.
    """
    log_dir = config.paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.logging.level.upper(), logging.INFO)

    root_logger = logging.getLogger("telemachus")
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    # Console handler — human-readable
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(PlainFormatter())
    root_logger.addHandler(console_handler)

    # File handler — JSON structured, with rotation
    log_file = log_dir / "telemachus.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialized",
        extra={"extra": {"log_dir": str(log_dir), "level": config.logging.level}},
    )

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the 'telemachus' namespace.

    Args:
        name: The logger name suffix, e.g. 'memory.store' becomes 'telemachus.memory.store'.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(f"telemachus.{name}")
