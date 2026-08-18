# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MembersCacheSnapshot
import pull_cross_group as pcg
from tests.conftest import wait_not_running


def test_open_picker_falls_back_to_live_source_fe7(monkeypatch):
    monkeypatch.setattr(pcg, "find_cross_group_chain_templates", lambda *_a, **_k: [])
    monkeypatch.setattr(
        pcg,
        "probe_source_group_fe7",
        lambda *_a, **_k: ({10001: "tok-a"}, "u_groupctx", "fe7rsp"),
    )
    assert pcg.open_cross_group_picker(Path("."), 200, 100) == "fe7rsp"


def test_query_context_token_falls_back_to_live(monkeypatch):
    monkeypatch.setattr(pcg, "extract_group_token_from_fe7", lambda *_a, **_k: None)
    monkeypatch.setattr(pcg, "find_source_context_token", lambda *_a, **_k: None)
    monkeypatch.setattr(pcg, "fetch_source_context_token_live", lambda *_a, **_k: "u_live")
    assert pcg.query_source_context_token(Path("."), 100, live_rsp=None) == "u_live"


def test_invite_survives_missing_picker_chain(monkeypatch, sample_members):
    invited: list[str] = []

    def capture_invite(**kwargs):
        invited.append(kwargs["context_token"])
        return True, None, ""

    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no picker chain")),
    )
    monkeypatch.setattr(cgb, "query_source_context_token", lambda *_a, **_k: "")
    monkeypatch.setattr(cgb, "token_owner_safe", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "query_invitee_token", lambda *_a, **_k: "")
    monkeypatch.setattr(cgb, "_invite_one", capture_invite)

    eligible = tuple(m for m in sample_members if m.eligible)
    snap = MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=eligible,
        context_token="u_cached_ctx",
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap

    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[eligible[0].qq],
        batch_size=10,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["status"] != "error"
    assert invited == ["u_cached_ctx"]
    assert st["success"] == 1


def test_find_cross_group_chain_keeps_partial_templates(monkeypatch):
    def fake_template(_cap, cmd_marker, data_len, **_k):
        if cmd_marker == "0xfe7_4":
            return "aa" * max(int(data_len), 96)
        return None

    import capture_utils as cu

    monkeypatch.setattr(cu, "find_packet_template", fake_template)
    monkeypatch.setattr(cu, "find_fe7_pagination_templates_generic", lambda *_a, **_k: [])
    chain = cu.find_cross_group_chain_templates(Path("."))
    assert chain
    assert any("0xfe7_4" in cmd for cmd, _ in chain)


def test_build_fe7_group_list_matches_ui_capture():
    import capture_utils as cu

    hx = cu.build_fe7_group_list(1080591561)
    assert len(bytes.fromhex(hx)) == 96
    assert hx == (
        "08e71f1004225708c989a2830410051802224b500158016001680170017801800101"
        "880101900101a00101a80101900301980301a00301a80301b00401b80401a00601"
        "a80601b00601b80601c00601c80601d00601d80601c00c01c80c016000"
    )


def test_extract_group_token_prefers_unpaired_uid():
    from pb_utils import encode_field_bytes, encode_field_varint
    import capture_utils as cu

    member = b"u_YJrHKtJ-EiYl6tj29EEe_Q"
    extra = b"u_L-kmmxaZHCAk0kDNlBp6Jg"
    payload = (
        encode_field_bytes(2, member)
        + encode_field_varint(4, 86943)
        + encode_field_bytes(2, extra)
    )
    assert cu.extract_group_token_from_fe7(payload.hex(), 1009406709) == extra.decode()


def test_probe_uses_built_list_when_capture_empty(monkeypatch, tmp_path):
    sent: list[str] = []

    def fake_send(hex_data, *, label=""):
        sent.append(hex_data)
        return b"u_L-kmmxaZHCAk0kDNlBp6Jg".hex()

    monkeypatch.setattr(pcg, "find_fe7_pagination_templates", lambda *_a, **_k: [])
    monkeypatch.setattr(pcg, "find_fe7_pagination_templates_generic", lambda *_a, **_k: [])
    monkeypatch.setattr(pcg, "_send_fe7", fake_send)
    tokens, ctx, rsp = pcg.probe_source_group_fe7(tmp_path, 1009406709)
    assert sent
    assert len(bytes.fromhex(sent[0])) == 96
    assert ctx
    assert rsp
