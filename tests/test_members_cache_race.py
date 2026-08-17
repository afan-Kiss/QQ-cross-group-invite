# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember


def _make_members(group_id: int, n: int = 3) -> list[SourceMember]:
    return [
        SourceMember(
            qq=group_id * 1000 + i,
            nickname=f"g{group_id}-m{i}",
            token=f"tok-{group_id}-{i}",
            role=MemberRole.MEMBER,
        )
        for i in range(n)
    ]


def test_members_cache_race_no_cross_group_mismatch():
    """Interleaved loads/reads must never mix group A key with group B members."""
    stop = threading.Event()
    errors: list[str] = []
    reads = {"n": 0}

    def writer(gid: int) -> None:
        while not stop.is_set():
            members = _make_members(gid)
            snapshot = MembersCacheSnapshot(
                source_group_id=gid,
                filter_staff=True,
                members=tuple(members),
            )
            with cgb._members_lock:
                cgb._members_snapshot = snapshot

    def reader() -> None:
        while not stop.is_set():
            with cgb._members_lock:
                snap = cgb._members_snapshot
            if snap is None:
                continue
            reads["n"] += 1
            for m in snap.members:
                if m.qq // 1000 != snap.source_group_id:
                    errors.append(
                        f"mismatch key={snap.source_group_id} qq={m.qq}"
                    )
                    stop.set()
                    return

    threads = [
        threading.Thread(target=writer, args=(111,), daemon=True),
        threading.Thread(target=writer, args=(222,), daemon=True),
        threading.Thread(target=reader, daemon=True),
        threading.Thread(target=reader, daemon=True),
    ]
    for t in threads:
        t.start()
    time.sleep(0.35)
    stop.set()
    for t in threads:
        t.join(timeout=1.0)

    assert not errors
    assert reads["n"] > 0


def test_load_source_members_assigns_atomic_snapshot(monkeypatch):
    def fake_fe7(_cap, source_group_id):
        return {int(source_group_id) * 1000 + i: f"tok{i}" for i in range(2)}

    def fake_ob(source_group_id):
        return [
            {
                "user_id": int(source_group_id) * 1000 + i,
                "nickname": f"n{i}",
                "role": "member",
            }
            for i in range(2)
        ]

    monkeypatch.setattr(cgb, "fetch_fe7_token_map_live", fake_fe7)
    monkeypatch.setattr(cgb, "scan_capture_fe7_token_map", lambda _c: {})
    monkeypatch.setattr(cgb, "_onebot_members", fake_ob)

    cgb.load_source_members(333, filter_staff=True)
    with cgb._members_lock:
        snap = cgb._members_snapshot
    assert snap is not None
    assert snap.key == (333, True)
    assert [m.qq for m in snap.members] == [333000, 333001]
    cached = cgb.get_cached_members()
    assert [m.qq for m in cached] == [333000, 333001]
