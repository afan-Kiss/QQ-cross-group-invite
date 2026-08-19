# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from pathlib import Path

import cross_group_batch as cgb
from cross_group_batch import MemberRole, MembersCacheSnapshot, SourceMember
import pull_cross_group as pcg
from tests.conftest import wait_not_running

TOK_A = "u_REDACTaAAAAAAAAAAAAAAA"
OIDB_OK = "1800"


def _oidb(code: int, extra_body: bytes | None = None) -> str:
    from pb_utils import encode_pb_message

    fields: dict = {3: [int(code)]}
    if extra_body is not None:
        fields[4] = [extra_body]
    return encode_pb_message(fields).hex()


def test_stop_during_fe7_does_not_send_fe1_or_758(monkeypatch, tmp_path):
    sent: list[str] = []
    stop = threading.Event()

    def fake_send(cmd, hex_data, **_k):
        sent.append(cmd)
        if "0xfe7_4" in cmd:
            stop.set()
            from pb_utils import encode_field_bytes, encode_pb_message

            body = encode_field_bytes(15, b"c" * 36)
            return {"code": 0, "data": encode_pb_message({3: [0], 4: [body]}).hex()}
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {})
    monkeypatch.setattr(pcg, "_interruptible_sleep", lambda *_a, **_k: stop.is_set())
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    try:
        pcg.open_cross_group_picker(
            tmp_path, 200, 100, desired_qqs=[10001], stop_event=stop
        )
        raised = False
    except pcg.PickerStopped:
        raised = True
    assert raised is True
    assert any("0xfe7_4" in c for c in sent)
    assert not any("0xfe1_8" in c for c in sent)
    assert not any("0x758_1" in c for c in sent)
    assert sum(1 for c in sent if "0xfe7_4" in c) == 1


def test_stop_after_fe1_before_758(monkeypatch):
    fe1_n = {"n": 0}
    sent_758 = []

    def fake_fe1(_cap, tokens, stop_event=None):
        fe1_n["n"] += 1
        if stop_event is not None:
            stop_event.set()
        return True

    monkeypatch.setattr(cgb, "sync_fe1_selection", fake_fe1)
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent_758.append(k) or (True, {"code": 0, "data": OIDB_OK}),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    cgb._state._stop.clear()
    member = SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER)
    results = cgb._invite_batch(
        target_group_id=200,
        source_group_id=100,
        members=[member],
        tokens=[TOK_A],
        capture_dir=Path("."),
    )
    assert fe1_n["n"] == 1
    assert sent_758 == []
    assert results[0][1] == "cancelled"
    assert "\u672a\u53d1\u9001\u9080\u8bf7" in results[0][3]


def test_stop_after_758_completes_membership_not_failed_send(monkeypatch):
    members = [
        SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="tok-b", role=MemberRole.MEMBER),
    ]
    snap = MembersCacheSnapshot(source_group_id=100, filter_staff=True, members=tuple(members))

    def fake_picker(*_a, **_k):
        return pcg.PickerSession(token_map={10001: TOK_A, 10002: "u_REDACTbAAAAAAAAAAAAAAA"}, fe7_pages=1)

    def fake_invite(**kwargs):
        cgb._state._stop.set()
        return [(m, "success", 0, "") for m in kwargs["members"]]

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(cgb, "_invite_batch", fake_invite)
    with cgb._members_lock:
        cgb._members_snapshot = snap
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["status"] == "stopped"
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10001]["status"] == "success"
    assert by_qq[10002]["status"] == "success"
    assert st["failed"] == 0


def test_stop_during_picker_marks_cancelled_not_failed(monkeypatch):
    members = [
        SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="tok-b", role=MemberRole.MEMBER),
    ]
    snap = MembersCacheSnapshot(source_group_id=100, filter_staff=True, members=tuple(members))
    sent_invite = []

    def fake_picker(*_a, **_k):
        raise pcg.PickerStopped("PICKER_FE7")

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(
        cgb,
        "_invite_batch",
        lambda **k: sent_invite.append(k) or [(m, "success", None, "") for m in k["members"]],
    )
    with cgb._members_lock:
        cgb._members_snapshot = snap
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    st = cgb.get_state()
    assert st["status"] == "stopped"
    assert sent_invite == []
    assert st["failed"] == 0
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10001]["status"] == "cancelled"
    assert by_qq[10002]["status"] == "cancelled"


