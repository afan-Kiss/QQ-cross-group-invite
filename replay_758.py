# -*- coding: utf-8 -*-
"""Replay captured NapCat 0x758 invite packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from myqq_api import load_cfg, send_napcat_packet
from pb_utils import (
    analyze_oidb_packet,
    build_invite_758_pb,
    decode_oidb_packet,
    normalize_hex,
    patch_invite_758_pb,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_CAPTURE_DIR = (
    ROOT.parent / "NapCatQQ-src" / "NapCat.Framework" / "logs" / "packet_capture"
)
CMD = "OidbSvcTrpcTcp.0x758_1"


def is_consent_invite_hex(hex_data: str) -> bool:
    """True when packet matches QQ UI consent invite (no invitee uin in block)."""
    try:
        pkt = decode_oidb_packet(CMD, hex_data)
    except ValueError:
        return False
    return pkt.invitee_uin is None


def latest_send_758(capture_dir: Path) -> tuple[str, str]:
    logs = sorted(capture_dir.glob("capture-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        raise FileNotFoundError(f"capture log dir not found: {capture_dir}")
    for log in logs:
        consent: tuple[str, str] | None = None
        last: tuple[str, str] | None = None
        with log.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("dir") != "SEND":
                    continue
                cmd = str(entry.get("cmd", ""))
                if "758" not in cmd.lower():
                    continue
                hex_data = normalize_hex(str(entry.get("hex", "")))
                if not hex_data:
                    continue
                last = (cmd, hex_data)
                if is_consent_invite_hex(hex_data):
                    consent = (cmd, hex_data)
        if consent:
            return consent
        if last:
            return last
    raise RuntimeError(f"no SEND 0x758 in {logs[0]}")


def parse_response(raw: str) -> dict:
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    inner = outer.get("data") if isinstance(outer, dict) else None
    if isinstance(inner, dict) and "data" in inner:
        return inner
    return outer if isinstance(outer, dict) else {"raw": raw}


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay 0x758 group invite packet")
    parser.add_argument("--hex", help="PB hex; default: latest capture log")
    parser.add_argument("--cmd", default=CMD, help="OIDB cmd name")
    parser.add_argument("--invitee", type=int, help="invitee QQ (requires --pull)")
    parser.add_argument("--pull", action="store_true", help="admin direct add (includes invitee uin)")
    parser.add_argument("--group", type=int, help="group internal code (optional)")
    parser.add_argument("--token", help="invite token (optional)")
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE_DIR)
    parser.add_argument("--webui-token", help="NapCat WebUI token")
    args = parser.parse_args()

    cfg = load_cfg()
    if args.hex:
        pb_hex = normalize_hex(args.hex)
        cmd = args.cmd
    else:
        cmd, pb_hex = latest_send_758(args.capture_dir)
        print("loaded latest SEND 0x758 from capture log")

    pkt = decode_oidb_packet(cmd, pb_hex)
    print(analyze_oidb_packet(cmd, pb_hex))

    if args.invitee is not None and not args.pull:
        print("warning: --invitee without --pull is ignored (consent invite has no uin in packet)")
        print("         use QQ UI to pick friend and capture token, or add --pull for direct add")

    if args.pull:
        if args.invitee is None:
            print("error: --pull requires --invitee")
            return 1
        pb_hex = patch_invite_758_pb(
            pb_hex,
            group_code=args.group or pkt.group_code or int(cfg.get("group_id") or 0),
            invitee_uin=args.invitee,
            invite_token=args.token or pkt.invite_token,
            pull=True,
        )
        pkt = decode_oidb_packet(cmd, pb_hex)
        print("\n--- patched (pull mode) ---")
        print(pkt.summary_text())
    elif args.group or args.token:
        pb_hex = build_invite_758_pb(
            group_code=args.group or pkt.group_code,
            invite_token=args.token or pkt.invite_token or "",
            pull=False,
        )
        pkt = decode_oidb_packet(cmd, pb_hex)
        print("\n--- rebuilt (consent invite) ---")
        print(pkt.summary_text())

    print(f"\nsend: {cmd}")
    print(f"PB ({len(pb_hex)//2} bytes): {pb_hex}")

    raw = send_napcat_packet(cmd, pb_hex, webui_token=args.webui_token, wait_rsp=True)
    resp = parse_response(raw)
    print("\n--- API response ---")
    print(json.dumps(resp, ensure_ascii=False, indent=2))

    rsp_hex = ""
    if isinstance(resp.get("data"), str):
        rsp_hex = resp["data"]
    ok = resp.get("status") == "ok" and resp.get("retcode") == 0
    if rsp_hex:
        print(f"\nserver PB ({len(rsp_hex)//2} bytes): {rsp_hex[:160]}{'...' if len(rsp_hex) > 160 else ''}")
        print("replay OK (response data present)")
        return 0
    if ok:
        print("\npacket sent, empty response - invite token likely expired (one-time).")
        print("invite again in QQ, then run: python replay_758.py")
        return 2
    print("\nreplay failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
