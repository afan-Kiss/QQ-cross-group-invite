# -*- coding: utf-8 -*-
from __future__ import annotations

from cross_group_batch import MemberRole, SourceMember
import cross_group_batch as cgb


def test_onebot_member_without_token_is_kept(monkeypatch):
    monkeypatch.setattr(
        cgb,
        "_onebot_members",
        lambda *_a, **_k: [
            {"user_id": 10001, "nickname": "A", "role": "member", "card": "ca"},
            {"user_id": 10002, "nickname": "B", "role": "member", "card": "cb"},
        ],
    )
    monkeypatch.setattr(cgb, "fetch_fe7_token_map_live", lambda *_a, **_k: {10001: "tok-a"})
    monkeypatch.setattr(cgb, "scan_capture_fe7_token_map", lambda *_a, **_k: {})
    monkeypatch.setattr(cgb, "resolve_capture_dir", lambda *_a, **_k: None)
    monkeypatch.setattr(cgb, "load_cfg", lambda: {})

    members = cgb.load_source_members(100, filter_staff=True)
    assert {m.qq for m in members} == {10001, 10002}
    by = {m.qq: m for m in members}
    assert by[10001].token == "tok-a"
    assert by[10001].to_public_dict()["has_token"] is True
    assert by[10002].token == ""
    assert by[10002].to_public_dict()["has_token"] is False
    assert by[10002].to_public_dict()["token"] == ""
    assert by[10002].eligible is True
    assert by[10002].nickname == "B"


def test_partial_invalid_selection_rejects_whole_start(monkeypatch, patch_network):
    invited: list[int] = []
    monkeypatch.setattr(
        cgb,
        "_invite_one",
        lambda **kwargs: invited.append(kwargs["member"].qq) or (True, None, ""),
    )
    snap = cgb.MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=(
            SourceMember(qq=10001, nickname="A", token="t1", role=MemberRole.MEMBER, eligible=True),
            SourceMember(
                qq=10004,
                nickname="Admin",
                token="t4",
                role=MemberRole.ADMIN,
                eligible=False,
                filter_reason="admin",
            ),
        ),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap

    import pytest

    with pytest.raises(ValueError, match="\u72b6\u6001\u5df2\u53d8\u5316"):
        cgb.start_batch(
            target_group_id=200,
            source_group_id=100,
            interval_ms=100,
            qq_list=[10001, 10004],
            batch_size=10,
            filter_staff=True,
        )
    assert invited == []
    assert cgb.get_state()["running"] is False


def test_missing_selected_qq_rejects_start(monkeypatch, patch_network):
    snap = cgb.MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=(
            SourceMember(qq=10001, nickname="A", token="t1", role=MemberRole.MEMBER, eligible=True),
        ),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap

    import pytest

    with pytest.raises(ValueError, match="\u72b6\u6001\u5df2\u53d8\u5316"):
        cgb.start_batch(
            target_group_id=200,
            source_group_id=100,
            interval_ms=100,
            qq_list=[10001, 99999],
            batch_size=10,
            filter_staff=True,
        )
