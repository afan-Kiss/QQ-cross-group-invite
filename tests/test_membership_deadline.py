# -*- coding: utf-8 -*-
"""Membership verify must honor shared deadline via real HTTP timeout."""
from __future__ import annotations

import time

import pull_cross_group as pcg


def test_wait_membership_timeout_zero_makes_zero_http(monkeypatch):
    calls: list[float] = []

    def fake_onebot(*_a, **kwargs):
        calls.append(float(kwargs.get("timeout") or 0))
        return {"status": "ok", "data": {"user_id": 1}}

    monkeypatch.setattr(pcg, "onebot_action", fake_onebot)
    out = pcg.wait_target_membership(1, 2, timeout=0)
    assert out is None
    assert calls == []


def test_target_group_has_member_passes_request_timeout(monkeypatch):
    seen: list[float] = []

    def fake_onebot(*_a, **kwargs):
        seen.append(float(kwargs.get("timeout") or 0))
        return {"status": "ok", "retcode": 0, "data": {"user_id": 9}}

    monkeypatch.setattr(pcg, "onebot_action", fake_onebot)
    assert pcg.target_group_has_member(1, 9, request_timeout=1.25) is True
    assert seen == [1.25]


def test_six_member_verify_wall_clock_under_retry_budget(monkeypatch):
    timeouts: list[float] = []
    monkeypatch.setattr(pcg, "MEMBERSHIP_RETRY_SEC", 0.4)
    monkeypatch.setattr(pcg, "MEMBERSHIP_HTTP_TIMEOUT_CAP", 0.2)
    monkeypatch.setattr(pcg, "MEMBERSHIP_RETRY_INTERVAL", 0.05)

    def fake_onebot(*_a, **kwargs):
        t = float(kwargs.get("timeout") or 0)
        timeouts.append(t)
        time.sleep(min(0.05, t))
        raise TimeoutError("slow")

    monkeypatch.setattr(pcg, "onebot_action", fake_onebot)
    import cross_group_batch as cgb
    from cross_group_batch import MemberRole, SourceMember

    monkeypatch.setattr(cgb, "MEMBERSHIP_RETRY_SEC", 0.4)
    members = [
        SourceMember(qq=30000 + i, nickname=f"m{i}", token="t", role=MemberRole.MEMBER)
        for i in range(6)
    ]
    t0 = time.monotonic()
    outcomes = cgb._verify_membership_chunk(1, members, 0)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.9
    assert len(outcomes) == 6
    assert all(kind == "failed" for _m, kind, _c, _msg in outcomes)
    assert timeouts
    assert max(timeouts) <= 0.2 + 1e-6
    for t in timeouts:
        assert t > 0
