# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import cross_group_batch as cgb
from cross_group_batch import MemberRole, SourceMember
from tests.conftest import wait_not_running, wait_until


def _members(n: int) -> list[SourceMember]:
    return [
        SourceMember(qq=20000 + i, nickname=f"m{i}", token=f"t{i}", role=MemberRole.MEMBER)
        for i in range(n)
    ]


def _patch_invite(monkeypatch, members):
    monkeypatch.setattr(cgb, "load_source_members", lambda *a, **k: list(members))
    monkeypatch.setattr(cgb, "missing_picker_templates", lambda *a, **k: [])
    monkeypatch.setattr(cgb, "open_cross_group_picker", lambda *a, **k: "fe7")
    monkeypatch.setattr(cgb, "token_owner_safe", lambda *a, **k: True)
    monkeypatch.setattr(cgb, "query_invitee_token", lambda *a, **k: "")
    monkeypatch.setattr(cgb, "_invite_one", lambda **k: (True, None, ""))


@pytest.mark.parametrize(
    "total,batch_size,expected_last",
    [
        (25, 20, 5),
        (40, 20, 20),
        (1, 20, 1),
        (21, 20, 1),
    ],
)
def test_last_batch_total_count(monkeypatch, total, batch_size, expected_last):
    members = _members(total)
    _patch_invite(monkeypatch, members)

    observed: list[int] = []
    orig_finish = cgb._finish_member

    def wrap_finish(member, **kwargs):
        with cgb._state_lock:
            observed.append(cgb._state.batch_total_count)
        return orig_finish(member, **kwargs)

    monkeypatch.setattr(cgb, "_finish_member", wrap_finish)

    cgb.start_batch(
        target_group_id=900,
        source_group_id=800,
        interval_ms=100,
        batch_size=batch_size,
        qq_list=[m.qq for m in members],
    )
    assert wait_not_running(timeout=8.0)
    st = cgb.get_state()
    assert st["done"] == total
    assert st["batch_total_count"] == expected_last
    assert st["batch_done"] == expected_last
    assert observed[-expected_last:] == [expected_last] * expected_last
    if total > batch_size:
        assert observed[0] == batch_size


def test_batch_done_on_last_partial_batch(monkeypatch):
    members = _members(25)
    _patch_invite(monkeypatch, members)

    cgb.start_batch(
        target_group_id=900,
        source_group_id=800,
        interval_ms=100,
        batch_size=20,
        qq_list=[m.qq for m in members],
    )
    assert wait_until(lambda: cgb.get_state()["done"] >= 20, timeout=5.0)
    assert wait_not_running(timeout=8.0)
    st = cgb.get_state()
    assert st["batch_number"] == 2
    assert st["batch_total_count"] == 5
    assert st["batch_done"] == 5
    assert sum(1 for e in st["timeline"] if e.get("event") == "batch_start") == 2
