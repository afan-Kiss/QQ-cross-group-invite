# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


def test_check_napcat_online_rejects_error_shaped(monkeypatch):
    import myqq_api as api

    monkeypatch.setattr(api, "port_open", lambda *a, **k: True)
    monkeypatch.setattr(
        api,
        "_onebot_full_response",
        lambda *a, **k: {"status": "failed", "retcode": 1, "data": {}},
    )
    ok, msg = api.check_napcat_online(onebot_url="http://127.0.0.1:9/api")
    assert ok is False
    assert "offline" in msg.lower() or "fail" in msg.lower()


def test_check_napcat_online_rejects_missing_identity(monkeypatch):
    import myqq_api as api

    monkeypatch.setattr(api, "port_open", lambda *a, **k: True)
    monkeypatch.setattr(
        api,
        "_onebot_full_response",
        lambda *a, **k: {"status": "ok", "retcode": 0, "data": {"nickname": "x"}},
    )
    ok, msg = api.check_napcat_online(onebot_url="http://127.0.0.1:9/api")
    assert ok is False


def test_test_napcat_connection_token_rules(monkeypatch, tmp_path):
    import myqq_api as api

    cfg_file = tmp_path / "config.json"
    cfg = {
        "onebot_url": "http://127.0.0.1:6099/api",
        "napcat_webui_token": "saved-token",
    }
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(api, "cfg_path", lambda: cfg_file)
    monkeypatch.setattr(api, "port_open", lambda *a, **k: True)
    monkeypatch.setattr(
        api,
        "_onebot_full_response",
        lambda *a, **k: {"status": "ok", "retcode": 0, "data": {"user_id": 10001}},
    )

    seen = {"tok": None}

    def fake_login(tok, **kwargs):
        seen["tok"] = tok
        return "cred"

    monkeypatch.setattr(api, "napcat_webui_login", fake_login)

    ok, msg, code = api.test_napcat_connection(onebot_url=None, napcat_webui_token="")
    assert ok and code == "OK"
    assert seen["tok"] == "saved-token"
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["napcat_webui_token"] == "saved-token"

    ok, msg, code = api.test_napcat_connection(
        onebot_url="http://127.0.0.1:6099/api",
        napcat_webui_token="transient-token",
    )
    assert ok and code == "OK"
    assert seen["tok"] == "transient-token"
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["napcat_webui_token"] == "saved-token"

    def boom(tok, **kwargs):
        raise RuntimeError("bad login")

    monkeypatch.setattr(api, "napcat_webui_login", boom)
    ok, msg, code = api.test_napcat_connection(napcat_webui_token="wrong")
    assert ok is False
    assert code == "WEBUI_TOKEN_INVALID"
    assert "wrong" not in msg
    assert json.loads(cfg_file.read_text(encoding="utf-8")) == cfg


def test_test_napcat_connection_missing_token(monkeypatch, tmp_path):
    import myqq_api as api

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onebot_url": "http://127.0.0.1:6099/api"}), encoding="utf-8")
    monkeypatch.setattr(api, "cfg_path", lambda: cfg_file)
    monkeypatch.setattr(api, "port_open", lambda *a, **k: True)
    monkeypatch.setattr(
        api,
        "_onebot_full_response",
        lambda *a, **k: {"status": "ok", "retcode": 0, "data": {"user_id": 1}},
    )
    ok, msg, code = api.test_napcat_connection(napcat_webui_token="")
    assert ok is False
    assert code == "WEBUI_TOKEN_MISSING"
