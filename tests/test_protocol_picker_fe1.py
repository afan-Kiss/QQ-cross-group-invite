# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MembersCacheSnapshot, SourceMember, MemberRole
import pull_cross_group as pcg
from tests.conftest import wait_not_running

TOK_A = "u_REDACTaAAAAAAAAAAAAAAA"
TOK_B = "u_REDACTbAAAAAAAAAAAAAAA"
TOK_OLD = "u_OLDTOKENAAAAAAAAAAAAAA"
TOK_FRESH = "u_FRESHTOKENAAAAAAAAAAAA"


def _758_hex(n: int = 2) -> str:
    from pb_utils import build_cross_group_758_pb

    toks = [f"u_REDACT{i:02d}AAAAAAAAAAAAAA" for i in range(n)]
    return build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=toks,
    )


def _recv_ok() -> str:
    from pb_utils import encode_field_varint

    return encode_field_varint(3, 0).hex()


def _row(seq: int, cmd: str, hx: str, direction: str = "SEND") -> dict:
    return {
        "seq": seq,
        "cmd": cmd,
        "dir": direction,
        "hex": hx,
        "dataLen": len(hx) // 2,
    }


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _88d_packet(outer: int, nested: int) -> str:
    from pb_utils import encode_pb_message

    body = encode_pb_message({1: [outer], 2: [{1: [nested]}]})
    return encode_pb_message({1: [0x88d], 2: [111], 4: [body]}).hex()


def test_picker_fresh_token_overrides_stale_member_token(monkeypatch, sample_members):
    sent_fe1: list[list[str]] = []
    sent_758: list[list[str]] = []

    def fake_fe1(_cap, tokens, **_k):
        sent_fe1.append(list(tokens))
        return True

    def fake_758(**kwargs):
        sent_758.append(list(kwargs.get("invitee_tokens") or []))
        return True, {"code": 0, "data": "1800"}

    monkeypatch.setattr(cgb, "sync_fe1_selection", fake_fe1)
    monkeypatch.setattr(cgb, "send_cross_group_invite", fake_758)
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(
            token_map={10001: TOK_FRESH, 10002: TOK_B},
            fe7_pages=2,
        ),
    )
    snap = MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=(
            SourceMember(qq=10001, nickname="a", token=TOK_OLD, role=MemberRole.MEMBER),
            SourceMember(qq=10002, nickname="b", token=TOK_B, role=MemberRole.MEMBER),
        ),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=10,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert sent_fe1 == [[TOK_FRESH, TOK_B]]
    assert sent_758 == [[TOK_FRESH, TOK_B]]
    assert TOK_OLD not in sent_fe1[0]
    assert TOK_OLD not in sent_758[0]


def test_picker_missing_qq_does_not_send_that_member(monkeypatch):
    sent = []

    def capture_send(**kwargs):
        sent.append(kwargs)
        return True, {"code": 0, "data": "1800"}

    monkeypatch.setattr(
        cgb,
        "open_cross_group_picker",
        lambda *_a, **_k: pcg.PickerSession(token_map={10002: TOK_B}, fe7_pages=1),
    )
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: True)
    monkeypatch.setattr(cgb, "send_cross_group_invite", capture_send)
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    snap = MembersCacheSnapshot(
        source_group_id=100,
        filter_staff=True,
        members=(
            SourceMember(qq=10001, nickname="a", token=TOK_OLD, role=MemberRole.MEMBER),
            SourceMember(qq=10002, nickname="b", token=TOK_B, role=MemberRole.MEMBER),
        ),
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=10,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert len(sent) == 1
    assert sent[0].get("invitee_tokens") == [TOK_B]
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert "\u5f53\u524d\u9009\u62e9\u5668\u4f1a\u8bdd" in (by_qq[10001].get("reason") or "")
    assert by_qq[10002]["status"] == "success"


def test_fe1_false_does_not_send_758(monkeypatch, sample_members):
    sent = []
    monkeypatch.setattr(cgb, "sync_fe1_selection", lambda *_a, **_k: False)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent.append(k) or (True, {}),
    )
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=sample_members[:2],
        tokens=[TOK_A, TOK_B],
        capture_dir=Path("."),
    )
    assert sent == []
    assert all(kind == "failed" for _m, kind, _c, _msg in results)
    assert results[0][3] == "\u8de8\u7fa4\u9009\u62e9\u540c\u6b65\u5931\u8d25\uff0c\u672a\u53d1\u9001\u9080\u8bf7"


