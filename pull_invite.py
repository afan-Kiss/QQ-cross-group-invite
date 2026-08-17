# -*- coding: utf-8 -*-
"""One-click admin pull: config + capture log, no CLI params required."""
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_utils import (
    DEFAULT_CAPTURE_DIR,
    extract_token_for_uin,
    extract_u_token_from_hex,
    extract_invite_tokens_from_hex,
    find_116c_select_template,
    find_bootstrap_templates,
    find_consent_758_template,
    find_fe1_select_template,
    find_fe7_pagination_templates,
    find_fe7_single_template,
    find_fe7_token_refresh_template,
    find_group_share_token,
    find_invite_ui_chain_templates,
    find_invite_ui_chain_from_anchor,
    find_post_select_activation_templates,
    find_successful_pull_template,
    find_permanent_uid_from_capture,
    find_pull_bootstrap_templates,
    extract_group_token_from_fe7,
    lookup_token_owner,
    token_owner_mismatch,
    find_all_758_pairs,
    latest_758_recv_for_invitee,
    latest_token_for_invitee,
    latest_valid_758,
    parse_fe7_token_map,
    patch_group_code_in_hex,
    patch_token_in_fe7_refresh,
    patch_u_token_in_hex,
    patch_uid_in_fe7_hex,
    scan_capture_fe7_token,
    watch_new_758_token,
    build_fe7_single_lookup,
    U_TOKEN_RE,
)
from myqq_api import (
    find_friend_uid_by_qq,
    load_cfg,
    save_cfg,
    send_napcat_packet,
)
from pb_utils import (
    build_invite_758_pb,
    decode_oidb_packet,
    parse_758_recv_status,
    patch_invite_758_pb,
)

ROOT = Path(__file__).resolve().parent
CMD_758 = "OidbSvcTrpcTcp.0x758_1"
CMD_FE7 = "OidbSvcTrpcTcp.0xfe7_4"
CMD_FE1 = "OidbSvcTrpcTcp.0xfe1_8"
CMD_116C = "OidbSvcTrpcTcp.0x116c_1"
FE7_SLEEP = 0.12
PACKET_SLEEP = 0.15


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


def resolve_targets(cfg: dict) -> tuple[int, int]:
    invitee = _cfg_int(cfg, "invitee_qq", "friend_qq")
    group_code = _cfg_int(cfg, "group_id", "group_code")
    if invitee is None:
        raise RuntimeError("config.json missing invitee_qq or friend_qq")
    if group_code is None:
        raise RuntimeError("config.json missing group_code or group_id")
    return group_code, invitee


