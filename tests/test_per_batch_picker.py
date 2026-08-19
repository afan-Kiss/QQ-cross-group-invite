# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
import pull_cross_group as pcg
from tests.conftest import invoke_758_send_hooks, wait_not_running

TOK_A1 = "u_PICKER1aAAAAAAAAAAAAAA"
TOK_A2 = "u_PICKER2aAAAAAAAAAAAAAA"
TOK_A3 = "u_PICKER3aAAAAAAAAAAAAAA"
TOK_B1 = "u_PICKER1bAAAAAAAAAAAAAA"
TOK_C2 = "u_PICKER2cAAAAAAAAAAAAAA"
OLD = "u_OLDMEMBERTOKENAAAAAAAA"


def _snap(members: list[SourceMember]) -> MembersCacheSnapshot:
    return MembersCacheSnapshot(source_group_id=100, filter_staff=True, members=tuple(members))


def test_batch_size_1_opens_picker_each_batch(monkeypatch):
    picker_calls: list[list[int]] = []
    invite_tokens: list[list[str]] = []
    maps = [
        {10001: TOK_A1},
        {10002: TOK_A2},
        {10003: TOK_A3},
    ]

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_calls.append(list(desired_qqs or []))
        return pcg.PickerSession(token_map=maps[len(picker_calls) - 1], fe7_pages=1)

    def fake_invite(**kwargs):
        invite_tokens.append(list(kwargs["tokens"]))
        return [(m, "success", None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="c", token=OLD, role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = _snap(members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002, 10003],
        batch_size=1,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert len(picker_calls) == 3
    assert picker_calls == [[10001], [10002], [10003]]
    assert invite_tokens == [[TOK_A1], [TOK_A2], [TOK_A3]]
    assert OLD not in {t for batch in invite_tokens for t in batch}


def test_batch_size_2_odd_tail_uses_second_picker(monkeypatch):
    picker_calls: list[list[int]] = []
    invite_tokens: list[list[str]] = []
    maps = [
        {10001: TOK_A1, 10002: TOK_B1},
        {10003: TOK_C2},
    ]

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_calls.append(list(desired_qqs or []))
        return pcg.PickerSession(token_map=maps[len(picker_calls) - 1], fe7_pages=1)

    def fake_invite(**kwargs):
        invite_tokens.append(list(kwargs["tokens"]))
        return [(m, "success", None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="c", token=OLD, role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = _snap(members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002, 10003],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert picker_calls == [[10001, 10002], [10003]]
    assert invite_tokens == [[TOK_A1, TOK_B1], [TOK_C2]]


def test_second_batch_missing_token_does_not_reuse_prior(monkeypatch):
    picker_calls: list[list[int]] = []
    invite_tokens: list[list[str]] = []

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_calls.append(list(desired_qqs or []))
        if len(picker_calls) == 1:
            return pcg.PickerSession(token_map={10001: TOK_A1, 10002: TOK_B1}, fe7_pages=1)
        return pcg.PickerSession(token_map={}, fe7_pages=1, missing_qqs=[10003])

    def fake_invite(**kwargs):
        invite_tokens.append(list(kwargs["tokens"]))
        return [(m, "success", None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token=OLD, role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="c", token=OLD, role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = _snap(members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002, 10003],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert picker_calls == [[10001, 10002], [10003]]
    assert invite_tokens == [[TOK_A1, TOK_B1]]
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10003]["status"] == "failed"
    assert OLD not in (by_qq[10003].get("reason") or "")
    assert "\u5f53\u524d\u9009\u62e9\u5668\u4f1a\u8bdd" in (by_qq[10003].get("reason") or "")
    assert by_qq[10001]["status"] == "success"


def test_protocol_chunking_keeps_tail_n1(monkeypatch):
    """Worker (not protocol fn) splits 11 as 6+5 when max=6, or with max=10 as 10+1."""
    sent: list[list[str]] = []
    picker_n = {"n": 0}

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        picker_n["n"] += 1
        qqs = list(desired_qqs or [])
        return cgb.PickerSession(
            token_map={q: f"u_REDACT{q % 100:02d}AAAAAAAAAAAAAA" for q in qqs},
            fe7_pages=1,
        )

    monkeypatch.setattr(cgb, "PROTOCOL_INVITE_PACKET_MAX", 10)
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
    members = [
        SourceMember(qq=20000 + i, nickname=f"m{i}", token=f"t{i}", role=MemberRole.MEMBER)
        for i in range(11)
    ]
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=11,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert [len(x) for x in sent] == [10, 1]
    assert picker_n["n"] == 2
    assert all(r["status"] == "success" for r in cgb.get_state()["results"])
