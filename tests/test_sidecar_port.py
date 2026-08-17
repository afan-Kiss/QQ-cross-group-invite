# -*- coding: utf-8 -*-
from __future__ import annotations

import socket
import threading
import time
import urllib.request


def test_sidecar_binds_custom_port(monkeypatch):
    """Start Handler server on ephemeral port via main()-equivalent bind."""
    import cross_group_service as svc

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    monkeypatch.setattr(svc, "load_cfg", lambda: {})
    monkeypatch.setattr(svc, "recover_stale_tasks", lambda: 0)
    monkeypatch.setattr(svc, "start_napcat_health_refresh", lambda: None)
    monkeypatch.setattr(
        "napcat_health._state",
        {"online": False, "message": "饭饭定制 offline", "checked_at": time.time()},
    )

    ready = threading.Event()
    err: list[BaseException] = []

    def run():
        try:
            svc.SESSION_ID = "port-sess"
            svc.SESSION_REQUIRED = True
            server = svc.ThreadingHTTPServer(("127.0.0.1", port), svc.Handler)
            svc._server = server
            ready.set()
            server.serve_forever()
        except BaseException as exc:
            err.append(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    assert ready.wait(3)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            body = resp.read().decode("utf-8")
        assert "cross-group-invite" in body
        assert '"ok": true' in body.replace("True", "true") or '"ok":true' in body.replace(" ", "")
    finally:
        if svc._server is not None:
            svc._server.shutdown()
            svc._server.server_close()
        t.join(timeout=3)
    assert not err, err
