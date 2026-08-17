# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import InviteRecord


def test_clear_logs():
    with cgb._state_lock:
        cgb._state.logs.extend(["a", "b", "c"])
    cgb.clear_logs()
    assert cgb.get_state()["logs"] == []


def test_clear_failed():
    with cgb._state_lock:
        cgb._state.errors.append(
            InviteRecord(qq=1, nickname="n", reason="fail")
        )
    cgb.clear_failed()
    assert cgb.get_state()["errors"] == []


def test_clear_rate_limits():
    with cgb._state_lock:
        cgb._state.frequent.append(
            InviteRecord(qq=2, nickname="f", reason="频繁")
        )
    cgb.clear_rate_limits()
    assert cgb.get_state()["frequent"] == []


def test_clear_state_all_kinds():
    with cgb._state_lock:
        cgb._state.logs.append("x")
        cgb._state.errors.append(InviteRecord(qq=1, nickname="e", reason="e"))
        cgb._state.frequent.append(InviteRecord(qq=2, nickname="f", reason="f"))
    cgb.clear_state()
    st = cgb.get_state()
    assert st["logs"] == []
    assert st["errors"] == []
    assert st["frequent"] == []


def test_clear_state_selective():
    with cgb._state_lock:
        cgb._state.logs.append("keep-fail")
        cgb._state.errors.append(InviteRecord(qq=1, nickname="e", reason="e"))
        cgb._state.frequent.append(InviteRecord(qq=2, nickname="f", reason="f"))
    cgb.clear_state(["logs"])
    st = cgb.get_state()
    assert st["logs"] == []
    assert len(st["errors"]) == 1
    assert len(st["frequent"]) == 1
