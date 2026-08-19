# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from pathlib import Path

import pytest

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
from pb_utils import build_cross_group_758_pb, extract_field_bytes, parse_cross_group_758_entries
from tests.conftest import invoke_758_send_hooks, wait_not_running

OLD = "u_OLDMEMBERTOKENAAAAAAAA"


def _tok(i: int) -> str:
    return f"u_REDACT{i:02d}AAAAAAAAAAAAAA"


def _members(n: int, start: int = 20000) -> list[SourceMember]:
    return [
        SourceMember(qq=start + i, nickname=f"m{i}", token=OLD, role=MemberRole.MEMBER)
        for i in range(n)
    ]


def test_proven_packet_max_is_min_fe1_and_758():
    assert cgb.PROVEN_FE1_TOKEN_MAX == 10
    assert cgb.PROVEN_758_BLOCK_MAX == 6
    assert cgb.PROTOCOL_INVITE_PACKET_MAX == 6
    assert cgb.PROTOCOL_INVITE_PACKET_MAX == min(
        cgb.PROVEN_FE1_TOKEN_MAX, cgb.PROVEN_758_BLOCK_MAX
    )


def test_protocol_chunk_sizes_table():
    assert cgb.protocol_chunk_sizes(1) == [1]
    assert cgb.protocol_chunk_sizes(6) == [6]
    assert cgb.protocol_chunk_sizes(7) == [6, 1]
    assert cgb.protocol_chunk_sizes(12) == [6, 6]
    assert cgb.protocol_chunk_sizes(13) == [6, 6, 1]
    assert cgb.protocol_chunk_sizes(20) == [6, 6, 6, 2]


def test_protocol_chunk_fn_rejects_more_than_max(monkeypatch):
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    members = _members(7)
    toks = [_tok(i) for i in range(7)]
    with pytest.raises(ValueError, match="PROTOCOL_INVITE_PACKET_MAX"):
        cgb._invite_protocol_chunk(
            target_group_id=200,
            source_group_id=100,
            members=members,
            tokens=toks,
            capture_dir=Path("."),
        )


def test_worker_batch_7_splits_6_plus_1_with_two_pickers(monkeypatch):
    picker_calls: list[list[int]] = []
    fe1_calls: list[list[str]] = []
    sent_758: list[list[str]] = []

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        picker_calls.append(qqs)
        return cgb.PickerSession(
            token_map={q: _tok(q % 100) for q in qqs},
            fe7_pages=1,
        )

    def fake_fe1(_cap, tokens, **_k):
        fe1_calls.append(list(tokens))
        return True

    def fake_758(**kwargs):
        sent_758.append(list(kwargs.get("invitee_tokens") or []))
        return True, {"code": 0, "data": "1800"}

    members = _members(7, start=10001)
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", fake_fe1)
    monkeypatch.setattr(cgb, "send_cross_group_invite", invoke_758_send_hooks(fake_758))
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
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
    assert len(picker_calls) == 2
    assert len(fe1_calls) == 2
    assert [len(x) for x in sent_758] == [6, 1]
    assert picker_calls[0] == [m.qq for m in members[:6]]
    assert picker_calls[1] == [members[6].qq]


