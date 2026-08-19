# -*- coding: utf-8 -*-
"""Real NapCat cross-group invite E2E harness (production start_batch path).

Gating:
  A) NapCat offline -> SKIPPED: NAPCAT_OFFLINE
  B) Online but tests/e2e.local.json missing or allow_real_invite!=true
     -> SKIPPED: REAL_E2E_CONFIG_MISSING_OR_DISABLED
  C) Online + config -> execute real invites (never unconditional skip)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import cross_group_batch as cgb
from myqq_api import check_napcat_online, load_cfg

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


def _load_e2e_config() -> dict:
    if not E2E_CONFIG_PATH.is_file():
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED")
    try:
        data = json.loads(E2E_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"REAL_E2E_CONFIG_MISSING_OR_DISABLED: {exc}")
    if not isinstance(data, dict) or data.get("allow_real_invite") is not True:
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED")
    return data


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
    return cgb.get_state()


def _assert_no_raw_token(text: str) -> None:
    assert "u_" not in text or "token_count=" in text


def _summarize(st: dict) -> dict:
    logs = "\n".join(st.get("logs") or [])
    return {
        "status": st.get("status"),
        "success": st.get("success"),
        "failed": st.get("failed"),
        "rate_limited": st.get("rate_limited"),
        "cancelled": st.get("cancelled"),
        "done": st.get("done"),
        "total": st.get("total"),
        "picker_lines": [ln for ln in (st.get("logs") or []) if "picker ui_batch" in ln],
        "gate": {
            "authorized": logs.count("758_authorized"),
            "send_started": logs.count("758_send_started"),
            "send_finished": logs.count("758_send_finished"),
            "stop_requested": logs.count("stop_requested"),
        },
    }


def test_real_e2e_single_member_n1():
    cfg = _require_real_e2e()
    qq = int(cfg["single_qq"])
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    interval = int(cfg.get("interval_ms") or 1500)
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=interval,
        qq_list=[qq],
        batch_size=1,
        filter_staff=True,
    )
    st = _wait_task()
    summary = _summarize(st)
    for line in st.get("logs") or []:
        if "picker" in line:
            _assert_no_raw_token(line)
    assert st["status"] == "success" or st["status"] == "completed"
    assert st["success"] >= 1
    assert st["total"] == 1
    assert st["done"] == 1
    assert summary["gate"]["authorized"] >= 1
    assert summary["gate"]["send_started"] >= 1
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[qq]["status"] == "success"


def test_real_e2e_odd_tail_2_plus_1():
    cfg = _require_real_e2e()
    qqs = [int(x) for x in cfg.get("odd_tail_qqs") or []]
    if len(qqs) < 3:
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED: odd_tail_qqs needs 3 QQs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    interval = int(cfg.get("interval_ms") or 1500)
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=interval,
        qq_list=qqs[:3],
        batch_size=2,
        filter_staff=True,
    )
    st = _wait_task()
    assert st["status"] in {"completed", "success"}
    assert st["done"] == 3
    # Last UI batch should be N=1 (2+1).
    assert any("protocol_chunk" in ln and "token_count=1" in ln for ln in st.get("logs") or [])


def test_real_e2e_protocol_chunks_6_plus_1():
    cfg = _require_real_e2e()
    qqs = [int(x) for x in cfg.get("protocol_7_qqs") or []]
    if len(qqs) < 7:
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED: protocol_7_qqs needs 7 QQs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    interval = int(cfg.get("interval_ms") or 1500)
    cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=interval,
        qq_list=qqs[:7],
        batch_size=7,
        filter_staff=True,
    )
    st = _wait_task(timeout=300.0)
    logs = "\n".join(st.get("logs") or [])
    assert "protocol_chunk_total=2" in logs
    assert logs.count("758_authorized") >= 2
    assert logs.count("758_send_started") >= 2
    assert st["done"] == 7


def test_real_e2e_stop_gate_between_chunks():
    cfg = _require_real_e2e()
    qqs = [int(x) for x in cfg.get("protocol_7_qqs") or []]
    if len(qqs) < 7:
        pytest.skip("REAL_E2E_CONFIG_MISSING_OR_DISABLED: protocol_7_qqs needs 7 QQs")
    source = int(cfg["source_group_id"])
    target = int(cfg["target_group_id"])
    interval = int(cfg.get("interval_ms") or 2000)
    task_id = cgb.start_batch(
        target_group_id=target,
        source_group_id=source,
        interval_ms=interval,
        qq_list=qqs[:7],
        batch_size=7,
        filter_staff=True,
    )
    # Wait until first 758 authorized, then stop before second chunk.
    deadline = time.time() + 120.0
    while time.time() < deadline:
        logs = "\n".join(cgb.get_state().get("logs") or [])
        if "758_send_finished" in logs or "758_send_started" in logs:
            cgb.stop_batch(task_id)
            break
        if not cgb.get_state().get("running"):
            break
        time.sleep(0.05)
    st = _wait_task(timeout=120.0)
    logs = "\n".join(st.get("logs") or [])
    assert "stop_requested" in logs
    # After stop, no new authorize beyond those already started.
    auth = logs.count("758_authorized")
    started = logs.count("758_send_started")
    assert started <= auth
    assert st["status"] in {"stopped", "completed", "error"}
