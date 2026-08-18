# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MembersCacheSnapshot
import pull_cross_group as pcg
from tests.conftest import wait_not_running

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cross_group_758_95b.json"


def test_open_picker_returns_none_without_chain(monkeypatch):
    monkeypatch.setattr(pcg, "missing_picker_templates", lambda *_a, **_k: ["0x88d_111(48B)"])
    monkeypatch.setattr(pcg, "find_cross_group_chain_templates", lambda *_a, **_k: [])
    monkeypatch.setattr(
        pcg,
        "probe_source_group_fe7",
        lambda *_a, **_k: ({10001: "tok-a"}, "u_groupctx", "fe7rsp"),
    )
    assert pcg.open_cross_group_picker(Path("."), 200, 100) is None


def test_query_context_token_falls_back_to_live(monkeypatch):
    monkeypatch.setattr(pcg, "extract_group_token_from_fe7", lambda *_a, **_k: None)
    monkeypatch.setattr(pcg, "find_source_context_token", lambda *_a, **_k: None)
    monkeypatch.setattr(pcg, "fetch_source_context_token_live", lambda *_a, **_k: "u_live")
    assert pcg.query_source_context_token(Path("."), 100, live_rsp=None) == "u_live"


def test_invite_errors_when_picker_chain_missing(monkeypatch, sample_members):
    monkeypatch.setattr(
        cgb, "missing_picker_templates", lambda *_a, **_k: ["0x88d_111(48B)"]
    )
    monkeypatch.setattr(cgb, "open_cross_group_picker", lambda *_a, **_k: "should-not-run")
    monkeypatch.setattr(cgb, "token_owner_safe", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "query_invitee_token", lambda *_a, **_k: "")
    invited: list[int] = []

    def capture_invite(**kwargs):
        invited.append(kwargs["member"].qq)
        return True, None, ""

    monkeypatch.setattr(cgb, "_invite_batch", capture_invite)

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
    assert st["status"] == "error"
    assert invited == []
    assert "\u6765\u6e90\u7fa4\u6210\u5458\u5df2\u52a0\u8f7d\uff0c\u4f46\u8de8\u7fa4\u9080\u8bf7\u51ed\u8bc1\u672a\u51c6\u5907\u6210\u529f" in (st["message"] or "")


