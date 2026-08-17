# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
from pathlib import Path


def test_save_cfg_atomic_and_bak(monkeypatch, tmp_path):
    import myqq_api as api

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"onebot_url": "A", "napcat_webui_token": "SECRET"}), encoding="utf-8")
    monkeypatch.setattr(api, "cfg_path", lambda: cfg_file)

    api.save_cfg({"onebot_url": "B", "napcat_webui_token": "SECRET2"})
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["onebot_url"] == "B"
    bak = cfg_file.with_name("config.json.bak")
    assert bak.is_file()
    assert "SECRET" in bak.read_text(encoding="utf-8")


def test_load_cfg_recovers_from_bak(monkeypatch, tmp_path):
    import myqq_api as api

    cfg_file = tmp_path / "config.json"
    bak = cfg_file.with_name("config.json.bak")
    bak.write_text(json.dumps({"onebot_url": "from-bak", "napcat_webui_token": "T"}), encoding="utf-8")
    cfg_file.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(api, "cfg_path", lambda: cfg_file)

    data = api.load_cfg()
    assert data["onebot_url"] == "from-bak"
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["onebot_url"] == "from-bak"


def test_concurrent_save_cfg(monkeypatch, tmp_path):
    import myqq_api as api

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(api, "cfg_path", lambda: cfg_file)

    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for n in range(20):
                api.save_cfg({"i": i, "n": n, "napcat_webui_token": "x"})
                api.load_cfg()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors
    json.loads(cfg_file.read_text(encoding="utf-8"))
