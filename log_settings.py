# -*- coding: utf-8 -*-
"""Shared log-settings bounds and safe parsing for sidecar config."""
from __future__ import annotations

from typing import Any

LOG_MAX_FILE_MB_MIN = 1
LOG_MAX_FILE_MB_MAX = 1024
LOG_RETENTION_DAYS_MIN = 1
LOG_RETENTION_DAYS_MAX = 3650
LOG_LEVELS = frozenset({"INFO", "WARN", "WARNING", "ERROR"})
DEFAULT_LOG_MAX_FILE_MB = 5
DEFAULT_LOG_RETENTION_DAYS = 7
DEFAULT_LOG_LEVEL = "INFO"
# RotatingFileHandler backup count is independent of retention days.
DEFAULT_LOG_BACKUP_COUNT = 5


def safe_int(value: Any, default: int, *, min_v: int | None = None, max_v: int | None = None) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default
    if min_v is not None and n < min_v:
        return default
    if max_v is not None and n > max_v:
        return default
    return n


def parse_log_level(value: Any, default: str = DEFAULT_LOG_LEVEL) -> str:
    level = str(value or default).strip().upper()
    if level == "WARNING":
        level = "WARN"
    if level not in {"INFO", "WARN", "ERROR"}:
        return default
    return level


def parse_log_settings(cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = cfg or {}
    max_mb = safe_int(
        cfg.get("max_log_file_mb"),
        DEFAULT_LOG_MAX_FILE_MB,
        min_v=LOG_MAX_FILE_MB_MIN,
        max_v=LOG_MAX_FILE_MB_MAX,
    )
    retention = safe_int(
        cfg.get("log_retention_days"),
        DEFAULT_LOG_RETENTION_DAYS,
        min_v=LOG_RETENTION_DAYS_MIN,
        max_v=LOG_RETENTION_DAYS_MAX,
    )
    auto_clean = cfg.get("auto_clean_logs", True)
    if isinstance(auto_clean, str):
        auto_clean = auto_clean.strip().lower() in {"1", "true", "yes", "on"}
    else:
        auto_clean = bool(auto_clean)
    return {
        "log_level": parse_log_level(cfg.get("log_level")),
        "max_log_file_mb": max_mb,
        "log_retention_days": retention,
        "auto_clean_logs": auto_clean,
        "backup_count": DEFAULT_LOG_BACKUP_COUNT,
    }


def validate_log_settings_payload(data: dict[str, Any]) -> None:
    """Raise ValueError with Chinese message if log fields in payload are invalid."""
    if "log_level" in data:
        level = str(data.get("log_level") or "").strip().upper()
        if level == "WARNING":
            level = "WARN"
        if level not in {"INFO", "WARN", "ERROR"}:
            raise ValueError("log_level ����Ϊ INFO/WARN/ERROR")

    if "max_log_file_mb" in data:
        raw = data.get("max_log_file_mb")
        try:
            n = int(str(raw).strip())
        except (TypeError, ValueError, AttributeError):
            raise ValueError("�����־�ļ�(MB)����Ϊ����") from None
        if n < LOG_MAX_FILE_MB_MIN or n > LOG_MAX_FILE_MB_MAX:
            raise ValueError(f"�����־�ļ�(MB)����Ϊ {LOG_MAX_FILE_MB_MIN}�C{LOG_MAX_FILE_MB_MAX}")

    if "log_retention_days" in data:
        raw = data.get("log_retention_days")
        try:
            n = int(str(raw).strip())
        except (TypeError, ValueError, AttributeError):
            raise ValueError("������������Ϊ����") from None
        if n < LOG_RETENTION_DAYS_MIN or n > LOG_RETENTION_DAYS_MAX:
            raise ValueError(f"������������Ϊ {LOG_RETENTION_DAYS_MIN}�C{LOG_RETENTION_DAYS_MAX}")

    if "auto_clean_logs" in data and not isinstance(data.get("auto_clean_logs"), (bool, int)):
        # allow 0/1 ints; reject arbitrary strings/objects
        if not isinstance(data.get("auto_clean_logs"), bool):
            raise ValueError("auto_clean_logs ����Ϊ����ֵ")