def test_worker_batch_13_three_independent_token_maps(monkeypatch):
    picker_calls: list[list[int]] = []
    fe1_calls: list[list[str]] = []
    sent_758: list[list[str]] = []
    ages: list[int] = []

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        picker_calls.append(qqs)
        time.sleep(0.01)
        return cgb.PickerSession(
            token_map={q: _tok(q % 100) for q in qqs},
            fe7_pages=1,
        )

    def fake_fe1(_cap, tokens, **_k):
        fe1_calls.append(list(tokens))
        return True

    def fake_758(**kwargs):
        sent_758.append(list(kwargs.get("invitee_tokens") or []))
        return True, {"code": 0, "data": "1800"}

    members = _members(13, start=10001)
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", fake_fe1)
    monkeypatch.setattr(cgb, "send_cross_group_invite", invoke_758_send_hooks(fake_758))
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=13,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert [len(x) for x in picker_calls] == [6, 6, 1]
    assert picker_calls[0] == [m.qq for m in members[:6]]
    assert picker_calls[1] == [m.qq for m in members[6:12]]
    assert picker_calls[2] == [members[12].qq]
    assert [len(x) for x in fe1_calls] == [6, 6, 1]
    assert [len(x) for x in sent_758] == [6, 6, 1]
    assert fe1_calls == sent_758
    assert sent_758[0] != sent_758[1]
    assert set(sent_758[0]).isdisjoint(set(sent_758[1]))
    assert set(sent_758[0]).isdisjoint(set(sent_758[2]))
    assert OLD not in {t for batch in sent_758 for t in batch}
    joined = "\n".join(cgb.get_state()["logs"])
    assert "ui_batch_number=1" in joined
    assert "protocol_chunk_total=3" in joined
    for line in cgb.get_state()["logs"]:
        if "picker ui_batch_number=" in line:
            assert "u_REDACT" not in line and OLD not in line
            ages.append(1)
    assert len(ages) == 3
    for chunk in sent_758:
        hx = build_cross_group_758_pb(
            target_group_id=1111111111,
            source_group_id=2222222222,
            invitee_tokens=chunk,
        )
        _t, _s, blocks = parse_cross_group_758_entries(
            extract_field_bytes(bytes.fromhex(hx), 4) or b""
        )
        assert len(blocks) == len(chunk)
        assert len(blocks) <= cgb.PROVEN_758_BLOCK_MAX


def test_second_protocol_chunk_missing_token_does_not_reuse_prior(monkeypatch):
    picker_calls: list[list[int]] = []
    sent_758: list[list[str]] = []
    maps = [
        {10001 + i: _tok(i) for i in range(6)},
        {},
        {10013: _tok(12)},
    ]

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_calls.append(list(desired_qqs or []))
        idx = len(picker_calls) - 1
        token_map = maps[idx] if idx < len(maps) else {}
        missing = [q for q in (desired_qqs or []) if q not in token_map]
        return cgb.PickerSession(token_map=token_map, fe7_pages=1, missing_qqs=missing)

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        invoke_758_send_hooks(
            lambda **k: sent_758.append(list(k.get("invitee_tokens") or []))
            or (True, {"code": 0, "data": "1800"})
        ),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    members = _members(13, start=10001)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=13,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert [len(x) for x in picker_calls] == [6, 6, 1]
    assert [len(x) for x in sent_758] == [6, 1]
    first_tokens = set(sent_758[0])
    assert sent_758[1] == [_tok(12)]
    assert first_tokens.isdisjoint(set(sent_758[1]))
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    for i in range(6, 12):
        assert by_qq[10001 + i]["status"] == "failed"
        assert OLD not in (by_qq[10001 + i].get("reason") or "")
    assert by_qq[10013]["status"] == "success"


def test_membership_verify_shared_deadline_not_six_full_timeouts(monkeypatch):
    starts: list[float] = []
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        invoke_758_send_hooks(lambda **_k: (True, {"code": 0, "data": "1800"})),
    )
    monkeypatch.setattr(cgb, "MEMBERSHIP_RETRY_SEC", 0.4)

    def fake_wait(*_a, timeout=5.0, **_k):
        starts.append(time.monotonic())
        time.sleep(0.12)
        return True

    monkeypatch.setattr(cgb, "wait_target_membership", fake_wait)
    members = _members(6)
    toks = [_tok(i) for i in range(6)]
    t0 = time.monotonic()
    cgb._invite_protocol_chunk(
        target_group_id=200,
        source_group_id=100,
        members=members,
        tokens=toks,
        capture_dir=Path("."),
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 0.6
    assert max(starts) - min(starts) < 0.15
    assert elapsed < 6 * 0.12 * 0.9 + 0.2
