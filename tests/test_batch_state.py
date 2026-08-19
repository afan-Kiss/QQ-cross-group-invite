# -*- coding: utf-8 -*-
from __future__ import annotations

from cross_group_batch import (
    BatchState,
    InviteRecord,
    InviteResult,
    InviteResultStatus,
    RateBucket,
    TaskRunStatus,
)


EXPECTED_STATE_KEYS = {
    "running",
    "status",
    "task_id",
    "total",
    "done",
    "success",
    "current_qq",
    "current_nickname",
    "message",
    "error_message",
    "started_at",
    "finished_at",
    "source_group_id",
    "target_group_id",
    "batch_size",
    "batch_count",
    "interval_ms",
    "batch_number",
    "batch_total_count",
    "batch_done",
    "total_batches",
    "next_invite_at",
    "interval_remaining_ms",
    "failed_count",
    "rate_limited_count",
    "cancelled",
    "cancelled_count",
    "frequent",
    "errors",
    "results",
    "rate_series",
    "logs",
    "timeline",
}


def test_batch_state_to_dict_fields():
    state = BatchState(
        running=True,
        status=TaskRunStatus.RUNNING,
        task_id="t1",
        total=3,
        done=1,
        success=1,
        message="邀请运行中",
        source_group_id=111,
        target_group_id=222,
        batch_size=20,
        interval_ms=1500,
        frequent=[InviteRecord(qq=1, nickname="a", reason="频繁")],
        errors=[InviteRecord(qq=2, nickname="b", reason="失败")],
        results=[InviteResult(qq=3, nickname="c", status=InviteResultStatus.WAITING)],
        rate_series=[RateBucket(timestamp=100, success=1)],
        logs=["line"],
        timeline=[{"event": "created"}],
    )
    data = state.to_dict()
    assert EXPECTED_STATE_KEYS.issubset(data.keys())
    assert data["running"] is True
    assert data["status"] == "running"
    assert data["task_id"] == "t1"
    assert data["total"] == 3
    assert data["done"] == 1
    assert data["success"] == 1
    assert data["batch_count"] == 20
    assert data["batch_total_count"] == 20
    assert len(data["frequent"]) == 1
    assert len(data["errors"]) == 1
    assert len(data["results"]) == 1
    assert data["rate_series"][0]["success"] == 1
    assert data["logs"] == ["line"]
    assert data["timeline"][0]["event"] == "created"


def test_task_run_status_values():
    assert TaskRunStatus.IDLE.value == "idle"
    assert TaskRunStatus.PREPARING.value == "preparing"
    assert TaskRunStatus.RUNNING.value == "running"
    assert TaskRunStatus.STOPPING.value == "stopping"
    assert TaskRunStatus.STOPPED.value == "stopped"
    assert TaskRunStatus.COMPLETED.value == "completed"
    assert TaskRunStatus.ERROR.value == "error"
    assert TaskRunStatus.INTERRUPTED.value == "interrupted"


def test_status_transition_helpers():
    """Document expected lifecycle status values used by the engine."""
    state = BatchState()
    assert state.status == TaskRunStatus.IDLE
    assert state.running is False

    # preparing -> running -> completed
    state.status = TaskRunStatus.PREPARING
    state.running = True
    assert state.to_dict()["status"] == "preparing"

    state.status = TaskRunStatus.RUNNING
    assert state.to_dict()["status"] == "running"

    state.status = TaskRunStatus.COMPLETED
    state.running = False
    assert state.to_dict()["status"] == "completed"
    assert state.to_dict()["running"] is False

    # stopping -> stopped
    state.status = TaskRunStatus.STOPPING
    assert state.to_dict()["status"] == "stopping"
    state.status = TaskRunStatus.STOPPED
    assert state.to_dict()["status"] == "stopped"

    # error terminal
    state.status = TaskRunStatus.ERROR
    state.error_message = "boom"
    d = state.to_dict()
    assert d["status"] == "error"
    assert d["error_message"] == "boom"


def test_invite_result_to_dict():
    r = InviteResult(
        qq=9,
        nickname="n",
        status=InviteResultStatus.SUCCESS,
        reason="",
        duration_ms=12,
    )
    d = r.to_dict()
    assert d["qq"] == 9
    assert d["status"] == "success"
    assert d["duration_ms"] == 12
    assert InviteResultStatus.CANCELLED.value == "cancelled"