def test_picker_protocol_error_on_88d(monkeypatch, tmp_path):
    sent = []

    def fake_send(cmd, hex_data, **_k):
        sent.append(cmd)
        return {"code": 0, "data": _oidb(2)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is None
    assert sent == [pcg.CMD_88D_111]


def test_empty_picker_token_map_with_desired_is_session_not_silent_ok(monkeypatch, tmp_path):
    def fake_send(cmd, hex_data, **_k):
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {})
    monkeypatch.setattr(pcg, "extract_fe7_page_cursor", lambda _r: None)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert sess.token_map == {}
    assert sess.missing_qqs == [10001]
    assert sess.error


def test_empty_picker_without_desired_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(pcg, "_send_packet", lambda *_a, **_k: {"code": 0, "data": _oidb(0)})
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {})
    monkeypatch.setattr(pcg, "extract_fe7_page_cursor", lambda _r: None)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    assert pcg.open_cross_group_picker(tmp_path, 200, 100) is None


def test_desired_qqs_stops_pagination_early(monkeypatch, tmp_path):
    fe7_n = {"n": 0}

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            fe7_n["n"] += 1
            from pb_utils import encode_field_bytes, encode_pb_message

            body = encode_field_bytes(15, b"c" * 36)
            return {"code": 0, "data": encode_pb_message({3: [0], 4: [body]}).hex()}
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {10001: TOK_A})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert sess.token_map == {10001: TOK_A}
    assert fe7_n["n"] == 1


def test_token_on_later_page(monkeypatch, tmp_path):
    pages = [{10099: "u_OTHERTOKENAAAAAAAAAAAA"}, {10001: TOK_A}]

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            from pb_utils import encode_field_bytes, encode_pb_message

            more = len(pages) > 1
            body = encode_field_bytes(15, b"c" * 36) if more else b""
            top = {3: [0]}
            if body:
                top[4] = [body]
            return {"code": 0, "data": encode_pb_message(top).hex()}
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: pages.pop(0) if pages else {})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert sess.token_map[10001] == TOK_A
    assert sess.fe7_pages == 2


def test_repeated_cursor_stops(monkeypatch, tmp_path):
    fe7_n = {"n": 0}

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            fe7_n["n"] += 1
            from pb_utils import encode_field_bytes, encode_pb_message

            body = encode_field_bytes(15, b"same-cursor-xxxxxxxxxxxxxxxxxx")
            return {"code": 0, "data": encode_pb_message({3: [0], 4: [body]}).hex()}
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {10099: TOK_A})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert fe7_n["n"] == 2
    assert 10001 in sess.missing_qqs


def test_pagination_safety_cap_records_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(pcg, "FE7_MAX_PAGES", 3)

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            from pb_utils import encode_field_bytes, encode_pb_message

            body = encode_field_bytes(15, bytes([fe7_n["n"]]) + b"x" * 35)
            return {"code": 0, "data": encode_pb_message({3: [0], 4: [body]}).hex()}
        return {"code": 0, "data": _oidb(0)}

    fe7_n = {"n": 0}

    def counting_send(cmd, hex_data, **k):
        if "0xfe7_4" in cmd:
            fe7_n["n"] += 1
        return fake_send(cmd, hex_data, **k)

    monkeypatch.setattr(pcg, "_send_packet", counting_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {10099: TOK_A})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert sess.hit_page_limit is True
    assert sess.fe7_pages == 3
    assert 10001 in sess.missing_qqs
    assert "\u5206\u9875\u8fbe\u5230\u5b89\u5168\u4e0a\u9650" in (sess.error or "")


def test_cursor_none_ends_pagination(monkeypatch, tmp_path):
    fe7_n = {"n": 0}

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            fe7_n["n"] += 1
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: {10001: TOK_A})
    monkeypatch.setattr(pcg, "extract_fe7_page_cursor", lambda _r: None)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100)
    assert sess is not None
    assert fe7_n["n"] == 1
    assert sess.termination_reason == "no_cursor"


def test_fe7_page1_protocol_error_returns_session(monkeypatch, tmp_path):
    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            return {"code": 0, "data": _oidb(2)}
        return {"code": 0, "data": _oidb(0)}

    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001])
    assert sess is not None
    assert sess.token_map == {}
    assert sess.termination_reason == "protocol_error"
    assert sess.failed_page == 1
    assert sess.protocol_error_code == 2
    assert 10001 in sess.missing_qqs
    assert sess.error


