# -*- coding: utf-8 -*-
"""interval_ms must pace protocol attempts BEFORE fresh picker."""
from __future__ import annotations

import threading
import time

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
from tests.conftest import invoke_758_send_hooks, wait_not_running

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def _members(n: int) -> list[SourceMember]:
    return [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(n)
    ]


def _install(monkeypatch, members, *, picker_delay=0.0, membership_delay=0.0, on_send=None, send_result=None):
    picker_started: list[float] = []
    fe1_at: list[float] = []
    send_at: list[float] = []
    sizes: list[int] = []
    fe1_n = {"n": 0}

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_started.append(time.monotonic())
        if picker_delay:
            time.sleep(picker_delay)
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: f"u_T{q % 100:02d}AAAAAAAAAAAAAAAAAA"[:24] for q in qqs},
            fe7_pages=1,
        )

    def fake_fe1(_cap, tokens, **_k):
        fe1_n["n"] += 1
        fe1_at.append(time.monotonic())
        return True

    def fake_758(**kwargs):
        send_at.append(time.monotonic())
        toks = list(kwargs.get("invitee_tokens") or [])
        sizes.append(len(toks))
        if on_send is not None:
            on_send(kwargs)
        if send_result is not None:
            return send_result(kwargs)
        return True, {"code": 0, "data": "1800"}

    def fake_wait(*_a, **_k):
        if membership_delay:
            time.sleep(membership_delay)
        return True

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", fake_fe1)
    monkeypatch.setattr(cgb, "send_cross_group_invite", invoke_758_send_hooks(fake_758))
    monkeypatch.setattr(cgb, "wait_target_membership", fake_wait)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    return picker_started, fe1_at, send_at, sizes, fe1_n


def test_batch20_cadence_between_758_sends(monkeypatch):
    members = _members(20)
    _picker, _fe1, timestamps, sizes, _n = _install(monkeypatch, members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=200,
        qq_list=[m.qq for m in members],
        batch_size=20,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert sizes == [6, 6, 6, 2]
    assert len(timestamps) == 4
    for a, b in zip(timestamps, timestamps[1:]):
        assert (b - a) >= 0.18


def test_cadence_wait_happens_before_second_picker(monkeypatch):
    members = _members(7)
    picker_started, _fe1, send_at, sizes, fe1_n = _install(monkeypatch, members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=800,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert sizes == [6, 1]
    assert len(picker_started) == 2
    assert picker_started[1] >= send_at[0] + 0.75
    assert picker_started[1] > send_at[0]
    assert fe1_n["n"] == 2
    sends = cgb.get_state()["protocol_sends"]
    assert [s["invitee_count"] for s in sends] == [6, 1]


def test_fe1_to_758_not_delayed_by_interval(monkeypatch):
    members = _members(7)
    _install(monkeypatch, members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=1000,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=6.0)
    timings = []
    for line in cgb.get_state()["logs"]:
        if "chunk_timing" in line and "fe1_to_send_ms=" in line:
            part = line.split("fe1_to_send_ms=", 1)[1]
            timings.append(int(part.split()[0]))
    assert len(timings) == 2
    assert all(ms < 250 for ms in timings)


def test_slow_prior_work_skips_extra_interval_sleep(monkeypatch):
    members = _members(7)
    picker_started, _fe1, send_at, sizes, _n = _install(
        monkeypatch, members, membership_delay=0.35
    )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=200,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert sizes == [6, 1]
    gap = picker_started[1] - send_at[0]
    assert gap >= 0.30
    assert gap < 0.55


def test_rate_limited_first_chunk_still_waits_before_next(monkeypatch):
    from pb_utils import encode_field_varint

    members = _members(7)
    fail_hex = encode_field_varint(3, 1289).hex()
    n = {"v": 0}

    def send_result(_kwargs):
        n["v"] += 1
        if n["v"] == 1:
            return False, {"code": 0, "data": fail_hex}
        return True, {"code": 0, "data": "1800"}

    picker_started, _fe1, timestamps, sizes, _fn = _install(
        monkeypatch, members, send_result=send_result
    )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=200,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert sizes == [6, 1]
    assert (timestamps[1] - timestamps[0]) >= 0.18
    assert picker_started[1] >= timestamps[0] + 0.18


def test_stop_during_cadence_wait_skips_current_picker(monkeypatch):
    members = _members(13)

    def on_send(_kwargs):
        def delayed_stop():
            time.sleep(0.05)
            cgb.stop_batch()

        if not getattr(on_send, "armed", False):
            on_send.armed = True
            threading.Thread(target=delayed_stop, daemon=True).start()

    picker_started, fe1_at, timestamps, sizes, fe1_n = _install(
        monkeypatch, members, on_send=on_send
    )
    t0 = time.monotonic()
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=800,
        qq_list=[m.qq for m in members],
        batch_size=13,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    assert time.monotonic() - t0 < 1.5
    assert sizes == [6]
    assert len(timestamps) == 1
    assert len(picker_started) == 1
    assert fe1_n["n"] == 1
    st = cgb.get_state()
    assert st["status"] == "stopped"
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10007]["status"] == "cancelled"
    assert st["cancelled_count"] >= 7
