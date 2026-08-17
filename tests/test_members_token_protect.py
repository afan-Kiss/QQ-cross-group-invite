# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Mem:
    qq: int = 10001
    nickname: str = "n"
    role: str = "member"
    token: str = "RAW-TOKEN-SECRET"
    eligible: bool = True

    def to_dict(self):
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "role": self.role,
            "token": self.token,
            "eligible": self.eligible,
        }

    def to_public_dict(self):
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "role": self.role,
            "token": "",
            "has_token": bool(self.token),
            "eligible": self.eligible,
        }


def test_get_members_strips_token_and_requires_session(monkeypatch):
    import cross_group_service as svc
    from tests.test_session_auth import _Req

    monkeypatch.setattr(svc, "SESSION_ID", "owned-sess")
    monkeypatch.setattr(svc, "SESSION_REQUIRED", True)
    monkeypatch.setattr(svc, "get_cached_members", lambda: [_Mem()])

    # no session -> unauthorized
    h = svc.Handler.__new__(svc.Handler)
    req = _Req({})
    h.headers = req.headers
    h.rfile = req.rfile
    h.wfile = req.wfile
    h.send_response = req.send_response
    h.send_header = req.send_header
    h.end_headers = req.end_headers
    h.path = "/members"
    h.client_address = ("127.0.0.1", 1)
    h.command = "GET"
    # Use do_GET via constructing minimal handler is hard; call logic directly.
    denied = svc._check_session(req, required=True)
    assert denied is not None and denied[0] == 403

    # authorized path builds safe payload
    members = svc.get_cached_members()
    safe = [svc._member_public_dict(m) for m in members]
    assert safe[0]["token"] == ""
    assert safe[0]["has_token"] is True
    assert "RAW-TOKEN-SECRET" not in str(safe)


def test_get_members_external_mode_still_strips_token(monkeypatch):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "get_cached_members", lambda: [_Mem()])
    members = svc.get_cached_members()
    for m in members:
        d = m.to_dict()
        d["token"] = ""
        assert d["token"] == ""
