# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import cross_group_batch as cgb
from cross_group_batch import TaskIdMismatch, TaskRunStatus
from tests.conftest import wait_not_running, wait_until


def test_stop_batch_mismatch_raises(monkeypatch, patch_network):
    members = [m for m in patch_network if m.eligible][:2]
    monkeypatch.setattr(cgb, "load_source_members", lambda *a, **k: list(members))
    monkeypatch.setattr(cgb, "_invite_one", lambda **k: (True, None, ""))

    tid = cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=10,
        qq_list=[m.qq for m in members],
    )
    assert wait_until(
        lambda: cgb.get_state()["status"] == TaskRunStatus.RUNNING.value,
        timeout=2.0,
    )

    with pytest.raises(TaskIdMismatch):
        cgb.stop_batch(task_id="not-the-task")

    st = cgb.get_state()
    assert st["running"] is True
    assert st["status"] == TaskRunStatus.RUNNING.value

    cgb.stop_batch(task_id=tid)
    assert wait_not_running(timeout=2.0)
    assert cgb.get_state()["status"] == TaskRunStatus.STOPPED.value


def test_stop_batch_none_stops_current(monkeypatch, patch_network):
    members = [m for m in patch_network if m.eligible][:2]
    monkeypatch.setattr(cgb, "load_source_members", lambda *a, **k: list(members))
    monkeypatch.setattr(cgb, "_invite_one", lambda **k: (True, None, ""))

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=10,
        qq_list=[m.qq for m in members],
    )
    assert wait_until(lambda: cgb.get_state()["done"] >= 1, timeout=2.0)
    cgb.stop_batch()
    assert wait_not_running(timeout=2.0)
    assert cgb.get_state()["status"] == TaskRunStatus.STOPPED.value