def test_fe1_token_list_equals_758_token_list():
    from pb_utils import (
        build_cross_group_758_pb,
        build_cross_group_fe1_pb,
        extract_field_bytes,
        parse_cross_group_758_entries,
        parse_fe1_tokens,
    )

    toks = [TOK_A, TOK_B]
    fe1 = build_cross_group_fe1_pb(toks)
    pb = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=toks,
    )
    assert parse_fe1_tokens(fe1) == toks
    _t, _s, parsed = parse_cross_group_758_entries(extract_field_bytes(bytes.fromhex(pb), 4) or b"")
    assert parsed == toks


def test_fe1_builder_matches_capture_sizes():
    from pb_utils import build_cross_group_fe1_pb

    assert len(bytes.fromhex(build_cross_group_fe1_pb([TOK_A]))) == 41
    ten = [f"u_REDACT{i:02d}AAAAAAAAAAAAAA" for i in range(10)]
    assert all(len(t) == 24 for t in ten)
    assert len(bytes.fromhex(build_cross_group_fe1_pb(ten))) == 276


def test_runtime_2_token_758_is_95b():
    from pb_utils import build_cross_group_758_pb

    hx = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=[TOK_A, TOK_B],
    )
    assert len(bytes.fromhex(hx)) == 95
    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "cross_group_758_95b.json").read_text(
            encoding="utf-8"
        )
    )
    assert hx == fixture["pb_hex"]


def test_runtime_6_token_758_is_232b():
    from pb_utils import build_cross_group_758_pb

    toks = [f"u_REDACT{i:02d}AAAAAAAAAAAAAA" for i in range(6)]
    hx = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=toks,
    )
    assert len(bytes.fromhex(hx)) == 232


def test_send_allows_1block(monkeypatch):
    sent = []
    monkeypatch.setattr(
        pcg,
        "_send_packet",
        lambda *a, **k: sent.append(a) or {"code": 0, "data": "1800" + "00" * 8},
    )
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    ok, resp = pcg.send_cross_group_invite(
        target_group_id=1,
        source_group_id=2,
        invitee_token=TOK_A,
        capture_dir=Path("."),
    )
    assert ok is True
    assert len(sent) == 1
    assert sent[0][0] == pcg.CMD_758
    from pb_utils import extract_field_bytes, parse_cross_group_758_entries

    _t, _s, toks = parse_cross_group_758_entries(
        extract_field_bytes(bytes.fromhex(sent[0][1]), 4) or b""
    )
    assert toks == [TOK_A]
    assert "error" not in resp


def test_runtime_1_token_758_has_one_block():
    from pb_utils import (
        build_cross_group_758_pb,
        extract_field_bytes,
        parse_cross_group_758_entries,
    )

    hx = build_cross_group_758_pb(
        target_group_id=1111111111,
        source_group_id=2222222222,
        invitee_tokens=[TOK_A],
    )
    _t, _s, toks = parse_cross_group_758_entries(
        extract_field_bytes(bytes.fromhex(hx), 4) or b""
    )
    assert toks == [TOK_A]


def test_88d_nested_same_and_different_varint_and_prefix():
    import capture_utils as cu
    from pb_utils import extract_field_bytes, read_varint

    outer = 1111111111
    nested = 1111111111
    hx = _88d_packet(outer, nested)
    same = cu.patch_88d_111_target(hx, 1222222222)
    assert cu.nested_group_in_88d_111(same) == 1222222222
    body = extract_field_bytes(bytes.fromhex(same), 4)
    val, _ = read_varint(body, 1)
    assert val == outer

    diff = cu.patch_88d_111_target(hx, 7)
    assert cu.nested_group_in_88d_111(diff) == 7
    body2 = extract_field_bytes(bytes.fromhex(diff), 4)
    val2, _ = read_varint(body2, 1)
    assert val2 == outer


def test_anchored_chain_same_session_only(tmp_path):
    import capture_utils as cu

    hx758 = _758_hex(2)
    recv = _recv_ok()
    complete = tmp_path / "capture-complete.log"
    _write_log(
        complete,
        [
            _row(1, "OidbSvcTrpcTcp.0x88d_14", "aa" * 10),
            _row(2, "OidbSvcTrpcTcp.0x88d_111", _88d_packet(1, 1111111111)),
            _row(3, "OidbSvcTrpcTcp.0x11ec_1", "bb" * 10),
            _row(4, "OidbSvcTrpcTcp.0xfe7_4", "cc" * 48),
            _row(5, "OidbSvcTrpcTcp.0xfe7_4", "dd" * 62),
            _row(9, "OidbSvcTrpcTcp.0x758_1", hx758),
            _row(9, "OidbSvcTrpcTcp.0x758_1", recv, "RECV"),
        ],
    )
    chain = cu.find_cross_group_chain_templates(tmp_path)
    cmds = [c for c, _ in chain]
    assert any("0x88d_111" in c for c in cmds)
    assert any("0x11ec_1" in c for c in cmds)
    assert sum(1 for c in cmds if "0xfe7_4" in c) == 2

    split = tmp_path / "split"
    split.mkdir()
    _write_log(
        split / "capture-a.log",
        [
            _row(1, "OidbSvcTrpcTcp.0x88d_111", _88d_packet(1, 2)),
            _row(2, "OidbSvcTrpcTcp.0x11ec_1", "bb" * 10),
            _row(9, "OidbSvcTrpcTcp.0x758_1", hx758),
            _row(9, "OidbSvcTrpcTcp.0x758_1", recv, "RECV"),
        ],
    )
    _write_log(
        split / "capture-b.log",
        [
            _row(3, "OidbSvcTrpcTcp.0xfe7_4", "cc" * 48),
            _row(20, "OidbSvcTrpcTcp.0x758_1", hx758),
            _row(20, "OidbSvcTrpcTcp.0x758_1", recv, "RECV"),
        ],
    )
    assert cu.find_cross_group_chain_templates(split) == []


