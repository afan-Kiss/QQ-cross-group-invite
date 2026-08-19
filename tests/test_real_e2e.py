# -*- coding: utf-8 -*-
"""Real NapCat cross-group invite E2E. Never fake PASS when offline."""
from __future__ import annotations

import pytest

from myqq_api import check_napcat_online, load_cfg


def _napcat_status() -> tuple[bool, str]:
    try:
        cfg = load_cfg()
    except Exception as exc:  # noqa: BLE001
        return False, f"config: {exc}"
    try:
        return check_napcat_online()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    del cfg
    return False, "unreachable"


def test_real_e2e_single_member_n1():
    online, msg = _napcat_status()
    if not online:
        pytest.skip(f"NapCat offline: {msg}")
    pytest.skip("Single-member real E2E not verified")


def test_real_e2e_odd_tail_2_plus_1():
    online, msg = _napcat_status()
    if not online:
        pytest.skip(f"NapCat offline: {msg}")
    pytest.skip("2+1 real E2E not verified")


def test_real_e2e_protocol_chunks_6_plus_1():
    online, msg = _napcat_status()
    if not online:
        pytest.skip(f"NapCat offline: {msg}")
    pytest.skip("6+1 protocol-chunk real E2E not verified")


def test_real_e2e_stop_gate_between_chunks():
    online, msg = _napcat_status()
    if not online:
        pytest.skip(f"NapCat offline: {msg}")
    pytest.skip("Stop-gate real E2E not verified")
