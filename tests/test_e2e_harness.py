# -*- coding: utf-8 -*-
"""Offline Real E2E harness structure: config, preflight, timeout, token leak."""
from __future__ import annotations

import json

import pytest

import cross_group_batch as cgb
from tests import test_real_e2e as e2e


def test_e2e_config_requires_disjoint_qq_sets():
    data = {
        "allow_real_invite": True,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 11,
        "odd_tail_qqs": [21, 22, 23],
        "protocol_7_qqs": [31, 32, 33, 34, 35, 36, 37],
        "stop_gate_qqs": [41, 42, 43, 44, 45, 46, 11],
        "interval_ms": 1500,
    }
    with pytest.raises(pytest.fail.Exception, match="REAL_E2E_CONFIG_INVALID: scenario QQ sets must be disjoint"):
        e2e.validate_e2e_config(data)


def test_e2e_config_accepts_four_disjoint_sets():
    data = {
        "allow_real_invite": True,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 11,
        "odd_tail_qqs": [21, 22, 23],
        "protocol_7_qqs": [31, 32, 33, 34, 35, 36, 37],
        "stop_gate_qqs": [41, 42, 43, 44, 45, 46, 47],
        "interval_ms": 1500,
    }
    out = e2e.validate_e2e_config(data)
    assert out["stop_gate_qqs"][-1] == 47
    assert out["protocol_7_qqs"][0] == 31


def test_minimal_n1_config_does_not_require_other_scenarios():
    data = {
        "allow_real_invite": True,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 10001,
        "odd_tail_qqs": [],
        "protocol_7_qqs": [],
        "stop_gate_qqs": [],
        "interval_ms": 1500,
    }
    base = e2e.validate_e2e_base_config(data)
    assert base["source_group_id"] == 1
    cfg = e2e.validate_e2e_config(data)
    assert e2e.require_e2e_scenario(cfg, "single_qq") == [10001]
    with pytest.raises(pytest.skip.Exception, match="REAL_E2E_SCENARIO_NOT_CONFIGURED: odd_tail_qqs"):
        e2e.require_e2e_scenario(cfg, "odd_tail_qqs")
    with pytest.raises(pytest.skip.Exception, match="REAL_E2E_SCENARIO_NOT_CONFIGURED: protocol_7_qqs"):
        e2e.require_e2e_scenario(cfg, "protocol_7_qqs")
    with pytest.raises(pytest.skip.Exception, match="REAL_E2E_SCENARIO_NOT_CONFIGURED: stop_gate_qqs"):
        e2e.require_e2e_scenario(cfg, "stop_gate_qqs")


def test_configured_scenario_overlap_with_single_fails():
    data = {
        "allow_real_invite": True,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 10001,
        "odd_tail_qqs": [10001, 10002, 10003],
        "protocol_7_qqs": [],
        "stop_gate_qqs": [],
        "interval_ms": 1500,
    }
    with pytest.raises(pytest.fail.Exception, match="disjoint"):
        e2e.validate_e2e_config(data)


def test_malformed_json_fails_not_skip(monkeypatch, tmp_path):
    bad = tmp_path / "e2e.local.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(e2e, "E2E_CONFIG_PATH", bad)
    with pytest.raises(pytest.fail.Exception, match="REAL_E2E_CONFIG_INVALID"):
        e2e._load_e2e_config()


def test_interval_out_of_range_fails():
    data = {
        "allow_real_invite": True,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 11,
        "interval_ms": 50,
    }
    with pytest.raises(pytest.fail.Exception, match="REAL_E2E_CONFIG_INVALID: interval_ms"):
        e2e.validate_e2e_base_config(data)
    data["interval_ms"] = 600001
    with pytest.raises(pytest.fail.Exception, match="REAL_E2E_CONFIG_INVALID: interval_ms"):
        e2e.validate_e2e_base_config(data)


def test_allow_real_invite_false_skips():
    data = {
        "allow_real_invite": False,
        "source_group_id": 1,
        "target_group_id": 2,
        "single_qq": 11,
        "interval_ms": 1500,
    }
    with pytest.raises(pytest.skip.Exception, match="REAL_E2E_CONFIG_MISSING_OR_DISABLED"):
        e2e.validate_e2e_config(data)


def test_e2e_example_json_has_stop_gate_field():
    p = e2e.E2E_CONFIG_PATH.with_name("e2e.local.example.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "stop_gate_qqs" in data
    assert data.get("allow_real_invite") is False


def test_preflight_already_in_target_fails(monkeypatch):
    member = cgb.SourceMember(qq=99, nickname="x", token="", eligible=True)
    monkeypatch.setattr(e2e, "_source_by_qq", lambda *_a, **_k: {99: member})
    monkeypatch.setattr(e2e, "target_group_has_member", lambda *_a, **_k: True)
    with pytest.raises(pytest.fail.Exception, match="E2E_PRECONDITION_FAILED"):
        e2e.preflight_not_in_target(
            source_group_id=1, target_group_id=2, qqs=[99], members_by_qq={99: member}
        )


def test_preflight_membership_none_is_not_pass(monkeypatch):
    member = cgb.SourceMember(qq=99, nickname="x", token="", eligible=True)
    monkeypatch.setattr(e2e, "target_group_has_member", lambda *_a, **_k: None)
    with pytest.raises(pytest.fail.Exception, match="E2E_PRECONDITION_UNVERIFIED"):
        e2e.preflight_not_in_target(
            source_group_id=1, target_group_id=2, qqs=[99], members_by_qq={99: member}
        )


def test_raw_token_regex_fails_even_with_token_count():
    line = "picker token_count=6 u_REALSECRETTOKENABCDEFG extra"
    with pytest.raises(AssertionError, match="raw invite token"):
        cgb.assert_no_raw_invite_tokens([line])
    cgb.assert_no_raw_invite_tokens(["picker token_count=6 token_hash=abcd1234"])


def test_parse_send_gate_events_stop_after_seq1():
    logs = [
        "[00:00:00] 758_authorized t=1.0 seq=1",
        "[00:00:00] 758_send_started t=1.1 seq=1",
        "[00:00:00] 758_send_finished t=1.2 seq=1",
        "[00:00:00] 758_response_received t=1.3 seq=1",
        "[00:00:00] stop_requested t=1.4 seq=1",
    ]
    events = cgb.parse_send_gate_events(logs)
    stop_i = next(i for i, e in enumerate(events) if e["event"] == "stop_requested")
    after = events[stop_i + 1 :]
    assert not any(e.get("seq") == 2 for e in after)
    assert events[0]["seq"] == 1


def test_wait_task_timeout_explicit_fail(monkeypatch):
    monkeypatch.setattr(cgb, "get_state", lambda: {"running": True, "task_id": "t1"})
    monkeypatch.setattr(cgb, "stop_batch", lambda *_a, **_k: None)
    monkeypatch.setattr(e2e.time, "time", lambda: 0 if not getattr(e2e.time, "_n", 0) else 999)
    # Use a tiny timeout with a clock that jumps after first loop.
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 0.0 if calls["n"] < 3 else 10.0

    monkeypatch.setattr(e2e.time, "time", fake_time)
    monkeypatch.setattr(e2e.time, "sleep", lambda *_a, **_k: None)
    with pytest.raises(pytest.fail.Exception, match="REAL_E2E_TIMEOUT"):
        e2e._wait_task(timeout=1.0)
