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
        return False, "NapCat offline (slow)"

    monkeypatch.setattr("napcat_health.check_napcat_online", boom)
    monkeypatch.setattr(napcat_health, "_state", {
        "online": True,
        "message": "NapCat online",
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
    assert payload["napcat_message"] == "NapCat online"
    assert "123456" not in payload["napcat_message"]
    assert "session_id" not in payload
    assert "secret-session" not in str(payload)


def test_public_napcat_message_strips_qq_identity():
    from napcat_health import public_napcat_message

    assert public_napcat_message(True, "NapCat online (QQ 123456)") == "NapCat online"
    assert public_napcat_message(False, "timeout") == "NapCat unavailable"
    assert public_napcat_message(False, "no response") == "NapCat unavailable"
    assert public_napcat_message(False, "other") == "NapCat offline"


def test_refresh_cache_stores_generic_message(monkeypatch):
    import napcat_health

    monkeypatch.setattr(
        "napcat_health.check_napcat_online",
        lambda *a, **k: (True, "NapCat online (QQ 999)"),
    )
    online, msg = napcat_health.refresh_napcat_cache()
    assert online is True
    assert msg == "NapCat online"
    assert "999" not in msg
