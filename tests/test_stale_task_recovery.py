# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import cross_group_batch as cgb
from cross_group_batch import TaskRunStatus


def test_recover_stale_tasks_marks_interrupted(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)

    tasks = [
        {
            "id": "old-running",
            "status": "running",
            "started_at": 1.0,
            "success": 3,
        },
        {
            "id": "old-preparing",
            "status": "preparing",
            "started_at": 2.0,
        },
        {
            "id": "old-stopping",
            "status": "stopping",
            "started_at": 3.0,
        },
        {
            "id": "done-ok",
            "status": "completed",
            "started_at": 4.0,
            "success": 9,
        },
    ]
    tasks_file.write_text(json.dumps(tasks), encoding="utf-8")

    n = cgb.recover_stale_tasks()
    assert n == 3
    loaded = json.loads(tasks_file.read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in loaded}
    for tid in ("old-running", "old-preparing", "old-stopping"):
        assert by_id[tid]["status"] == TaskRunStatus.INTERRUPTED.value
        assert by_id[tid]["finished_at"] > 0
        assert by_id[tid]["error_message"] == cgb._STALE_MSG
    assert by_id["done-ok"]["status"] == "completed"
    assert by_id["done-ok"]["success"] == 9


def test_recover_skips_live_running_task(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)

    with cgb._state_lock:
        cgb._state.running = True
        cgb._state.task_id = "live-1"
        cgb._state.status = TaskRunStatus.RUNNING

    tasks_file.write_text(
        json.dumps(
            [
                {"id": "live-1", "status": "running", "started_at": 1.0},
                {"id": "stale-1", "status": "running", "started_at": 0.5},
            ]
        ),
        encoding="utf-8",
    )
    n = cgb.recover_stale_tasks()
    assert n == 1
    loaded = {t["id"]: t for t in json.loads(tasks_file.read_text(encoding="utf-8"))}
    assert loaded["live-1"]["status"] == "running"
    assert loaded["stale-1"]["status"] == "interrupted"
