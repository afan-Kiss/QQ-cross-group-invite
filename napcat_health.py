# -*- coding: utf-8 -*-
"""Thread-safe NapCat reachability cache for fast /health and /status."""
from __future__ import annotations

import threading
import time
from typing import Any

from myqq_api import check_napcat_online

_lock = threading.RLock()
_cond = threading.Condition(_lock)
_state: dict[str, Any] = {
    "online": False,
    "message": "NapCat checking",
    "checked_at": 0.0,
}
_refresh_in_flight = False
_stop = threading.Event()
_thread: threading.Thread | None = None

REFRESH_INTERVAL_SEC = 3.0


def public_napcat_message(online: bool, detail: str = "") -> str:
    """Generic NapCat status for unauthenticated /health (no QQ identity)."""
    if online:
        return "NapCat online"
    low = (detail or "").lower()
    if any(x in low for x in ("timeout", "timed out", "unavailable", "no response")):
        return "NapCat unavailable"
    if "checking" in low:
        return "NapCat checking"
    return "NapCat offline"


def refresh_napcat_cache(*, timeout: float = 2.5, wait_if_busy: bool = True) -> tuple[bool, str]:
    """Probe NapCat and update cache.

    When another probe is in flight:
    - wait_if_busy=True (manual refresh): wait for it to finish and return the fresh cache.
    - wait_if_busy=False (background loop): skip and return current cache.
    """
    global _refresh_in_flight
    with _cond:
        if _refresh_in_flight:
            if not wait_if_busy:
                return bool(_state["online"]), str(_state["message"])
            while _refresh_in_flight:
                _cond.wait(timeout=timeout + 1.0)
            return bool(_state["online"]), str(_state["message"])
        _refresh_in_flight = True
    try:
        online, detail = check_napcat_online(timeout=timeout)
        message = public_napcat_message(online, detail)
        with _cond:
            _state["online"] = online
            _state["message"] = message
            _state["checked_at"] = time.time()
            return online, message
    except Exception:
        message = "NapCat unavailable"
        with _cond:
            _state["online"] = False
            _state["message"] = message
            _state["checked_at"] = time.time()
            return False, message
    finally:
        with _cond:
            _refresh_in_flight = False
            _cond.notify_all()


def get_napcat_cache() -> tuple[bool, str, float]:
    with _lock:
        return bool(_state["online"]), str(_state["message"]), float(_state["checked_at"])


def start_napcat_health_refresh() -> None:
    """Start background refresher without blocking the caller (no sync probe)."""
    global _thread
    _stop.clear()
    with _lock:
        if _thread is not None and _thread.is_alive():
            return

        def _loop() -> None:
            while not _stop.is_set():
                refresh_napcat_cache(wait_if_busy=False)
                _stop.wait(REFRESH_INTERVAL_SEC)

        _thread = threading.Thread(target=_loop, daemon=True, name="napcat-health")
        _thread.start()


def stop_napcat_health_refresh() -> None:
    global _thread
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=1.0)
    with _lock:
        if _thread is t:
            _thread = None
