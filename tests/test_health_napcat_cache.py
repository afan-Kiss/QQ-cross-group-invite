# -*- coding: utf-8 -*-
from __future__ import annotations

import time


def test_build_health_payload_uses_cache_not_live_probe(monkeypatch):
    import napcat_health
    import cross_group_service as svc

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        time.sleep(0.05)
        return False, "饭饭定制 offline (slow)"

    monkeypatch.setattr("napcat_health.check_napcat_online", boom)
    monkeypatch.setattr(napcat_health, "_state", {
        "online": True,
        "message": "饭饭定制 online",
        "checked_at": time.time(),
    })
    monkeypatch.setattr(svc, "SESSION_ID", "secret-session")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)

    t0 = time.perf_counter()
    payload = svc.build_health_payload()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1
    assert calls["n"] == 0
    assert payload["ok"] is True
    assert payload["napcat_online"] is True
    assert payload["napcat_message"] == "饭饭定制 online"
    assert "123456" not in payload["napcat_message"]
    assert "session_id" not in payload
    assert "secret-session" not in str(payload)


def test_public_napcat_message_strips_qq_identity():
    from napcat_health import public_napcat_message

    assert public_napcat_message(True, "饭饭定制 online (QQ 123456)") == "饭饭定制 online"
    assert public_napcat_message(False, "timeout") == "饭饭定制 unavailable"
    assert public_napcat_message(False, "no response") == "饭饭定制 unavailable"
    assert public_napcat_message(False, "other") == "饭饭定制 offline"


def test_refresh_cache_stores_generic_message(monkeypatch):
    import napcat_health

    monkeypatch.setattr(
        "napcat_health.check_napcat_online",
        lambda *a, **k: (True, "饭饭定制 online (QQ 999)"),
    )
    online, msg = napcat_health.refresh_napcat_cache()
    assert online is True
    assert msg == "饭饭定制 online"
    assert "999" not in msg
