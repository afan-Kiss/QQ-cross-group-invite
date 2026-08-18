# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
import pull_cross_group as pcg
from tests.conftest import wait_not_running

TOK_A = "u_REDACTaAAAAAAAAAAAAAAA"
TOK_B = "u_REDACTbAAAAAAAAAAAAAAA"
TOK_C = "u_REDACTcAAAAAAAAAAAAAAA"


def _snap(members: list[SourceMember]) -> MembersCacheSnapshot:
    return MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=tuple(members),
    )


def test_batch_count_1_single_member_sends(monkeypatch):
    sent: list[list[str]] = []

    def fake_invite(**kwargs):
        sent.append(list(kwargs["tokens"]))
        return [(m, True, None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token="old", role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(token_map={10001: TOK_A}, fe7_pages=1),
    )
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = _snap(members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001],
        batch_size=1,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert sent == [[TOK_A]]
    assert cgb.get_state()["success"] == 1


def test_batch_count_2_with_odd_final_batch(monkeypatch):
    batches: list[list[int]] = []

    def fake_invite(**kwargs):
        batches.append([m.qq for m in kwargs["members"]])
        return [(m, True, None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token="t1", role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="t2", role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="c", token="t3", role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(
            token_map={10001: TOK_A, 10002: TOK_B, 10003: TOK_C},
            fe7_pages=1,
        ),
    )
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
    assert batches == [[10001, 10002], [10003]]
    assert cgb.get_state()["success"] == 3


def test_batch_count_1_three_members_three_batches(monkeypatch):
    batches: list[list[int]] = []

    def fake_invite(**kwargs):
        batches.append([m.qq for m in kwargs["members"]])
        return [(m, True, None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token="t1", role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="t2", role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="c", token="t3", role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(
            token_map={10001: TOK_A, 10002: TOK_B, 10003: TOK_C},
            fe7_pages=1,
        ),
    )
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
    assert batches == [[10001], [10002], [10003]]


def test_partial_ready_does_not_refuse_remaining(monkeypatch):
    sent: list[list[int]] = []

    def fake_invite(**kwargs):
        sent.append([m.qq for m in kwargs["members"]])
        return [(m, True, None, "") for m in kwargs["members"]]

    members = [
        SourceMember(qq=10001, nickname="a", token="t1", role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="t2", role=MemberRole.MEMBER),
    ]
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(token_map={10002: TOK_B}, fe7_pages=1),
    )
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = _snap(members)
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert sent == [[10002]]
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10001]["status"] == "failed"
    assert "\u5f53\u524d\u9009\u62e9\u5668\u4f1a\u8bdd" in (by_qq[10001].get("reason") or "")
    assert by_qq[10002]["status"] == "success"


def test_invite_batch_allows_single_token(monkeypatch):
    sent = []
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent.append(k) or (True, {"code": 0, "data": "1800"}),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    member = SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER)
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[member],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert len(sent) == 1
    assert sent[0]["invitee_tokens"] == [TOK_A]
    assert results[0][1] is True


def test_live_builders_sizes_and_target():
    import capture_utils as cu

    hx111 = cu.build_88d_111(1009406709)
    assert len(bytes.fromhex(hx111)) == 48
    assert cu.nested_group_in_88d_111(hx111) == 1009406709

    hx11ec = cu.build_11ec_1(1009406709)
    assert len(bytes.fromhex(hx11ec)) == 266
    from pb_utils import decode_pb_message, extract_field_bytes

    body = extract_field_bytes(bytes.fromhex(hx11ec), 4)
    assert decode_pb_message(body).get(1) == [1009406709]

    assert len(bytes.fromhex(cu.build_fe7_group_list(1080591561))) == 96
    nxt = cu.build_fe7_group_list(1080591561, page_cursor=b"c" * 36)
    assert len(bytes.fromhex(nxt)) == 134
