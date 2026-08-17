# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import cross_group_batch as cgb


def test_save_tasks_atomic_replace_and_bak(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)

    cgb._save_tasks([{"id": "a", "status": "completed"}])
    assert tasks_file.is_file()
    assert json.loads(tasks_file.read_text(encoding="utf-8"))[0]["id"] == "a"

    cgb._save_tasks(
        [
            {"id": "a", "status": "completed"},
            {"id": "b", "status": "completed"},
        ]
    )
    bak = Path(str(tasks_file) + ".bak")
    assert bak.is_file()
    assert json.loads(bak.read_text(encoding="utf-8"))[0]["id"] == "a"
    assert len(json.loads(tasks_file.read_text(encoding="utf-8"))) == 2
    assert not (tmp_path / "tasks.json.tmp").exists()


def test_load_tasks_falls_back_to_bak(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    bak = Path(str(tasks_file) + ".bak")
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)

    bak.write_text(
        json.dumps([{"id": "from-bak", "status": "completed"}]),
        encoding="utf-8",
    )
    tasks_file.write_text("{not-json", encoding="utf-8")

    loaded = cgb._load_tasks()
    assert loaded[0]["id"] == "from-bak"


def test_load_tasks_corrupt_without_bak_returns_empty(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)
    tasks_file.write_text("{broken", encoding="utf-8")
    assert cgb._load_tasks() == []
