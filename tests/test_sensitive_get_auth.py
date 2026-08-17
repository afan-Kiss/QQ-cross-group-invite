# -*- coding: utf-8 -*-
from __future__ import annotations


def test_owned_sensitive_get_requires_session(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_ID", "owned")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)
    monkeypatch.setattr(
        svc,
        "load_cfg",
        lambda: {
            "target_group_id": "1",
            "source_group_id": "2",
            "batch_count": "20",
            "interval_ms": "1500",
            "filter_staff": True,
            "onebot_url": "",
            "napcat_webui_token": "",
        },
    )
    monkeypatch.setattr(svc, "get_state", lambda: {"running": False, "status": "idle"})
    monkeypatch.setattr(svc, "get_cached_members", lambda: [])
    monkeypatch.setattr(svc, "list_tasks", lambda: [])
    monkeypatch.setattr(svc, "get_task", lambda tid: None)

    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)

    for path in ("/config", "/status", "/members", "/tasks", "/tasks/abc"):
        h = svc.Handler.__new__(svc.Handler)
        h.headers = {}  # type: ignore[attr-defined]
        h.path = path
        h.do_GET()
        assert captured["code"] == 403, path
        assert captured["body"]["code"] == "UNAUTHORIZED"

        h2 = svc.Handler.__new__(svc.Handler)
        h2.headers = {"X-App-Session": "owned"}  # type: ignore[attr-defined]
        h2.path = path
        h2.do_GET()
        assert captured["code"] in (200, 404), path


def test_unlocked_sensitive_get_allows_missing_header(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_ID", "ext")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(
        svc,
        "load_cfg",
        lambda: {
            "target_group_id": "1",
            "source_group_id": "2",
            "batch_count": "20",
            "interval_ms": "1500",
            "filter_staff": True,
            "onebot_url": "",
            "napcat_webui_token": "secret",
        },
    )
    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)
    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/config"
    h.do_GET()
    assert captured["code"] == 200
    assert captured["body"]["napcat_webui_token"] == ""
    assert captured["body"]["has_napcat_token"] is True


def test_health_always_open(monkeypatch):
    import cross_group_service as svc
    import napcat_health

    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)
    monkeypatch.setattr(svc, "SESSION_ID", "owned")
    monkeypatch.setattr(
        napcat_health,
        "_state",
        {"online": False, "message": "饭饭定制 offline", "checked_at": 1.0},
    )
    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)
    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/health"
    h.do_GET()
    assert captured["code"] == 200
    assert captured["body"]["ok"] is True
