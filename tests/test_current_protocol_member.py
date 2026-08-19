# -*- coding: utf-8 -*-
"""current_qq / message follow protocol chunk, not only UI batch head."""
from __future__ import annotations

import time

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
from tests.conftest import invoke_758_send_hooks, wait_not_running

TOK = "u_REDACTaAAAAAAAAAAAAAAA"


def test_current_member_updates_per_protocol_chunk(monkeypatch):
    seen: list[tuple[int, str]] = []
    n = {"v": 0}

    def fake_picker(_cap, _t, _s, *, desired_qqs=None, stop_event=None):
        qqs = list(desired_qqs or [])
        # Capture current member as each protocol chunk begins (picker is first step).
        st = cgb.get_state()
        seen.append((int(st.get("current_qq") or 0), str(st.get("message") or "")))
        return cgb.PickerSession(
            token_map={q: f"u_T{q % 100:02d}AAAAAAAAAAAAAAAAAA"[:24] for q in qqs},
            fe7_pages=1,
        )

    def slow_758(**_k):
        n["v"] += 1
        time.sleep(0.02)
        return True, {"code": 0, "data": "1800"}

    members = [
        SourceMember(qq=10001 + i, nickname=f"m{i}", token=TOK, role=MemberRole.MEMBER)
        for i in range(7)
    ]
    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "send_cross_group_invite", invoke_758_send_hooks(slow_758))
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[m.qq for m in members],
        batch_size=7,
        filter_staff=True,
    )
    assert wait_not_running(timeout=5.0)
    assert len(seen) == 2
    assert seen[0][0] == 10001
    assert seen[1][0] == 10007
    assert "\u534f\u8bae\u5b50\u5305 1/2" in seen[0][1]
    assert "\u534f\u8bae\u5b50\u5305 2/2" in seen[1][1]
