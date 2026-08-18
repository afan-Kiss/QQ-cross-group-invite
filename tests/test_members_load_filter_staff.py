# -*- coding: utf-8 -*-
from __future__ import annotations


def _post_members_load(monkeypatch, payload: dict):
    import cross_group_service as svc

    monkeypatch.setattr(svc, "SESSION_REQUIRED", False)
    monkeypatch.setattr(svc, "check_napcat_online", lambda: (True, "ok"))
    loads: list = []

    def fake_load(source, filter_staff=True, record_logs=False):
        loads.append({"source": source, "filter_staff": filter_staff})
        return []

    monkeypatch.setattr(svc, "load_source_members", fake_load)
    captured: dict = {}
    monkeypatch.setattr(
        svc,
        "_json_response",
        lambda handler, code, obj: captured.update(code=code, body=obj),
    )
    h = svc.Handler.__new__(svc.Handler)
    h.headers = {}  # type: ignore[attr-defined]
    h.path = "/members/load"
    h._read_json = lambda: payload  # type: ignore[method-assign]
    h.do_POST()
    return captured.get("code"), captured.get("body"), loads


def test_members_load_accepts_filter_staff_true(monkeypatch):
    code, _body, loads = _post_members_load(
        monkeypatch,
        {"source_group_id": 100, "filter_staff": True},
    )
    assert code == 200
    assert loads == [{"source": 100, "filter_staff": True}]


def test_members_load_accepts_filter_staff_false(monkeypatch):
    code, _body, loads = _post_members_load(
        monkeypatch,
        {"source_group_id": 100, "filter_staff": False},
    )
    assert code == 200
    assert loads == [{"source": 100, "filter_staff": False}]


def test_members_load_rejects_filter_staff_string(monkeypatch):
    code, body, loads = _post_members_load(
        monkeypatch,
        {"source_group_id": 100, "filter_staff": "false"},
    )
    assert code == 400
    assert loads == []
    assert "filter_staff" in str(body)


def test_members_load_rejects_filter_staff_int(monkeypatch):
    code, body, loads = _post_members_load(
        monkeypatch,
        {"source_group_id": 100, "filter_staff": 0},
    )
    assert code == 400
    assert loads == []
    assert "filter_staff" in str(body)
