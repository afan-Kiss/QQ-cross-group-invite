# -*- coding: utf-8 -*-
from __future__ import annotations


def test_build_health_payload_service_id(monkeypatch):
    monkeypatch.setattr(
        "cross_group_service.check_napcat_online",
        lambda: (True, "ok"),
    )
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_ID", "sess-test")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)

    payload = svc.build_health_payload()
    assert payload["ok"] is True
    assert payload["service"] == "cross-group-invite"
    assert payload["service"] == svc.SERVICE_ID
    assert "version" in payload
    assert "pid" in payload
    assert payload["pid"] == payload["pid"]
    assert payload["session_id"] == "sess-test"
    assert payload["session_required"] is True
    assert payload["owned"] is True
    assert payload["napcat_online"] is True


def test_cors_exact_allowlist_only():
    from cross_group_service import ALLOWED_ORIGINS

    assert "null" not in ALLOWED_ORIGINS
    assert "http://localhost:34115" not in ALLOWED_ORIGINS
    assert "" in ALLOWED_ORIGINS
    assert "http://wails.localhost" in ALLOWED_ORIGINS
    assert "https://wails.localhost" in ALLOWED_ORIGINS
    assert "http://wails.localhost:34115" in ALLOWED_ORIGINS
    # no wildcard prefix matching — only exact entries
    assert not any(o.endswith(".*") for o in ALLOWED_ORIGINS)
