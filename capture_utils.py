# -*- coding: utf-8 -*-
"""Read NapCat packet_capture logs for 0x758 invite tokens."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from pb_utils import decode_oidb_packet, normalize_hex, parse_758_recv_status

ROOT = Path(__file__).resolve().parent
DEFAULT_CAPTURE_DIR = (
    ROOT.parent / "NapCatQQ-src" / "NapCat.Framework" / "logs" / "packet_capture"
)
CMD_758 = "OidbSvcTrpcTcp.0x758_1"
U_TOKEN_RE = re.compile(rb"u_[A-Za-z0-9_-]{16,}")


@dataclass
class Capture758:
    ts: str
    seq: int
    cmd: str
    send_hex: str
    recv_hex: str
    recv_len: int
    recv_code: int | None
    recv_ok: bool
    token: str | None
    group_code: int | None
    log_path: Path


def extract_u_token(data: bytes) -> str | None:
    m = U_TOKEN_RE.search(data)
    return m.group(0).decode("utf-8", errors="replace") if m else None


def extract_u_token_from_hex(hex_data: str) -> str | None:
    if not hex_data:
        return None
    try:
        return extract_u_token(bytes.fromhex(normalize_hex(hex_data)))
    except ValueError:
        return None


def iter_capture_logs(capture_dir: Path):
    if not capture_dir.is_dir():
        return
    logs = sorted(capture_dir.glob("capture-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for log in logs:
        yield log


def load_log_entries(log_path: Path) -> list[dict]:
    entries: list[dict] = []
    with log_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def index_by_seq(entries: list[dict]) -> dict[int, dict[str, dict]]:
    out: dict[int, dict[str, dict]] = {}
    for e in entries:
        seq = e.get("seq")
        if not isinstance(seq, int):
            continue
        direction = str(e.get("dir", "")).upper()
        if direction not in ("SEND", "RECV"):
            continue
        out.setdefault(seq, {})[direction] = e
    return out


def parse_758_send(hex_data: str) -> tuple[str | None, int | None]:
    try:
        pkt = decode_oidb_packet(CMD_758, hex_data)
    except ValueError:
        return None, None
    return pkt.invite_token, pkt.group_code


def find_all_758_pairs(capture_dir: Path) -> list[Capture758]:
    hits: list[Capture758] = []
    for log in iter_capture_logs(capture_dir):
        entries = load_log_entries(log)
        by_seq = index_by_seq(entries)
        for seq, pair in by_seq.items():
            send = pair.get("SEND")
            if not send:
                continue
            cmd = str(send.get("cmd", ""))
            if "758" not in cmd.lower():
                continue
            hex_data = normalize_hex(str(send.get("hex", "")))
            if not hex_data or hex_data.startswith("0000"):
                continue
            recv = pair.get("RECV") or {}
            recv_hex = str(recv.get("hex", ""))
            recv_len = int(recv.get("dataLen") or (len(recv_hex) // 2 if recv_hex else 0))
            recv_code, recv_ok = parse_758_recv_status(recv_hex)
            token, group_code = parse_758_send(hex_data)
            hits.append(
                Capture758(
                    ts=str(send.get("ts", "")),
                    seq=seq,
                    cmd=cmd,
                    send_hex=hex_data,
                    recv_hex=recv_hex,
                    recv_len=recv_len,
                    recv_code=recv_code,
                    recv_ok=recv_ok,
                    token=token,
                    group_code=group_code,
                    log_path=log,
                )
            )
    return hits


def latest_valid_758(
    capture_dir: Path,
    *,
    group_code: int | None = None,
    min_recv_len: int = 100,
) -> Capture758 | None:
    """Latest 0x758 whose server RECV field3==0 (token accepted)."""
    for hit in find_all_758_pairs(capture_dir):
        if hit.recv_len < min_recv_len:
            continue
        if not hit.recv_ok:
            continue
        if group_code is not None and hit.group_code not in (None, group_code):
            continue
        if not hit.token:
            continue
        return hit
    return None


def latest_token_for_invitee(
    capture_dir: Path,
    invitee: int,
    *,
    group_code: int | None = None,
) -> tuple[str | None, int]:
    """Token from a captured 0x758 pull SEND that included this invitee uin."""
    from pb_utils import decode_oidb_packet

    for hit in find_all_758_pairs(capture_dir):
        try:
            pkt = decode_oidb_packet(CMD_758, hit.send_hex)
        except ValueError:
            continue
        if pkt.invitee_uin != invitee or not pkt.invite_token:
            continue
        if group_code is not None and pkt.group_code not in (None, group_code):
            continue
        return pkt.invite_token, hit.recv_len
    return None, 0


def latest_any_token(capture_dir: Path) -> tuple[str | None, int | None, Path | None]:
    """Newest invite token from any successful 758 in capture logs."""
    hit = latest_valid_758(capture_dir)
    if not hit:
        return None, None, None
    return hit.token, hit.group_code, hit.log_path


def _read_varint_at(data: bytes, start: int) -> tuple[int, int]:
    val = 0
    shift = 0
    i = start
    while i < len(data):
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, i


def parse_fe7_token_map(hex_data: str) -> dict[int, str]:
    """Parse 0xfe7_4 RECV: map invitee QQ uin -> u_ token."""
    if not hex_data:
        return {}
    try:
        data = bytes.fromhex(normalize_hex(hex_data))
    except ValueError:
        return {}
    out: dict[int, str] = {}
    i = 0
    while i < len(data) - 4:
        if data[i] != 0x12:
            i += 1
            continue
        ln, j = _read_varint_at(data, i + 1)
        if ln <= 0 or j + ln > len(data):
            i += 1
            continue
        chunk = data[j : j + ln]
        if not chunk.startswith(b"u_"):
            i += 1
            continue
        token = chunk.decode("utf-8", errors="replace")
        k = j + ln
        while k < min(len(data), j + ln + 24):
            tag = data[k]
            field = tag >> 3
            wire = tag & 7
            if wire != 0:
                k += 1
                continue
            k += 1
            uin, k = _read_varint_at(data, k)
            if uin > 10000:
                out[uin] = token
                break
            k += 1
        i += 1
    return out


def extract_token_for_uin(hex_data: str, uin: int) -> str | None:
    """Find invite token in 0xfe7_4 RECV paired with invitee uin."""
    from pb_utils import encode_varint, normalize_hex

    if not hex_data or not uin:
        return None
    hit = parse_fe7_token_map(hex_data).get(int(uin))
    if hit:
        return hit
    try:
        data = bytes.fromhex(normalize_hex(hex_data))
    except ValueError:
        return None
    needles = [bytes([0x20]) + encode_varint(int(uin)), encode_varint(int(uin))]
    for needle in needles:
        idx = data.find(needle)
        if idx < 0:
            continue
        for window in (
            data[max(0, idx - 120) : idx + 8],
            data[idx : min(len(data), idx + 120)],
        ):
            m = U_TOKEN_RE.search(window)
            if m:
                return m.group(0).decode("utf-8", errors="replace")
    return None


def find_fe7_group_template(capture_dir: Path, group_code: int) -> str | None:
    """0xfe7_4 SEND that loads group friend list (contains group internal code)."""
    pages = find_fe7_pagination_templates(capture_dir, group_code)
    return pages[0] if pages else None


def find_fe7_pagination_templates(capture_dir: Path, group_code: int) -> list[str]:
    """All captured 0xfe7_4 group-list pages (96-byte SEND) for this group."""
    group_hex = encode_group_varint_hex(group_code)
    if not group_hex:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "SEND":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if group_hex not in hex_data or len(hex_data) < 160:
                continue
            if hex_data in seen:
                continue
            seen.add(hex_data)
            out.append(hex_data)
    return out


def find_fe7_pagination_templates_generic(capture_dir: Path) -> list[str]:
    """Any captured fe7_4 group-list page; group id is patched before send."""
    seen: set[str] = set()
    out: list[str] = []
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "SEND":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if len(hex_data) < 160:
                continue
            if hex_data in seen:
                continue
            seen.add(hex_data)
            out.append(hex_data)
    return out


def find_fe7_single_template(capture_dir: Path, group_code: int) -> str | None:
    """0xfe7_4 SEND with embedded u_ uid (70-byte single-friend lookup)."""
    group_hex = encode_group_varint_hex(group_code)
    if not group_hex:
        return None
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "SEND":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if group_hex not in hex_data:
                continue
            if U_TOKEN_RE.search(bytes.fromhex(hex_data)):
                if 120 <= len(hex_data) <= 160:
                    return hex_data
    return None


def find_fe7_token_refresh_template(capture_dir: Path, group_code: int) -> str | None:
    """0xfe7_4 SEND with group + prior token (124-byte refresh preferred)."""
    group_hex = encode_group_varint_hex(group_code)
    if not group_hex:
        return None
    fallback: str | None = None
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "SEND":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if group_hex not in hex_data:
                continue
            if not U_TOKEN_RE.search(bytes.fromhex(hex_data)):
                continue
            data_len = int(entry.get("dataLen") or (len(hex_data) // 2))
            if data_len == 124:
                return hex_data
            if data_len >= 120 and fallback is None:
                fallback = hex_data
    return fallback


def find_group_share_token(capture_dir: Path, group_code: int) -> str | None:
    """Group invite link token from capture (55-byte 758 SEND or 124-byte fe7 refresh)."""
    for hit in find_all_758_pairs(capture_dir):
        if hit.group_code != group_code or not hit.token:
            continue
        try:
            pkt = decode_oidb_packet(CMD_758, hit.send_hex)
        except ValueError:
            continue
        if pkt.invitee_uin is None:
            return pkt.invite_token
    refresh = find_fe7_token_refresh_template(capture_dir, group_code)
    if refresh:
        return extract_u_token_from_hex(refresh)
    return None


# Field mask from QQ NT 96-byte 0xfe7_4 group-list SEND (fields 10-21, 50-53, 70-71, 100-107, 200-201).
FE7_MEMBER_FIELD_MASK = bytes.fromhex(
    "500158016001680170017801800101880101900101a00101a80101"
    "900301980301a00301a80301b00401b80401a00601a80601b00601"
    "b80601c00601c80601d00601d80601c00c01c80c01"
)


def build_fe7_group_list(group_code: int) -> str:
    """Build 0xfe7_4 group member-list page (96-byte UI capture) without a log template."""
    from pb_utils import encode_field_bytes, encode_field_varint, encode_pb_message

    body = bytearray()
    body.extend(encode_field_varint(1, int(group_code)))
    body.extend(encode_field_varint(2, 5))
    body.extend(encode_field_varint(3, 2))
    body.extend(encode_field_bytes(4, FE7_MEMBER_FIELD_MASK))
    top = encode_pb_message({1: [0xfe7], 2: [4], 4: [bytes(body)], 12: [0]})
    return top.hex()


def build_fe7_single_lookup(group_code: int, uid: str) -> str:
    """Build 0xfe7_4 single-friend lookup PB (embed u_ uid)."""
    from pb_utils import encode_field_bytes, encode_field_varint, encode_pb_message

    uid_b = uid.encode("utf-8")
    inner = encode_pb_message({2: [uid_b]})
    body = bytearray()
    body.extend(encode_field_varint(1, int(group_code)))
    body.extend(encode_field_varint(2, 3))
    body.extend(encode_field_bytes(5, inner))
    top = encode_pb_message({1: [0xfe7], 2: [4], 4: [bytes(body)]})
    return top.hex()


def patch_uid_in_fe7_hex(hex_data: str, uid: str, group_code: int) -> str:
    """Replace embedded u_ uid in captured fe7 single lookup."""
    from pb_utils import encode_field_bytes, normalize_hex

    h = normalize_hex(hex_data)
    m = U_TOKEN_RE.search(bytes.fromhex(h))
    if not m:
        return build_fe7_single_lookup(group_code, uid)
    old = m.group(0).decode("utf-8", errors="replace")
    uid_b = uid.encode("utf-8")
    inner = encode_field_bytes(2, uid_b)
    old_inner = encode_field_bytes(2, old.encode("utf-8"))
    old_bytes = bytes.fromhex(h)
    idx = old_bytes.find(bytes.fromhex(old_inner.hex()))
    if idx < 0:
        return build_fe7_single_lookup(group_code, uid)
    patched = old_bytes[:idx] + inner + old_bytes[idx + len(old_inner) :]
    return patched.hex()


def find_permanent_uid_from_capture(
    capture_dir: Path, group_code: int, invitee: int | None = None
) -> str | None:
    """NT uid (u_xxx) from captured fe7 single-friend lookup for this group."""
    del invitee  # uid is stable; invite token is not
    single = find_fe7_single_template(capture_dir, group_code)
    if single:
        m = U_TOKEN_RE.search(bytes.fromhex(normalize_hex(single)))
        if m:
            return m.group(0).decode("utf-8", errors="replace")
    return None


def lookup_token_owner(capture_dir: Path, token: str) -> int | None:
    """Return invitee QQ uin that owns this fe7 invite token (from captured RECV)."""
    if not token:
        return None
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "RECV":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            for uin, tok in parse_fe7_token_map(str(entry.get("hex", ""))).items():
                if tok == token:
                    return int(uin)
    return None


def token_owner_mismatch(
    capture_dir: Path, token: str, invitee: int
) -> int | None:
    """If token is known to belong to another uin, return that uin; else None."""
    owner = lookup_token_owner(capture_dir, token)
    if owner is not None and owner != int(invitee):
        return owner
    return None


def scan_capture_fe7_token(capture_dir: Path, invitee: int) -> str | None:
    """Latest invite token for invitee from any captured fe7_4 RECV."""
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "RECV":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hex_data = str(entry.get("hex", ""))
            token = extract_token_for_uin(hex_data, invitee)
            if token:
                return token
    return None


def scan_capture_fe7_token_map(capture_dir: Path) -> dict[int, str]:
    """Merge all uin->token pairs from captured fe7_4 RECV pages."""
    merged: dict[int, str] = {}
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "RECV":
                continue
            if "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            merged.update(parse_fe7_token_map(str(entry.get("hex", ""))))
    return merged


def merge_fe7_token_maps(hex_pages: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for h in hex_pages:
        out.update(parse_fe7_token_map(h))
    return out


def patch_u_token_in_hex(hex_data: str, token: str) -> str:
    """Replace first embedded u_ string in raw packet hex."""
    from pb_utils import encode_field_bytes, normalize_hex

    h = normalize_hex(hex_data)
    m = U_TOKEN_RE.search(bytes.fromhex(h))
    if not m:
        return h
    old = m.group(0).decode("utf-8", errors="replace")
    old_b = encode_field_bytes(1, old.encode("utf-8"))
    new_b = encode_field_bytes(1, token.encode("utf-8"))
    data = bytes.fromhex(h)
    idx = data.find(bytes.fromhex(old_b.hex()))
    if idx < 0:
        return h
    return (data[:idx] + new_b + data[idx + len(old_b) :]).hex()


# Successful manual mint order (capture-1786855921751 seq 4855364-4855389).
INVITE_UI_SELECT_CHAIN: list[tuple[str, int]] = [
    ("0xfe1_8", 41),
    ("0x116c_1", 39),
    ("0xfe1_8", 207),
    ("0x9075_1", 50),
    ("0x7ed_12", 50),
    ("0x116c_1", 39),
    ("0xfe1_8", 41),
    ("0xfe1_8", 41),
    ("0xfe1_8", 273),
    ("0xfe1_8", 273),
]

PULL_BOOTSTRAP_CHAIN: list[tuple[str, int]] = [
    ("0xfe7_4", 96),
    ("0xfe7_4", 124),
    ("0x88d_0", 405),
    ("0xaf6_0", 17),
    ("0xfe7_4", 96),
]

# After UI select, before 59-byte pull (manual seq 4855378-4855389).
POST_UI_ACTIVATION_CHAIN: list[tuple[str, int]] = [
    ("0x88d_111", 35),
    *PULL_BOOTSTRAP_CHAIN,
]

MINT_CHAIN_CMD_MARKERS = (
    "0xfe1_8",
    "0x116c_1",
    "0x9075_1",
    "0x7ed_12",
    "0xfe7_4",
    "0x88d_0",
    "0x88d_111",
    "0x88d_14",
    "0x11ec_1",
    "0xaf6_0",
    "0x758_1",
)

# Cross-group invite: open picker in target group, browse source group members.
CROSS_GROUP_OPEN_CHAIN: list[tuple[str, int]] = [
    ("0x88d_14", 259),
    ("0x88d_111", 48),
]

CROSS_GROUP_PREP_CHAIN: list[tuple[str, int]] = [
    ("0x11ec_1", 266),
    ("0x88d_0", 405),
    ("0xfe7_4", 96),
    ("0xfe7_4", 124),
]


def find_packet_template(
    capture_dir: Path,
    cmd_marker: str,
    data_len: int,
    *,
    require_u_token: bool = False,
    len_slop: int = 0,
) -> str | None:
    """Latest captured SEND template matching cmd suffix and payload size."""
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "SEND":
                continue
            cmd = str(entry.get("cmd", ""))
            if cmd_marker not in cmd:
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if not hex_data:
                continue
            reported = int(entry.get("dataLen") or 0)
            actual = len(hex_data) // 2
            if min(abs((reported or actual) - data_len), abs(actual - data_len)) > len_slop:
                continue
            if require_u_token and not U_TOKEN_RE.search(bytes.fromhex(hex_data)):
                continue
            return hex_data
    return None


def find_invite_ui_chain_templates(capture_dir: Path) -> list[tuple[str, str]]:
    """Templates for fe1/116c/9075/7ed invitee select chain (from capture)."""
    out: list[tuple[str, str]] = []
    for cmd_marker, data_len in INVITE_UI_SELECT_CHAIN:
        tpl = find_packet_template(
            capture_dir, cmd_marker, data_len, require_u_token=True
        )
        if not tpl:
            return []
        full_cmd = next(
            (
                f"OidbSvcTrpcTcp.{cmd_marker}"
                for cmd_marker in (cmd_marker,)
            ),
            cmd_marker,
        )
        out.append((full_cmd, tpl))
    return out


def find_cross_group_chain_templates(
    capture_dir: Path,
) -> list[tuple[str, str]]:
    """Templates for cross-group picker open + prep (88d_14/111, 11ec, fe7).

    Missing packets are skipped instead of dropping the whole chain: member
    loading already works off generic fe7 pages, and invite should too.
    """
    out: list[tuple[str, str]] = []
    for cmd_marker, data_len in CROSS_GROUP_OPEN_CHAIN + CROSS_GROUP_PREP_CHAIN:
        tpl = find_packet_template(capture_dir, cmd_marker, data_len, len_slop=16)
        if tpl:
            out.append((f"OidbSvcTrpcTcp.{cmd_marker}", tpl))
    if not any("0xfe7_4" in cmd for cmd, _ in out):
        pages = find_fe7_pagination_templates_generic(capture_dir)
        for page in pages[:2]:
            out.append(("OidbSvcTrpcTcp.0xfe7_4", page))
    return out


def find_cross_group_758_template(
    capture_dir: Path, target_group_id: int
) -> str | None:
    """Latest successful 95-byte cross-group 0x758 SEND for target group."""
    from pb_utils import parse_cross_group_758_body, extract_field_bytes, normalize_hex

    target_hex = encode_group_varint_hex(target_group_id)
    if not target_hex:
        return None
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "SEND":
                continue
            if "0x758_1" not in str(entry.get("cmd", "")):
                continue
            if int(entry.get("dataLen") or 0) < 90:
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if target_hex not in hex_data:
                continue
            body = extract_field_bytes(bytes.fromhex(hex_data), 4)
            if not body:
                continue
            tgt, src, ctx, inv = parse_cross_group_758_body(body)
            if tgt == int(target_group_id) and src and ctx and inv and ctx != inv:
                return hex_data
    return None


def find_source_context_token(
    capture_dir: Path, source_group_id: int
) -> str | None:
    """Source-group context token from cross-group 758 capture or fe7 group token."""
    from pb_utils import parse_cross_group_758_body, extract_field_bytes, normalize_hex

    src_hex = encode_group_varint_hex(source_group_id)
    if src_hex:
        for log in iter_capture_logs(capture_dir):
            for entry in reversed(load_log_entries(log)):
                if entry.get("dir") != "SEND" or "0x758_1" not in str(entry.get("cmd", "")):
                    continue
                hex_data = normalize_hex(str(entry.get("hex", "")))
                if src_hex not in hex_data:
                    continue
                body = extract_field_bytes(bytes.fromhex(hex_data), 4)
                if not body:
                    continue
                _, src, ctx, inv = parse_cross_group_758_body(body)
                if src == int(source_group_id) and ctx and inv and ctx != inv:
                    return ctx
    return find_known_group_token(capture_dir, source_group_id)


def find_fe1_multi_select_template(capture_dir: Path) -> str | None:
    """fe1_8 SEND with multiple u_ tokens (confirm cross-group selection)."""
    return find_packet_template(capture_dir, "0xfe1_8", 276, require_u_token=True)


def find_success_pull_anchor(
    capture_dir: Path,
    group_code: int,
    invitee: int,
) -> tuple[Path, int, str] | None:
    """Best captured 59-byte 0x758 pull for invitee with RECV f3=0."""

    def score(hit: Capture758, send_hex: str) -> int:
        pts = hit.recv_len
        if hit.recv_len >= 924:
            pts += 50
        if "1786855921751" in hit.log_path.name:
            pts += 30
        try:
            data = bytes.fromhex(send_hex)
            if len(data) > 6 and data[6] == 0x32:
                pts += 40
        except ValueError:
            pass
        return pts

    best: tuple[int, Path, int, str] | None = None
    for hit in find_all_758_pairs(capture_dir):
        if not hit.recv_ok or hit.group_code != group_code:
            continue
        if len(hit.send_hex) // 2 != 59:
            continue
        try:
            pkt = decode_oidb_packet(CMD_758, hit.send_hex)
        except ValueError:
            continue
        if pkt.invitee_uin != invitee or not pkt.invite_token:
            continue
        pts = score(hit, hit.send_hex)
        if best is None or pts > best[0] or (pts == best[0] and hit.seq > best[2]):
            best = (pts, hit.log_path, hit.seq, hit.send_hex)
    if best is None:
        return None
    return best[1], best[2], best[3]


def find_sequence_in_log(
    log_path: Path,
    before_seq: int,
    chain: list[tuple[str, int]],
    *,
    require_u_token: bool = False,
) -> list[tuple[str, str]]:
    """Ordered SEND templates from one capture log (ascending seq, before pull)."""
    entries = [
        e
        for e in load_log_entries(log_path)
        if e.get("dir") == "SEND" and isinstance(e.get("seq"), int) and e["seq"] < before_seq
    ]
    out: list[tuple[str, str]] = []
    last_seq = 0
    for cmd_marker, data_len in chain:
        picked: dict | None = None
        for entry in sorted(entries, key=lambda e: int(e["seq"])):
            seq = int(entry["seq"])
            if seq <= last_seq:
                continue
            cmd = str(entry.get("cmd", ""))
            if cmd_marker not in cmd:
                continue
            if int(entry.get("dataLen") or 0) != data_len:
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            if not hex_data:
                continue
            if require_u_token and not U_TOKEN_RE.search(bytes.fromhex(hex_data)):
                continue
            picked = entry
            break
        if not picked:
            return []
        out.append((f"OidbSvcTrpcTcp.{cmd_marker}", normalize_hex(str(picked.get("hex", "")))))
        last_seq = int(picked["seq"])
    return out


def find_invite_ui_chain_from_anchor(
    capture_dir: Path, group_code: int, invitee: int
) -> list[tuple[str, str]]:
    anchor = find_success_pull_anchor(capture_dir, group_code, invitee)
    if not anchor:
        return []
    log_path, before_seq, _ = anchor
    return find_sequence_in_log(
        log_path, before_seq, INVITE_UI_SELECT_CHAIN, require_u_token=True
    )


def find_post_select_activation_templates(
    capture_dir: Path, group_code: int, invitee: int
) -> list[tuple[str, str]]:
    anchor = find_success_pull_anchor(capture_dir, group_code, invitee)
    if not anchor:
        return []
    log_path, before_seq, _ = anchor
    return find_sequence_in_log(log_path, before_seq, POST_UI_ACTIVATION_CHAIN)


def find_successful_pull_template(
    capture_dir: Path, group_code: int, invitee: int
) -> str | None:
    anchor = find_success_pull_anchor(capture_dir, group_code, invitee)
    if not anchor:
        return None
    return anchor[2]


def find_pull_bootstrap_templates(capture_dir: Path) -> list[tuple[str, str]]:
    """Templates for fe7/88d/af6 bootstrap after consent 758."""
    out: list[tuple[str, str]] = []
    for cmd_marker, data_len in PULL_BOOTSTRAP_CHAIN:
        tpl = find_packet_template(capture_dir, cmd_marker, data_len)
        if not tpl:
            return []
        out.append((f"OidbSvcTrpcTcp.{cmd_marker}", tpl))
    return out


def find_consent_758_template(capture_dir: Path, group_code: int) -> str | None:
    """55-byte 0x758 consent SEND (group token, no invitee uin)."""
    from pb_utils import decode_oidb_packet

    for hit in find_all_758_pairs(capture_dir):
        if hit.group_code != group_code or not hit.token:
            continue
        try:
            pkt = decode_oidb_packet(CMD_758, hit.send_hex)
        except ValueError:
            continue
        if pkt.invitee_uin is None and len(hit.send_hex) // 2 <= 56:
            return hit.send_hex
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "SEND" or "758" not in str(entry.get("cmd", "")):
                continue
            if int(entry.get("dataLen") or 0) != 55:
                continue
            hex_data = normalize_hex(str(entry.get("hex", "")))
            try:
                pkt = decode_oidb_packet(CMD_758, hex_data)
            except ValueError:
                continue
            if pkt.invitee_uin is None and pkt.group_code == group_code:
                return hex_data
    return None


def find_fe1_select_template(capture_dir: Path) -> str | None:
    """Short fe1_8 SEND used when selecting one invitee (41-byte)."""
    return find_packet_template(capture_dir, "0xfe1_8", 41, require_u_token=True)


def find_116c_select_template(capture_dir: Path) -> str | None:
    """116c_1 SEND when confirming invitee selection (39-byte)."""
    for log in iter_capture_logs(capture_dir):
        for entry in load_log_entries(log):
            if entry.get("dir") != "SEND":
                continue
            if "0x116c_1" not in str(entry.get("cmd", "")):
                continue
            if int(entry.get("dataLen") or 0) == 39:
                hex_data = normalize_hex(str(entry.get("hex", "")))
                if U_TOKEN_RE.search(bytes.fromhex(hex_data)):
                    return hex_data
    return None


def extract_invite_tokens_from_hex(hex_data: str) -> list[str]:
    if not hex_data:
        return []
    try:
        data = bytes.fromhex(normalize_hex(hex_data))
    except ValueError:
        return []
    return [m.group(0).decode("utf-8", errors="replace") for m in U_TOKEN_RE.finditer(data)]


def patch_token_in_fe7_refresh(hex_data: str, token: str, group_code: int) -> str:
    """Patch embedded token in 124-byte fe7 refresh (group code must already match template)."""
    del group_code  # outer OIDB field1 is cmd, not group ?? do not patch_group_code_in_hex here
    from pb_utils import normalize_hex

    h = normalize_hex(hex_data)
    data = bytearray(bytes.fromhex(h))
    m = U_TOKEN_RE.search(bytes(data))
    if not m:
        return h
    old = m.group(0)
    new = token.encode("utf-8")
    if len(new) != len(old):
        # rebuild inner field2 length-delimited
        inner = bytes([0x12, len(new)]) + new
        outer = bytes([0x2a, len(inner)]) + inner
        start = m.start()
        # find 2a tag before token
        scan = max(0, start - 4)
        for i in range(scan, start):
            if data[i] == 0x2a:
                ln, j = _read_varint_at(data, i + 1)
                if j <= start < j + ln:
                    return (
                        bytes(data[:i]) + outer + bytes(data[j + ln:])
                    ).hex()
    idx = m.start()
    data[idx : idx + len(old)] = new
    return bytes(data).hex()


def encode_group_varint_hex(group_code: int) -> str | None:
    from pb_utils import encode_varint

    return encode_varint(int(group_code)).hex()


def find_bootstrap_templates(capture_dir: Path) -> list[tuple[str, str]]:
    """Packets QQ sends just before minting an invite token (from successful capture)."""
    for log in iter_capture_logs(capture_dir):
        entries = load_log_entries(log)
        send_758_idx = None
        for i, e in enumerate(entries):
            if e.get("dir") != "SEND":
                continue
            if "758" not in str(e.get("cmd", "")).lower():
                continue
            seq = e.get("seq")
            recv = next(
                (
                    x
                    for x in entries
                    if x.get("dir") == "RECV" and x.get("seq") == seq
                ),
                None,
            )
            recv_len = int((recv or {}).get("dataLen") or 0)
            if recv_len >= 100:
                send_758_idx = i
                break
        if send_758_idx is None:
            continue
        templates: list[tuple[str, str]] = []
        for e in entries[max(0, send_758_idx - 40) : send_758_idx]:
            if e.get("dir") != "SEND":
                continue
            cmd = str(e.get("cmd", ""))
            if not any(k in cmd for k in ("0xfe7_4", "0xaf6_0", "0x88d_")):
                continue
            hex_data = normalize_hex(str(e.get("hex", "")))
            if hex_data:
                templates.append((cmd, hex_data))
        if templates:
            return templates
    return []


def patch_group_code_in_hex(hex_data: str, group_code: int) -> str:
    """Replace group internal code inside OIDB field4 body (never top-level cmd field)."""
    from pb_utils import encode_varint, extract_field_bytes, normalize_hex, replace_field_bytes

    h = normalize_hex(hex_data)
    data = bytes.fromhex(h)
    new_gc = encode_varint(int(group_code))
    if new_gc in data:
        return h

    body = extract_field_bytes(data, 4)
    if not body:
        return h

    body_ba = bytearray(body)
    if not body_ba or body_ba[0] != 0x08:
        return h
    i = 1
    val_start = i
    while i < len(body_ba):
        b = body_ba[i]
        i += 1
        if not (b & 0x80):
            break
    old_gc = bytes(body_ba[val_start:i])
    if old_gc == new_gc:
        return h
    new_body = bytes(body_ba[:val_start]) + new_gc + bytes(body_ba[i:])
    return replace_field_bytes(data, 4, new_body).hex()


def latest_758_recv_for_invitee(
    capture_dir: Path,
    invitee: int,
    *,
    since_mtime: float | None = None,
    min_recv_len: int = 200,
) -> tuple[bool, int, int | None]:
    """Latest 0x758 pull for invitee: (recv_ok, recv_len, field3 code)."""
    from pb_utils import decode_oidb_packet

    best_ok = False
    best_len = 0
    best_code: int | None = None
    for hit in find_all_758_pairs(capture_dir):
        if since_mtime is not None and hit.log_path.stat().st_mtime < since_mtime:
            continue
        try:
            pkt = decode_oidb_packet(CMD_758, hit.send_hex)
        except ValueError:
            continue
        if pkt.invitee_uin != invitee:
            continue
        if hit.recv_len < min_recv_len:
            continue
        if hit.recv_len >= best_len:
            best_len = hit.recv_len
            best_ok = hit.recv_ok
            best_code = hit.recv_code
    return best_ok, best_len, best_code


def extract_group_token_from_fe7(hex_data: str, group_code: int | None = None) -> str | None:
    """Context token from 0xfe7_4 RECV: extra uid not paired to a member, else first token.

    The group-code proximity heuristic is last: it usually hits the first member
    in the list, which is an invitee token, not the picker context.
    """
    del group_code
    if not hex_data:
        return None
    try:
        normalize_hex(hex_data)
    except ValueError:
        return None
    per_user = set(parse_fe7_token_map(hex_data).values())
    toks = extract_invite_tokens_from_hex(hex_data)
    for tok in toks:
        if tok not in per_user:
            return tok
    return toks[0] if toks else None


def extract_group_token_from_af6(hex_data: str) -> str | None:
    """Group invite token from 0xaf6_0 RECV (appears after consent 758)."""
    if not hex_data or "success" not in bytes.fromhex(normalize_hex(hex_data)).decode("utf-8", errors="replace").lower():
        pass
    toks = extract_invite_tokens_from_hex(hex_data)
    return toks[0] if toks else None


def find_known_group_token(capture_dir: Path, group_code: int) -> str | None:
    """Best-effort group share token from capture (758 ok or fe7 group list)."""
    hit = latest_valid_758(capture_dir, group_code=group_code)
    if hit and hit.token:
        return hit.token
    for log in iter_capture_logs(capture_dir):
        for entry in reversed(load_log_entries(log)):
            if entry.get("dir") != "RECV" or "0xfe7_4" not in str(entry.get("cmd", "")):
                continue
            hx = str(entry.get("hex", ""))
            tok = extract_group_token_from_fe7(hx, group_code)
            if tok and tok != find_permanent_uid_from_capture(capture_dir, group_code, None):
                return tok
    return None


def watch_new_758_token(
    capture_dir: Path,
    *,
    timeout: float = 20.0,
    since_mtime: float | None = None,
) -> Capture758 | None:
    deadline = time.time() + timeout
    seen: set[tuple[str, int]] = set()
    for hit in find_all_758_pairs(capture_dir):
        seen.add((str(hit.log_path), hit.seq))
    while time.time() < deadline:
        for hit in find_all_758_pairs(capture_dir):
            key = (str(hit.log_path), hit.seq)
            if key in seen:
                continue
            if since_mtime is not None and hit.log_path.stat().st_mtime < since_mtime:
                continue
            if hit.token and hit.recv_len >= 100 and hit.recv_ok:
                return hit
            seen.add(key)
        time.sleep(0.4)
    return None
