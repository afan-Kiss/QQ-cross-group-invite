# -*- coding: utf-8 -*-
from __future__ import annotations


def test_myqq_call_hint_does_not_embed_token(monkeypatch):
    import myqq_api as api

    monkeypatch.setattr(
        api,
        "load_cfg",
        lambda: {"token": "SUPER-SECRET-TOKEN", "base_url": "http://127.0.0.1:9/"},
    )
    monkeypatch.setattr(api, "port_open", lambda *a, **k: False)
    try:
        api.call("Api_GetOnlineQQlist")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        msg = str(exc)
        assert "SUPER-SECRET-TOKEN" not in msg
        assert "Token=" not in msg
        assert "HTTP API Token" in msg


def test_webui_login_error_no_raw_obj(monkeypatch):
    import myqq_api as api
    import json
    from io import BytesIO

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"code": 403, "message": "bad", "Credential": "leak"}).encode()

    monkeypatch.setattr(api, "load_cfg", lambda: {})
    monkeypatch.setattr(api.urllib.request, "urlopen", lambda *a, **k: Resp())
    try:
        api.napcat_webui_login("tok", api_url="http://127.0.0.1:9/api", force=True)
        raise AssertionError("expected fail")
    except RuntimeError as exc:
        msg = str(exc)
        assert "leak" not in msg
        assert "Credential" not in msg
        assert "code=403" in msg
