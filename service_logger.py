# -*- coding: utf-8 -*-
"""Rotating file logger for the cross-group sidecar service."""
from __future__ import annotations

import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QQCrossGroupInvite" / "logs"
LOG_FILE = LOG_DIR / "service.log"

# Only delete matching app log files; never recurse into unrelated trees.
_LOG_NAME_RE = re.compile(r"^(service|app)\.log(\.\d+)?$", re.IGNORECASE)

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(\"token\"\s*:\s*\")([^\"]+)(\")"), r"\1***\3"),
    (re.compile(r"(?i)(u_[A-Za-z0-9+/=_-]{8,})"), "***"),
    (re.compile(r"(?i)(context[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(Authorization\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(onebot[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(napcat[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(napcat[_-]?webui[_-]?token\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(password\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(\"password\"\s*:\s*\")([^\"]+)(\")"), r"\1***\3"),
    (re.compile(r"(?i)(session[_-]?id\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(X-App-Session\s*[:=]\s*)(\S+)"), r"\1***"),
    (re.compile(r"(?i)(cookie\s*[:=]\s*)(\S+)"), r"\1***"),
]


class _SanitizeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in _SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


def sanitize_text(text: str) -> str:
    out = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def cleanup_old_logs(
    log_dir: Path | None = None,
    *,
    retention_days: int,
    auto_clean: bool,
    now: float | None = None,
) -> list[str]:
    """Delete expired app log files by mtime when auto_clean is enabled.

    Returns list of deleted file names (not full paths with secrets).
    """
    if not auto_clean:
        return []
    days = max(1, int(retention_days))
    root = Path(log_dir) if log_dir is not None else LOG_DIR
    if not root.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - days * 86400
    deleted: list[str] = []
    try:
        for entry in root.iterdir():
            if not entry.is_file():
                continue
            if not _LOG_NAME_RE.match(entry.name):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                try:
                    entry.unlink()
                    deleted.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return deleted
    return deleted


def setup_service_logger(
    name: str = "cross-group-service",
    *,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    retention_days: int = 7,
    auto_clean_logs: bool = True,
) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # backupCount is rotation depth, independent of retention_days.
    cleanup_old_logs(
        LOG_DIR,
        retention_days=retention_days,
        auto_clean=auto_clean_logs,
    )

    logger = logging.getLogger(name)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()

    level_name = str(level).upper()
    if level_name == "WARN":
        level_name = "WARNING"
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=max(1024 * 1024, int(max_bytes)),
        backupCount=max(1, int(backup_count)),
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler.addFilter(_SanitizeFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
