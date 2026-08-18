# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import TaskRunStatus
from tests.conftest import wait_not_running


def test_timeline_error_once(monkeypatch, patch_network):
    def boom(*_a, **_k):
        raise RuntimeError("only-once-error")

    monkeypatch.setattr(cgb, "query_source_context_token", boom)

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        batch_size=5,
        qq_list=[m.qq for m in patch_network if m.eligible][:1],
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["status"] == TaskRunStatus.ERROR.value
    errors = [e for e in st["timeline"] if e.get("event") == "error"]
    assert len(errors) == 1
    assert "only-once-error" in errors[0].get("detail", "")
