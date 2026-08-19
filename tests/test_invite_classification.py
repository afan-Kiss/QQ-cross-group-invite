# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
from pb_utils import encode_field_varint
from tests.conftest import wait_not_running

TOK_A = "u_REDACTaAAAAAAAAAAAAAAA"


def _snap(members: list[SourceMember]) -> MembersCacheSnapshot:
    return MembersCacheSnapshot(source_group_id=100, filter_staff=True, members=tuple(members))


def _one_member() -> SourceMember:
    return SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER)


def test_classify_1289_is_rate_limited():
    assert cgb.classify_invite_failure(1289, "") == "rate_limited"
    assert cgb.classify_invite_failure(1289, "whatever") == "rate_limited"


def test_classify_message_frequent_without_1289():
    assert cgb.classify_invite_failure(1, "\u64cd\u4f5c\u9891\u7e41") == "rate_limited"
    assert cgb.classify_invite_failure(None, "too fast") == "rate_limited"
    assert cgb.classify_invite_failure(2, "rate limited") == "rate_limited"


def test_classify_rate_word_boundary_not_substring():
    assert cgb.classify_invite_failure(None, "rate limited") == "rate_limited"
    assert cgb.classify_invite_failure(None, "too fast") == "rate_limited"
    assert cgb.classify_invite_failure(None, "rate_limited") == "rate_limited"
    assert cgb.classify_invite_failure(None, "rate-limit hit") == "rate_limited"
    assert cgb.classify_invite_failure(None, "separate protocol error") == "failed"
    assert cgb.classify_invite_failure(None, "generated packet failed") == "failed"


def test_classify_ordinary_protocol_error_is_failed():
    assert cgb.classify_invite_failure(2, "\u9080\u8bf7\u5931\u8d25") == "failed"
    assert cgb.classify_invite_failure(None, "758 \u8fd4\u56de\u65e0\u6cd5\u786e\u8ba4\u9080\u8bf7\u6210\u529f") == "failed"


def test_classifier_never_returns_cancelled():
    assert cgb.classify_invite_failure(None, "\u5df2\u505c\u6b62\uff0c\u672a\u53d1\u9001\u9080\u8bf7") != "cancelled"
    assert cgb.classify_invite_failure(1289, "cancelled") == "rate_limited"


def test_758_code_1289_counts_rate_limited_not_failed(monkeypatch):
    fail_hex = encode_field_varint(3, 1289).hex()
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **_k: (False, {"code": 0, "data": fail_hex}),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    member = _one_member()
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: cgb.PickerSession(token_map={10001: TOK_A}, fe7_pages=1),
    )
    with cgb._members_lock:
        cgb._members_snapshot = _snap([member])
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001],
        batch_size=1,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10001]["status"] == "rate_limited"
    assert st["rate_limited_count"] == 1
    assert st["failed_count"] == 0
    assert st["failed"] == 0
    assert any(x["qq"] == 10001 for x in st["frequent"])
    assert not any(x["qq"] == 10001 for x in st["errors"])


def test_invite_batch_1289_kind_is_rate_limited(monkeypatch):
    fail_hex = encode_field_varint(3, 1289).hex()
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **_k: (False, {"code": 0, "data": fail_hex}),
    )
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[_one_member()],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert results[0][1] == "rate_limited"
    assert results[0][2] == 1289


def test_message_frequent_without_1289_is_rate_limited(monkeypatch):
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **_k: (False, {"code": 1, "message": "\u64cd\u4f5c\u9891\u7e41"}),
    )
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[_one_member()],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert results[0][1] == "rate_limited"


def test_ordinary_protocol_error_is_failed(monkeypatch):
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **_k: (False, {"code": 2, "message": "\u9080\u8bf7\u5931\u8d25"}),
    )
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[_one_member()],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert results[0][1] == "failed"


def test_cancelled_does_not_increment_failed_or_rate_limited(monkeypatch):
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    sent = []
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent.append(k) or (True, {"code": 0, "data": "1800"}),
    )
    cgb._state._stop.set()
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[_one_member()],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert sent == []
    assert results[0][1] == "cancelled"
    member = _one_member()
    with cgb._state_lock:
        cgb._state.results = [
            cgb.InviteResult(
                qq=member.qq,
                nickname=member.nickname,
                status=cgb.InviteResultStatus.INVITING,
            )
        ]
    cgb._apply_invite_outcomes(results, {member.qq: cgb._now()})
    st = cgb.get_state()
    assert st["failed_count"] == 0
    assert st["rate_limited_count"] == 0
    assert st["cancelled_count"] == 1
    assert st["done"] == 1
    assert st["success"] + st["failed"] + st["rate_limited"] + st["cancelled"] == st["done"]
