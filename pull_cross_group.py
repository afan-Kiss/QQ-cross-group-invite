# -*- coding: utf-8 -*-
"""Cross-group invite: pull members from another group into target group (0x758 95B)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from capture_utils import (
    DEFAULT_CAPTURE_DIR,
    build_fe7_group_list,
    build_fe7_single_lookup,
    extract_group_token_from_fe7,
    extract_token_for_uin,
    find_cross_group_758_template,
    find_cross_group_chain_templates,
    find_fe1_multi_select_template,
    find_fe7_pagination_templates,
    find_fe7_pagination_templates_generic,
    find_fe7_single_template,
    find_permanent_uid_from_capture,
    find_source_context_token,
    lookup_token_owner,
    parse_fe7_token_map,
    patch_group_code_in_hex,
    patch_uid_in_fe7_hex,
    scan_capture_fe7_token,
    token_owner_mismatch,
    U_TOKEN_RE,
)
from myqq_api import find_friend_uid_by_qq, load_cfg, save_cfg, send_napcat_packet
from pb_utils import (
    build_cross_group_758_pb,
    decode_oidb_packet,
    parse_758_recv_status,
    patch_cross_group_758_pb,
)

CMD_758 = "OidbSvcTrpcTcp.0x758_1"
CMD_FE7 = "OidbSvcTrpcTcp.0xfe7_4"
CMD_FE1 = "OidbSvcTrpcTcp.0xfe1_8"
PACKET_SLEEP = 0.15
FE7_SLEEP = 0.12


def _cfg_int(cfg: dict, *keys: str) -> int | None:
    for k in keys:
        raw = str(cfg.get(k) or "").strip()
        if raw.isdigit():
            return int(raw)
    return None


def _parse_api_response(raw: str) -> dict:
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    inner = outer.get("data") if isinstance(outer, dict) else None
    if isinstance(inner, dict) and "data" in inner:
        return inner
    return outer if isinstance(outer, dict) else {"raw": raw}


def _response_ok(resp: dict) -> bool:
    data = resp.get("data")
    if isinstance(data, str) and len(data) >= 8:
        code, ok = parse_758_recv_status(data)
        if code is not None:
            return ok
        if len(data) >= 200:
            return True
    return resp.get("status") == "ok" and resp.get("retcode") == 0 and bool(data)


def _rsp_hex(resp: dict) -> str:
    data = resp.get("data")
    return data if isinstance(data, str) else ""


def resolve_capture_dir(cfg: dict) -> Path:
    raw = str(cfg.get("capture_dir") or "").strip()
    return Path(raw) if raw else DEFAULT_CAPTURE_DIR


def resolve_cross_targets(cfg: dict) -> tuple[int, int, int]:
    target = _cfg_int(cfg, "target_group_id")
    source = _cfg_int(cfg, "source_group_id")
    invitee = _cfg_int(cfg, "invitee_qq", "friend_qq")
    if target is None:
        raise RuntimeError("config.json missing target_group_id (target group peerUid)")
    if source is None:
        raise RuntimeError("config.json missing source_group_id (source group peerUid)")
    if invitee is None:
        raise RuntimeError("config.json missing invitee_qq")
    return target, source, invitee


def _send_packet(cmd: str, hex_data: str, *, label: str | None = None) -> dict:
    if label:
        print(f"  send: {label} ({len(hex_data) // 2} bytes)")
    raw = send_napcat_packet(cmd, hex_data, wait_rsp=True)
    return _parse_api_response(raw)


def _send_fe7(hex_data: str, *, label: str = "fe7_4") -> str:
    resp = _send_packet(CMD_FE7, hex_data, label=label)
    time.sleep(FE7_SLEEP)
    return _rsp_hex(resp)


def _resolve_nt_uid(capture_dir: Path, group_id: int, invitee: int) -> str | None:
    uid = find_permanent_uid_from_capture(capture_dir, group_id, invitee)
    if uid:
        return uid
    return find_friend_uid_by_qq(invitee, no_cache=True)


def query_invitee_token(
    capture_dir: Path, source_group_id: int, invitee: int
) -> str | None:
    """Resolve invitee u_ token from source group fe7 list."""
    uid = _resolve_nt_uid(capture_dir, source_group_id, invitee)
    if uid:
        single_tpl = find_fe7_single_template(capture_dir, source_group_id)
        if single_tpl:
            fe7_hex = patch_uid_in_fe7_hex(single_tpl, uid, source_group_id)
        else:
            fe7_hex = build_fe7_single_lookup(source_group_id, uid)
        rsp = _send_fe7(fe7_hex, label="fe7 source single lookup")
        token = extract_token_for_uin(rsp, invitee)
        if token:
            print(f"invitee token from fe7 single: {token}")
            return token

    pages = _fe7_list_pages(capture_dir, source_group_id)
    if pages:
        merged: dict[int, str] = {}
        for i, page_hex in enumerate(pages, 1):
            patched = patch_group_code_in_hex(page_hex, source_group_id)
            rsp = _send_fe7(patched, label=f"fe7 source page {i}/{len(pages)}")
            if rsp:
                merged.update(parse_fe7_token_map(rsp))
        token = merged.get(invitee)
        if token:
            print(f"invitee token from fe7 pages: {token}")
            return token

    token = scan_capture_fe7_token(capture_dir, invitee)
    if token:
        print(f"invitee token from capture scan: {token}")
    return token


def _fe7_list_pages(capture_dir: Path, source_group_id: int) -> list[str]:
    """Captured list pages, or a built 96-byte 0xfe7_4 that does not need packet logs."""
    pages = find_fe7_pagination_templates(capture_dir, source_group_id)
    if not pages:
        pages = find_fe7_pagination_templates_generic(capture_dir)
    if not pages:
        pages = [build_fe7_group_list(source_group_id)]
        print("no fe7 templates in capture; using built group-list packet")
    return pages


def probe_source_group_fe7(
    capture_dir: Path, source_group_id: int, *, max_pages: int = 8
) -> tuple[dict[int, str], str, str | None]:
    """Live 0xfe7_4 against the source group: member tokens + group context token."""
    pages = _fe7_list_pages(capture_dir, source_group_id)
    merged: dict[int, str] = {}
    context = ""
    last_rsp: str | None = None
    for i, page_hex in enumerate(pages, 1):
        patched = patch_group_code_in_hex(page_hex, source_group_id)
        rsp = _send_fe7(patched, label=f"fe7 source page {i}")
        if rsp:
            last_rsp = rsp
            merged.update(parse_fe7_token_map(rsp))
            if not context:
                context = extract_group_token_from_fe7(rsp, source_group_id) or ""
        if i >= max_pages:
            break
    return merged, context, last_rsp


def fetch_source_context_token_live(
    capture_dir: Path, source_group_id: int
) -> str | None:
    """Same live fe7 path used when loading members; does not need a full picker chain."""
    try:
        _tokens, context, last_rsp = probe_source_group_fe7(
            capture_dir, source_group_id, max_pages=4
        )
    except Exception as exc:
        print(f"live source fe7 failed: {exc}")
        return None
    if context:
        return context
    if last_rsp:
        return extract_group_token_from_fe7(last_rsp, source_group_id)
    return None


def query_source_context_token(
    capture_dir: Path, source_group_id: int, *, live_rsp: str | None = None
) -> str | None:
    """Source group context token (first entry in cross-group 758)."""
    if live_rsp:
        tok = extract_group_token_from_fe7(live_rsp, source_group_id)
        if tok:
            print(f"source context token from live fe7: {tok}")
            return tok
    tok = find_source_context_token(capture_dir, source_group_id)
    if tok:
        print(f"source context token from capture: {tok}")
        return tok
    return fetch_source_context_token_live(capture_dir, source_group_id)


def patch_fe1_token_list(hex_data: str, tokens: list[str]) -> str:
    """Replace u_ tokens in fe1_8 multi-select template preserving count."""
    data = bytearray(bytes.fromhex(hex_data))
    matches = list(U_TOKEN_RE.finditer(bytes(data)))
    if not matches:
        raise ValueError("fe1 template has no u_ tokens")
    if len(tokens) != len(matches):
        raise ValueError(
            f"fe1 token count mismatch: template has {len(matches)}, got {len(tokens)}"
        )
    offset = 0
    for m, tok in zip(matches, tokens):
        old = m.group(0)
        new = tok.encode("utf-8")
        if len(old) != len(new):
            raise ValueError(f"token length mismatch for fe1 patch: {old!r} vs {tok!r}")
        start = m.start() + offset
        data[start : start + len(old)] = new
    return bytes(data).hex()


def open_cross_group_picker(
    capture_dir: Path, target_group_id: int, source_group_id: int
) -> str | None:
    """Replay cross-group picker open chain; return first fe7 rsp for context token.

    If the captured picker chain is incomplete, fall back to the same live fe7
    pages used to load source-group members.
    """
    chain = find_cross_group_chain_templates(capture_dir)
    live_fe7 = None
    if chain:
        print(f"open cross-group picker ({len(chain)} packets)...")
        for cmd, tpl in chain:
            label = cmd.rsplit(".", 1)[-1]
            hex_data = patch_group_code_in_hex(tpl, target_group_id)
            if "0xfe7_4" in cmd:
                hex_data = patch_group_code_in_hex(hex_data, source_group_id)
            resp = _send_packet(cmd, hex_data, label=label)
            rsp = _rsp_hex(resp)
            if "0xfe7_4" in cmd and rsp:
                live_fe7 = rsp
            time.sleep(PACKET_SLEEP)
    else:
        print("no complete picker chain in capture; using live source-group fe7")
    if live_fe7:
        return live_fe7
    _tokens, _ctx, last_rsp = probe_source_group_fe7(capture_dir, source_group_id)
    return last_rsp


def sync_fe1_selection(capture_dir: Path, tokens: list[str]) -> bool:
    """Confirm selection via fe1_8 multi-token sync (optional pre-758 step)."""
    tpl = find_fe1_multi_select_template(capture_dir)
    if not tpl:
        return False
    try:
        hex_data = patch_fe1_token_list(tpl, tokens)
    except ValueError as exc:
        print(f"fe1 selection sync skipped: {exc}")
        return False
    _send_packet(CMD_FE1, hex_data, label="fe1_8 selection sync")
    time.sleep(PACKET_SLEEP)
    return True


def send_cross_group_invite(
    *,
    target_group_id: int,
    source_group_id: int,
    source_context_token: str,
    invitee_token: str,
    capture_dir: Path,
) -> tuple[bool, dict]:
    tpl = find_cross_group_758_template(capture_dir, target_group_id)
    if tpl:
        pb_hex = patch_cross_group_758_pb(
            tpl,
            target_group_id=target_group_id,
            source_group_id=source_group_id,
            source_context_token=source_context_token,
            invitee_token=invitee_token,
        )
    else:
        pb_hex = build_cross_group_758_pb(
            target_group_id=target_group_id,
            source_group_id=source_group_id,
            source_context_token=source_context_token,
            invitee_token=invitee_token,
        )

    pkt = decode_oidb_packet(CMD_758, pb_hex)
    print("\n--- cross-group 758 ---")
    print(pkt.summary_text())
    print(f"PB ({len(pb_hex) // 2} bytes)")

    resp = _send_packet(CMD_758, pb_hex, label="758 cross-group invite")
    ok = _response_ok(resp)
    if not ok:
        data = _rsp_hex(resp)
        if data:
            code, _ = parse_758_recv_status(data)
            print(f"758 recv code={code}")
    return ok, resp


def run(cfg: dict | None = None) -> int:
    cfg = cfg or load_cfg()
    capture_dir = resolve_capture_dir(cfg)
    target_group_id, source_group_id, invitee = resolve_cross_targets(cfg)

    print("=== cross-group invite ===")
    print(f"target_group_id: {target_group_id}")
    print(f"source_group_id: {source_group_id}")
    print(f"invitee_qq: {invitee}")
    print(f"capture_dir: {capture_dir}")

    live_fe7 = open_cross_group_picker(capture_dir, target_group_id, source_group_id)

    invitee_token = query_invitee_token(capture_dir, source_group_id, invitee)
    if not invitee_token:
        raise RuntimeError(
            f"cannot resolve invitee token for QQ {invitee} in source group {source_group_id}"
        )
    wrong = token_owner_mismatch(capture_dir, invitee_token, invitee)
    if wrong is not None:
        raise RuntimeError(
            f"token {invitee_token} belongs to QQ {wrong}, not {invitee}"
        )

    context_token = query_source_context_token(
        capture_dir, source_group_id, live_rsp=live_fe7
    )
    if not context_token:
        raise RuntimeError(
            f"cannot resolve source context token for group {source_group_id}. "
            "Capture a manual cross-group invite for this source group first."
        )
    if context_token == invitee_token:
        raise RuntimeError("source context token equals invitee token")

    sync_fe1_selection(capture_dir, [context_token, invitee_token])

    ok, resp = send_cross_group_invite(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        source_context_token=context_token,
        invitee_token=invitee_token,
        capture_dir=capture_dir,
    )

    print("\n--- API response ---")
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    if ok:
        cfg["cross_group_last_ok"] = {
            "target_group_id": target_group_id,
            "source_group_id": source_group_id,
            "invitee_qq": invitee,
            "invitee_token": invitee_token,
            "source_context_token": context_token,
        }
        save_cfg(cfg)
        print("\nOK: cross-group invite accepted")
        return 0
    print("\nfailed: server rejected cross-group 758")
    return 1


def main() -> int:
    try:
        return run()
    except RuntimeError as exc:
        print(f"\nerror: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
