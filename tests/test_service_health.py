# -*- coding: utf-8 -*-
from __future__ import annotations


def test_build_health_payload_service_id(monkeypatch):
    import napcat_health
    import cross_group_service as svc

    monkeypatch.setattr(
        napcat_health,
        "_state",
        {"online": True, "message": "饭饭定制 online", "checked_at": 1.0},
    )
    monkeypatch.setattr(svc, "SESSION_ID", "sess-test-secret")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)

    payload = svc.build_health_payload()
    assert payload["ok"] is True
    assert payload["service"] == "cross-group-invite"
    assert payload["service"] == svc.SERVICE_ID
    assert "version" in payload
    assert "pid" in payload
    assert "session_id" not in payload
    assert payload.get("session_match") is False
    assert payload["session_required"] is True
    assert payload["owned"] is True
    assert payload["napcat_online"] is True
    assert payload["napcat_message"] == "饭饭定制 online"

    matched = svc.build_health_payload("sess-test-secret")
    assert matched["session_match"] is True
    assert "session_id" not in matched
    assert "sess-test-secret" not in str(matched)

    wrong = svc.build_health_payload("other")
    assert wrong["session_match"] is False


def test_cors_exact_allowlist_only():
    from cross_group_service import ALLOWED_ORIGINS

    assert "null" not in ALLOWED_ORIGINS
    assert "http://localhost:34115" not in ALLOWED_ORIGINS
    assert "" in ALLOWED_ORIGINS
    assert "http://wails.localhost" in ALLOWED_ORIGINS
    assert "https://wails.localhost" in ALLOWED_ORIGINS
    assert "http://wails.localhost:34115" in ALLOWED_ORIGINS
    assert not any(o.endswith(".*") for o in ALLOWED_ORIGINS)
