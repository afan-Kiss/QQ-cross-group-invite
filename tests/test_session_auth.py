# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from io import BytesIO


class _Req(BaseHTTPRequestHandler):
    def __init__(self, headers: dict[str, str], body: bytes = b"{}"):
        self.headers = headers  # type: ignore[assignment]
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.requestline = "POST /config HTTP/1.1"
        self.command = "POST"
        self.request_version = "HTTP/1.1"
        self.client_address = ("127.0.0.1", 12345)
        self._headers_buffer: list[str] = []
        self._status = 0

    def send_response(self, code, message=None):
        self._status = code

    def send_header(self, keyword, value):
        self._headers_buffer.append(f"{keyword}: {value}")

    def end_headers(self):
        pass

    def log_message(self, fmt, *args):
        return


def test_owned_mutating_requires_session(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_ID", "owned-sess")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)

    denied = svc._check_session(_Req({}), required=True)
    assert denied is not None
    assert denied[0] == 403
    assert denied[1]["code"] == "UNAUTHORIZED"

    ok = svc._check_session(_Req({"X-App-Session": "owned-sess"}), required=True)
    assert ok is None


def test_unowned_allows_missing_header(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_ID", "ext-sess")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)

    assert svc._check_session(_Req({}), required=False) is None
    wrong = svc._check_session(_Req({"X-App-Session": "bad"}), required=False)
    assert wrong is not None and wrong[0] == 403


def test_static_blocks_path_traversal(tmp_path, monkeypatch):
    import cross_group_service as svc

    web = tmp_path / "web"
    web.mkdir()
    (web / "ok.txt").write_text("hi", encoding="utf-8")
    monkeypatch.setattr(svc, "WEB_DIR", web)

    root = web.resolve()
    escaped = (web / ".." / "secret.txt").resolve()
    try:
        escaped.relative_to(root)
        raise AssertionError("expected traversal path to fall outside WEB_DIR")
    except ValueError:
        pass

    # Handler rejects escaped paths before reading
    class Dummy:
        pass

    h = svc.Handler.__new__(svc.Handler)
    assert h._serve_static("/../secret.txt") is False
