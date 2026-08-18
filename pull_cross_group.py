# -*- coding: utf-8 -*-
"""Cross-group invite: pull members from another group into target group (0x758 95B)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_utils import (
    DEFAULT_CAPTURE_DIR,
    build_fe7_group_list,
    build_fe7_single_lookup,
    extract_group_token_from_fe7,
    extract_token_for_uin,
    find_cross_group_chain_templates,
    find_fe1_multi_select_template,
    find_fe7_pagination_templates,
    find_fe7_pagination_templates_generic,
    find_fe7_single_template,
    find_permanent_uid_from_capture,
    find_source_context_token,
    lookup_token_owner,
    missing_picker_templates,
    parse_fe7_token_map,
    patch_88d_111_target,
    patch_group_code_in_hex,
    patch_uid_in_fe7_hex,
    scan_capture_fe7_token,
    token_owner_mismatch,
    U_TOKEN_RE,
)
from myqq_api import find_friend_uid_by_qq, load_cfg, onebot_action, save_cfg, send_napcat_packet
from pb_utils import (
    build_cross_group_758_pb,
    describe_token,
    parse_758_recv_status,
    parse_cross_group_758_entries,
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


def protocol_log(stage: str, **fields: object) -> None:
    parts = [f"[{stage}]"]
    for key, val in fields.items():
        if val is None:
            continue
        parts.append(f"{key}={val}")
    print(" ".join(parts))


def _parse_api_response(raw: str) -> dict:
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    inner = outer.get("data") if isinstance(outer, dict) else None
    if isinstance(inner, dict) and "data" in inner:
        merged = dict(inner)
        if isinstance(outer, dict) and "code" in outer and "code" not in merged:
            merged["code"] = outer.get("code")
        return merged
    return outer if isinstance(outer, dict) else {"raw": raw}


def _api_send_failed(resp: dict) -> str:
    if not isinstance(resp, dict):
        return "send_packet 响应无法解析"
    code = resp.get("code")
    if code not in (None, 0, "0"):
        return str(resp.get("message") or resp.get("msg") or f"send_packet code={code}")
    status = str(resp.get("status") or "").lower()
    retcode = resp.get("retcode")
    if status in {"failed", "error"}:
        return str(resp.get("message") or resp.get("wording") or "send_packet status=failed")
    if retcode not in (None, 0, "0") and status != "ok":
        return str(resp.get("message") or resp.get("wording") or f"send_packet retcode={retcode}")
    return ""


def _response_ok(resp: dict) -> bool:
    """Only field3==0 on the 0x758 RECV body counts as protocol success."""
    if not isinstance(resp, dict):
        return False
    if _api_send_failed(resp):
        return False
    data = resp.get("data")
    if not isinstance(data, str) or len(data) < 8:
        return False
    code, ok = parse_758_recv_status(data)
    if code is None:
        return False
    return ok


def _rsp_hex(resp: dict) -> str:
    data = resp.get("data")
    return data if isinstance(data, str) else ""


def resolve_capture_dir(cfg: dict) -> Path:
    raw = str(cfg.get("capture_dir") or "").strip()
    repo = Path(__file__).resolve().parent.parent
    candidates = [
        Path(raw) if raw else None,
        DEFAULT_CAPTURE_DIR,
        repo / "NapCatQQ-src" / "NapCat.Framework" / "logs" / "packet_capture",
        repo / "NapCatQQ-src" / "NapCat.Shell" / "logs" / "packet_capture",
    ]
    seen: set[str] = set()
    for path in candidates:
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_dir() and any(path.glob("capture-*.log")):
            return path
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


def _send_packet(cmd: str, hex_data: str, *, label: str | None = None, stage: str = "") -> dict:
    send_len = len(hex_data) // 2
    if label:
        print(f"  send: {label} ({send_len} bytes)")
    raw = send_napcat_packet(cmd, hex_data, wait_rsp=True)
    resp = _parse_api_response(raw)
    api_err = _api_send_failed(resp)
    rsp = _rsp_hex(resp)
    code, proto_ok = parse_758_recv_status(rsp) if rsp else (None, False)
    protocol_log(
        stage or (label or cmd.rsplit(".", 1)[-1]),
        cmd=cmd.rsplit(".", 1)[-1],
        send_len=send_len,
        api_err=api_err or "none",
        recv_len=len(rsp) // 2 if rsp else 0,
        proto_code=code,
        proto_ok=proto_ok,
    )
    return resp


def _send_fe7(hex_data: str, *, label: str = "fe7_4") -> str:
    resp = _send_packet(CMD_FE7, hex_data, label=label, stage="SOURCE_FE7")
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
            print(f"invitee token from fe7 single: {describe_token(token)}")
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
            print(f"invitee token from fe7 pages: {describe_token(token)}")
            return token

    token = scan_capture_fe7_token(capture_dir, invitee)
    if token:
        print(f"invitee token from capture scan: {describe_token(token)}")
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
    """Diagnostic unpaired FE7 uid only. Not a 758 invitee/context block."""
    if live_rsp:
        tok = extract_group_token_from_fe7(live_rsp, source_group_id)
        if tok:
            print(f"unpaired fe7 token: {describe_token(tok)}")
            return tok
    tok = find_source_context_token(capture_dir, source_group_id)
    if tok:
        print(f"token from capture 758: {describe_token(tok)}")
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
            raise ValueError(
                "token length mismatch for fe1 patch: "
                f"{describe_token(old.decode('utf-8', errors='replace'))} vs {describe_token(tok)}"
            )
        start = m.start() + offset
        data[start : start + len(old)] = new
    return bytes(data).hex()


def open_cross_group_picker(
    capture_dir: Path, target_group_id: int, source_group_id: int
) -> str | None:
    """Replay the required picker session. Incomplete capture must not send 758."""
    missing = missing_picker_templates(capture_dir)
    if missing:
        protocol_log(
            "PICKER_SESSION",
            result="missing_templates",
            missing=",".join(missing),
        )
        return None
    chain = find_cross_group_chain_templates(capture_dir)
    if not chain:
        protocol_log("PICKER_SESSION", result="empty_chain")
        return None
    live_fe7 = None
    print(f"open cross-group picker ({len(chain)} packets)...")
    for cmd, tpl in chain:
        label = cmd.rsplit(".", 1)[-1]
        stage = "PICKER_FE7"
        if "0x88d_14" in cmd:
            stage = "PICKER_88D"
            hex_data = tpl
        elif "0x88d_111" in cmd:
            stage = "PICKER_88D"
            hex_data = patch_88d_111_target(tpl, target_group_id)
        elif "0x11ec_1" in cmd:
            stage = "PICKER_11EC"
            hex_data = patch_group_code_in_hex(tpl, target_group_id)
        elif "0xfe7_4" in cmd:
            hex_data = patch_group_code_in_hex(tpl, source_group_id)
        else:
            hex_data = tpl
        resp = _send_packet(cmd, hex_data, label=label, stage=stage)
        if _api_send_failed(resp):
            protocol_log("PICKER_SESSION", result="send_failed", cmd=label)
            return None
        rsp = _rsp_hex(resp)
        if "0xfe7_4" in cmd and rsp:
            live_fe7 = rsp
        time.sleep(PACKET_SLEEP)
    protocol_log("PICKER_SESSION", result="ok", fe7_rsp=bool(live_fe7))
    return live_fe7 or "ok"


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
    invitee_token: str,
    capture_dir: Path,
    source_context_token: str | None = None,
) -> tuple[bool, dict]:
    del source_context_token
    del capture_dir
    pb_hex = build_cross_group_758_pb(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        invitee_tokens=[invitee_token],
    )
    body = bytes.fromhex(pb_hex)
    from pb_utils import extract_field_bytes

    parsed = parse_cross_group_758_entries(extract_field_bytes(body, 4) or b"")
    protocol_log(
        "INVITE_758",
        send_len=len(body),
        target=parsed[0],
        source=parsed[1],
        invitee_blocks=len(parsed[2]),
        invitee=describe_token(invitee_token),
    )
    resp = _send_packet(CMD_758, pb_hex, label="758 cross-group invite", stage="INVITE_758")
    ok = _response_ok(resp)
    if not ok:
        data = _rsp_hex(resp)
        code, _ = parse_758_recv_status(data) if data else (None, False)
        api_err = _api_send_failed(resp)
        protocol_log(
            "INVITE_758",
            result="not_confirmed",
            proto_code=code,
            api_err=api_err or "none",
            recv_len=len(data) // 2 if data else 0,
        )
    return ok, resp


def target_group_has_member(target_group_id: int, user_id: int) -> bool | None:
    """True/False if OneBot can tell; None if the lookup itself failed."""
    try:
        raw = onebot_action(
            "get_group_member_info",
            {
                "group_id": int(target_group_id),
                "user_id": int(user_id),
                "no_cache": True,
            },
            timeout=20,
        )
    except Exception as exc:
        protocol_log("VERIFY_TARGET_MEMBER", result="lookup_error", err=type(exc).__name__)
        return None
    if not isinstance(raw, dict):
        return False
    code = raw.get("code")
    status = str(raw.get("status") or "").lower()
    retcode = raw.get("retcode")
    if code not in (None, 0, "0") or status in {"failed", "error"}:
        protocol_log("VERIFY_TARGET_MEMBER", result="not_in_group")
        return False
    if retcode not in (None, 0, "0") and status != "ok":
        protocol_log("VERIFY_TARGET_MEMBER", result="not_in_group")
        return False
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    uid = None
    if isinstance(data, dict):
        uid = data.get("user_id") or data.get("uin")
    try:
        present = int(uid) == int(user_id) if uid not in (None, "", 0, "0") else False
    except (TypeError, ValueError):
        present = False
    protocol_log("VERIFY_TARGET_MEMBER", result="present" if present else "absent")
    return present


def run(cfg: dict | None = None) -> int:
    cfg = cfg or load_cfg()
    capture_dir = resolve_capture_dir(cfg)
    target_group_id, source_group_id, invitee = resolve_cross_targets(cfg)

    print("=== cross-group invite ===")
    print(f"target_group_id: {target_group_id}")
    print(f"source_group_id: {source_group_id}")
    print(f"invitee_qq: {invitee}")
    print(f"capture_dir: {capture_dir}")

    picker = open_cross_group_picker(capture_dir, target_group_id, source_group_id)
    if not picker:
        missing = missing_picker_templates(capture_dir)
        raise RuntimeError(
            "来源群成员已加载，但跨群邀请凭证未准备成功。"
            + (f" 缺少抓包: {', '.join(missing)}" if missing else "")
        )

    invitee_token = query_invitee_token(capture_dir, source_group_id, invitee)
    if not invitee_token:
        raise RuntimeError(
            f"cannot resolve invitee token for QQ {invitee} in source group {source_group_id}"
        )
    wrong = token_owner_mismatch(capture_dir, invitee_token, invitee)
    if wrong is not None:
        raise RuntimeError(f"invitee token belongs to QQ {wrong}, not {invitee}")

    sync_fe1_selection(capture_dir, [invitee_token])

    ok, resp = send_cross_group_invite(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        invitee_token=invitee_token,
        capture_dir=capture_dir,
    )
    data = _rsp_hex(resp)
    code, _ = parse_758_recv_status(data) if data else (None, False)
    protocol_log("INVITE_758", proto_ok=ok, proto_code=code)
    if not ok:
        print("failed: 758 返回无法确认邀请成功")
        return 1
    time.sleep(0.8)
    present = target_group_has_member(target_group_id, invitee)
    if present is True:
        cfg["cross_group_last_ok"] = {
            "target_group_id": target_group_id,
            "source_group_id": source_group_id,
            "invitee_qq": invitee,
        }
        save_cfg(cfg)
        print("OK: target group now contains the invitee")
        return 0
    print("failed: 服务器响应已返回，但目标群成员未出现")
    return 1


def main() -> int:
    try:
        return run()
    except RuntimeError as exc:
        print(f"\nerror: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
