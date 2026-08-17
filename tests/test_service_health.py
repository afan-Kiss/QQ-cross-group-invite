# -*- coding: utf-8 -*-
from __future__ import annotations


def test_build_health_payload_service_id(monkeypatch):
    monkeypatch.setattr(
        "cross_group_service.check_napcat_online",
        lambda: (True, "ok"),
    )
    from cross_group_service import SERVICE_ID, build_health_payload

    payload = build_health_payload()
    assert payload["ok"] is True
    assert payload["service"] == "cross-group-invite"
    assert payload["service"] == SERVICE_ID
    assert "version" in payload
    assert "pid" in payload
    assert payload["napcat_online"] is True