def test_membership_retries_until_present(monkeypatch):
    hits = {"n": 0}

    def lookup(_g, _u):
        hits["n"] += 1
        return True if hits["n"] >= 3 else False

    monkeypatch.setattr(pcg, "target_group_has_member", lookup)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)

    class Stop:
        def is_set(self):
            return False

        def wait(self, _t):
            return False

    assert pcg.wait_target_membership(1, 2, stop_event=Stop(), timeout=5, interval=0.01) is True
    assert hits["n"] >= 3


def test_membership_lookup_error_is_unknown(monkeypatch):
    monkeypatch.setattr(
        pcg,
        "onebot_action",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("timeout")),
    )
    assert pcg.target_group_has_member(1, 2) is None
    monkeypatch.setattr(
        pcg,
        "onebot_action",
        lambda *_a, **_k: {"status": "failed", "retcode": 1403, "message": "unauthorized"},
    )
    assert pcg.target_group_has_member(1, 2) is None
    monkeypatch.setattr(
        pcg,
        "onebot_action",
        lambda *_a, **_k: {"status": "failed", "retcode": 2, "wording": "\u4e0d\u5728\u7fa4\u5185"},
    )
    assert pcg.target_group_has_member(1, 2) is False


def test_open_picker_merges_all_fe7_pages(monkeypatch, tmp_path):
    pages = [
        {10001: TOK_A},
        {10002: TOK_FRESH},
    ]
    cursors = [b"cursor-page-1-xxxxxxxxxxxxxxxxxx", None]
    sent_cmds: list[str] = []

    def fake_send(cmd, hex_data, **_k):
        sent_cmds.append(cmd)
        if "0xfe7_4" in cmd:
            from pb_utils import encode_field_bytes, encode_pb_message

            cur = cursors.pop(0) if cursors else None
            body = bytearray(b"\x08\x01")
            if cur:
                body.extend(encode_field_bytes(15, cur))
            top = encode_pb_message({3: [0], 4: [bytes(body)]})
            return {"code": 0, "data": top.hex()}
        return {"code": 0, "data": "1800"}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _rsp: pages.pop(0) if pages else {})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100)
    assert sess is not None
    assert sess.fe7_pages == 2
    assert sess.token_map == {10001: TOK_A, 10002: TOK_FRESH}
    assert any("0x88d_111" in c for c in sent_cmds)
    assert any("0x11ec_1" in c for c in sent_cmds)
    assert sum(1 for c in sent_cmds if "0xfe7_4" in c) == 2


def test_open_picker_works_without_capture_logs(monkeypatch, tmp_path):
    empty = tmp_path / "empty_capture"
    empty.mkdir()
    sent: list[str] = []

    def fake_send(cmd, hex_data, **_k):
        sent.append(cmd)
        if "0xfe7_4" in cmd:
            return {"code": 0, "data": "1800"}
        return {"code": 0, "data": "1800"}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _rsp: {10001: TOK_A})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(empty, 200, 100)
    assert sess is not None
    assert sess.token_map == {10001: TOK_A}
    assert not list(empty.glob("capture-*.log"))
    assert any("0x88d_111" in c for c in sent)


def test_sync_fe1_uses_builder_not_276_template(monkeypatch):
    sent = []
    monkeypatch.setattr(
        pcg,
        "_send_packet",
        lambda cmd, hx, **k: sent.append((cmd, hx)) or {"code": 0, "data": "ok"},
    )
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    assert pcg.sync_fe1_selection(Path("."), [TOK_A, TOK_B]) is True
    assert sent and sent[0][0] == pcg.CMD_FE1
    from pb_utils import parse_fe1_tokens

    assert parse_fe1_tokens(sent[0][1]) == [TOK_A, TOK_B]
    assert TOK_OLD not in sent[0][1]
