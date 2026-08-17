# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time


def _reset_napcat(monkeypatch):
    import napcat_health

    napcat_health.stop_napcat_health_refresh()
    with napcat_health._cond:
        napcat_health._refresh_in_flight = False
        napcat_health._state.update(
            {"online": False, "message": "饭饭定制 checking", "checked_at": 0.0}
        )
        napcat_health._cond.notify_all()
    napcat_health._stop.clear()
    return napcat_health


def test_start_napcat_health_refresh_nonblocking(monkeypatch):
    napcat_health = _reset_napcat(monkeypatch)

    def slow(*a, **k):
        time.sleep(2.0)
        return False, "timeout"

    monkeypatch.setattr("napcat_health.check_napcat_online", slow)
    t0 = time.perf_counter()
    napcat_health.start_napcat_health_refresh()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, elapsed
    online, msg, _ = napcat_health.get_napcat_cache()
    assert online is False
    assert "checking" in msg.lower() or "offline" in msg.lower() or "unavailable" in msg.lower()
    napcat_health.stop_napcat_health_refresh()


def test_manual_refresh_waits_for_in_flight(monkeypatch):
    napcat_health = _reset_napcat(monkeypatch)
    calls = {"n": 0}
    started = threading.Event()

    def probe(*a, **k):
        calls["n"] += 1
        started.set()
        time.sleep(0.35)
        return True, "饭饭定制 online (QQ 1)"

    monkeypatch.setattr("napcat_health.check_napcat_online", probe)

    def bg():
        napcat_health.refresh_napcat_cache(wait_if_busy=False)

    t = threading.Thread(target=bg)
    t.start()
    assert started.wait(3), "first probe did not start"
    online, msg = napcat_health.refresh_napcat_cache(wait_if_busy=True)
    t.join(timeout=3)
    assert online is True
    assert msg == "饭饭定制 online"
    assert calls["n"] == 1


def test_stop_then_start_again(monkeypatch):
    napcat_health = _reset_napcat(monkeypatch)
    monkeypatch.setattr("napcat_health.check_napcat_online", lambda *a, **k: (False, "offline"))
    napcat_health.start_napcat_health_refresh()
    napcat_health.stop_napcat_health_refresh()
    napcat_health.start_napcat_health_refresh()
    assert napcat_health._thread is not None and napcat_health._thread.is_alive()
    napcat_health.stop_napcat_health_refresh()


def test_sidecar_start_refresh_nonblocking_before_bind(monkeypatch):
    import napcat_health

    napcat_health = _reset_napcat(monkeypatch)
    monkeypatch.setattr(
        "napcat_health.check_napcat_online",
        lambda *a, **k: (time.sleep(5), (False, "timeout"))[1],
    )
    t0 = time.perf_counter()
    napcat_health.start_napcat_health_refresh()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5
    napcat_health.stop_napcat_health_refresh()