def test_fe7_page2_protocol_error_keeps_page1_token(monkeypatch, tmp_path):
    pages = {"n": 0}

    def fake_send(cmd, hex_data, **_k):
        if "0xfe7_4" in cmd:
            pages["n"] += 1
            if pages["n"] == 1:
                from pb_utils import encode_field_bytes, encode_pb_message

                body = encode_field_bytes(15, b"c" * 36)
                return {"code": 0, "data": encode_pb_message({3: [0], 4: [body]}).hex()}
            return {"code": 0, "data": _oidb(7)}
        return {"code": 0, "data": _oidb(0)}

    maps = [{10001: TOK_A}, {}]
    monkeypatch.setattr(pcg, "_send_packet", fake_send)
    monkeypatch.setattr(pcg, "parse_fe7_token_map", lambda _r: maps.pop(0) if maps else {})
    monkeypatch.setattr(pcg.time, "sleep", lambda *_a, **_k: None)
    sess = pcg.open_cross_group_picker(tmp_path, 200, 100, desired_qqs=[10001, 10002])
    assert sess is not None
    assert sess.token_map == {10001: TOK_A}
    assert sess.termination_reason == "protocol_error"
    assert sess.failed_page == 2
    assert 10002 in sess.missing_qqs
    assert 10001 not in sess.missing_qqs


def test_page2_error_zero_desired_tokens_does_not_send_fe1_758(monkeypatch):
    fe1 = []
    sent_758 = []

    def fake_picker(*_a, **_k):
        return pcg.PickerSession(
            token_map={},
            fe7_pages=1,
            requested_qqs=[10001, 10002],
            missing_qqs=[10001, 10002],
            error="FE7 page 2 protocol error",
            termination_reason="protocol_error",
            protocol_error_code=7,
            failed_page=2,
        )

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(
        cgb, "sync_fe1_selection", lambda *_a, **_k: fe1.append(1) or True
    )
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent_758.append(k) or (True, {"code": 0, "data": OIDB_OK}),
    )
    members = [
        SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="tok-b", role=MemberRole.MEMBER),
    ]
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert fe1 == []
    assert sent_758 == []
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert "FE7" in (by_qq[10001].get("reason") or "")
    assert "\u534f\u8bae\u9519\u8bef" in (by_qq[10001].get("reason") or "")
    assert by_qq[10001]["status"] == "failed"
    assert by_qq[10002]["status"] == "failed"


def test_page1_token_page2_error_invites_only_mapped_member(monkeypatch):
    fe1: list[list[str]] = []
    sent_758: list[list[str]] = []

    def fake_picker(*_a, **_k):
        return pcg.PickerSession(
            token_map={10001: TOK_A},
            fe7_pages=1,
            requested_qqs=[10001, 10002],
            missing_qqs=[10002],
            termination_reason="protocol_error",
            protocol_error_code=7,
            failed_page=2,
            error="FE7 page 2 protocol error",
        )

    monkeypatch.setattr(cgb, "open_cross_group_picker", fake_picker)
    monkeypatch.setattr(
        cgb, "sync_fe1_selection", lambda _c, tokens, **_k: fe1.append(list(tokens)) or True
    )
    monkeypatch.setattr(
        cgb,
        "send_cross_group_invite",
        lambda **k: sent_758.append(list(k.get("invitee_tokens") or []))
        or (True, {"code": 0, "data": OIDB_OK}),
    )
    monkeypatch.setattr(cgb, "wait_target_membership", lambda *_a, **_k: True)
    members = [
        SourceMember(qq=10001, nickname="a", token=TOK_A, role=MemberRole.MEMBER),
        SourceMember(qq=10002, nickname="b", token="tok-b", role=MemberRole.MEMBER),
    ]
    with cgb._members_lock:
        cgb._members_snapshot = MembersCacheSnapshot(
            source_group_id=100, filter_staff=True, members=tuple(members)
        )
    cgb.start_batch(
        target_group_id=200,
        source_group_id=100,
        interval_ms=100,
        qq_list=[10001, 10002],
        batch_size=2,
        filter_staff=True,
    )
    assert wait_not_running(timeout=2.0)
    assert fe1 == [[TOK_A]]
    assert sent_758 == [[TOK_A]]
    st = cgb.get_state()
    by_qq = {r["qq"]: r for r in st["results"]}
    assert by_qq[10001]["status"] == "success"
    assert by_qq[10002]["status"] == "failed"
    assert "\u7b2c 2 \u9875" in (by_qq[10002].get("reason") or "")
