# -*- coding: utf-8 -*-
from __future__ import annotations


def test_default_fanfan_token():
    import myqq_api as api

    assert api.DEFAULT_FANFAN_TOKEN == "123456"
    assert api._default_fanfan_token({}) == "123456"
    assert api._default_fanfan_token({"napcat_webui_token": "abc"}) == "abc"
    assert api._default_fanfan_token({}, "") == "123456"
    assert api._default_fanfan_token({}, "xyz") == "xyz"


def test_onebot_action_uses_webui_when_url_ends_with_api(monkeypatch):
    import myqq_api as api

    seen = {}
    monkeypatch.setattr(
        api,
        "load_cfg",
        lambda: {"onebot_url": "http://127.0.0.1:6099/api", "napcat_webui_token": "123456"},
    )

    def fake_webui(action, params=None, **_kw):
        seen["action"] = action
        seen["params"] = params
        return {"status": "ok", "retcode": 0, "data": [{"user_id": 10001, "role": "member"}]}

    monkeypatch.setattr(api, "_webui_debug_call", fake_webui)
    raw = api.onebot_action("get_group_member_list", {"group_id": 100})
    assert seen["action"] == "get_group_member_list"
    assert seen["params"] == {"group_id": 100}
    assert raw["data"][0]["user_id"] == 10001
