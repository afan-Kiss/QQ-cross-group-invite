# -*- coding: utf-8 -*-
"""Batch cross-group invite engine with member filtering."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from capture_utils import (
    find_fe7_pagination_templates,
    find_fe7_pagination_templates_generic,
    parse_fe7_token_map,
    patch_group_code_in_hex,
    scan_capture_fe7_token_map,
)
from myqq_api import load_cfg, onebot_action, send_napcat_packet
from pb_utils import parse_758_recv_status
from pull_cross_group import (
    CMD_FE7,
    _parse_api_response,
    _rsp_hex,
    open_cross_group_picker,
    query_invitee_token,
    query_source_context_token,
    resolve_capture_dir,
    send_cross_group_invite,
    sync_fe1_selection,
)

FE7_SLEEP = 0.12


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    UNKNOWN = "unknown"


@dataclass
class SourceMember:
    qq: int
    nickname: str
    token: str
    role: MemberRole = MemberRole.MEMBER
    card: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "token": self.token,
            "role": self.role.value,
            "card": self.card,
        }


@dataclass
class InviteRecord:
    qq: int
    nickname: str
    reason: str
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "reason": self.reason,
            "at": self.at,
        }


@dataclass
class BatchState:
    running: bool = False
    total: int = 0
    done: int = 0
    success: int = 0
    current_qq: int = 0
    current_nickname: str = ""
    message: str = ""
    frequent: list[InviteRecord] = field(default_factory=list)
    errors: list[InviteRecord] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "total": self.total,
            "done": self.done,
            "success": self.success,
            "current_qq": self.current_qq,
            "current_nickname": self.current_nickname,
            "message": self.message,
            "frequent": [x.to_dict() for x in self.frequent],
            "errors": [x.to_dict() for x in self.errors],
            "logs": self.logs[-200:],
        }


_state = BatchState()
_state_lock = threading.Lock()
_members_cache: list[SourceMember] = []
_members_cache_key: tuple[int, bool] | None = None


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _state_lock:
        _state.logs.append(line)
        if len(_state.logs) > 500:
            _state.logs = _state.logs[-300:]


def _extract_error_text(hex_data: str) -> str:
    if not hex_data:
        return ""
    try:
        raw = bytes.fromhex(hex_data)
    except ValueError:
        return ""
    texts: list[str] = []
    for m in re.finditer(rb"[\xe4-\xe9][\x80-\xbf]{2}(?:[\xe4-\xe9][\x80-\xbf]{2})+", raw):
        try:
            s = m.group().decode("utf-8")
            if len(s) >= 2:
                texts.append(s)
        except UnicodeDecodeError:
            continue
    return texts[0] if texts else ""


def _failure_reason(code: int | None) -> str:
    if code == 1289:
        return "\u64cd\u4f5c\u592a\u9891\u7e41"
    if code is not None:
        return f"\u9080\u8bf7\u5931\u8d25\uff08\u9519\u8bef\u7801 {code}\uff09"
    return "\u9080\u8bf7\u5931\u8d25"


def _classify_failure(code: int | None, msg: str) -> str:
    text = msg or ""
    if code == 1289:
        return "frequent"
    if any(k in text for k in ("\u9891\u7e41", "\u64cd\u4f5c\u9891\u7e41", "too fast", "rate")):
        return "frequent"
    return "error"


def fetch_fe7_token_map_live(
    capture_dir, source_group_id: int
) -> dict[int, str]:
    pages = find_fe7_pagination_templates(capture_dir, source_group_id)
    if not pages:
        pages = find_fe7_pagination_templates_generic(capture_dir)
    if not pages:
        return {}
    merged: dict[int, str] = {}
    for i, page_hex in enumerate(pages, 1):
        patched = patch_group_code_in_hex(page_hex, source_group_id)
        raw = send_napcat_packet(CMD_FE7, patched, wait_rsp=True)
        resp = _parse_api_response(raw)
        rsp_hex = _rsp_hex(resp)
        if rsp_hex:
            merged.update(parse_fe7_token_map(rsp_hex))
        time.sleep(FE7_SLEEP)
        if i >= 8:
            break
    return merged


def _onebot_members(source_group_id: int) -> list[dict[str, Any]]:
    try:
        raw = onebot_action(
            "get_group_member_list", {"group_id": int(source_group_id)}
        )
    except Exception:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        inner = raw.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def load_source_members(
    source_group_id: int,
    *,
    filter_staff: bool = True,
    capture_dir=None,
    record_logs: bool = False,
) -> list[SourceMember]:
    global _members_cache
    cfg = load_cfg()
    cap = capture_dir or resolve_capture_dir(cfg)

    def log(msg: str) -> None:
        if record_logs:
            _log(msg)

    log(f"\u6b63\u5728\u52a0\u8f7d\u6765\u6e90\u7fa4\u6210\u5458\uff0c\u7fa4\u53f7={source_group_id}...")

    token_map = fetch_fe7_token_map_live(cap, source_group_id)
    if not token_map:
        token_map = scan_capture_fe7_token_map(cap)
        if token_map:
            log("\u5b9e\u65f6\u62c9\u4e0d\u5230\u6210\u5458\uff0c\u5df2\u4ece\u6293\u5305\u8bb0\u5f55\u6062\u590d")
        else:
            log("\u62c9\u53d6\u6210\u5458\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u786e\u8ba4\u7fa4\u53f7\u6b63\u786e\u4e14 NapCat \u5728\u7ebf")
    ob_list = _onebot_members(source_group_id)
    by_qq: dict[int, SourceMember] = {}

    for item in ob_list:
        qq_raw = item.get("user_id") or item.get("uin")
        if qq_raw is None:
            continue
        try:
            qq = int(qq_raw)
        except (TypeError, ValueError):
            continue
        role_raw = str(item.get("role") or "member").lower()
        if role_raw == "owner":
            role = MemberRole.OWNER
        elif role_raw == "admin":
            role = MemberRole.ADMIN
        else:
            role = MemberRole.MEMBER
        if filter_staff and role in (MemberRole.OWNER, MemberRole.ADMIN):
            continue
        nick = str(item.get("nickname") or item.get("nick") or str(qq))
        card = str(item.get("card") or "")
        token = token_map.get(qq, "")
        if not token:
            continue
        by_qq[qq] = SourceMember(
            qq=qq, nickname=nick, token=token, role=role, card=card
        )

    if not by_qq and token_map:
        for qq, token in token_map.items():
            if qq < 10000:
                continue
            by_qq[qq] = SourceMember(
                qq=qq, nickname=str(qq), token=token, role=MemberRole.UNKNOWN
            )

    members = sorted(by_qq.values(), key=lambda m: m.qq)
    global _members_cache_key
    _members_cache = members
    _members_cache_key = (int(source_group_id), bool(filter_staff))
    log(f"\u5df2\u52a0\u8f7d {len(members)} \u540d\u53ef\u9080\u8bf7\u6210\u5458\uff08\u8fc7\u6ee4\u7fa4\u4e3b/\u7ba1\u7406\u5458={filter_staff}\uff09")
    return members


def get_cached_members() -> list[SourceMember]:
    return list(_members_cache)


def get_state() -> dict[str, Any]:
    with _state_lock:
        return _state.to_dict()


def stop_batch() -> None:
    with _state_lock:
        _state._stop.set()
        _state.message = "\u6b63\u5728\u505c\u6b62..."
    _log("\u6536\u5230\u505c\u6b62\u8bf7\u6c42")


def _invite_one(
    *,
    target_group_id: int,
    source_group_id: int,
    context_token: str,
    member: SourceMember,
    capture_dir,
) -> tuple[bool, int | None, str]:
    sync_fe1_selection(capture_dir, [context_token, member.token])
    ok, resp = send_cross_group_invite(
        target_group_id=target_group_id,
        source_group_id=source_group_id,
        source_context_token=context_token,
        invitee_token=member.token,
        capture_dir=capture_dir,
    )
    rsp_hex = _rsp_hex(resp)
    code, _ = parse_758_recv_status(rsp_hex) if rsp_hex else (None, False)
    msg = _extract_error_text(rsp_hex)
    if not ok and not msg and isinstance(resp, dict):
        msg = str(resp.get("message") or resp.get("wording") or "")
    return ok, code, msg


def start_batch(
    *,
    target_group_id: int,
    source_group_id: int,
    count: int,
    interval_ms: int,
    filter_staff: bool = True,
    qq_list: list[int] | None = None,
) -> None:
    with _state_lock:
        if _state.running:
            raise RuntimeError("\u4e0a\u4e00\u6b21\u9080\u8bf7\u8fd8\u6ca1\u7ed3\u675f\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5")
        _state._stop.clear()
        _state.running = True
        _state.total = 0
        _state.done = 0
        _state.success = 0
        _state.frequent.clear()
        _state.errors.clear()
        _state.logs.clear()
        _state.message = "\u51c6\u5907\u4e2d..."

    def worker() -> None:
        cfg = load_cfg()
        cap = resolve_capture_dir(cfg)
        try:
            cache_key = (int(source_group_id), bool(filter_staff))
            members = _members_cache
            if _members_cache_key != cache_key or not members:
                members = load_source_members(
                    source_group_id,
                    filter_staff=filter_staff,
                    capture_dir=cap,
                    record_logs=True,
                )
            if qq_list:
                allow = set(qq_list)
                members = [m for m in members if m.qq in allow]
            if count > 0:
                members = members[:count]

            with _state_lock:
                _state.total = len(members)
            if not members:
                raise RuntimeError("\u6ca1\u6709\u53ef\u9080\u8bf7\u6210\u5458")

            _log("\u6b63\u5728\u51c6\u5907\u8de8\u7fa4\u9080\u8bf7...")
            live_fe7 = open_cross_group_picker(cap, target_group_id, source_group_id)
            context_token = query_source_context_token(
                cap, source_group_id, live_rsp=live_fe7
            )
            if not context_token:
                raise RuntimeError("\u65e0\u6cd5\u83b7\u53d6\u6765\u6e90\u7fa4\u4fe1\u606f\uff0c\u8bf7\u786e\u8ba4\u7fa4\u53f7\u6b63\u786e\uff0c\u5e76\u4fdd\u7559\u8fc7\u8de8\u7fa4\u9080\u8bf7\u7684\u6293\u5305\u8bb0\u5f55")

            if target_group_id == source_group_id:
                raise RuntimeError("\u76ee\u6807\u7fa4\u548c\u6765\u6e90\u7fa4\u4e0d\u80fd\u76f8\u540c")

            for member in members:
                with _state_lock:
                    if _state._stop.is_set():
                        _state.message = "\u5df2\u505c\u6b62"
                        break
                    _state.current_qq = member.qq
                    _state.current_nickname = member.nickname
                    _state.message = f"\u9080\u8bf7 {member.nickname}({member.qq})"

                token = member.token
                if not token or not token_owner_safe(cap, member.qq, token):
                    fresh = query_invitee_token(cap, source_group_id, member.qq)
                    if fresh:
                        token = fresh
                        member.token = fresh
                if not token:
                    reason = "\u627e\u4e0d\u5230\u8be5\u6210\u5458\u7684\u9080\u8bf7\u4fe1\u606f"
                    rec = InviteRecord(qq=member.qq, nickname=member.nickname, reason=reason)
                    with _state_lock:
                        _state.done += 1
                        _state.errors.append(rec)
                        _log(f"\u5931\u8d25 {member.nickname}({member.qq}): {reason}")
                    continue
                if context_token == token:
                    reason = "\u6765\u6e90\u7fa4\u4fe1\u606f\u4e0e\u6210\u5458\u4fe1\u606f\u51b2\u7a81\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u6210\u5458"
                    rec = InviteRecord(qq=member.qq, nickname=member.nickname, reason=reason)
                    with _state_lock:
                        _state.done += 1
                        _state.errors.append(rec)
                        _log(f"\u5931\u8d25 {member.nickname}({member.qq}): {reason}")
                    continue

                ok, code, msg = _invite_one(
                    target_group_id=target_group_id,
                    source_group_id=source_group_id,
                    context_token=context_token,
                    member=member,
                    capture_dir=cap,
                )
                reason = msg or _failure_reason(code)
                kind = _classify_failure(code, reason)
                rec = InviteRecord(qq=member.qq, nickname=member.nickname, reason=reason)
                with _state_lock:
                    _state.done += 1
                    if ok:
                        _state.success += 1
                        _log(f"\u6210\u529f {member.nickname}({member.qq})")
                    elif kind == "frequent":
                        _state.frequent.append(rec)
                        _log(f"\u9891\u7e41 {member.nickname}({member.qq}): {reason}")
                    else:
                        _state.errors.append(rec)
                        _log(f"\u5931\u8d25 {member.nickname}({member.qq}): {reason}")

                with _state_lock:
                    if _state._stop.is_set():
                        break
                if interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)

        except Exception as exc:
            _log(f"\u5f02\u5e38\u7ec8\u6b62: {exc}")
            with _state_lock:
                _state.message = str(exc)
        finally:
            with _state_lock:
                _state.running = False
                if not _state.message.startswith("\u5df2\u505c"):
                    _state.message = "\u5df2\u5b8c\u6210"
            _log("\u4efb\u52a1\u7ed3\u675f")

    threading.Thread(target=worker, daemon=True).start()


def token_owner_safe(capture_dir, qq: int, token: str) -> bool:
    from capture_utils import lookup_token_owner

    owner = lookup_token_owner(capture_dir, token)
    if owner is not None and owner != qq:
        return False
    return True
