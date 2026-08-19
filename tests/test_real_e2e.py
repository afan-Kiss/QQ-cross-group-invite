# -*- coding: utf-8 -*-
"""Real NapCat cross-group invite E2E harness (production start_batch path).

Gating:
  A) NapCat offline -> SKIPPED: NAPCAT_OFFLINE
  B) File missing or allow_real_invite!=true
     -> SKIPPED: REAL_E2E_CONFIG_MISSING_OR_DISABLED
  C) Malformed JSON / invalid base fields / overlapping configured QQs
     -> FAIL REAL_E2E_CONFIG_INVALID (not skip)
  D) Scenario QQ list empty -> SKIPPED: REAL_E2E_SCENARIO_NOT_CONFIGURED
  E) Online + valid scenario config -> execute production start_batch

Minimal N=1 only needs source/target/single_qq. Optional 2+1 / 6+1 / stop
scenarios are independent and must not block Single N=1.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import cross_group_batch as cgb
from myqq_api import check_napcat_online, load_cfg
from pull_cross_group import resolve_capture_dir, target_group_has_member, wait_target_membership

E2E_CONFIG_PATH = Path(__file__).resolve().parent / "e2e.local.json"


def _napcat_status() -> tuple[bool, str]:
    try:
        load_cfg()
    except Exception as exc:  # noqa: BLE001
        return False, f"config: {exc}"
    try:
        return check_napcat_online()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _fail_cfg(msg: str) -> None:
    pytest.fail(f"REAL_E2E_CONFIG_INVALID: {msg}")


def validate_e2e_base_config(data: dict) -> dict:
    if not isinstance(data, dict):
        _fail_cfg("config must be an object")
    try:
        source = int(data.get("source_group_id") or 0)
        target = int(data.get("target_group_id") or 0)
    except (TypeError, ValueError) as exc:
        _fail_cfg(f"group ids must be integers: {exc}")
    if source <= 0 or target <= 0:
        _fail_cfg("source_group_id and target_group_id must be > 0")
    if source == target:
        _fail_cfg("source and target must differ")
    raw_interval = data.get("interval_ms", 1500)
    try:
        interval = int(raw_interval)
    except (TypeError, ValueError) as exc:
        _fail_cfg(f"interval_ms must be an integer: {exc}")
    if interval < 100 or interval > 600000:
        _fail_cfg("interval_ms must be 100-600000")
    return {
        "source_group_id": source,
        "target_group_id": target,
        "interval_ms": interval,
    }


def _parse_optional_qq_list(raw, *, min_n: int, name: str) -> list[int]:
    if raw is None or raw == []:
        return []
    if not isinstance(raw, list):
        _fail_cfg(f"{name} must be a list")
    out: list[int] = []
    for x in raw:
        try:
            q = int(x)
        except (TypeError, ValueError):
            _fail_cfg(f"{name} contains invalid QQ")
        if q <= 0:
            _fail_cfg(f"{name} contains invalid QQ")
        if q not in out:
            out.append(q)
    if 0 < len(out) < min_n:
        _fail_cfg(f"{name} needs at least {min_n} QQs")
    return out[:min_n]


def _parse_optional_single_qq(raw) -> int:
    if raw in (None, "", 0, "0"):
        return 0
    try:
        q = int(raw)
    except (TypeError, ValueError):
        _fail_cfg("single_qq must be an integer")
    if q < 0:
        _fail_cfg("single_qq contains invalid QQ")
    return q


def _configured_scenario_qqs(cfg: dict) -> dict[str, list[int]]:
    sets: dict[str, list[int]] = {}
    single = int(cfg.get("single_qq") or 0)
    if single > 0:
        sets["single_qq"] = [single]
    odd = list(cfg.get("odd_tail_qqs") or [])
    if odd:
        sets["odd_tail_qqs"] = odd[:3]
    proto = list(cfg.get("protocol_7_qqs") or [])
    if proto:
        sets["protocol_7_qqs"] = proto[:7]
    stop = list(cfg.get("stop_gate_qqs") or [])
    if stop:
        sets["stop_gate_qqs"] = stop[:7]
    return sets


def _assert_configured_qqs_disjoint(cfg: dict) -> None:
    seen: dict[int, str] = {}
    for name, qqs in _configured_scenario_qqs(cfg).items():
        for qq in qqs:
            prev = seen.get(qq)
            if prev is not None:
                _fail_cfg("scenario QQ sets must be disjoint")
            seen[qq] = name


def validate_e2e_config(data: dict) -> dict:
    """Base fields + optional scenario QQ lists. Does not require all scenarios."""
    if not isinstance(data, dict) or data.get("allow_real_invite") is not True:
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED")
    base = validate_e2e_base_config(data)
    cfg = {
        **base,
        "single_qq": _parse_optional_single_qq(data.get("single_qq")),
        "odd_tail_qqs": _parse_optional_qq_list(
            data.get("odd_tail_qqs"), min_n=3, name="odd_tail_qqs"
        ),
        "protocol_7_qqs": _parse_optional_qq_list(
            data.get("protocol_7_qqs"), min_n=7, name="protocol_7_qqs"
        ),
        "stop_gate_qqs": _parse_optional_qq_list(
            data.get("stop_gate_qqs"), min_n=7, name="stop_gate_qqs"
        ),
    }
    _assert_configured_qqs_disjoint(cfg)
    return cfg


def require_e2e_scenario(cfg: dict, name: str) -> list[int]:
    if name == "single_qq":
        qq = int(cfg.get("single_qq") or 0)
        if qq <= 0:
            pytest.skip("REAL_E2E_SCENARIO_NOT_CONFIGURED: single_qq")
        return [qq]
    qqs = list(cfg.get(name) or [])
    if not qqs:
        pytest.skip(f"REAL_E2E_SCENARIO_NOT_CONFIGURED: {name}")
    return qqs


def _load_e2e_config() -> dict:
    if not E2E_CONFIG_PATH.is_file():
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED")
    try:
        data = json.loads(E2E_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"REAL_E2E_CONFIG_INVALID: {exc}")
    return validate_e2e_config(data)


def _require_real_e2e() -> dict:
    online, msg = _napcat_status()
    if not online:
        pytest.skip(f"NAPCAT_OFFLINE: {msg}")
    return _load_e2e_config()


def _wait_task(timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = cgb.get_state()
        if not st.get("running"):
            return st
        time.sleep(0.2)
    st = cgb.get_state()
    if st.get("running"):
        try:
            cgb.stop_batch(st.get("task_id"))
        except Exception:  # noqa: BLE001
            pass
        pytest.fail(f"REAL_E2E_TIMEOUT: task still running after {timeout} seconds")
    return st


def _assert_logs_clean(st: dict) -> None:
    cgb.assert_no_raw_invite_tokens(st.get("logs") or [], where="state.logs")


def _assert_counts(
    st: dict,
    *,
    total: int,
    success: int,
    cancelled: int = 0,
    failed: int = 0,
    rate_limited: int = 0,
) -> None:
    assert st["total"] == total
    assert st["done"] == total
    assert st["success"] == success
    assert st["failed"] == failed
    assert st["rate_limited"] == rate_limited
    assert st["cancelled"] == cancelled
    waiting = sum(1 for r in st["results"] if r["status"] == "waiting")
    inviting = sum(1 for r in st["results"] if r["status"] == "inviting")
    assert waiting == 0
    assert inviting == 0
    assert st["success"] + st["failed"] + st["rate_limited"] + st["cancelled"] == st["done"]


def _assert_protocol_sends(st: dict, counts: list[int], codes: list[int]) -> None:
    sends = st.get("protocol_sends") or []
    assert [int(x.get("invitee_count") or 0) for x in sends] == counts
    assert [x.get("protocol_code") for x in sends] == codes


def _source_by_qq(source_group_id: int) -> dict[int, cgb.SourceMember]:
    cfg = load_cfg()
    cap = resolve_capture_dir(cfg)
    members = cgb.load_source_members(
        source_group_id,
        filter_staff=True,
        capture_dir=cap,
        record_logs=False,
    )
    return {m.qq: m for m in members}


def preflight_not_in_target(
    *,
    source_group_id: int,
    target_group_id: int,
    qqs: list[int],
    members_by_qq: dict[int, cgb.SourceMember] | None = None,
) -> None:
    by_qq = members_by_qq if members_by_qq is not None else _source_by_qq(source_group_id)
    for qq in qqs:
        member = by_qq.get(int(qq))
        if member is None:
            pytest.fail(f"E2E_PRECONDITION_FAILED: qq {qq} not in source group")
        if not member.eligible:
            pytest.fail(
                f"E2E_PRECONDITION_FAILED: qq {qq} is not eligible "
                f"({member.filter_reason or 'filter_staff'})"
            )
        present = target_group_has_member(target_group_id, int(qq), request_timeout=5.0)
        if present is True:
            pytest.fail(
                f"E2E_PRECONDITION_FAILED: qq {qq} already exists in target group. "
                "Remove this test account from the target group before rerun."
            )
        if present is None:
            pytest.fail(
                "E2E_PRECONDITION_UNVERIFIED: cannot verify target membership before test"
            )


def _assert_target_membership(target_group_id: int, qqs: list[int]) -> None:
    for qq in qqs:
        present = wait_target_membership(target_group_id, int(qq), timeout=8.0)
        if present is not True:
            pytest.fail(f"target membership != True for qq {qq} (got {present})")


def test_real_e2e_single_member_n1():
    cfg = _require_real_e2e()
    qqs = require_e2e_scenario(cfg, "single_qq")
    qq = qqs[0]
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    preflight_not_in_target(source_group_id=source, target_group_id=target, qqs=[qq])
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=int(cfg["interval_ms"]),
        qq_list=[qq],
        batch_size=1,
        filter_staff=True,
    )
    st = _wait_task()
    _assert_logs_clean(st)
    assert st["status"] == "completed"
    _assert_counts(st, total=1, success=1)
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[qq]["status"] == "success"
    _assert_protocol_sends(st, [1], [0])
    events = cgb.parse_send_gate_events(st["logs"])
    assert [e["event"] for e in events if e["event"] == "758_authorized"] == ["758_authorized"]
    assert [e["seq"] for e in events if e["event"] == "758_send_started"] == [1]
    assert [e["seq"] for e in events if e["event"] == "758_response_received"] == [1]
    _assert_target_membership(target, [qq])


def test_real_e2e_odd_tail_2_plus_1():
    cfg = _require_real_e2e()
    qqs = require_e2e_scenario(cfg, "odd_tail_qqs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    preflight_not_in_target(source_group_id=source, target_group_id=target, qqs=qqs)
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=int(cfg["interval_ms"]),
        qq_list=qqs,
        batch_size=2,
        filter_staff=True,
    )
    st = _wait_task()
    _assert_logs_clean(st)
    assert st["status"] == "completed"
    _assert_counts(st, total=3, success=3)
    by_qq = {r["qq"]: r for r in st["results"]}
    for qq in qqs:
        assert by_qq[qq]["status"] == "success"
    _assert_protocol_sends(st, [2, 1], [0, 0])
    _assert_target_membership(target, qqs)


def test_real_e2e_protocol_chunks_6_plus_1():
    cfg = _require_real_e2e()
    qqs = require_e2e_scenario(cfg, "protocol_7_qqs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    preflight_not_in_target(source_group_id=source, target_group_id=target, qqs=qqs)
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=int(cfg["interval_ms"]),
        qq_list=qqs,
        batch_size=7,
        filter_staff=True,
    )
    st = _wait_task(timeout=300.0)
    _assert_logs_clean(st)
    logs = "\n".join(st.get("logs") or [])
    assert "protocol_chunk_total=2" in logs
    events = cgb.parse_send_gate_events(st["logs"])
    assert [e["event"] for e in events if e["event"] == "758_authorized"] == [
        "758_authorized",
        "758_authorized",
    ]
    assert [e["seq"] for e in events if e["event"] == "758_send_started"] == [1, 2]
    assert st["status"] == "completed"
    _assert_counts(st, total=7, success=7)
    by_qq = {r["qq"]: r for r in st["results"]}
    for qq in qqs:
        assert by_qq[qq]["status"] == "success"
    _assert_protocol_sends(st, [6, 1], [0, 0])
    _assert_target_membership(target, qqs)


def test_real_e2e_stop_gate_between_chunks():
    cfg = _require_real_e2e()
    qqs = require_e2e_scenario(cfg, "stop_gate_qqs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    preflight_not_in_target(source_group_id=source, target_group_id=target, qqs=qqs)
    interval = max(int(cfg["interval_ms"]), 1500)
    task_id = cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=interval,
        qq_list=qqs,
        batch_size=7,
        filter_staff=True,
    )
    deadline = time.time() + 120.0
    stopped = False
    while time.time() < deadline:
        events = cgb.parse_send_gate_events(cgb.get_state().get("logs") or [])
        got_resp = any(
            e["event"] == "758_response_received" and e.get("seq") == 1 for e in events
        )
        if got_resp:
            cgb.stop_batch(task_id)
            stopped = True
            break
        if not cgb.get_state().get("running"):
            break
        time.sleep(0.05)
    if not stopped:
        pytest.fail("stop gate never saw 758_response_received seq=1")
    st = _wait_task(timeout=120.0)
    _assert_logs_clean(st)
    events = cgb.parse_send_gate_events(st.get("logs") or [])
    stop_i = next(i for i, e in enumerate(events) if e["event"] == "stop_requested")
    after = events[stop_i + 1 :]
    assert not any(e["event"] == "758_authorized" and e.get("seq") == 2 for e in after)
    assert not any(e["event"] == "758_send_started" and e.get("seq") == 2 for e in after)
    auth = [e for e in events if e["event"] == "758_authorized"]
    started = [e for e in events if e["event"] == "758_send_started"]
    finished = [e for e in events if e["event"] == "758_send_finished"]
    resp = [e for e in events if e["event"] == "758_response_received"]
    assert len(auth) == 1 and auth[0]["seq"] == 1
    assert len(started) == 1 and started[0]["seq"] == 1
    assert len(finished) == 1 and finished[0]["seq"] == 1
    assert len(resp) == 1 and resp[0]["seq"] == 1
    assert st["status"] == "stopped"
    _assert_counts(st, total=7, success=6, cancelled=1)
    by_qq = {r["qq"]: r for r in st["results"]}
    for qq in qqs[:6]:
        assert by_qq[qq]["status"] == "success"
    assert by_qq[qqs[6]]["status"] == "cancelled"
    _assert_protocol_sends(st, [6], [0])
    _assert_target_membership(target, qqs[:6])
