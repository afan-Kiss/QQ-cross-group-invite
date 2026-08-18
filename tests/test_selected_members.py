# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import cross_group_batch as cgb
from tests.conftest import wait_not_running


def test_empty_qq_list_raises(patch_network):
    with pytest.raises(ValueError, match="至少选择"):
        cgb.start_batch(
            target_group_id=200,
            source_group_id=100,
            interval_ms=100,
            qq_list=[],
        )


def test_qq_list_filters_members(monkeypatch, patch_network):
    selected = [10001, 10003]
    invited: list[int] = []

    def capture_invite(**kwargs):
        invited.extend(m.qq for m in kwargs["members"])
        return [(m, True, None, "") for m in kwargs["members"]]

    monkeypatch.setattr(cgb, "_invite_batch", capture_invite)

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        batch_size=10,
        qq_list=selected,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["total"] == 2
    assert st["success"] == 2
    assert set(invited) == set(selected)
    assert all(r["qq"] in selected for r in st["results"])


def test_qq_list_rejects_ineligible_staff_selection(monkeypatch, patch_network, sample_members):
    # 10004 is admin / ineligible — whole start must fail before inviting.
    invited: list[int] = []

    def capture_invite(**kwargs):
        invited.extend(m.qq for m in kwargs["members"])
        return [(m, True, None, "") for m in kwargs["members"]]

    monkeypatch.setattr(cgb, "_invite_batch", capture_invite)
    snap = cgb.MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=tuple(sample_members),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap

    with pytest.raises(ValueError, match="\u72b6\u6001\u5df2\u53d8\u5316"):
        cgb.start_batch(
            target_group_id=200,
            source_group_id=100,
            interval_ms=100,
            qq_list=[10001, 10004],
            filter_staff=True,
        )
    assert invited == []
