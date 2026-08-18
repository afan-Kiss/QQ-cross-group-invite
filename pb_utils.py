# -*- coding: utf-8 -*-
"""Parse PB log lines and decode OIDB invite packets."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# cmd: OidbSvcTrpcTcp.0x758_1, pb: abcd...
LOG_CMD_PB_RE = re.compile(
    r"cmd\s*:\s*([^\s,]+)\s*,\s*pb\s*:\s*([0-9a-fA-F]+)",
    re.IGNORECASE,
)
LOG_DIR_RE = re.compile("\u3010(send|recv)\u3011", re.IGNORECASE)


def normalize_hex(raw: str) -> str:
    s = re.sub(r"[^0-9a-fA-F]", "", raw or "")
    if len(s) % 2:
        raise ValueError("PB hex length must be even")
    return s.lower()


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint must be non-negative")
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _tag(field_num: int, wire: int) -> bytes:
    return bytes([field_num << 3 | wire])


def encode_field_varint(field_num: int, value: int) -> bytes:
    return _tag(field_num, 0) + encode_varint(value)


def encode_field_bytes(field_num: int, data: bytes) -> bytes:
    return _tag(field_num, 2) + encode_varint(len(data)) + data


def encode_pb_message(fields: dict[int, list[Any]]) -> bytes:
    out = bytearray()
    for fn in sorted(fields.keys()):
        for val in fields[fn]:
            if isinstance(val, int):
                out.extend(encode_field_varint(fn, val))
            elif isinstance(val, bytes):
                out.extend(encode_field_bytes(fn, val))
            elif isinstance(val, dict):
                out.extend(encode_field_bytes(fn, encode_pb_message(val)))
            else:
                raise TypeError(f"unsupported field type: {type(val)!r}")
    return bytes(out)


def parse_invite_758_body(body: bytes) -> tuple[int | None, str | None, int | None]:
    """Linear parse 0x758 field4 body (avoid mis-decoding token bytes as nested PB)."""
    group_code = token = invitee = None
    i = 0
    while i < len(body):
        if i >= len(body):
            break
        tag = body[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            val, i = read_varint(body, i)
            if fn == 1:
                group_code = val
        elif wt == 2:
            ln, i = read_varint(body, i)
            chunk = body[i : i + ln]
            i += ln
            if fn == 2:
                j = 0
                while j < len(chunk):
                    btag = chunk[j]
                    j += 1
                    bfn = btag >> 3
                    bwt = btag & 7
                    if bwt == 0:
                        bval, j = read_varint(chunk, j)
                        if bfn == 1:
                            group_code = bval
                        elif bfn == 2:
                            invitee = bval
                    elif bwt == 2:
                        bln, j = read_varint(chunk, j)
                        bchunk = chunk[j : j + bln]
                        j += bln
                        if bfn == 1:
                            token = bchunk.decode("utf-8", errors="replace")
                        elif bfn == 2:
                            k = 0
                            while k < len(bchunk):
                                ntag = bchunk[k]
                                k += 1
                                nfn = ntag >> 3
                                nwt = ntag & 7
                                if nwt == 0:
                                    nval, k = read_varint(bchunk, k)
                                    if nfn == 2:
                                        invitee = nval
                                elif nwt == 2:
                                    nln, k = read_varint(bchunk, k)
                                    nchunk = bchunk[k : k + nln]
                                    k += nln
                                    if nfn == 1:
                                        token = nchunk.decode(
                                            "utf-8", errors="replace"
                                        )
            elif fn == 3 and ln == 0:
                pass
        else:
            break
    return group_code, token, invitee


def build_invite_758_pb(
    *,
    group_code: int,
    invite_token: str,
    invitee_uin: int | None = None,
    pull: bool = False,
    subcmd: int = 1,
) -> str:
    """Build OidbSvcTrpcTcp.0x758_1 PB from structured fields.

    Consent invite (default): body.field2 wraps token only; body.field3 is empty.
    Direct pull (pull=True): body.field2 holds token (field1) + invitee uin (field2);
    no body.field3; trailing zero fields stay on body (matches QQ UI capture).
    """
    if pull:
        if invitee_uin is None:
            raise ValueError("pull mode requires invitee_uin")
        inner = bytearray()
        inner.extend(
            encode_field_bytes(1, invite_token.encode("utf-8"))
        )
        inner.extend(encode_field_varint(2, int(invitee_uin)))
        body = bytearray()
        body.extend(encode_field_varint(1, int(group_code)))
        body.extend(encode_field_bytes(2, bytes(inner)))
        body.extend(encode_field_varint(4, 0))
        body.extend(encode_field_varint(5, 0))
        body.extend(encode_field_bytes(6, b""))
        body.extend(encode_field_varint(7, 0))
        body.extend(encode_field_varint(10, 0))
        body.extend(encode_field_varint(12, 0))
        top_fields: dict[int, list[Any]] = {
            1: [0x758],
            2: [subcmd],
            4: [bytes(body)],
        }
        return encode_pb_message(top_fields).hex()

    block_fields: dict[int, list[Any]] = {1: [invite_token.encode("utf-8")]}
    body_fields: dict[int, list[Any]] = {
        1: [int(group_code)],
        2: [encode_pb_message(block_fields)],
        3: [b""],
        4: [0],
        5: [0],
        6: [b""],
        7: [0],
        10: [0],
    }
    top_fields = {
        1: [0x758],
        2: [subcmd],
        4: [encode_pb_message(body_fields)],
        12: [0],
    }
    return encode_pb_message(top_fields).hex()


def describe_token(tok: str | None) -> str:
    """Log-safe token metadata. Never include the raw u_ value."""
    import hashlib

    if not tok:
        return "token_present=false"
    digest = hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8]
    return f"token_present=true token_len={len(tok)} token_hash={digest}"


def build_cross_group_758_pb(
    *,
    target_group_id: int,
    source_group_id: int,
    invitee_tokens: list[str] | None = None,
    invitee_token: str | None = None,
    source_context_token: str | None = None,
    subcmd: int = 1,
) -> str:
    """Cross-group 0x758_1 from successful UI captures (95B two invitees / 232B six).

    Real SEND layout (capture-1786860477114 seq 9957015 / 9957026 / 9957135):
      top.field1=0x758 top.field2=1 top.field4=body top.field12=0
      body.field1=target_group_id
      body.field2 repeated {field1=u_ member token, field2=source_group_id}
      body.field3 empty, 4=0, 5=0, 6 empty, 7=0, 10=0

    Each field2 block is an invitee, not a separate 'context' token.
    source_context_token is ignored; kept only so old callers do not crash.
    """
    del source_context_token
    tokens = [t for t in (invitee_tokens or []) if t]
    if invitee_token:
        tokens.append(invitee_token)
    if not tokens:
        raise ValueError("cross-group 758 requires at least one invitee token")
    blocks = [
        {1: [tok.encode("utf-8")], 2: [int(source_group_id)]} for tok in tokens
    ]
    body_fields: dict[int, list[Any]] = {
        1: [int(target_group_id)],
        2: blocks,
        3: [b""],
        4: [0],
        5: [0],
        6: [b""],
        7: [0],
        10: [0],
    }
    top_fields = {
        1: [0x758],
        2: [subcmd],
        4: [encode_pb_message(body_fields)],
        12: [0],
    }
    return encode_pb_message(top_fields).hex()


def parse_cross_group_758_entries(
    body: bytes,
) -> tuple[int | None, int | None, list[str]]:
    """Parse cross-group 758 body -> target, source_group, invitee tokens."""
    target, source, tokens, _entries = _parse_cross_group_758_blocks(body)
    return target, source, tokens


def parse_cross_group_758_body(
    body: bytes,
) -> tuple[int | None, int | None, str | None, str | None]:
    """Parse cross-group 758 -> target, source, first_token, second_token.

    First/second tokens are invitee blocks (captures use 2 or 6 members).
    Names kept for callers; they are not a distinct context vs invitee pair.
    """
    target, source, tokens, _entries = _parse_cross_group_758_blocks(body)
    first = tokens[0] if tokens else None
    second = tokens[1] if len(tokens) > 1 else first
    return target, source, first, second


def _parse_cross_group_758_blocks(
    body: bytes,
) -> tuple[int | None, int | None, list[str], list[tuple[str | None, int | None]]]:
    """Shared decoder for repeated body.field2 invitee blocks."""
    target = source = None
    entries: list[tuple[str | None, int | None]] = []
    i = 0
    while i < len(body):
        tag = body[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            val, i = read_varint(body, i)
            if fn == 1:
                target = val
        elif wt == 2:
            ln, i = read_varint(body, i)
            chunk = body[i : i + ln]
            i += ln
            if fn == 2:
                tok = src = None
                j = 0
                while j < len(chunk):
                    btag = chunk[j]
                    j += 1
                    bfn = btag >> 3
                    bwt = btag & 7
                    if bwt == 0:
                        bval, j = read_varint(chunk, j)
                        if bfn == 2:
                            src = bval
                    elif bwt == 2:
                        bln, j = read_varint(chunk, j)
                        bchunk = chunk[j : j + bln]
                        j += bln
                        if bfn == 1:
                            tok = bchunk.decode("utf-8", errors="replace")
                entries.append((tok, src))
                if src is not None and source is None:
                    source = src
        else:
            break
    tokens = [tok for tok, _src in entries if tok]
    return target, source, tokens, entries


def patch_cross_group_758_pb(
    pb_hex: str,
    *,
    target_group_id: int,
    source_group_id: int,
    invitee_token: str,
    source_context_token: str | None = None,
    invitee_tokens: list[str] | None = None,
) -> str:
    """Rebuild 758 from the proven field layout instead of splicing captures."""
    del pb_hex
    del source_context_token
    tokens = list(invitee_tokens or [])
    if invitee_token:
        tokens.append(invitee_token)
    return build_cross_group_758_pb(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        invitee_tokens=tokens,
    )


def patch_invite_758_pb(
    pb_hex: str,
    *,
    group_code: int,
    invitee_uin: int | None = None,
    invite_token: str | None = None,
    pull: bool = False,
) -> str:
    """Rewrite 0x758 invite PB with custom group/token.

    Default (pull=False): consent invite — no invitee uin in packet (matches QQ UI).
    pull=True: admin direct add — invitee uin goes in block.field2.
    """
    data = bytes.fromhex(normalize_hex(pb_hex))
    body_bytes = extract_field_bytes(data, 4)
    if not body_bytes:
        raise ValueError("PB is not a 0x758-style invite packet (missing field4 body)")
    gc, token, invitee = parse_invite_758_body(body_bytes)
    if invite_token is None:
        if not token:
            raise ValueError("cannot detect invite token from source packet")
        invite_token = token
    if pull and invitee_uin is not None and invitee is not None:
        return patch_758_pull_template(
            pb_hex,
            group_code=int(group_code),
            invitee_uin=int(invitee_uin),
            invite_token=invite_token,
        )
    return build_invite_758_pb(
        group_code=int(group_code),
        invite_token=invite_token,
        invitee_uin=int(invitee_uin) if pull and invitee_uin is not None else None,
        pull=pull,
    )


def patch_758_pull_template(
    pb_hex: str,
    *,
    group_code: int,
    invitee_uin: int,
    invite_token: str,
) -> str:
    """Patch captured 59-byte pull template in-place (preserve QQ wire layout)."""
    import re

    data = bytearray(bytes.fromhex(normalize_hex(pb_hex)))
    body_bytes = extract_field_bytes(data, 4)
    if not body_bytes:
        raise ValueError("missing field4 body")
    gc_old, tok_old, inv_old = parse_invite_758_body(body_bytes)

    if gc_old is not None and int(gc_old) != int(group_code):
        old_gc = encode_varint(int(gc_old))
        new_gc = encode_varint(int(group_code))
        idx = data.find(old_gc)
        if idx >= 0:
            data[idx : idx + len(old_gc)] = new_gc

    if tok_old and invite_token:
        old_b = tok_old.encode("utf-8")
        new_b = invite_token.encode("utf-8")
        if len(old_b) != len(new_b):
            raise ValueError("invite token length mismatch for in-place patch")
        idx = data.find(old_b)
        if idx < 0:
            m = re.search(rb"u_[A-Za-z0-9_-]{16,}", bytes(data))
            if not m:
                raise ValueError("cannot locate invite token in template")
            old_b = m.group(0)
            new_b = invite_token.encode("utf-8")
            if len(old_b) != len(new_b):
                raise ValueError("invite token length mismatch for in-place patch")
            idx = m.start()
        data[idx : idx + len(old_b)] = new_b

    if inv_old is not None and int(inv_old) != int(invitee_uin):
        old_u = encode_varint(int(inv_old))
        new_u = encode_varint(int(invitee_uin))
        idx = data.find(old_u)
        if idx >= 0:
            data[idx : idx + len(old_u)] = new_u

    return bytes(data).hex()


def extract_field_bytes(data: bytes, field_num: int) -> bytes | None:
    i = 0
    while i < len(data):
        tag = data[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            _, i = read_varint(data, i)
        elif wt == 2:
            ln, i = read_varint(data, i)
            chunk = data[i : i + ln]
            i += ln
            if fn == field_num:
                return chunk
        elif wt == 5:
            i += 4
        elif wt == 1:
            i += 8
        else:
            break
    return None


def replace_field_bytes(data: bytes, field_num: int, new_content: bytes) -> bytes:
    """Replace one length-delimited top-level field; re-encode length prefix."""
    out = bytearray()
    i = 0
    replaced = False
    while i < len(data):
        tag = data[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            _, j = read_varint(data, i)
            out.append(tag)
            out.extend(data[i:j])
            i = j
        elif wt == 2:
            ln, j = read_varint(data, i)
            chunk = data[j : j + ln]
            i = j + ln
            if fn == field_num:
                out.extend(encode_field_bytes(field_num, new_content))
                replaced = True
            else:
                out.append(tag)
                out.extend(encode_varint(ln))
                out.extend(chunk)
        elif wt == 5:
            out.extend(data[i - 1 : i + 4])
            i += 4
        elif wt == 1:
            out.extend(data[i - 1 : i + 8])
            i += 8
        else:
            break
    if not replaced:
        out.extend(encode_field_bytes(field_num, new_content))
    return bytes(out)


def replace_field_varint(data: bytes, field_num: int, new_value: int) -> bytes:
    """Replace the first varint field_num; re-encode so length may change."""
    out = bytearray()
    i = 0
    replaced = False
    while i < len(data):
        tag = data[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            _val, j = read_varint(data, i)
            if fn == field_num and not replaced:
                out.extend(encode_field_varint(field_num, int(new_value)))
                replaced = True
            else:
                out.append(tag)
                out.extend(data[i:j])
            i = j
        elif wt == 2:
            ln, j = read_varint(data, i)
            chunk = data[j : j + ln]
            i = j + ln
            out.append(tag)
            out.extend(encode_varint(ln))
            out.extend(chunk)
        elif wt == 5:
            out.extend(data[i - 1 : i + 4])
            i += 4
        elif wt == 1:
            out.extend(data[i - 1 : i + 8])
            i += 8
        else:
            out.extend(data[i - 1 :])
            break
    if not replaced:
        out.extend(encode_field_varint(field_num, int(new_value)))
    return bytes(out)


def build_cross_group_fe1_pb(tokens: list[str]) -> str:
    """0xfe1_8 selection sync from capture-1786860477114.

    SEND layout (seq 9957014 41B / seq 9957025 and 9957134 276B):
      top.field1=0xfe1 top.field2=8 top.field4=body top.field12=0
      body.field1 = repeated u_ tokens
      body.field3 = {field1=101, field3=2}

    1 token -> 41B; 10 tokens -> 276B. Same repeated field1 for any N.
    """
    cleaned = [t for t in tokens if t]
    if not cleaned:
        raise ValueError("fe1 requires at least one token")
    body_fields: dict[int, list[Any]] = {
        1: [tok.encode("utf-8") for tok in cleaned],
        3: [{1: [101], 3: [2]}],
    }
    top_fields = {
        1: [0xFE1],
        2: [8],
        4: [encode_pb_message(body_fields)],
        12: [0],
    }
    return encode_pb_message(top_fields).hex()


def parse_fe1_tokens(hex_data: str) -> list[str]:
    """Return body.field1 tokens from a 0xfe1_8 SEND."""
    if not hex_data:
        return []
    data = bytes.fromhex(normalize_hex(hex_data))
    body = extract_field_bytes(data, 4) or data
    fields = decode_pb_message(body)
    out: list[str] = []
    for val in fields.get(1) or []:
        if isinstance(val, bytes) and val.startswith(b"u_"):
            out.append(val.decode("utf-8", errors="replace"))
        elif isinstance(val, dict):
            inner = _first(val, 1)
            if isinstance(inner, bytes) and inner.startswith(b"u_"):
                out.append(inner.decode("utf-8", errors="replace"))
    return out


def read_varint(data: bytes, i: int) -> tuple[int, int]:
    val = 0
    shift = 0
    while i < len(data):
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, i


def decode_pb_message(data: bytes) -> dict[int, list[Any]]:
    """Return field_no -> list of values (int | bytes | nested dict)."""
    out: dict[int, list[Any]] = {}
    i = 0
    while i < len(data):
        tag = data[i]
        i += 1
        fn = tag >> 3
        wt = tag & 7
        if wt == 0:
            val, i = read_varint(data, i)
            out.setdefault(fn, []).append(val)
        elif wt == 2:
            ln, i = read_varint(data, i)
            chunk = data[i : i + ln]
            i += ln
            val: Any = chunk
            if len(chunk) >= 2 and (chunk[0] & 7) in (0, 2):
                try:
                    val = decode_pb_message(chunk)
                except Exception:
                    val = chunk
            out.setdefault(fn, []).append(val)
        elif wt == 5:
            if i + 4 > len(data):
                break
            val = int.from_bytes(data[i : i + 4], "little")
            i += 4
            out.setdefault(fn, []).append(val)
        elif wt == 1:
            if i + 8 > len(data):
                break
            val = int.from_bytes(data[i : i + 8], "little")
            i += 8
            out.setdefault(fn, []).append(val)
        else:
            break
    return out


def _first(fields: dict[int, list[Any]], num: int, default: Any = None) -> Any:
    vals = fields.get(num) or []
    return vals[0] if vals else default


def _as_text(value: Any) -> str | None:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    if isinstance(value, dict):
        inner = _first(value, 1)
        if isinstance(inner, bytes):
            try:
                return inner.decode("utf-8")
            except UnicodeDecodeError:
                return inner.hex()
    return None


def parse_cmd_meta(cmd: str) -> tuple[int | None, int | None]:
    m = re.search(r"0x([0-9a-fA-F]+)_(\d+)", cmd or "")
    if not m:
        return None, None
    return int(m.group(1), 16), int(m.group(2))


@dataclass
class ParsedPacket:
    cmd: str
    pb_hex: str
    direction: str = ""
    oidb: int | None = None
    subcmd: int | None = None
    group_code: int | None = None
    invite_token: str | None = None
    invitee_uin: int | None = None
    fields: dict[int, list[Any]] = field(default_factory=dict)
    raw_log: str = ""

    def summary_lines(self) -> list[str]:
        lines = [
            f"direction: {self.direction or '(unknown)'}",
            f"cmd: {self.cmd}",
            f"pb length: {len(self.pb_hex)//2} bytes",
        ]
        if self.oidb is not None:
            lines.append(f"OIDB: 0x{self.oidb:x} ({self.oidb})")
        if self.subcmd is not None:
            lines.append(f"subcmd: {self.subcmd}")
        if self.group_code is not None:
            lines.append(f"group internal code: {self.group_code} (0x{self.group_code:x})")
        if self.invite_token:
            lines.append(f"invite token: {describe_token(self.invite_token)}")
        if self.invitee_uin is not None:
            lines.append(f"invitee uin: {self.invitee_uin}")
        return lines

    def summary_text(self) -> str:
        return "\n".join(self.summary_lines())


def is_invite_758_packet(pkt: ParsedPacket) -> bool:
    body = _first(pkt.fields, 4)
    if not isinstance(body, dict):
        try:
            body = _first(decode_pb_message(bytes.fromhex(normalize_hex(pkt.pb_hex))), 4)
        except ValueError:
            return False
    return isinstance(body, dict) and isinstance(_first(body, 2), dict)


def apply_custom_params(
    pkt: ParsedPacket,
    *,
    group_code: int | None = None,
    invitee_uin: int | None = None,
    invite_token: str | None = None,
    pull: bool = False,
) -> ParsedPacket:
    if not is_invite_758_packet(pkt):
        raise ValueError(
            f"当前仅支持 0x758 邀请包重写（field4.body.field1=群内部码, field2.field1=邀请 token）。"
            f" cmd={pkt.cmd}"
        )
    gc = group_code if group_code is not None else pkt.group_code
    iu = invitee_uin if invitee_uin is not None else pkt.invitee_uin
    tk = invite_token if invite_token is not None else pkt.invite_token
    if gc is None:
        raise ValueError("群内部码不能为空")
    if pull and iu is None:
        raise ValueError("直接拉群模式需要被邀请人 QQ")
    new_hex = patch_invite_758_pb(
        pkt.pb_hex, group_code=gc, invitee_uin=iu, invite_token=tk, pull=pull
    )
    new_pkt = decode_oidb_packet(pkt.cmd, new_hex)
    new_pkt.direction = pkt.direction
    new_pkt.raw_log = pkt.raw_log
    return new_pkt


def decode_invite_body(body: dict[int, list[Any]]) -> tuple[int | None, str | None, int | None]:
    group_code = _first(body, 1)
    if not isinstance(group_code, int):
        group_code = None
    token = None
    invitee = None
    block = _first(body, 2)
    if isinstance(block, dict):
        direct_token = _as_text(_first(block, 1))
        if direct_token and direct_token.startswith("u_"):
            token = direct_token
        for val in block.get(2) or []:
            if isinstance(val, int):
                invitee = val
            elif isinstance(val, dict):
                token = _as_text(_first(val, 1)) or token
            elif isinstance(val, bytes):
                token = _as_text(val) or token
    elif isinstance(block, bytes):
        token = _as_text(block)
    return group_code, token, invitee


def parse_758_recv_status(hex_data: str) -> tuple[int | None, bool]:
    """Parse 0x758 RECV: field3==0 means accepted; 1289 = stale/consumed token."""
    if not hex_data:
        return None, False
    try:
        fields = decode_pb_message(bytes.fromhex(normalize_hex(hex_data)))
    except ValueError:
        return None, False
    code = _first(fields, 3)
    if not isinstance(code, int):
        return None, False
    return code, code == 0


def decode_oidb_packet(cmd: str, pb_hex: str) -> ParsedPacket:
    pb_hex = normalize_hex(pb_hex)
    data = bytes.fromhex(pb_hex)
    fields = decode_pb_message(data)
    oidb_from_cmd, sub_from_cmd = parse_cmd_meta(cmd)
    oidb = _first(fields, 1) if isinstance(_first(fields, 1), int) else oidb_from_cmd
    subcmd = _first(fields, 2) if isinstance(_first(fields, 2), int) else sub_from_cmd
    body_bytes = extract_field_bytes(data, 4)
    group_code = token = invitee = None
    if body_bytes:
        group_code, token, invitee = parse_invite_758_body(body_bytes)
    else:
        body = _first(fields, 4)
        if isinstance(body, dict):
            group_code, token, invitee = decode_invite_body(body)
    return ParsedPacket(
        cmd=cmd.strip(),
        pb_hex=pb_hex,
        oidb=oidb if isinstance(oidb, int) else oidb_from_cmd,
        subcmd=subcmd if isinstance(subcmd, int) else sub_from_cmd,
        group_code=group_code,
        invite_token=token,
        invitee_uin=invitee,
        fields=fields,
    )


def parse_log_line(text: str) -> ParsedPacket:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("paste log line is empty")
    m = LOG_CMD_PB_RE.search(raw)
    if not m:
        raise ValueError("cannot find 'cmd: ..., pb: ...' in pasted text")
    cmd = m.group(1).strip()
    pb_hex = normalize_hex(m.group(2))
    pkt = decode_oidb_packet(cmd, pb_hex)
    pkt.raw_log = raw
    dm = LOG_DIR_RE.search(raw)
    if dm:
        pkt.direction = dm.group(1).lower()
    return pkt


def analyze_oidb_packet(cmd: str, pb_hex: str) -> str:
    pkt = decode_oidb_packet(cmd, pb_hex)
    lines = pkt.summary_lines() + ["", "top-level protobuf fields:"]
    for fn in sorted(pkt.fields.keys()):
        for val in pkt.fields[fn]:
            if isinstance(val, int):
                lines.append(f"  field {fn} varint = {val} (0x{val:x})")
            elif isinstance(val, bytes):
                lines.append(f"  field {fn} bytes = {val.hex()}")
            elif isinstance(val, dict):
                lines.append(f"  field {fn} message ({len(val)} subfields)")
    if cmd.startswith("OidbSvcTrpcTcp.0x758"):
        lines.extend(
            [
                "",
                "0x758 invite packet:",
                "  field4.body.field1 = group internal code",
                "  field4.body.field2.field1 = invite token string",
                "  field4.body.field2.field2 = invitee uin (pull: varint beside token)",
                "  field4.body.field3 = empty (consent invite only; absent in pull)",
            ]
        )
    return "\n".join(lines)


def build_pack_payload(cmd: str, pb_hex: str, fmt: str) -> str:
    cmd = (cmd or "").strip()
    pb_hex = normalize_hex(pb_hex)
    if fmt == "hex_only":
        return pb_hex
    if fmt == "pipe":
        return f"{cmd}|{pb_hex}"
    if fmt == "newline":
        return f"{cmd}\n{pb_hex}"
    if fmt == "json":
        return json.dumps({"cmd": cmd, "pb": pb_hex}, ensure_ascii=False, separators=(",", ":"))
    if fmt == "json_cmd_data":
        return json.dumps({"cmd": cmd, "data": pb_hex}, ensure_ascii=False, separators=(",", ":"))
    if fmt == "cmd_space_hex":
        return f"{cmd} {pb_hex}"
    raise ValueError(f"unknown pack format: {fmt}")


PACK_FORMATS: dict[str, str] = {
    "json": 'JSON {"cmd","pb"}',
    "json_cmd_data": 'JSON {"cmd","data"}',
    "pipe": "cmd|hex",
    "newline": "cmd + newline + hex",
    "cmd_space_hex": "cmd space hex",
    "hex_only": "pb hex only",
}

SAMPLE_LOG = (
    "2026-8-15 19:47:33 | \u3010send\u3011[PB\u6570\u636e] cmd: OidbSvcTrpcTcp.0x758_1, pb: "
    "08d80e1001223408c6bad2800312200a18755f565152366b5344445f6f43656b6754784b6562473567"
    "10b7da89e3021a00200028003200380050006000"
)
