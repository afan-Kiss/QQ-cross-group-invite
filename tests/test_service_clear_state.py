# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import InviteRecord


def test_clear_logs():
    with cgb._state_lock:
        cgb._state.logs.extend(["a", "b", "c"])
    cgb.clear_logs()
    assert cgb.get_state()["logs"] == []


def test_clear_failed_keeps_task_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(cgb, "_tasks_path", lambda: tmp_path / "tasks.json")
    with cgb._state_lock:
        cgb._state.task_id = "t-clear"
        cgb._state.success = 2
        cgb._state.failed_count = 1
        cgb._state.errors.append(InviteRecord(qq=1, nickname="n", reason="fail"))
    cgb._persist_current_task()
    cgb.clear_failed()
    assert cgb.get_state()["errors"] == []
    assert cgb.get_state()["failed"] == 1
    persisted = {t["id"]: t for t in cgb._load_tasks()}
    assert persisted["t-clear"]["failed"] == 1
    assert persisted["t-clear"]["success"] == 2


def test_clear_rate_limits_keeps_task_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(cgb, "_tasks_path", lambda: tmp_path / "tasks.json")
    with cgb._state_lock:
        cgb._state.task_id = "t-clear2"
        cgb._state.success = 1
        cgb._state.rate_limited_count = 1
        cgb._state.frequent.append(InviteRecord(qq=2, nickname="f", reason="rate"))
    cgb._persist_current_task()
    cgb.clear_rate_limits()
    assert cgb.get_state()["frequent"] == []
    assert cgb.get_state()["rate_limited"] == 1
    persisted = {t["id"]: t for t in cgb._load_tasks()}
    assert persisted["t-clear2"]["rate_limited"] == 1
    assert persisted["t-clear2"]["success"] == 1


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
