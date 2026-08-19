# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember, TaskRunStatus
from tests.conftest import wait_not_running

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def _members(n: int) -> list[SourceMember]:
    return [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(n)
    ]


def _ready_running() -> None:
    with cgb._state_lock:
        cgb._state.running = True
        cgb._state.status = TaskRunStatus.RUNNING
        cgb._state.task_id = "gate-task"
        cgb._state._stop.clear()


def test_stop_before_authorize_sends_zero_758(monkeypatch):
    sent = []
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent.append(k) or (True, {"code": 0, "data": "1800"}),
    )
    _ready_running()
    cgb.stop_batch()
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=_members(1),
        tokens=[TOK],
        capture_dir=Path("."),
    )
    assert sent == []
    assert results[0][1] == "cancelled"
    logs = "\n".join(cgb.get_state()["logs"])
    assert "stop_requested" in logs
    assert "\u672a\u53d1\u9001\u9080\u8bf7" in results[0][3]


def test_authorize_then_stop_blocks_subsequent_758(monkeypatch):
    sent: list[list[str]] = []
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)

    def fake_758(**kwargs):
        sent.append(list(kwargs.get("invitee_tokens") or []))
        cgb.stop_batch()
        return True, {"code": 0, "data": "1800"}

    monkeypatch.setattr(cgb, "send_cross_group_invite", fake_758)
    _ready_running()
    members = _members(7)
    toks = [f"u_REDACT{i:02d}AAAAAAAAAAAAAA" for i in range(7)]
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=members,
        tokens=toks,
        capture_dir=Path("."),
    )
    assert [len(x) for x in sent] == [6]
    kinds = [k for _m, k, _c, _msg in results]
    assert kinds[:6] == ["success"] * 6
    assert kinds[6:] == ["cancelled"]
    logs = "\n".join(cgb.get_state()["logs"])
    assert "758_authorized" in logs
    assert "758_send_started" in logs
    assert "stop_requested" in logs


def test_stop_between_worker_chunks_skips_chunk2_picker_and_758(monkeypatch):
    picker_calls: list[list[int]] = []
    sent_758: list[list[str]] = []

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_calls.append(list(desired_qqs or []))
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: f"u_T{q % 100:02d}AAAAAAAAAAAAAAAAAA"[:24] for q in qqs},
            fe7_pages=1,
        )

    def fake_758(**kwargs):
        sent_758.append(list(kwargs.get("invitee_tokens") or []))
        cgb.stop_batch()
        return True, {"code": 0, "data": "1800"}

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "send_cross_group_invite", fake_758)
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    members = _members(7)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    assert len(picker_calls) == 1
    assert picker_calls[0] == [m.qq for m in members[:6]]
    assert len(sent_758) == 1
    assert len(sent_758[0]) == 6
    st = cgb.get_state()
    assert st["status"] == "stopped"
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10007]["status"] == "cancelled"
    assert st["failed_count"] == 0


def test_authorize_stop_lock_is_mutex():
    _ready_running()
    seq = cgb.authorize_758_send()
    assert seq is not None
    cgb.stop_batch()
    assert cgb.authorize_758_send() is None


def test_concurrent_stop_and_authorize_never_double_send():
    _ready_running()
    results: list[int | None] = []

    def do_stop():
        cgb.stop_batch()

    def do_auth():
        results.append(cgb.authorize_758_send())

    threads = [
        threading.Thread(target=do_stop),
        threading.Thread(target=do_auth),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    assert cgb.authorize_758_send() is None
    if results and results[0] is not None:
        assert cgb._state._stop.is_set()
