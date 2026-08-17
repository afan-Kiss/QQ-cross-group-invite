# -*- coding: utf-8 -*-
from __future__ import annotations

import threading


def test_concurrent_upsert_different_ids(tmp_path, monkeypatch):
    import cross_group_batch as cgb

    monkeypatch.setattr(cgb, "_tasks_path", lambda: tmp_path / "tasks.json")
    (tmp_path / "tasks.json").write_text("[]", encoding="utf-8")

    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for j in range(20):
                cgb._upsert_task_record({"id": f"t-{i}", "n": j, "status": "completed"})
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert not errors
    tasks = cgb._load_tasks()
    ids = {t["id"] for t in tasks}
    assert ids == {f"t-{i}" for i in range(8)}
    for t in tasks:
        assert t["n"] == 19
