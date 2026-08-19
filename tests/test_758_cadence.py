# -*- coding: utf-8 -*-
"""interval_ms must pace real 758 send attempts across protocol chunks."""
from __future__ import annotations

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


def _install_happy_path(monkeypatch, members, *, on_send=None, send_result=None):
    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: f"u_T{q % 100:02d}AAAAAAAAAAAAAAAAAA"[:24] for q in qqs},
            fe7_pages=1,
        )

    timestamps: list[float] = []
    sizes: list[int] = []

    def fake_758(**kwargs):
        timestamps.append(time.monotonic())
        toks = list(kwargs.get("invitee_tokens") or [])
        sizes.append(len(toks))
        if on_send is not None:
            on_send(kwargs)
        if send_result is not None:
            return send_result(kwargs)
        return True, {"code": 0, "data": "1800"}

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "send_cross_group_invite", invoke_758_send_hooks(fake_758))
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    return timestamps, sizes


def test_batch20_cadence_between_758_sends(monkeypatch):
    members = _members(20)
    timestamps, sizes = _install_happy_path(monkeypatch, members)
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


def test_batch13_three_sends_respect_interval(monkeypatch):
    members = _members(13)
    timestamps, sizes = _install_happy_path(monkeypatch, members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=150,
        qq_list=[m.qq for m in members],
        batch_size=13,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert sizes == [6, 6, 1]
    for a, b in zip(timestamps, timestamps[1:]):
        assert (b - a) >= 0.13


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

    timestamps, sizes = _install_happy_path(
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


def test_stop_during_cadence_wait_skips_further_758(monkeypatch):
    import threading

    members = _members(13)

    def on_send(_kwargs):
        if len(getattr(on_send, "n", [])) >= 0:
            pass

        def delayed_stop():
            time.sleep(0.05)
            cgb.stop_batch()

        if not getattr(on_send, "armed", False):
            on_send.armed = True
            threading.Thread(target=delayed_stop, daemon=True).start()

    timestamps, sizes = _install_happy_path(monkeypatch, members, on_send=on_send)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=800,
        qq_list=[m.qq for m in members],
        batch_size=13,
        filter_staff=True,
    )
    assert wait_not_running(timeout=3.0)
    assert sizes == [6]
    assert len(timestamps) == 1
    st = cgb.get_state()
    assert st["status"] == "stopped"