def resolve_capture_dir(cfg: dict) -> Path:
    raw = str(cfg.get("capture_dir") or "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_CAPTURE_DIR


def _send_packet(cmd: str, hex_data: str, *, label: str | None = None) -> dict:
    if label:
        print(f"  send: {label} ({len(hex_data) // 2} bytes)")
    raw = send_napcat_packet(cmd, hex_data, wait_rsp=True)
    resp = _parse_api_response(raw)
    if resp.get("code") not in (None, 0) and resp.get("retcode") not in (0, None):
        msg = resp.get("message") or resp.get("wording") or str(resp)
        if "未初始化" in msg or resp.get("code") == -1:
            raise RuntimeError(f"NapCat not ready: {msg}")
    return resp


def _send_fe7(hex_data: str, *, label: str = "fe7_4") -> tuple[dict, str]:
    resp = _send_packet(CMD_FE7, hex_data, label=label)
    time.sleep(FE7_SLEEP)
    return resp, _rsp_hex(resp)


def _resolve_nt_uid(
    capture_dir: Path, group_code: int, invitee: int
) -> str | None:
    uid = find_permanent_uid_from_capture(capture_dir, group_code, invitee)
    if uid:
        print(f"NT uid from capture: {uid}")
        return uid
    uid = find_friend_uid_by_qq(invitee, no_cache=True)
    if uid:
        print(f"NT uid from OneBot: {uid}")
        return uid
    return None


def query_fe7_pages(
    capture_dir: Path,
    group_code: int,
    invitee: int,
) -> str | None:
    """Paginate captured fe7 group-list templates and merge uin→token map."""
    pages = find_fe7_pagination_templates(capture_dir, group_code)
    if not pages:
        return None
    print(f"query fe7 friend list ({len(pages)} page template(s))...")
    merged: dict[int, str] = {}
    for i, page_hex in enumerate(pages, 1):
        patched = patch_group_code_in_hex(page_hex, group_code)
        _, rsp_hex = _send_fe7(patched, label=f"fe7_4 page {i}/{len(pages)}")
        if rsp_hex:
            merged.update(parse_fe7_token_map(rsp_hex))
    token = merged.get(invitee)
    if token:
        print(f"token from fe7 pages for {invitee}: {token}")
    return token


def query_fe7_single_lookup(
    capture_dir: Path,
    group_code: int,
    invitee: int,
    uid: str,
) -> str | None:
    """Single-friend fe7 lookup by permanent NT uid."""
    single_tpl = find_fe7_single_template(capture_dir, group_code)
    if single_tpl:
        fe7_hex = patch_uid_in_fe7_hex(single_tpl, uid, group_code)
    else:
        fe7_hex = build_fe7_single_lookup(group_code, uid)
    _, rsp_hex = _send_fe7(fe7_hex, label="fe7_4 single lookup")
    if not rsp_hex:
        return None
    token = extract_token_for_uin(rsp_hex, invitee)
    if token:
        print(f"token from fe7 single lookup: {token}")
    return token


def run_bootstrap_packets(
    capture_dir: Path,
    group_code: int,
    invitee: int,
    *,
    skip_fe7: bool = False,
) -> str | None:
    """Replay af6 / 88d bootstrap chain from capture (before 0x758)."""
    templates = find_bootstrap_templates(capture_dir)
    if not templates:
        return None
    token: str | None = None
    fe7_pages = {h for h in find_fe7_pagination_templates(capture_dir, group_code)}
    for cmd, hex_data in templates:
        if skip_fe7 and "0xfe7_4" in cmd:
            continue
        if "0xfe7_4" in cmd and hex_data in fe7_pages:
            continue
        patched = patch_group_code_in_hex(hex_data, group_code)
        resp = _send_packet(cmd, patched, label=cmd)
        rsp_hex = _rsp_hex(resp)
        if rsp_hex and invitee:
            token = extract_token_for_uin(rsp_hex, invitee) or token
        elif rsp_hex:
            token = extract_u_token_from_hex(rsp_hex) or token
        time.sleep(FE7_SLEEP)
    return token


def _pick_session_token(rsp_hex: str, *exclude: str) -> str | None:
    blocked = {x for x in exclude if x}
    for tok in extract_invite_tokens_from_hex(rsp_hex):
        if tok in blocked or tok.startswith("u_invalid"):
            continue
        return tok
    return None


def _group_share_token_hint(capture_dir: Path, group_code: int) -> str | None:
    """Group link token for 59-byte 758 pull (never use in 55-byte consent)."""
    return find_group_share_token(capture_dir, group_code)


def _assert_token_safe_for_invitee(
    capture_dir: Path, token: str, invitee: int, *, context: str
) -> None:
    wrong = token_owner_mismatch(capture_dir, token, invitee)
    if wrong is not None:
        raise RuntimeError(
            f"{context}: token {token} belongs to QQ {wrong}, not target {invitee}. "
            "Refusing to send — 55-byte consent would pull the wrong person."
        )


def replay_invite_ui_chain(
    capture_dir: Path,
    group_code: int,
    invitee: int,
    invite_token: str,
) -> bool:
    """
    Replay full QQ invite UI select chain from capture:
    fe1/116c/9075/7ed/fe1 — establishes invitee context before consent 758.
    """
    chain = find_invite_ui_chain_from_anchor(capture_dir, group_code, invitee)
    if not chain:
        chain = find_invite_ui_chain_templates(capture_dir)
    if not chain:
        print("capture missing invite UI chain templates; using minimal fe1+116c")
        fe1_tpl = find_fe1_select_template(capture_dir)
        c116_tpl = find_116c_select_template(capture_dir)
        if not fe1_tpl:
            return False
        chain = [(CMD_FE1, fe1_tpl)]
        if c116_tpl:
            chain.append((CMD_116C, c116_tpl))

    print(f"replay invite UI chain ({len(chain)} packets) for {invitee}...")
    perm_uid = find_permanent_uid_from_capture(capture_dir, group_code, invitee) or ""
    for cmd, tpl in chain:
        hex_data = patch_u_token_in_hex(tpl, invite_token)
        hex_data = patch_group_code_in_hex(hex_data, group_code)
        label = cmd.rsplit(".", 1)[-1]
        resp = _send_packet(cmd, hex_data, label=f"{label} select")
        rsp_hex = _rsp_hex(resp)
        fresh = _pick_session_token(rsp_hex, invite_token, perm_uid)
        if fresh and fresh != invite_token:
            print(f"  session token from {label}: {fresh}")
            invite_token = fresh
        time.sleep(PACKET_SLEEP)
    return True


def send_consent_758(
    *,
    group_code: int,
    group_token: str,
    invitee: int,
    capture_dir: Path,
    after_ui_select: bool = False,
) -> tuple[bool, dict]:
    """
    55-byte consent 758 — without invitee uin pulls token owner.
    After UI select, manual QQ uses group token (u_qFScq) to activate pull session.
    """
    if not after_ui_select:
        _assert_token_safe_for_invitee(
            capture_dir, group_token, invitee, context="758 consent"
        )
    tpl = find_consent_758_template(capture_dir, group_code)
    if tpl:
        pb_hex = patch_invite_758_pb(
            tpl,
            group_code=group_code,
            invite_token=group_token,
            pull=False,
        )
    else:
        pb_hex = build_invite_758_pb(
            group_code=group_code,
            invite_token=group_token,
            pull=False,
        )
    since = time.time() - 1
    resp = _send_packet(CMD_758, pb_hex, label="758 consent (activate session)")
    ok = _response_ok(resp)
    if not ok:
        time.sleep(0.4)
        hit = latest_valid_758(capture_dir, group_code=group_code, min_recv_len=200)
        if hit and hit.log_path.stat().st_mtime >= since - 2:
            print(f"capture confirms 758 consent ok (seq {hit.seq}, f3=0)")
            ok = True
    return ok, resp


def activate_pull_session(
    capture_dir: Path,
    group_code: int,
    group_token: str,
    invitee: int,
    *,
    invitee_token: str | None = None,
) -> str | None:
    """
    Post-select activation from manual success log:
    88d_111 -> consent(invitee token) -> fe7/88d/af6 bootstrap(group token refresh).
    Never send 55-byte consent with group token (pulls token owner QQ 472336362).
    """
    if not invitee_token:
        print("missing invitee token for session activation")
        return None

    activation = find_post_select_activation_templates(capture_dir, group_code, invitee)
    if not activation:
        print("no post-select templates from successful capture; using generic bootstrap")
        activation = find_pull_bootstrap_templates(capture_dir)
    if not activation:
        print("no activation/bootstrap templates in capture")
        return group_token

    print(f"post-select activation ({len(activation)} templates + consent)...")
    token = group_token
    sent_consent = False
    for cmd, hex_data in activation:
        label = cmd.rsplit(".", 1)[-1]
        patched = patch_group_code_in_hex(hex_data, group_code)
        data_len = len(patched) // 2
        if (
            "0xfe7_4" in cmd
            and data_len in (124, 127)
            and U_TOKEN_RE.search(bytes.fromhex(patched))
        ):
            patched = patch_token_in_fe7_refresh(patched, token, group_code)
            label = f"{label} refresh"

        resp = _send_packet(cmd, patched, label=label)
        _rsp_hex(resp)
        time.sleep(PACKET_SLEEP)

        if "88d_111" in cmd and not sent_consent:
            ok, _ = send_consent_758(
                group_code=group_code,
                group_token=group_token,
                invitee=invitee,
                capture_dir=capture_dir,
                after_ui_select=True,
            )
            sent_consent = True
            if not ok:
                print("758 group consent after UI select failed")
                return None

    if not sent_consent:
        ok, _ = send_consent_758(
            group_code=group_code,
            group_token=group_token,
            invitee=invitee,
            capture_dir=capture_dir,
            after_ui_select=True,
        )
        if not ok:
            return None

    print(f"group pull token ready: {group_token}")
    return group_token


def mint_invitee_pull_token(
    capture_dir: Path,
    group_code: int,
    invitee: int,
    *,
    hint_token: str | None = None,
) -> str | None:
    """
    Full programmatic mint: fe7 invite token → UI select chain → bootstrap.
    Returns group share token for 59-byte pull (invitee uin in packet, not consent).
    """
    del hint_token
    uid = _resolve_nt_uid(capture_dir, group_code, invitee)
    invitee_token: str | None = None
    in_live_list = False
    if uid:
        invitee_token = query_fe7_single_lookup(capture_dir, group_code, invitee, uid)
        if invitee_token:
            in_live_list = True
    if not invitee_token:
        invitee_token = query_fe7_pages(capture_dir, group_code, invitee)
        if invitee_token:
            in_live_list = True
    if not invitee_token:
        invitee_token = scan_capture_fe7_token(capture_dir, invitee)
    if invitee_token:
        owner = lookup_token_owner(capture_dir, invitee_token)
        if owner is not None and owner != invitee:
            print(f"reject token {invitee_token}: owned by QQ {owner}")
            invitee_token = None
    if not invitee_token:
        print(f"no fe7 invite token for invitee {invitee}")
        return None
    if not in_live_list:
        print(
            f"warning: {invitee} not in live fe7 friend list; "
            f"using captured token {invitee_token}"
        )

    print(f"invitee fe7 token for {invitee}: {invitee_token}")
    if not replay_invite_ui_chain(capture_dir, group_code, invitee, invitee_token):
        print("invite UI chain replay failed")
        return None

    share_hint = _group_share_token_hint(capture_dir, group_code)
    if not share_hint:
        print("no group share token in capture")
        return None
    owner = lookup_token_owner(capture_dir, share_hint)
    if owner is not None and owner != invitee:
        print(
            f"group token {share_hint} owned by QQ {owner}; "
            f"59-byte pull will target invitee={invitee} in packet (no consent)"
        )

    return activate_pull_session(
        capture_dir,
        group_code,
        share_hint,
        invitee,
        invitee_token=invitee_token,
    )


def mint_token_via_friend_select(
    capture_dir: Path,
    group_code: int,
    invitee: int,
    invite_token: str,
) -> str | None:
    """Backward-compatible alias — runs full UI chain."""
    replay_invite_ui_chain(capture_dir, group_code, invitee, invite_token)
    return invite_token


def programmatic_fetch_token(
    capture_dir: Path,
    group_code: int,
    invitee: int,
) -> str | None:
    """Mint per-invitee pull token (fe7 select + bootstrap)."""
    print("programmatic token fetch (invitee fe7 token)...")
    return mint_invitee_pull_token(capture_dir, group_code, invitee)


def acquire_token(
    cfg: dict, capture_dir: Path, group_code: int, invitee: int
) -> str:
    # Do not trust stale config cache ?? always fetch fresh token first.
    cfg.pop("invite_token", None)

    token = programmatic_fetch_token(capture_dir, group_code, invitee)
    if token:
        cfg["invite_token"] = token
        save_cfg(cfg)
        return token

    print("programmatic fetch failed; trying capture fe7 for invitee...")
    token = scan_capture_fe7_token(capture_dir, invitee)
    if token:
        print(f"invitee token from capture fe7: {token}")

    if not token:
        token, recv_len = latest_token_for_invitee(
            capture_dir, invitee, group_code=group_code
        )
        if token and recv_len >= 100:
            print(f"token from capture 758 pull: {token}")

    if token:
        print("retrying bootstrap with capture hint token...")
        token = bootstrap_token(
            cfg, capture_dir, group_code, invitee, hint_token=token
        )
        return token

    print("full bootstrap (no prior token)...")
    return bootstrap_token(cfg, capture_dir, group_code, invitee)


def bootstrap_token(
    cfg: dict,
    capture_dir: Path,
    group_code: int,
    invitee: int | None = None,
    *,
    hint_token: str | None = None,
) -> str:
    since = time.time()
    if not invitee:
        raise RuntimeError("bootstrap requires invitee qq")
    token = mint_invitee_pull_token(
        capture_dir, group_code, invitee, hint_token=hint_token
    )

    if not token and invitee:
        token, _ = latest_token_for_invitee(
            capture_dir, invitee, group_code=group_code
        )
        if token:
            print(f"token from capture pull log: {token}")

    if not token and invitee:
        hit = watch_new_758_token(capture_dir, timeout=15.0, since_mtime=since - 2)
        if hit and hit.token:
            from pb_utils import decode_oidb_packet
            try:
                pkt = decode_oidb_packet(CMD_758, hit.send_hex)
            except ValueError:
                pkt = None
            if pkt and pkt.invitee_uin == invitee:
                token = hit.token

    if not token:
        raise RuntimeError(
            "programmatic token mint failed (758 f3=1289). "
            "Ensure NapCat packet capture is enabled and at least one manual "
            "group-invite session was captured for this group."
        )

    print(f"bootstrap token: {token}")
    cfg["invite_token"] = token
    save_cfg(cfg)
    return token


def send_pull(
    *,
    group_code: int,
    invitee: int,
    token: str,
    template_hex: str | None = None,
    capture_dir: Path | None = None,
) -> tuple[bool, dict]:
    if template_hex is None and capture_dir is not None:
        template_hex = find_successful_pull_template(capture_dir, group_code, invitee)
    if template_hex:
        pb_hex = patch_invite_758_pb(
            template_hex,
            group_code=group_code,
            invitee_uin=invitee,
            invite_token=token,
            pull=True,
        )
    else:
        pb_hex = build_invite_758_pb(
            group_code=group_code,
            invite_token=token,
            invitee_uin=invitee,
            pull=True,
        )

    pkt = decode_oidb_packet(CMD_758, pb_hex)
    if pkt.invitee_uin != invitee:
        raise RuntimeError(
            f"758 packet invitee mismatch: got {pkt.invitee_uin}, want {invitee}"
        )
    owner = lookup_token_owner(capture_dir, token) if capture_dir else None
    if owner is not None and owner != invitee:
        print(
            f"note: pull token owner QQ {owner}, packet invitee={invitee} "
            "(59-byte pull uses invitee field, not consent)"
        )
    print("\n--- pull packet ---")
    print(pkt.summary_text())
    print(f"PB ({len(pb_hex)//2} bytes)")

    since = time.time() - 1
    raw = send_napcat_packet(CMD_758, pb_hex, wait_rsp=True)
    resp = _parse_api_response(raw)
    ok = _response_ok(resp)
    if not ok and capture_dir is not None:
        time.sleep(0.5)
        recv_ok, recv_len, recv_code = latest_758_recv_for_invitee(
            capture_dir, invitee, since_mtime=since - 2, min_recv_len=200
        )
        if recv_ok:
            print(f"capture confirms 0x758 RECV ok ({recv_len} bytes, f3=0)")
            ok = True
        elif recv_len >= 200:
            print(
                f"capture 0x758 RECV {recv_len} bytes but f3={recv_code} (token stale)"
            )
    return ok, resp


def main() -> int:
    cfg = load_cfg()
    capture_dir = resolve_capture_dir(cfg)
    group_code, invitee = resolve_targets(cfg)

    print("=== pull invite (zero-arg) ===")
    print(f"group_code: {group_code}")
    print(f"invitee: {invitee}")
    print(f"capture_dir: {capture_dir}")

    token = acquire_token(cfg, capture_dir, group_code, invitee)
    ok, resp = send_pull(
        group_code=group_code,
        invitee=invitee,
        token=token,
        template_hex=None,
        capture_dir=capture_dir,
    )

    if ok:
        print("\nOK: pull packet accepted by server")
        cfg["invite_token"] = token
        save_cfg(cfg)
        return 0

    print("\ntoken expired or consumed, bootstrap + retry...")
    cfg.pop("invite_token", None)
    save_cfg(cfg)
    token = bootstrap_token(cfg, capture_dir, group_code, invitee)
    ok, resp = send_pull(
        group_code=group_code,
        invitee=invitee,
        token=token,
        template_hex=None,
        capture_dir=capture_dir,
    )
    print("\n--- API response ---")
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    if ok:
        print("\nretry OK")
        return 0

    print("\nfailed: programmatic mint or pull rejected by server (758 f3=1289)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
