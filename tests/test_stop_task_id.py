# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember, TaskIdMismatch, TaskRunStatus
from tests.conftest import invoke_758_send_hooks, wait_not_running, wait_until

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def _eligible(n: int = 3) -> list[SourceMember]:
    return [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(n)
    ]


def _install_live_invite(monkeypatch, members: list[SourceMember]) -> None:
    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: TOK for q in qqs},
            fe7_pages=1,
        )

    monkeypatch.setattr(cgb, "load_source_members", lambda *a, **k: list(members))
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        invoke_758_send_hooks(lambda **_k: (True, {"code": 0, "data": "1800"})),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )


def test_stop_batch_mismatch_raises(monkeypatch):
    members = _eligible(3)
    _install_live_invite(monkeypatch, members)
    tid = cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=2,
        qq_list=[m.qq for m in members],
    )
    assert wait_until(
        lambda: cgb.get_state()["status"] == TaskRunStatus.RUNNING.value,
        timeout=2.0,
    )

    with pytest.raises(TaskIdMismatch):
        cgb.stop_batch(task_id="not-the-task")

    st = cgb.get_state()
    assert st["running"] is True
    assert st["status"] == TaskRunStatus.RUNNING.value

    cgb.stop_batch(task_id=tid)
    assert wait_not_running(timeout=2.0)
    assert cgb.get_state()["status"] == TaskRunStatus.STOPPED.value


def test_stop_batch_none_stops_current(monkeypatch):
    members = _eligible(3)
    _install_live_invite(monkeypatch, members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=2,
        qq_list=[m.qq for m in members],
    )
    assert wait_until(lambda: cgb.get_state()["done"] >= 1, timeout=2.0)
    cgb.stop_batch()
    assert wait_not_running(timeout=2.0)
    assert cgb.get_state()["status"] == TaskRunStatus.STOPPED.value
