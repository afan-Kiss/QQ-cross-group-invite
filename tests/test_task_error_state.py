# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import TaskRunStatus
from tests.conftest import wait_not_running


def test_worker_exception_sets_error_not_completed(monkeypatch, patch_network):
    def boom(*_a, **_k):
        raise RuntimeError("forced worker failure")

    monkeypatch.setattr(cgb, "open_cross_group_picker", boom)

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        batch_size=5,
        qq_list=[m.qq for m in patch_network if m.eligible][:2],
    )

    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["running"] is False
    assert st["status"] == TaskRunStatus.ERROR.value
    assert st["message"] != "已完成"
    assert "forced worker failure" in st["message"]
    assert "forced worker failure" in st["error_message"]
