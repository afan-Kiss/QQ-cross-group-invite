# -*- coding: utf-8 -*-
from __future__ import annotations

import time

import cross_group_batch as cgb
from cross_group_batch import TaskRunStatus
from tests.conftest import wait_not_running, wait_until


def test_stop_batch_interrupts_long_interval(monkeypatch, patch_network):
    members = [m for m in patch_network if m.eligible][:3]
    monkeypatch.setattr(
        cgb,
        "load_source_members",
        lambda *a, **k: list(members),
    )
    # Instant invites; long wait between them exercises interruptible wait
    monkeypatch.setattr(cgb, "_invite_one", lambda **k: (True, None, ""))

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=60_000,
        batch_size=10,
        qq_list=[m.qq for m in members],
    )

    assert wait_until(
        lambda: cgb.get_state()["status"] == TaskRunStatus.RUNNING.value
        and cgb.get_state()["done"] >= 1,
        timeout=2.0,
    ), "batch never entered running / first invite"

    t0 = time.time()
    cgb.stop_batch()
    assert wait_not_running(timeout=1.0), "stop_batch did not finish within 1s"
    elapsed = time.time() - t0
    assert elapsed < 1.0

    st = cgb.get_state()
    assert st["running"] is False
    assert st["status"] == TaskRunStatus.STOPPED.value
    assert st["message"] == "已停止"
