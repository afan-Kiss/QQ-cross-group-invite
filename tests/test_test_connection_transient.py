# -*- coding: utf-8 -*-
from __future__ import annotations


def test_test_connection_does_not_save_cfg(monkeypatch):
    import cross_group_service as svc

    saved = {"n": 0}

    def boom_save(*a, **k):
        saved["n"] += 1
        raise AssertionError("save_cfg must not be called")

    monkeypatch.setattr(svc, "save_cfg", boom_save)
    monkeypatch.setattr(svc, "load_cfg", lambda: {"onebot_url": "http://old.example/api"})
    monkeypatch.setattr(
        svc,
        "check_napcat_online",
        lambda *a, **k: (False, "offline"),
    )

    # Simulate handler branch: transient URL, no save
    probe_url = "http://bad.example/api"
    online, msg = svc.check_napcat_online(onebot_url=probe_url)
    assert online is False
    assert saved["n"] == 0
    assert svc.load_cfg()["onebot_url"] == "http://old.example/api"
