# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cross_group_batch as cgb
from cross_group_batch import (
    BatchState,
    InviteRecord,
    InviteResult,
    InviteResultStatus,
    MemberRole,
    SourceMember,
    TaskRunStatus,
)


def _reset_engine() -> None:
    # Ensure any leftover worker finishes quickly
    cgb._state._stop.set()
    deadline = time.time() + 2.0
    while cgb._state.running and time.time() < deadline:
        time.sleep(0.01)

    with cgb._state_lock:
        cgb._state = BatchState()
        cgb._owned_task_id = None
        cgb._758_auth_seq = 0
        cgb._last_758_send_mono = 0.0
    with cgb._members_lock:
        cgb._members_snapshot = None


def invoke_758_send_hooks(fn):
    """Test helper: monkeypatched 758 still fires production send-gate hooks."""

    def wrapper(**kwargs):
        before = kwargs.get("before_network_send")
        after = kwargs.get("after_network_send")
        on_resp = kwargs.get("on_response_received")
        on_exc = kwargs.get("on_send_exception")
        if before is not None:
            before()
        try:
            result = fn(**kwargs)
        except Exception:
            if after is not None:
                after()
            if on_exc is not None:
                on_exc()
            raise
        if after is not None:
            after()
        if on_resp is not None:
            on_resp()
        return result

    return wrapper


@pytest.fixture(autouse=True)
def _clean_batch_engine(monkeypatch, tmp_path):
    _reset_engine()
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setattr(cgb, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cgb, "TASKS_FILE", tasks_file)
    monkeypatch.setattr(cgb, "load_cfg", lambda: {})
    monkeypatch.setattr(
        cgb, "resolve_capture_dir", lambda _cfg: tmp_path / "capture"
    )
    yield
    _reset_engine()


@pytest.fixture
def sample_members():
    return [
        SourceMember(qq=10001, nickname="alice", token="tok-a", role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="bob", token="tok-b", role=MemberRole.MEMBER),
        SourceMember(qq=10003, nickname="carol", token="tok-c", role=MemberRole.MEMBER),
        SourceMember(
            qq=10004,
            nickname="admin",
            token="tok-d",
            role=MemberRole.ADMIN,
            eligible=False,
            filter_reason="管理员",
        ),
    ]


@pytest.fixture
def patch_network(monkeypatch, sample_members):
    """Make invite path instant; no NapCat needed."""

    def fake_load(source_group_id, *, filter_staff=True, capture_dir=None, record_logs=False):
        return list(sample_members)

    monkeypatch.setattr(cgb, "load_source_members", fake_load)
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *a, **k: cgb.PickerSession(
            token_map={m.qq: m.token for m in sample_members if m.token},
            fe7_pages=1,
        ),
    )
    monkeypatch.setattr(cgb, "token_owner_safe", lambda *a, **k: True)
    monkeypatch.setattr(cgb, "query_invitee_token", lambda *a, **k: "")
    def _instant_invite(**k):
        return [(m, True, None, "") for m in k["members"]]

    monkeypatch.setattr(cgb, "_invite_protocol_chunk", _instant_invite)
    monkeypatch.setattr(cgb, "_invite_batch", _instant_invite)
    return sample_members


def wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def wait_not_running(timeout=2.0) -> bool:
    return wait_until(lambda: not cgb.get_state()["running"], timeout=timeout)
