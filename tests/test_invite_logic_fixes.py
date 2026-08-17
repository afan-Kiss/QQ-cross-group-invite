# -*- coding: utf-8 -*-
from __future__ import annotations

from cross_group_batch import MemberRole, SourceMember
import cross_group_batch as cgb
from tests.conftest import wait_not_running


def test_token_map_fallback_respects_filter_staff(monkeypatch):
    monkeypatch.setattr(cgb, "_onebot_members", lambda *_a, **_k: [])
    monkeypatch.setattr(cgb, "fetch_fe7_token_map_live", lambda *_a, **_k: {10001: "tok-a"})
    monkeypatch.setattr(cgb, "scan_capture_fe7_token_map", lambda *_a, **_k: {})
    monkeypatch.setattr(cgb, "resolve_capture_dir", lambda *_a, **_k: None)
    monkeypatch.setattr(cgb, "load_cfg", lambda: {})

    members = cgb.load_source_members(100, filter_staff=True)
    assert len(members) == 1
    assert members[0].role == MemberRole.UNKNOWN
    assert members[0].eligible is False

    members2 = cgb.load_source_members(100, filter_staff=False)
    assert members2[0].eligible is True


def test_mismatched_token_fails_without_invite(monkeypatch, patch_network):
    invited: list[int] = []

    def capture_invite(**kwargs):
        invited.append(kwargs["member"].qq)
        return True, None, ""

    monkeypatch.setattr(cgb, "_invite_one", capture_invite)
    monkeypatch.setattr(cgb, "token_owner_safe", lambda *_a, **_k: False)
    monkeypatch.setattr(cgb, "query_invitee_token", lambda *_a, **_k: "")
    snap = cgb.MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=(
            SourceMember(
                qq=10001,
                nickname="A",
                token="tok-for-someone-else",
                role=MemberRole.MEMBER,
                eligible=True,
            ),
        ),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap
    monkeypatch.setattr(
        cgb, "query_source_context_token", lambda *_a, **_k: "ctx-token"
    )

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001],
        batch_size=10,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert invited == []
    assert st["failed_count"] == 1
    assert st["success"] == 0
    reason = st["results"][0].get("reason") or ""
    assert "TOKEN" in reason.upper() or "\u627e\u4e0d\u5230" in reason


def test_invite_start_rejects_zero_batch_and_interval(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "check_napcat_online", lambda: (True, "ok"))
    calls: list[dict] = []
    monkeypatch.setattr(svc, "start_batch", lambda **kwargs: calls.append(kwargs) or "task-1")

    captured: dict = {}

    def fake_json(handler, code, obj):
        captured["code"] = code
        captured["body"] = obj

    monkeypatch.setattr(svc, "_json_response", fake_json)

    def run(payload: dict):
        captured.clear()
        h = svc.Handler.__new__(svc.Handler)
        h.headers = {}  # type: ignore[attr-defined]
        h.path = "/invite/start"
        h._read_json = lambda: payload  # type: ignore[method-assign]
        h.do_POST()
        return captured.get("code"), captured.get("body")

    code, body = run(
        {
            "source_group_id": 100,
            "target_group_id": 200,
            "batch_count": 0,
            "interval_ms": 1500,
            "qq_list": [10001],
            "filter_staff": True,
        }
    )
    assert code == 400
    assert calls == []
    assert body and "batch_count" in str(body.get("message", body))

    code2, body2 = run(
        {
            "source_group_id": 100,
            "target_group_id": 200,
            "batch_count": 10,
            "interval_ms": 0,
            "qq_list": [10001],
            "filter_staff": True,
        }
    )
    assert code2 == 400
    assert calls == []
    assert body2 and "interval_ms" in str(body2.get("message", body2))
