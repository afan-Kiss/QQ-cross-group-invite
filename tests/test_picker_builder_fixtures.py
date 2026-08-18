# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import capture_utils as cu
from pb_utils import decode_pb_message, extract_field_bytes

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "picker_live_builders.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_88d_111_fixture_matches_builder_and_static_fields():
    fx = _load()
    target = int(fx["placeholder_target_group"])
    hx = cu.build_88d_111(target)
    assert hx == fx["88d_111_pb_hex"]
    assert len(bytes.fromhex(hx)) == fx["88d_111_send_len"] == 48
    top = decode_pb_message(bytes.fromhex(hx))
    exp = fx["expected"]
    assert top[1][0] == exp["88d_top_f1"]
    assert top[2][0] == exp["88d_top_f2"]
    assert top[12][0] == exp["88d_top_f12"]
    body = extract_field_bytes(bytes.fromhex(hx), 4)
    bf = decode_pb_message(body)
    assert bf[1][0] == fx["oidb_88d_111_body_type"] == cu.OIDB_88D_111_BODY_TYPE
    assert cu.nested_group_in_88d_111(hx) == target
    inner = extract_field_bytes(body, 2)
    flags = extract_field_bytes(inner, 2)
    assert flags.hex() == fx["88d_111_flags_hex"] == cu._88D_111_GROUP_FLAGS.hex()


def test_11ec_fixture_matches_builder_and_static_fields():
    fx = _load()
    target = int(fx["placeholder_target_group"])
    hx = cu.build_11ec_1(target)
    assert hx == fx["11ec_pb_hex"]
    assert len(bytes.fromhex(hx)) == fx["11ec_send_len"] == 266
    top = decode_pb_message(bytes.fromhex(hx))
    exp = fx["expected"]
    assert top[1][0] == exp["11ec_top_f1"]
    assert top[2][0] == exp["11ec_top_f2"]
    assert top[12][0] == exp["11ec_top_f12"]
    body = extract_field_bytes(bytes.fromhex(hx), 4)
    bf = decode_pb_message(body)
    assert bf[1][0] == target
    inner = extract_field_bytes(body, 2)
    inn = decode_pb_message(inner)
    assert inn[1][0] == exp["11ec_inner_f1"]
    assert inn[2][0] == exp["11ec_inner_f2"]
    xml = extract_field_bytes(inner, 4)
    style = extract_field_bytes(inner, 5)
    assert xml.hex() == fx["11ec_msg_template_hex"]
    assert style.hex() == fx["11ec_style_blob_hex"]
    assert extract_field_bytes(inner, 3) == b""
    assert extract_field_bytes(inner, 6) == b""
    assert b"u_" not in bytes.fromhex(hx)


def test_fe7_fixture_first_page_and_cursor_field15():
    fx = _load()
    source = int(fx["placeholder_source_group"])
    first = cu.build_fe7_group_list(source)
    assert first == fx["fe7_first_page_pb_hex"]
    assert len(bytes.fromhex(first)) == fx["fe7_first_page_send_len"] == 96
    top = decode_pb_message(bytes.fromhex(first))
    exp = fx["expected"]
    assert top[1][0] == exp["fe7_top_f1"]
    assert top[2][0] == exp["fe7_top_f2"]
    body = extract_field_bytes(bytes.fromhex(first), 4)
    bf = decode_pb_message(body)
    assert bf[1][0] == source
    assert bf[2][0] == exp["fe7_body_f2"]
    assert bf[3][0] == exp["fe7_body_f3"]
    assert 15 not in bf

    cursor = bytes.fromhex(fx["fe7_page_cursor_hex"])
    nxt = cu.build_fe7_group_list(source, page_cursor=cursor)
    assert nxt == fx["fe7_next_page_pb_hex"]
    assert len(bytes.fromhex(nxt)) == fx["fe7_next_page_send_len"] == 134
    nb = extract_field_bytes(bytes.fromhex(nxt), 4)
    nf = decode_pb_message(nb)
    assert 15 in nf
    raw_cur = extract_field_bytes(nb, 15)
    assert raw_cur == cursor
    assert exp["fe7_cursor_field"] == 15

    recv = fx["fe7_recv_with_cursor_hex"]
    assert cu.extract_fe7_page_cursor(recv) == cursor
    assert b"u_" not in bytes.fromhex(first)
    assert b"u_" not in bytes.fromhex(nxt)
