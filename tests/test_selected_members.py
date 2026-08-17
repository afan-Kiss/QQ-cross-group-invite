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
        invited.append(kwargs["member"].qq)
        return True, None, ""

    monkeypatch.setattr(cgb, "_invite_one", capture_invite)

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


def test_qq_list_excludes_ineligible_staff(monkeypatch, patch_network):
    # 10004 is admin / ineligible in sample_members
    invited: list[int] = []

    def capture_invite(**kwargs):
        invited.append(kwargs["member"].qq)
        return True, None, ""

    monkeypatch.setattr(cgb, "_invite_one", capture_invite)

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10004],
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["total"] == 1
    assert invited == [10001]
