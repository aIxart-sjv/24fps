"""
Location: 24fps/backend/app/logging/forensic_logger.py

Structured JSON logging foundation shared by both technical application
logs and, later, forensic processing logs (Master Specification Section
68 distinguishes these two categories but requires both to be
structured and traceable, not free-form print statements).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings


class JsonLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a `LogRecord` into a JSON string.

        Args:
            record: The log record emitted by the logging framework.

        Returns:
            A JSON-encoded string representing the log entry.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extra_fields = getattr(record, "forensic_context", None)
        if isinstance(extra_fields, dict):
            payload["context"] = extra_fields

        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED_LOGGERS: set[str] = set()


def get_logger(name: str, log_filename: str = "application.log") -> logging.Logger:
    """Return a configured, JSON-structured logger instance.

    Writes simultaneously to stdout (local development visibility) and
    to an append-mode file under the configured `log_root`. Configuration
    is idempotent: repeated calls with the same `(name, log_filename)`
    pair will not duplicate handlers.

    Args:
        name: Dotted logger name, conventionally the calling module's
            `__name__`.
        log_filename: Filename (relative to `settings.log_root`) that
            this logger's file handler writes to. Distinct subsystems
            may supply distinct filenames to physically separate log
            streams (e.g. future `acquisition.log`, `recovery.log`).

    Returns:
        A `logging.Logger` configured with JSON formatting on both a
        stream handler and a file handler.

    Raises:
        OSError: If the configured log directory cannot be created or
            the log file cannot be opened for appending.
    """
    settings = get_settings()
    logger = logging.getLogger(name)

    dedup_key = f"{name}:{log_filename}"
    if dedup_key in _CONFIGURED_LOGGERS:
        return logger

    settings.log_root.mkdir(parents=True, exist_ok=True)
    log_path: Path = settings.log_root / log_filename

    formatter = JsonLogFormatter()

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(filename=str(log_path), encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.setLevel(settings.log_level.value)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    _CONFIGURED_LOGGERS.add(dedup_key)
    return logger
