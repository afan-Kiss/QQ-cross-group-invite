# -*- coding: utf-8 -*-
from __future__ import annotations


def _post_config(monkeypatch, payload: dict):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    saved: dict = {"n": 0, "cfg": None}

    def fake_save(cfg):
        saved["n"] += 1
        saved["cfg"] = dict(cfg)

    monkeypatch.setattr(svc, "load_cfg", lambda: {"interval_ms": "1500", "batch_count": "20"})
    monkeypatch.setattr(svc, "save_cfg", fake_save)

    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)

    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/config"
    h._read_json = lambda: payload  # type: ignore[method-assign]
    h.do_POST()
    return captured.get("code"), captured.get("body"), saved


def test_config_rejects_batch_zero(monkeypatch):
    code, body, saved = _post_config(monkeypatch, {"batch_count": 0})
    assert code == 400
    assert saved["n"] == 0
    assert "batch_count" in str(body)


def test_config_rejects_interval_zero(monkeypatch):
    code, body, saved = _post_config(monkeypatch, {"interval_ms": 0})
    assert code == 400
    assert saved["n"] == 0
    assert "interval_ms" in str(body)


def test_config_rejects_batch_abc(monkeypatch):
    code, body, saved = _post_config(monkeypatch, {"batch_count": "abc"})
    assert code == 400
    assert saved["n"] == 0


def test_config_rejects_same_groups(monkeypatch):
    code, body, saved = _post_config(
        monkeypatch,
        {"source_group_id": "10001", "target_group_id": "10001"},
    )
    assert code == 400
    assert saved["n"] == 0


def test_config_rejects_filter_staff_string(monkeypatch):
    code, body, saved = _post_config(monkeypatch, {"filter_staff": "false"})
    assert code == 400
    assert saved["n"] == 0
    assert "filter_staff" in str(body)


def test_config_accepts_valid_payload(monkeypatch):
    code, body, saved = _post_config(
        monkeypatch,
        {
            "source_group_id": "10001",
            "target_group_id": "20002",
            "batch_count": "10",
            "interval_ms": "1500",
            "filter_staff": True,
        },
    )
    assert code == 200
    assert saved["n"] == 1
    assert saved["cfg"]["batch_count"] == "10"
    assert saved["cfg"]["filter_staff"] is True


def test_get_config_default_interval_1500(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "load_cfg", lambda: {})
    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)
    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/config"
    h.client_address = ("127.0.0.1", 1)
    # sensitive GET may require session - bypass by calling payload path directly
    # Use do_GET with _require_owned_read mocked
    monkeypatch.setattr(svc, "_require_owned_read", lambda self: False)
    monkeypatch.setattr(svc, "_is_sensitive_get", lambda path: False)
    h.do_GET()
    assert captured["code"] == 200
    assert captured["body"]["interval_ms"] == "1500"


def test_invite_start_rejects_qq_list_string(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "check_napcat_online", lambda: (True, "ok"))
    calls: list = []
    monkeypatch.setattr(svc, "start_batch", lambda **k: calls.append(k) or "t1")
    captured: dict = {}
    monkeypatch.setattr(
        svc,
        "_json_response",
        lambda handler, code, obj: captured.update(code=code, body=obj),
    )
    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/invite/start"
    h._read_json = lambda: {  # type: ignore[method-assign]
        "source_group_id": 100,
        "target_group_id": 200,
        "batch_count": 10,
        "interval_ms": 1500,
        "filter_staff": True,
        "qq_list": "12345",
    }
    h.do_POST()
    assert captured["code"] == 400
    assert calls == []
    assert "qq_list" in str(captured["body"])
