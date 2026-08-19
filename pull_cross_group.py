# -*- coding: utf-8 -*-
"""Cross-group invite: pull members from another group into target group (0x758 95B)."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from pathlib import Path

from capture_utils import (
    DEFAULT_CAPTURE_DIR,
    build_11ec_1,
    build_88d_111,
    build_fe7_group_list,
    build_fe7_single_lookup,
    extract_fe7_page_cursor,
    extract_group_token_from_fe7,
    extract_token_for_uin,
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
from myqq_api import find_friend_uid_by_qq, load_cfg, onebot_action, save_cfg, send_napcat_packet
from pb_utils import (
    build_cross_group_758_pb,
    build_cross_group_fe1_pb,
    describe_token,
    extract_field_bytes,
    parse_758_recv_status,
    parse_cross_group_758_entries,
    parse_fe1_tokens,
)

CMD_758 = "OidbSvcTrpcTcp.0x758_1"
CMD_FE7 = "OidbSvcTrpcTcp.0xfe7_4"
CMD_FE1 = "OidbSvcTrpcTcp.0xfe1_8"
CMD_88D_111 = "OidbSvcTrpcTcp.0x88d_111"
CMD_11EC = "OidbSvcTrpcTcp.0x11ec_1"
PACKET_SLEEP = 0.15
FE7_SLEEP = 0.12
# Safety cap only. Prefer desired_qqs / no-cursor / stop as primary stop conditions.
FE7_MAX_PAGES = 64
MEMBERSHIP_RETRY_SEC = 5.0
MEMBERSHIP_RETRY_INTERVAL = 0.8
NOT_IN_GROUP_MARKERS = (
    "不在群",
    "不是群成员",
    "群成员不存在",
    "not in group",
    "member not found",
    "no such member",
)


class PickerStopped(Exception):
    """User stop requested before invite packets were fully sent."""


class PickerProtocolError(Exception):
    """OIDB picker stage failed at protocol or empty-result level."""

    def __init__(self, message: str, *, stage: str = "", code: int | None = None):
        super().__init__(message)
        self.stage = stage
        self.code = code


@dataclass
class PickerSession:
    token_map: dict[int, str] = field(default_factory=dict)
    fe7_pages: int = 0
    created_at: float = 0.0
    requested_qqs: list[int] = field(default_factory=list)
    missing_qqs: list[int] = field(default_factory=list)
    error: str = ""
    hit_page_limit: bool = False
    termination_reason: str = ""
    protocol_error_code: int | None = None
    failed_page: int | None = None


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


def _stop_requested(stop_event) -> bool:
    return bool(stop_event is not None and getattr(stop_event, "is_set", lambda: False)())


def _interruptible_sleep(seconds: float, stop_event=None) -> bool:
    """Sleep unless stop_event fires. True means stopped."""
    if seconds <= 0:
        return _stop_requested(stop_event)
    if stop_event is not None and hasattr(stop_event, "wait"):
        return bool(stop_event.wait(seconds))
    time.sleep(seconds)
    return _stop_requested(stop_event)


def _raise_if_stopped(stop_event, *, stage: str) -> None:
    if _stop_requested(stop_event):
        protocol_log(stage, result="stopped")
        raise PickerStopped(stage)


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


def parse_oidb_recv_status(hex_data: str) -> tuple[int | None, bool]:
    """OIDB top-level field3==0 is protocol OK for 88d/11ec/FE7/758 RECV."""
    return parse_758_recv_status(hex_data)


def _oidb_protocol_failed(resp: dict, *, require_status: bool = True) -> str:
    """Transport OK but OIDB RECV field3 != 0 / missing.

    require_status=True: missing/unparseable body is an error (picker stages).
    require_status=False: unparseable body is ignored; non-zero field3 still fails.
    """
    if not isinstance(resp, dict):
        return "响应无法解析"
    api_err = _api_send_failed(resp)
    if api_err:
        return api_err
    data = _rsp_hex(resp)
    if not data:
        return "缺少协议响应" if require_status else ""
    try:
        code, ok = parse_oidb_recv_status(data)
    except Exception:
        return "协议状态无法解析" if require_status else ""
    if code is None:
        return "协议状态无法解析" if require_status else ""
    if not ok:
        return f"协议错误 code={code}"
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
    code, proto_ok = parse_oidb_recv_status(rsp) if rsp else (None, False)
    protocol_log(
        stage or (label or cmd.rsplit(".", 1)[-1]),
        cmd=cmd.rsplit(".", 1)[-1],
        send_len=send_len,
        api_err=api_err or "none",
        recv_len=len(rsp) // 2 if rsp else 0,
        proto_code=code if code is not None else "none",
        proto_ok=proto_ok,
    )
    return resp


def _send_fe7(hex_data: str, *, label: str = "fe7_4", stop_event=None) -> str:
    _raise_if_stopped(stop_event, stage="SOURCE_FE7")
    resp = _send_packet(CMD_FE7, hex_data, label=label, stage="SOURCE_FE7")
    if _interruptible_sleep(FE7_SLEEP, stop_event):
        raise PickerStopped("SOURCE_FE7")
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
    capture_dir: Path,
    target_group_id: int,
    source_group_id: int,
    *,
    desired_qqs: list[int] | None = None,
    stop_event=None,
) -> PickerSession | None:
    """Live picker: built 88d_111 + 11ec + paginated FE7.

    capture_dir is unused at runtime (kept for call-site compatibility).
    When desired_qqs is set, FE7 stops once all requested QQ tokens are mapped.

    88d_14 remains an optional catalog prefix observed in historical picker
    windows. The live path does not send it and does not require capture files.
    """
    del capture_dir
    requested = [int(q) for q in (desired_qqs or []) if int(q) > 0]
    wanted = set(requested)
    token_map: dict[int, str] = {}
    fe7_pages = 0
    hit_page_limit = False
    created_at = time.time()
    print("open cross-group picker (live)...")

    def _fail(stage_name: str, err: str, *, code: int | None = None) -> None:
        protocol_log(
            "PICKER_SESSION",
            result="protocol_failed",
            picker_stage=stage_name,
            err=err,
            proto_code=code if code is not None else "none",
            fe7_pages=fe7_pages,
            mapped=len(token_map),
            requested=len(requested),
            missing=len(wanted - set(token_map)),
        )

    try:
        _raise_if_stopped(stop_event, stage="PICKER_88D")
        hx111 = build_88d_111(target_group_id)
        resp = _send_packet(CMD_88D_111, hx111, label="88d_111", stage="PICKER_88D")
        err = _oidb_protocol_failed(resp)
        if err:
            code, _ = parse_oidb_recv_status(_rsp_hex(resp)) if _rsp_hex(resp) else (None, False)
            _fail("PICKER_88D", err, code=code)
            return None
        if _interruptible_sleep(PACKET_SLEEP, stop_event):
            raise PickerStopped("PICKER_88D")

        _raise_if_stopped(stop_event, stage="PICKER_11EC")
        resp = _send_packet(
            CMD_11EC,
            build_11ec_1(target_group_id),
            label="11ec_1",
            stage="PICKER_11EC",
        )
        err = _oidb_protocol_failed(resp)
        if err:
            code, _ = parse_oidb_recv_status(_rsp_hex(resp)) if _rsp_hex(resp) else (None, False)
            _fail("PICKER_11EC", err, code=code)
            return None
        if _interruptible_sleep(PACKET_SLEEP, stop_event):
            raise PickerStopped("PICKER_11EC")

        cursor: bytes | None = None
        seen_cursors: set[bytes] = set()
        termination_reason = ""
        protocol_error_code: int | None = None
        failed_page: int | None = None
        while fe7_pages < FE7_MAX_PAGES:
            _raise_if_stopped(stop_event, stage="PICKER_FE7")
            hx = build_fe7_group_list(source_group_id, page_cursor=cursor)
            resp = _send_packet(
                CMD_FE7,
                hx,
                label=f"fe7_4 page {fe7_pages + 1}",
                stage="PICKER_FE7",
            )
            err = _oidb_protocol_failed(resp)
            if err:
                code, _ = parse_oidb_recv_status(_rsp_hex(resp)) if _rsp_hex(resp) else (None, False)
                failed_page = fe7_pages + 1
                protocol_error_code = code
                termination_reason = "protocol_error"
                protocol_log(
                    "PICKER_FE7",
                    result="page_protocol_failed",
                    page=failed_page,
                    err=err,
                    proto_code=code if code is not None else "none",
                )
                if not wanted and not token_map:
                    _fail("PICKER_FE7", err, code=code)
                    return None
                missing = sorted(wanted - set(token_map)) if wanted else []
                msg = f"FE7 第 {failed_page} 页协议错误"
                if err:
                    msg = f"{msg}：{err}"
                return PickerSession(
                    token_map=token_map,
                    fe7_pages=fe7_pages,
                    created_at=created_at,
                    requested_qqs=requested,
                    missing_qqs=missing,
                    error=msg,
                    hit_page_limit=hit_page_limit,
                    termination_reason=termination_reason,
                    protocol_error_code=protocol_error_code,
                    failed_page=failed_page,
                )
            fe7_pages += 1
            rsp = _rsp_hex(resp)
            page_map = parse_fe7_token_map(rsp) if rsp else {}
            token_map.update(page_map)
            missing_n = len(wanted - set(token_map)) if wanted else 0
            protocol_log(
                "PICKER_FE7",
                page=fe7_pages,
                mapped=len(page_map),
                merged=len(token_map),
                requested=len(requested),
                missing=missing_n,
            )
            if wanted and wanted.issubset(token_map.keys()):
                termination_reason = "desired_complete"
                protocol_log("PICKER_FE7", result="desired_complete", page=fe7_pages)
                break
            cursor = extract_fe7_page_cursor(rsp) if rsp else None
            if not cursor:
                termination_reason = "no_cursor"
                break
            if cursor in seen_cursors:
                termination_reason = "cursor_repeat"
                protocol_log("PICKER_FE7", result="cursor_repeat", page=fe7_pages)
                break
            seen_cursors.add(cursor)
            if _interruptible_sleep(PACKET_SLEEP, stop_event):
                raise PickerStopped("PICKER_FE7")
        else:
            hit_page_limit = True
            termination_reason = "page_limit"

        missing = sorted(wanted - set(token_map)) if wanted else []
        if hit_page_limit and missing:
            msg = f"FE7 分页达到安全上限 {FE7_MAX_PAGES}，仍缺少 {len(missing)} 名成员凭证"
            protocol_log(
                "PICKER_SESSION",
                result="pagination_limit",
                fe7_pages=fe7_pages,
                mapped=len(token_map),
                requested=len(requested),
                missing=len(missing),
            )
            return PickerSession(
                token_map=token_map,
                fe7_pages=fe7_pages,
                created_at=created_at,
                requested_qqs=requested,
                missing_qqs=missing,
                error=msg,
                hit_page_limit=True,
                termination_reason="page_limit",
            )

        if not token_map:
            if wanted:
                msg = "选择器未返回本批所需成员的邀请凭证"
                protocol_log(
                    "PICKER_SESSION",
                    result="desired_missing",
                    fe7_pages=fe7_pages,
                    mapped=0,
                    requested=len(requested),
                    missing=len(requested),
                )
                return PickerSession(
                    token_map={},
                    fe7_pages=fe7_pages,
                    created_at=created_at,
                    requested_qqs=requested,
                    missing_qqs=list(requested),
                    error=msg,
                    hit_page_limit=hit_page_limit,
                    termination_reason=termination_reason or "no_cursor",
                )
            _fail("PICKER_FE7", "选择器未返回任何成员邀请凭证")
            return None

        protocol_log(
            "PICKER_SESSION",
            result="ok",
            fe7_pages=fe7_pages,
            mapped=len(token_map),
            requested=len(requested),
            missing=len(missing),
            termination=termination_reason or "ok",
        )
        return PickerSession(
            token_map=token_map,
            fe7_pages=fe7_pages,
            created_at=created_at,
            requested_qqs=requested,
            missing_qqs=missing,
            hit_page_limit=hit_page_limit,
            termination_reason=termination_reason or "no_cursor",
        )
    except PickerStopped:
        protocol_log(
            "PICKER_SESSION",
            result="stopped",
            fe7_pages=fe7_pages,
            mapped=len(token_map),
            requested=len(requested),
        )
        raise


def sync_fe1_selection(
    capture_dir: Path, tokens: list[str], *, stop_event=None
) -> bool:
    """Send 0xfe1_8 with the same token list that will go into 758."""
    del capture_dir
    cleaned = [t for t in tokens if t]
    if not cleaned:
        return False
    _raise_if_stopped(stop_event, stage="FE1_SYNC")
    try:
        hex_data = build_cross_group_fe1_pb(cleaned)
    except ValueError as exc:
        protocol_log("FE1_SYNC", result="build_failed", err=type(exc).__name__)
        return False
    parsed = parse_fe1_tokens(hex_data)
    if parsed != cleaned:
        protocol_log("FE1_SYNC", result="parse_mismatch", n=len(parsed), want=len(cleaned))
        return False
    protocol_log(
        "FE1_SYNC",
        send_len=len(bytes.fromhex(hex_data)),
        token_n=len(cleaned),
        tokens=",".join(describe_token(t) for t in cleaned),
    )
    _raise_if_stopped(stop_event, stage="FE1_SYNC")
    resp = _send_packet(CMD_FE1, hex_data, label="fe1_8 selection sync", stage="FE1_SYNC")
    if _interruptible_sleep(PACKET_SLEEP, stop_event):
        raise PickerStopped("FE1_SYNC")
    err = _oidb_protocol_failed(resp, require_status=False)
    if err:
        protocol_log("FE1_SYNC", result="protocol_failed", err=err)
        return False
    return True


def send_cross_group_invite(
    *,
    target_group_id: int,
    source_group_id: int,
    invitee_token: str = "",
    invitee_tokens: list[str] | None = None,
    capture_dir: Path | None = None,
    source_context_token: str | None = None,
    stop_event=None,
) -> tuple[bool, dict]:
    del source_context_token
    del capture_dir
    tokens = [t for t in (invitee_tokens or []) if t]
    if invitee_token:
        tokens.append(invitee_token)
    if not tokens:
        protocol_log("INVITE_758", result="no_tokens", n=0)
        return False, {"error": "no_tokens"}
    _raise_if_stopped(stop_event, stage="INVITE_758")
    pb_hex = build_cross_group_758_pb(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        invitee_tokens=tokens,
    )
    body = bytes.fromhex(pb_hex)
    parsed = parse_cross_group_758_entries(extract_field_bytes(body, 4) or b"")
    protocol_log(
        "INVITE_758",
        send_len=len(body),
        target=parsed[0],
        source=parsed[1],
        invitee_blocks=len(parsed[2]),
        invitees=",".join(describe_token(t) for t in tokens),
    )
    _raise_if_stopped(stop_event, stage="INVITE_758")
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


def _not_in_group_text(raw: dict) -> bool:
    blob = " ".join(
        str(raw.get(k) or "")
        for k in ("message", "msg", "wording", "prompt", "error")
    ).lower()
    return any(m.lower() in blob for m in NOT_IN_GROUP_MARKERS)


def target_group_has_member(target_group_id: int, user_id: int) -> bool | None:
    """True in group, False explicitly absent, None if lookup itself failed."""
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
        protocol_log("VERIFY_TARGET_MEMBER", result="lookup_error", err="non_dict")
        return None
    status = str(raw.get("status") or "").lower()
    retcode = raw.get("retcode")
    code = raw.get("code")
    infra = False
    if code not in (None, 0, "0") and not _not_in_group_text(raw):
        infra = True
    if status in {"failed", "error"} and not _not_in_group_text(raw):
        infra = True
    if retcode not in (None, 0, "0") and status != "ok" and not _not_in_group_text(raw):
        infra = True
    if infra:
        protocol_log("VERIFY_TARGET_MEMBER", result="lookup_error", retcode=retcode, status=status or "none")
        return None
    if _not_in_group_text(raw):
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
    if status in {"failed", "error"} and not present:
        protocol_log("VERIFY_TARGET_MEMBER", result="not_in_group")
        return False
    protocol_log("VERIFY_TARGET_MEMBER", result="present" if present else "absent")
    return present


def wait_target_membership(
    target_group_id: int,
    user_id: int,
    *,
    stop_event=None,
    timeout: float = MEMBERSHIP_RETRY_SEC,
    interval: float = MEMBERSHIP_RETRY_INTERVAL,
) -> bool | None:
    """Retry membership lookup. None = never confirmed (lookup errors / stopped)."""
    deadline = time.time() + timeout
    saw_false = False
    last: bool | None = None
    while True:
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            break
        last = target_group_has_member(target_group_id, user_id)
        if last is True:
            return True
        if last is False:
            saw_false = True
        if time.time() >= deadline:
            break
        remaining = min(interval, max(0.0, deadline - time.time()))
        if remaining <= 0:
            break
        if stop_event is not None and hasattr(stop_event, "wait"):
            if stop_event.wait(remaining):
                break
        else:
            time.sleep(remaining)
    if last is True:
        return True
    if saw_false:
        return False
    return None


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
    if picker is None:
        raise RuntimeError("来源群成员已加载，但跨群邀请凭证未准备成功")

    invitee_token = picker.token_map.get(int(invitee))
    if not invitee_token:
        raise RuntimeError("当前选择器会话没有返回该成员的邀请凭证")
    if not sync_fe1_selection(capture_dir, [invitee_token]):
        raise RuntimeError("跨群选择同步失败，未发送邀请")
    try:
        ok, resp = send_cross_group_invite(
            target_group_id=target_group_id,
            source_group_id=source_group_id,
            invitee_tokens=[invitee_token],
            capture_dir=capture_dir,
        )
    except PickerStopped:
        print("stopped before 758")
        return 1
    data = _rsp_hex(resp)
    code, _ = parse_758_recv_status(data) if data else (None, False)
    protocol_log("INVITE_758", proto_ok=ok, proto_code=code)
    if not ok:
        print("failed: 758 返回无法确认邀请成功")
        return 1
    present = wait_target_membership(target_group_id, invitee)
    if present is True:
        print("ok: invitee is in target group")
        return 0
    if present is False:
        print("failed: 服务器响应已返回，但目标群成员未出现")
        return 1
    print("failed: 758 已返回，但无法确认目标群成员")
    return 1


def main() -> int:
    try:
        return run()
    except RuntimeError as exc:
        print(f"\nerror: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
