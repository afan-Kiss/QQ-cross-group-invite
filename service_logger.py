# -*- coding: utf-8 -*-
"""Rotating file logger for the cross-group sidecar service."""
from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QQCrossGroupInvite" / "logs"
LOG_FILE = LOG_DIR / "service.log"

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(\"token\"\s*:\s*\")([^\"]+)(\")"), r"\1***\3"),
    (re.compile(r"(?i)(u_[A-Za-z0-9+/=_-]{8,})"), "***"),
    (re.compile(r"(?i)(context[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(Authorization\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(onebot[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(napcat[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
]


class _SanitizeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in _SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


def setup_service_logger(name: str = "cross-group-service") -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler.addFilter(_SanitizeFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
