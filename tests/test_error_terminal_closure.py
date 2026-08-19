# -*- coding: utf-8 -*-
"""ERROR/STOPPED terminal must close waiting/inviting members."""
from __future__ import annotations

from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember, TaskRunStatus
from tests.conftest import invoke_758_send_hooks, wait_not_running

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def _members(n: int) -> list[SourceMember]:
    return [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(n)
    ]


def _assert_terminal_invariant(st: dict) -> None:
    by_status = {}
    for r in st["results"]:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    assert by_status.get("waiting", 0) == 0
    assert by_status.get("inviting", 0) == 0
    assert st["done"] == st["total"]
    assert (
        st["success"] + st["failed"] + st["rate_limited"] + st["cancelled"] == st["done"]
    )


def test_error_on_second_picker_closes_unresolved(monkeypatch):
    picker_n = {"n": 0}
    sent: list[list[str]] = []

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_n["n"] += 1
        if picker_n["n"] >= 2:
            raise RuntimeError("picker boom")
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: f"u_T{q % 100:02d}AAAAAAAAAAAAAAAAAA"[:24] for q in qqs},
            fe7_pages=1,
        )

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        invoke_758_send_hooks(
            lambda **k: sent.append(list(k.get("invitee_tokens") or []))
            or (True, {"code": 0, "data": "1800"})
        ),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    members = _members(8)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=8,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    st = cgb.get_state()
    assert st["status"] == "error"
    assert "picker boom" in (st["error_message"] or "")
    assert len(sent) == 1
    assert len(sent[0]) == 6
    by_qq = {r["qq"]: r for r in st["results"]}
    for i in range(6):
        assert by_qq[10001 + i]["status"] == "success"
    for i in range(6, 8):
        assert by_qq[10001 + i]["status"] == "failed"
        assert "\u4efb\u52a1\u5f02\u5e38\u7ec8\u6b62" in (by_qq[10001 + i].get("reason") or "")
    assert st["cancelled_count"] == 0
    _assert_terminal_invariant(st)


def test_send_exception_closes_unresolved_and_keeps_error_message(monkeypatch):
    def boom(**_k):
        raise RuntimeError("urllib explode")

    monkeypatch.setattr(cgb, "open_cross_group_picker", lambda *_a, **_k: cgb.PickerSession(
        token_map={10001: TOK, 10002: TOK},
        fe7_pages=1,
    ))
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "send_cross_group_invite", boom)
    members = _members(2)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    st = cgb.get_state()
    assert st["status"] == "error"
    assert st["error_message"] == "urllib explode"
    assert all(r["status"] == "failed" for r in st["results"])
    assert st["cancelled_count"] == 0
    _assert_terminal_invariant(st)


def test_membership_verify_exception_no_inviting_left(monkeypatch):
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: cgb.PickerSession(token_map={10001: TOK}, fe7_pages=1),
    )
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        invoke_758_send_hooks(lambda **_k: (True, {"code": 0, "data": "1800"})),
    )

    def boom_wait(*_a, **_k):
        raise RuntimeError("membership explode")

    monkeypatch.setattr(cgb, "wait_target_membership", boom_wait)
    members = _members(1)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=1,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    st = cgb.get_state()
    assert st["status"] == "error"
    assert "membership explode" in (st["error_message"] or "")
    assert st["results"][0]["status"] == "failed"
    _assert_terminal_invariant(st)


def test_finalize_stopped_marks_cancelled_not_failed():
    with cgb._state_lock:
        cgb._state.running = True
        cgb._state.status = TaskRunStatus.RUNNING
        cgb._state.total = 2
        cgb._state.results = [
            cgb.InviteResult(qq=1, nickname="a", status=cgb.InviteResultStatus.WAITING),
            cgb.InviteResult(qq=2, nickname="b", status=cgb.InviteResultStatus.INVITING),
        ]
    cgb.finalize_unresolved_results(TaskRunStatus.STOPPED, "\u5df2\u505c\u6b62\uff0c\u672a\u53d1\u9001\u9080\u8bf7")
    st = cgb.get_state()
    assert st["cancelled_count"] == 2
    assert st["failed_count"] == 0
    _assert_terminal_invariant({**st, "total": 2, "done": st["done"]})
