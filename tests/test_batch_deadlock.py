# -*- coding: utf-8 -*-
"""CRITICAL: ensure RLock + finish/_log paths cannot deadlock worker threads."""
from __future__ import annotations

import threading
import time

import cross_group_batch as cgb
from cross_group_batch import (
    InviteResult,
    InviteResultStatus,
    SourceMember,
    TaskRunStatus,
)
from tests.conftest import wait_not_running, wait_until


def test_log_while_holding_lock_does_not_deadlock():
    done = threading.Event()
    err: list[BaseException] = []

    def worker():
        try:
            with cgb._state_lock:
                cgb._log("holding lock then log")
                cgb._finish_member(
                    SourceMember(qq=1, nickname="a", token="t"),
                    status=InviteResultStatus.SUCCESS,
                    reason="",
                    started_at=time.time(),
                )
                cgb._finish_member(
                    SourceMember(qq=2, nickname="b", token="t"),
                    status=InviteResultStatus.FAILED,
                    reason="fail",
                    started_at=time.time(),
                )
                cgb._finish_member(
                    SourceMember(qq=3, nickname="c", token="t"),
                    status=InviteResultStatus.RATE_LIMITED,
                    reason="频繁",
                    started_at=time.time(),
                )
                cgb._log("after finish paths")
        except BaseException as exc:  # noqa: BLE001
            err.append(exc)
        finally:
            done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    assert done.wait(2.0), "deadlock: thread holding lock + _log/_finish did not finish in 2s"
    t.join(timeout=0.5)
    assert not err
    assert cgb._state.success == 1
    assert len(cgb._state.errors) == 1
    assert len(cgb._state.frequent) == 1


def test_start_batch_success_fail_frequent_finishes(monkeypatch, patch_network):
    call = {"n": 0}

    def invite(**kwargs):
        out = []
        for m in kwargs["members"]:
            call["n"] += 1
            n = call["n"]
            if n == 1:
                out.append((m, True, None, ""))
            elif n == 2:
                out.append((m, False, 1, "邀请失败"))
            else:
                out.append((m, False, 1289, "操作太频繁"))
        return out

    monkeypatch.setattr(cgb, "_invite_batch", invite)

    # Only first 3 eligible members
    members = [m for m in patch_network if m.eligible][:3]
    monkeypatch.setattr(
        cgb,
        "load_source_members",
        lambda *a, **k: list(members),
    )

    tid = cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        batch_size=10,
        qq_list=[m.qq for m in members],
    )
    assert tid
    assert wait_not_running(timeout=2.0), "worker did not finish within 2s"
    st = cgb.get_state()
    assert st["running"] is False
    assert st["status"] == TaskRunStatus.COMPLETED.value
    assert st["success"] == 1
    assert len(st["errors"]) == 1
    assert len(st["frequent"]) == 1
    assert st["done"] == 3


def test_finish_member_under_lock_with_results_list():
    """Simulate hot path: results list present, finish while lock held, then log."""
    with cgb._state_lock:
        cgb._state.results = [
            InviteResult(qq=11, nickname="x"),
            InviteResult(qq=12, nickname="y"),
        ]
        cgb._state.running = True
        cgb._state.status = TaskRunStatus.RUNNING

    done = threading.Event()

    def hot():
        with cgb._state_lock:
            for qq, status, reason in (
                (11, InviteResultStatus.SUCCESS, ""),
                (12, InviteResultStatus.FAILED, "err"),
            ):
                cgb._finish_member(
                    SourceMember(qq=qq, nickname=str(qq), token="t"),
                    status=status,
                    reason=reason,
                    started_at=time.time(),
                )
                cgb._log(f"logged {qq}")
        done.set()

    threading.Thread(target=hot, daemon=True).start()
    assert done.wait(2.0), "deadlock on finish+log under RLock"
    assert wait_until(lambda: cgb._state.done == 2, timeout=1.0)
    with cgb._state_lock:
        cgb._state.running = False
