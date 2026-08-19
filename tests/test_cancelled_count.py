# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import (
    InviteResultStatus,
    MemberRole,
    MembersCacheSnapshot,
    SourceMember,
)
from tests.conftest import wait_not_running

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def test_cancelled_count_on_stop_before_send(monkeypatch):
    members = [
        SourceMember(qq=10001, nickname="a", token=TOK, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token=TOK, role=MemberRole.MEMBER),
    ]

    def fake_picker(*_a, **_k):
        raise cgb.PickerStopped("PICKER_FE7")

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["cancelled"] == 2
    assert st["cancelled_count"] == 2
    assert st["failed_count"] == 0
    assert st["rate_limited_count"] == 0
    assert st["success"] == 0
    assert st["done"] == 2
    assert st["success"] + st["failed"] + st["rate_limited"] + st["cancelled"] == st["done"]
    persisted = {t["id"]: t for t in cgb.list_tasks()}
    rec = persisted[st["task_id"]]
    assert rec["cancelled"] == 2
    assert rec["failed"] == 0


def test_finish_member_cancelled_increments_count():
    m = SourceMember(qq=9, nickname="n", token=TOK, role=MemberRole.MEMBER)
    with cgb._state_lock:
        cgb._state.results = [cgb.InviteResult(qq=9, nickname="n")]
    cgb._finish_member(
        m,
        status=InviteResultStatus.CANCELLED,
        reason="\u5df2\u505c\u6b62\uff0c\u672a\u53d1\u9001\u9080\u8bf7",
        started_at=cgb._now(),
    )
    st = cgb.get_state()
    assert st["cancelled_count"] == 1
    assert st["done"] == 1
    assert st["failed_count"] == 0
    assert st["rate_limited_count"] == 0
    assert st["success"] + st["failed"] + st["rate_limited"] + st["cancelled"] == st["done"]