def test_find_cross_group_chain_rejects_partial_templates(tmp_path):
    import capture_utils as cu
    from pb_utils import build_cross_group_758_pb, encode_field_varint

    hx758 = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=["u_REDACTaAAAAAAAAAAAAAAA", "u_REDACTbAAAAAAAAAAAAAAA"],
    )
    recv = encode_field_varint(3, 0).hex()

    def row(seq, cmd, hx, direction="SEND"):
        return {
            "seq": seq,
            "cmd": cmd,
            "dir": direction,
            "hex": hx,
            "dataLen": len(hx) // 2,
        }

    a = tmp_path / "capture-a.log"
    a.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                row(1, "OidbSvcTrpcTcp.0x88d_111", "08aa01"),
                row(2, "OidbSvcTrpcTcp.0x11ec_1", "08aa02"),
                row(10, "OidbSvcTrpcTcp.0x758_1", hx758),
                row(10, "OidbSvcTrpcTcp.0x758_1", recv, "RECV"),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    b = tmp_path / "capture-b.log"
    b.write_text(
        "\n".join(
            json.dumps(x)
            for x in (
                row(3, "OidbSvcTrpcTcp.0xfe7_4", "aa" * 96),
                row(20, "OidbSvcTrpcTcp.0x758_1", hx758),
                row(20, "OidbSvcTrpcTcp.0x758_1", recv, "RECV"),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert cu.find_cross_group_chain_templates(tmp_path) == []
    assert cu.missing_picker_templates(tmp_path) == ["anchored_picker_chain"]


def test_build_fe7_group_list_matches_ui_capture():
    import capture_utils as cu

    hx = cu.build_fe7_group_list(1080591561)
    assert len(bytes.fromhex(hx)) == 96
    assert hx == (
        "08e71f1004225708c989a2830410051802224b500158016001680170017801800101"
        "880101900101a00101a80101900301980301a00301a80301b00401b80401a00601"
        "a80601b00601b80601c00601c80601d00601d80601c00c01c80c016000"
    )


def _fe7_mapped(token: bytes, uin: int) -> bytes:
    from pb_utils import encode_field_bytes, encode_field_varint

    return encode_field_bytes(2, token) + encode_field_varint(4, uin)


def test_extract_group_token_prefers_unpaired_uid():
    from pb_utils import encode_field_bytes
    import capture_utils as cu

    member = b"u_YJrHKtJ-EiYl6tj29EEe_Q"
    extra = b"u_L-kmmxaZHCAk0kDNlBp6Jg"
    payload = _fe7_mapped(member, 86943) + encode_field_bytes(2, extra)
    assert cu.extract_group_token_from_fe7(payload.hex(), 1009406709) == extra.decode()


def test_extract_group_token_member_only_is_none():
    import capture_utils as cu

    member = b"u_YJrHKtJ-EiYl6tj29EEe_Q"
    payload = _fe7_mapped(member, 86943)
    assert cu.parse_fe7_token_map(payload.hex()) == {86943: member.decode()}
    assert cu.extract_group_token_from_fe7(payload.hex(), 1009406709) is None


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
    assert ctx == ""
    assert rsp


def test_response_ok_rejects_large_unparseable_body():
    blob = "ab" * 220
    assert pcg._response_ok({"code": 0, "data": blob}) is False
    assert pcg._response_ok({"code": 0, "data": "0800"}) is False
    ok_hex = (
        __import__("pb_utils").encode_field_varint(1, 0)
        + __import__("pb_utils").encode_field_varint(3, 0)
    ).hex()
    assert pcg._response_ok({"code": 0, "data": ok_hex}) is True
    fail_hex = __import__("pb_utils").encode_field_varint(3, 1289).hex()
    assert pcg._response_ok({"code": 0, "data": fail_hex}) is False


def test_describe_token_never_includes_raw_value():
    from pb_utils import describe_token, ParsedPacket

    raw = "u_REDACTaAAAAAAAAAAAAAAA"
    text = describe_token(raw)
    assert raw not in text
    assert "token_present=true" in text
    pkt = ParsedPacket(cmd="OidbSvcTrpcTcp.0x758_1", pb_hex="00", invite_token=raw)
    joined = "\n".join(pkt.summary_lines())
    assert raw not in joined


def test_golden_758_95b_matches_builder():
    from pb_utils import (
        build_cross_group_758_pb,
        extract_field_bytes,
        parse_cross_group_758_entries,
        patch_cross_group_758_pb,
    )

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hx = fixture["pb_hex"]
    assert len(bytes.fromhex(hx)) == 95
    assert len(bytes.fromhex(hx)) == fixture["send_len"]
    toks = fixture["invitee_tokens"]
    assert len(toks) == 2
    assert len(toks[0]) == len(toks[1]) == 24
    built = build_cross_group_758_pb(
        target_group_id=fixture["target_group_id"],
        source_group_id=fixture["source_group_id"],
        invitee_tokens=toks,
    )
    assert built == hx
    body = extract_field_bytes(bytes.fromhex(hx), 4)
    target, source, tokens = parse_cross_group_758_entries(body)
    assert target == fixture["target_group_id"]
    assert source == fixture["source_group_id"]
    assert tokens == toks
    rebuilt = patch_cross_group_758_pb(
        "deadbeef",
        target_group_id=fixture["target_group_id"],
        source_group_id=fixture["source_group_id"],
        invitee_token="",
        invitee_tokens=toks,
    )
    assert rebuilt == hx


def test_builder_six_invitees_is_232_bytes():
    from pb_utils import build_cross_group_758_pb, extract_field_bytes, parse_cross_group_758_entries

    toks = [f"u_REDACT{i:02d}AAAAAAAAAAAAAA" for i in range(6)]
    assert all(len(t) == 24 for t in toks)
    hx = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=toks,
    )
    assert len(bytes.fromhex(hx)) == 232
    _t, _s, parsed = parse_cross_group_758_entries(extract_field_bytes(bytes.fromhex(hx), 4))
    assert parsed == toks


def test_88d_111_patches_nested_target_not_outer():
    from pb_utils import encode_pb_message, extract_field_bytes, read_varint
    import capture_utils as cu

    outer = 537099973
    nested = 1111111111
    body = encode_pb_message({1: [outer], 2: [{1: [nested]}]})
    top = encode_pb_message({1: [0x88d], 2: [111], 4: [body]})
    hx = top.hex()
    assert cu.nested_group_in_88d_111(hx) == nested
    patched = cu.patch_88d_111_target(hx, 1222222222)
    assert cu.nested_group_in_88d_111(patched) == 1222222222
    new_body = extract_field_bytes(bytes.fromhex(patched), 4)
    assert new_body is not None
    assert new_body[0] == 0x08
    val, _ = read_varint(new_body, 1)
    assert val == outer


def test_invite_batch_requires_target_membership(monkeypatch, sample_members):
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **_k: (True, {"code": 0, "data": "1800"}),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: False)
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=sample_members[:2],
        tokens=["u_REDACTaAAAAAAAAAAAAAAA", "u_REDACTbAAAAAAAAAAAAAAA"],
        capture_dir=Path("."),
    )
    assert [ok for _m, ok, _c, _msg in results] == [False, False]
    assert results[0][3] == "\u670d\u52a1\u5668\u54cd\u5e94\u5df2\u8fd4\u56de\uff0c\u4f46\u76ee\u6807\u7fa4\u6210\u5458\u672a\u51fa\u73b0"
