# -*- coding: utf-8 -*-
"""Thread-safe NapCat reachability cache for fast /health and /status."""
from __future__ import annotations

import threading
import time
from typing import Any

from myqq_api import check_napcat_online

_lock = threading.RLock()
_state: dict[str, Any] = {
    "online": False,
    "message": "NapCat offline",
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
    return "NapCat offline"


def refresh_napcat_cache(*, timeout: float = 2.5) -> tuple[bool, str]:
    """Synchronously probe NapCat and update cache."""
    global _refresh_in_flight
    with _lock:
        if _refresh_in_flight:
            return bool(_state["online"]), str(_state["message"])
        _refresh_in_flight = True
    try:
        online, detail = check_napcat_online(timeout=timeout)
        message = public_napcat_message(online, detail)
        with _lock:
            _state["online"] = online
            _state["message"] = message
            _state["checked_at"] = time.time()
        return online, message
    except Exception:
        message = "NapCat unavailable"
        with _lock:
            _state["online"] = False
            _state["message"] = message
            _state["checked_at"] = time.time()
        return False, message
    finally:
        with _lock:
            _refresh_in_flight = False


def get_napcat_cache() -> tuple[bool, str, float]:
    with _lock:
        return bool(_state["online"]), str(_state["message"]), float(_state["checked_at"])


def start_napcat_health_refresh() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return

        def _loop() -> None:
            while not _stop.is_set():
                refresh_napcat_cache()
                _stop.wait(REFRESH_INTERVAL_SEC)

        _thread = threading.Thread(target=_loop, daemon=True, name="napcat-health")
        _thread.start()

    # Prime cache before first request.
    refresh_napcat_cache()


def stop_napcat_health_refresh() -> None:
    _stop.set()
