# -*- coding: utf-8 -*-
from __future__ import annotations


def test_clear_failed_keeps_cumulative_counts(tmp_path, monkeypatch):
    import cross_group_batch as cgb
    from cross_group_batch import InviteRecord, InviteResultStatus, SourceMember

    monkeypatch.setattr(cgb, "_tasks_path", lambda: tmp_path / "tasks.json")

    with cgb._state_lock:
        cgb._state.task_id = "t1"
        cgb._state.running = True
        cgb._state.failed_count = 0
        cgb._state.rate_limited_count = 0
        cgb._state.errors.clear()
        cgb._state.frequent.clear()

    m = SourceMember(qq=1, nickname="a", token="tok", eligible=True)
    cgb._finish_member(m, status=InviteResultStatus.FAILED, reason="x", started_at=cgb._now())
    m2 = SourceMember(qq=2, nickname="b", token="tok", eligible=True)
    cgb._finish_member(m2, status=InviteResultStatus.FAILED, reason="y", started_at=cgb._now())
    m3 = SourceMember(qq=3, nickname="c", token="tok", eligible=True)
    cgb._finish_member(m3, status=InviteResultStatus.RATE_LIMITED, reason="z", started_at=cgb._now())
    cgb._persist_current_task()

    assert cgb._state.failed_count == 2
    assert cgb._state.rate_limited_count == 1
    assert len(cgb._state.errors) == 2
    assert len(cgb._state.frequent) == 1

    cgb.clear_failed()
    cgb.clear_rate_limits()
    assert len(cgb._state.errors) == 0
    assert len(cgb._state.frequent) == 0
    assert cgb._state.failed_count == 2
    assert cgb._state.rate_limited_count == 1

    st = cgb.get_state()
    assert st["failed"] == 2
    assert st["rate_limited"] == 1
    assert st["failed_count"] == 2

    tasks = cgb._load_tasks()
    rec = next(x for x in tasks if x.get("id") == "t1")
    assert rec["failed"] == 2
    assert rec["rate_limited"] == 1
