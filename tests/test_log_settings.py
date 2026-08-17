# -*- coding: utf-8 -*-
from __future__ import annotations


def test_safe_int_and_parse_log_settings():
    from log_settings import parse_log_settings, safe_int

    assert safe_int("abc", 5, min_v=1, max_v=10) == 5
    assert safe_int("0", 5, min_v=1, max_v=10) == 5
    assert safe_int("1", 5, min_v=1, max_v=10) == 1
    assert safe_int("1024", 5, min_v=1, max_v=1024) == 1024
    assert safe_int("1025", 5, min_v=1, max_v=1024) == 5

    parsed = parse_log_settings(
        {
            "max_log_file_mb": "abc",
            "log_retention_days": "xyz",
            "log_level": "nope",
            "auto_clean_logs": True,
        }
    )
    assert parsed["max_log_file_mb"] == 5
    assert parsed["log_retention_days"] == 7
    assert parsed["log_level"] == "INFO"
    assert parsed["backup_count"] == 5


def test_validate_log_settings_payload_bounds():
    import pytest
    from log_settings import validate_log_settings_payload

    validate_log_settings_payload({"max_log_file_mb": 1, "log_retention_days": 1, "log_level": "INFO"})
    validate_log_settings_payload({"max_log_file_mb": 1024, "log_retention_days": 3650})

    with pytest.raises(ValueError):
        validate_log_settings_payload({"max_log_file_mb": "abc"})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"max_log_file_mb": 0})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"max_log_file_mb": 1025})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"log_retention_days": "abc"})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"log_retention_days": 0})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"log_retention_days": 3651})
    with pytest.raises(ValueError):
        validate_log_settings_payload({"log_level": "DEBUG"})


def test_config_post_rejects_bad_log_settings(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "SESSION_ID", "x")
    monkeypatch.setattr(svc, "load_cfg", lambda: {})
    saved = {"n": 0}
    monkeypatch.setattr(svc, "save_cfg", lambda _cfg: saved.__setitem__("n", saved["n"] + 1))
    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)

    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/config"
    h._read_json = lambda: {"max_log_file_mb": "abc"}  # type: ignore[method-assign]
    h.do_POST()
    assert captured["code"] == 400
    assert captured["body"]["code"] == "INVALID_ARGUMENT"
    assert saved["n"] == 0


def test_sidecar_init_tolerates_corrupt_log_cfg():
    from log_settings import parse_log_settings
    from service_logger import setup_service_logger

    cfg = {
        "max_log_file_mb": "abc",
        "log_retention_days": "nope",
        "log_level": "???",
        "auto_clean_logs": True,
    }
    log_cfg = parse_log_settings(cfg)
    logger = setup_service_logger(
        name="hotfix-bad-cfg",
        level=log_cfg["log_level"],
        max_bytes=log_cfg["max_log_file_mb"] * 1024 * 1024,
        backup_count=log_cfg["backup_count"],
        retention_days=log_cfg["log_retention_days"],
        auto_clean_logs=False,
    )
    assert logger is not None
