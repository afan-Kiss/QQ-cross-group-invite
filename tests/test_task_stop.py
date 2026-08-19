# -*- coding: utf-8 -*-
from __future__ import annotations

import time

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember, TaskRunStatus
from tests.conftest import invoke_758_send_hooks, wait_not_running, wait_until

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def test_stop_batch_interrupts_long_interval(monkeypatch):
    members = [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(3)
    ]

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(token_map={q: TOK for q in qqs}, fe7_pages=1)

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

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=2,
        qq_list=[m.qq for m in members],
    )

    assert wait_until(
        lambda: cgb.get_state()["status"] == TaskRunStatus.RUNNING.value
        and cgb.get_state()["done"] >= 1,
        timeout=2.0,
    ), "batch never entered running / first invite"

    t0 = time.time()
    cgb.stop_batch()
    assert wait_not_running(timeout=1.0), "stop_batch did not finish within 1s"
    elapsed = time.time() - t0
    assert elapsed < 1.0

    st = cgb.get_state()
    assert st["running"] is False
    assert st["status"] == TaskRunStatus.STOPPED.value
    assert st["message"] == "\u5df2\u505c\u6b62"
