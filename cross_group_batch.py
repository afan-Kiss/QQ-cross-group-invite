# -*- coding: utf-8 -*-
"""Batch cross-group invite engine with member filtering."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
RATE_BUCKET_SEC = 5
RATE_RETENTION_SEC = 5 * 60
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QQCrossGroupInvite" / "data"
TASKS_FILE = DATA_DIR / "tasks.json"


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    UNKNOWN = "unknown"


class TaskRunStatus(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class TaskIdMismatch(Exception):
    """Raised when stop_batch(task_id=...) does not match the live task."""

    def __init__(self, requested: str, current: str) -> None:
        self.requested = requested
        self.current = current
        super().__init__(
            f"task_id mismatch: requested={requested!r} current={current!r}"
        )


class InviteResultStatus(str, Enum):
    WAITING = "waiting"
    INVITING = "inviting"
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    FILTERED = "filtered"


@dataclass
class SourceMember:
    qq: int
    nickname: str
    token: str
    role: MemberRole = MemberRole.MEMBER
    card: str = ""
    eligible: bool = True
    filter_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "token": self.token,
            "role": self.role.value,
            "card": self.card,
            "eligible": self.eligible,
            "filter_reason": self.filter_reason,
        }


@dataclass
class InviteRecord:
    qq: int
    nickname: str
    reason: str
    at: float = field(default_factory=time.time)
    source_group_id: int = 0
    target_group_id: int = 0
    task_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "reason": self.reason,
            "at": self.at,
            "source_group_id": self.source_group_id,
            "target_group_id": self.target_group_id,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class MembersCacheSnapshot:
    source_group_id: int
    filter_staff: bool
    members: tuple[SourceMember, ...]

    @property
    def key(self) -> tuple[int, bool]:
        return (self.source_group_id, self.filter_staff)


@dataclass
class InviteResult:
    qq: int
    nickname: str
    status: InviteResultStatus = InviteResultStatus.WAITING
    reason: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "status": self.status.value,
            "reason": self.reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }


@dataclass
class RateBucket:
    timestamp: int
    success: int = 0
    failed: int = 0
    rate_limited: int = 0

    @property
    def total(self) -> int:
        return self.success + self.failed + self.rate_limited

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "success": self.success,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "total": self.total,
        }


@dataclass
class BatchState:
    running: bool = False
    status: TaskRunStatus = TaskRunStatus.IDLE
    task_id: str = ""
    total: int = 0
    done: int = 0
    success: int = 0
    current_qq: int = 0
    current_nickname: str = ""
    message: str = ""
    error_message: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    source_group_id: int = 0
    target_group_id: int = 0
    batch_size: int = 20
    interval_ms: int = 1500
    batch_number: int = 0
    batch_total_count: int = 0
    batch_done: int = 0
    total_batches: int = 0
    next_invite_at: float = 0.0
    failed_count: int = 0
    rate_limited_count: int = 0
    frequent: list[InviteRecord] = field(default_factory=list)
    errors: list[InviteRecord] = field(default_factory=list)
    results: list[InviteResult] = field(default_factory=list)
    rate_series: list[RateBucket] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> dict[str, Any]:
        now = time.time()
        remaining = 0
        if self.running and self.next_invite_at > now:
            remaining = int(max(0, (self.next_invite_at - now) * 1000))
        return {
            "running": self.running,
            "status": self.status.value,
            "task_id": self.task_id,
            "total": self.total,
            "done": self.done,
            "success": self.success,
            "current_qq": self.current_qq,
            "current_nickname": self.current_nickname,
            "message": self.message,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "source_group_id": self.source_group_id,
            "target_group_id": self.target_group_id,
            "batch_size": self.batch_size,
            "batch_count": self.batch_size,
            "interval_ms": self.interval_ms,
            "batch_number": self.batch_number,
            "batch_total_count": self.batch_total_count or self.batch_size,
            "batch_done": self.batch_done,
            "total_batches": self.total_batches,
            "next_invite_at": self.next_invite_at,
            "interval_remaining_ms": remaining,
            "rate_limited": self.rate_limited_count,
            "failed": self.failed_count,
            "rate_limited_count": self.rate_limited_count,
            "failed_count": self.failed_count,
            "frequent": [x.to_dict() for x in self.frequent],
            "errors": [x.to_dict() for x in self.errors],
            "results": [x.to_dict() for x in self.results],
            "rate_series": [x.to_dict() for x in self.rate_series],
            "logs": self.logs[-200:],
            "timeline": list(self.timeline),
        }


_state = BatchState()
_state_lock = threading.RLock()
_members_lock = threading.RLock()
_members_snapshot: MembersCacheSnapshot | None = None
_owned_task_id: str | None = None
_tasks_io_lock = threading.Lock()
_STALE_STATUSES = frozenset(
    {
        TaskRunStatus.PREPARING.value,
        TaskRunStatus.RUNNING.value,
        TaskRunStatus.STOPPING.value,
    }
)
_STALE_MSG = "上次运行异常中断（进程退出）"


def _now() -> float:
    return time.time()


def _make_task_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def _append_timeline(event: str, detail: str = "") -> None:
    _state.timeline.append(
        {"at": _now(), "event": event, "detail": detail}
    )


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _state_lock:
        _state.logs.append(line)
        if len(_state.logs) > 500:
            _state.logs = _state.logs[-300:]


def _interruptible_wait(seconds: float) -> bool:
    """Wait up to seconds. Returns True if stop was requested."""
    if seconds <= 0:
        return _state._stop.is_set()
    return _state._stop.wait(seconds)


def _record_rate(kind: str) -> None:
    bucket_ts = int(_now() // RATE_BUCKET_SEC) * RATE_BUCKET_SEC
    cutoff = _now() - RATE_RETENTION_SEC
    series = _state.rate_series
    if not series or series[-1].timestamp != bucket_ts:
        series.append(RateBucket(timestamp=bucket_ts))
    bucket = series[-1]
    if kind == "success":
        bucket.success += 1
    elif kind == "rate_limited":
        bucket.rate_limited += 1
    else:
        bucket.failed += 1
    _state.rate_series = [b for b in series if b.timestamp >= cutoff]


def _tasks_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TASKS_FILE


def _tasks_bak_path(path: Path | None = None) -> Path:
    p = path or _tasks_path()
    return p.with_name(p.name + ".bak")


def _read_tasks_file(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else []


def _load_tasks_unlocked() -> list[dict[str, Any]]:
    path = _tasks_path()
    if not path.is_file():
        return []
    try:
        return _read_tasks_file(path)
    except OSError as exc:
        logger.warning("failed to read tasks.json: %s", exc)
        return []
    except json.JSONDecodeError as exc:
        logger.warning("tasks.json corrupt (%s); trying .bak", exc)
        bak = _tasks_bak_path(path)
        if bak.is_file():
            try:
                return _read_tasks_file(bak)
            except (OSError, json.JSONDecodeError) as bak_exc:
                logger.error("tasks.json.bak also unreadable: %s", bak_exc)
        else:
            logger.error("tasks.json corrupt and no .bak available")
        return []


def _load_tasks() -> list[dict[str, Any]]:
    with _tasks_io_lock:
        return _load_tasks_unlocked()


def _save_tasks_unlocked(tasks: list[dict[str, Any]]) -> None:
    path = _tasks_path()
    payload = json.dumps(tasks[-200:], ensure_ascii=False, indent=2)
    if path.is_file():
        try:
            _read_tasks_file(path)
        except (OSError, json.JSONDecodeError):
            pass
        else:
            try:
                bak = _tasks_bak_path(path)
                bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError as exc:
                logger.warning("failed to write tasks.json.bak: %s", exc)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        logger.error("atomic tasks.json write failed: %s", exc)
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass
        raise


def _save_tasks(tasks: list[dict[str, Any]]) -> None:
    with _tasks_io_lock:
        _save_tasks_unlocked(tasks)


def recover_stale_tasks() -> int:
    """Mark non-live preparing/running/stopping tasks as interrupted. Returns count."""
    with _state_lock:
        live_id = _state.task_id if _state.running else ""
        live_status = _state.status.value if _state.running else ""
        if live_status not in _STALE_STATUSES:
            live_id = ""

    with _tasks_io_lock:
        tasks = _load_tasks_unlocked()
        if not tasks:
            return 0
        changed = 0
        now = _now()
        for item in tasks:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "")
            tid = str(item.get("id") or "")
            if status in _STALE_STATUSES and tid and tid != live_id:
                item["status"] = TaskRunStatus.INTERRUPTED.value
                item["finished_at"] = item.get("finished_at") or now
                item["error_message"] = _STALE_MSG
                item["stop_reason"] = "process_exit"
                changed += 1
        if changed:
            _save_tasks_unlocked(tasks)
        return changed


def _upsert_task_record(record: dict[str, Any]) -> None:
    with _tasks_io_lock:
        tasks = _load_tasks_unlocked()
        tid = record.get("id")
        replaced = False
        for i, item in enumerate(tasks):
            if item.get("id") == tid:
                tasks[i] = {**item, **record}
                replaced = True
                break
        if not replaced:
            tasks.append(record)
        _save_tasks_unlocked(tasks)


def list_tasks() -> list[dict[str, Any]]:
    with _state_lock:
        current = None
        if _state.task_id:
            current = {
                "id": _state.task_id,
                "source_group_id": _state.source_group_id,
                "target_group_id": _state.target_group_id,
                "created_at": _state.started_at,
                "started_at": _state.started_at,
                "finished_at": _state.finished_at,
                "status": _state.status.value,
                "selected_count": _state.total,
                "total": _state.total,
                "success": _state.success,
                "rate_limited": _state.rate_limited_count,
                "failed": _state.failed_count,
                "batch_size": _state.batch_size,
                "interval_ms": _state.interval_ms,
                "stop_reason": "",
                "error_message": _state.error_message,
                "timeline": list(_state.timeline),
            }
    tasks = _load_tasks()
    if current:
        found = False
        for i, t in enumerate(tasks):
            if t.get("id") == current["id"]:
                tasks[i] = {**t, **current}
                found = True
                break
        if not found:
            tasks.append(current)
    tasks.sort(key=lambda x: float(x.get("started_at") or x.get("created_at") or 0), reverse=True)
    return tasks


def get_task(task_id: str) -> dict[str, Any] | None:
    for t in list_tasks():
        if t.get("id") == task_id:
            return t
    return None


def _persist_current_task(**extra: Any) -> None:
    with _state_lock:
        if not _state.task_id:
            return
        record = {
            "id": _state.task_id,
            "source_group_id": _state.source_group_id,
            "target_group_id": _state.target_group_id,
            "created_at": _state.started_at,
            "started_at": _state.started_at,
            "finished_at": _state.finished_at,
            "status": _state.status.value,
            "selected_count": _state.total,
            "total": _state.total,
            "success": _state.success,
            "rate_limited": _state.rate_limited_count,
            "failed": _state.failed_count,
            "batch_size": _state.batch_size,
            "interval_ms": _state.interval_ms,
            "stop_reason": extra.get("stop_reason", ""),
            "error_message": _state.error_message,
            "timeline": list(_state.timeline),
        }
    _upsert_task_record(record)


def clear_logs() -> None:
    with _state_lock:
        _state.logs.clear()


def clear_failed() -> None:
    with _state_lock:
        _state.errors.clear()


def clear_rate_limits() -> None:
    with _state_lock:
        _state.frequent.clear()


def clear_state(kinds: list[str] | None = None) -> None:
    if not kinds:
        kinds = ["logs", "failed", "rate_limits"]
    if "logs" in kinds:
        clear_logs()
    if "failed" in kinds:
        clear_failed()
    if "rate_limits" in kinds or "frequent" in kinds:
        clear_rate_limits()


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
        return "操作太频繁"
    if code is not None:
        return f"邀请失败（错误码 {code}）"
    return "邀请失败"


def _classify_failure(code: int | None, msg: str) -> str:
    text = msg or ""
    if code == 1289:
        return "frequent"
    if any(k in text for k in ("频繁", "操作频繁", "too fast", "rate")):
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
    """Load full member set. Staff are marked filtered when filter_staff=True."""
    global _members_snapshot
    cfg = load_cfg()
    cap = capture_dir or resolve_capture_dir(cfg)

    def log(msg: str) -> None:
        if record_logs:
            _log(msg)

    log(f"正在加载来源群成员，群号={source_group_id}...")

    token_map = fetch_fe7_token_map_live(cap, source_group_id)
    if not token_map:
        token_map = scan_capture_fe7_token_map(cap)
        if token_map:
            log("实时拉不到成员，已从抓包记录恢复")
        else:
            log("拉取成员列表失败，请确认群号正确且 NapCat 在线")
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
        nick = str(item.get("nickname") or item.get("nick") or str(qq))
        card = str(item.get("card") or "")
        token = token_map.get(qq, "")
        if not token:
            continue
        is_staff = role in (MemberRole.OWNER, MemberRole.ADMIN)
        eligible = not (filter_staff and is_staff)
        filter_reason = ""
        if filter_staff and is_staff:
            filter_reason = "群主" if role == MemberRole.OWNER else "管理员"
        by_qq[qq] = SourceMember(
            qq=qq,
            nickname=nick,
            token=token,
            role=role,
            card=card,
            eligible=eligible,
            filter_reason=filter_reason,
        )

    if not by_qq and token_map:
        for qq, token in token_map.items():
            if qq < 10000:
                continue
            by_qq[qq] = SourceMember(
                qq=qq,
                nickname=str(qq),
                token=token,
                role=MemberRole.UNKNOWN,
                eligible=True,
            )

    members = sorted(by_qq.values(), key=lambda m: m.qq)
    snapshot = MembersCacheSnapshot(
        source_group_id=int(source_group_id),
        filter_staff=bool(filter_staff),
        members=tuple(members),
    )
    with _members_lock:
        _members_snapshot = snapshot
    eligible_count = sum(1 for m in members if m.eligible)
    filtered_count = len(members) - eligible_count
    log(
        f"已加载 {len(members)} 名成员（可邀请 {eligible_count}，已过滤 {filtered_count}，"
        f"过滤群主/管理员={filter_staff}）"
    )
    return list(members)


def get_cached_members() -> list[SourceMember]:
    with _members_lock:
        snap = _members_snapshot
    if snap is None:
        return []
    return list(snap.members)


def get_state() -> dict[str, Any]:
    with _state_lock:
        return _state.to_dict()


def stop_batch(task_id: str | None = None) -> None:
    with _state_lock:
        if task_id is not None:
            current = _state.task_id or ""
            if task_id != current:
                raise TaskIdMismatch(task_id, current)
        if not _state.running and _state.status not in (
            TaskRunStatus.PREPARING,
            TaskRunStatus.RUNNING,
        ):
            return
        _state._stop.set()
        _state.status = TaskRunStatus.STOPPING
        _state.message = "正在停止..."
    _log("收到停止请求")


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


def _update_result(qq: int, **fields: Any) -> None:
    for r in _state.results:
        if r.qq == qq:
            for k, v in fields.items():
                setattr(r, k, v)
            return


def _finish_member(
    member: SourceMember,
    *,
    status: InviteResultStatus,
    reason: str,
    started_at: float,
) -> None:
    finished = _now()
    duration = int(max(0, (finished - started_at) * 1000)) if started_at else 0
    with _state_lock:
        rec = InviteRecord(
            qq=member.qq,
            nickname=member.nickname,
            reason=reason,
            source_group_id=_state.source_group_id,
            target_group_id=_state.target_group_id,
            task_id=_state.task_id,
        )
        _state.done += 1
        if _state.batch_size > 0:
            _state.batch_done += 1
            if _state.batch_number <= 0:
                _state.batch_number = ((_state.done - 1) // _state.batch_size) + 1
        _update_result(
            member.qq,
            status=status,
            reason=reason,
            started_at=started_at,
            finished_at=finished,
            duration_ms=duration,
        )
        if status == InviteResultStatus.SUCCESS:
            _state.success += 1
            _record_rate("success")
        elif status == InviteResultStatus.RATE_LIMITED:
            _state.frequent.append(rec)
            _state.rate_limited_count += 1
            _record_rate("rate_limited")
            _append_timeline("rate_limited", f"{member.nickname}({member.qq})")
        elif status == InviteResultStatus.FAILED:
            _state.errors.append(rec)
            _state.failed_count += 1
            _record_rate("failed")
            _append_timeline("failed", f"{member.nickname}({member.qq}): {reason}")


def start_batch(
    *,
    target_group_id: int,
    source_group_id: int,
    count: int = 0,
    interval_ms: int = 1500,
    filter_staff: bool = True,
    qq_list: list[int] | None = None,
    batch_size: int | None = None,
) -> str:
    """Start invite batch. count is ignored when qq_list is provided.
    batch_size = per-batch size (not total invite count).
    """
    global _owned_task_id
    resolved_batch_size = int(batch_size if batch_size is not None else (count or 20))
    if resolved_batch_size < 1:
        resolved_batch_size = 20
    if resolved_batch_size > 1000:
        raise ValueError("每批人数必须在 1-1000 之间")
    if interval_ms < 100 or interval_ms > 600000:
        raise ValueError("邀请间隔必须在 100-600000 毫秒之间")
    if target_group_id <= 0 or source_group_id <= 0:
        raise ValueError("群号必须为正整数")
    if target_group_id == source_group_id:
        raise ValueError("目标群和来源群不能相同")

    cleaned_qq: list[int] | None = None
    if qq_list is not None:
        seen: set[int] = set()
        cleaned_qq = []
        for x in qq_list:
            q = int(x)
            if q <= 0:
                raise ValueError("qq_list 包含无效 QQ 号")
            if q not in seen:
                seen.add(q)
                cleaned_qq.append(q)
        if not cleaned_qq:
            raise ValueError("请至少选择一名成员")

    task_id = _make_task_id()
    with _state_lock:
        if _state.running:
            raise RuntimeError("上一次邀请还没结束，请稍后再试")
        _state._stop.clear()
        _state.running = True
        _state.status = TaskRunStatus.PREPARING
        _state.task_id = task_id
        _state.total = 0
        _state.done = 0
        _state.success = 0
        _state.failed_count = 0
        _state.rate_limited_count = 0
        _state.current_qq = 0
        _state.current_nickname = ""
        _state.frequent.clear()
        _state.errors.clear()
        _state.results.clear()
        _state.rate_series.clear()
        _state.logs.clear()
        _state.timeline.clear()
        _state.message = "准备中..."
        _state.error_message = ""
        _state.started_at = _now()
        _state.finished_at = 0.0
        _state.source_group_id = source_group_id
        _state.target_group_id = target_group_id
        _state.batch_size = resolved_batch_size
        _state.interval_ms = interval_ms
        _state.batch_number = 0
        _state.batch_done = 0
        _state.batch_total_count = resolved_batch_size
        _state.total_batches = 0
        _state.next_invite_at = 0.0
        _owned_task_id = task_id
        _append_timeline("created", task_id)

    _persist_current_task()

    def worker() -> None:
        final_status = TaskRunStatus.COMPLETED
        final_message = "已完成"
        error_message = ""
        cfg = load_cfg()
        cap = resolve_capture_dir(cfg)
        try:
            cache_key = (int(source_group_id), bool(filter_staff))
            with _members_lock:
                snap = _members_snapshot
            if snap is not None and snap.key == cache_key and snap.members:
                members = list(snap.members)
            else:
                members = load_source_members(
                    source_group_id,
                    filter_staff=filter_staff,
                    capture_dir=cap,
                    record_logs=True,
                )
                with _state_lock:
                    _append_timeline("members_loaded", str(len(members)))

            # Only invite eligible members; honor qq_list selection
            invite_members = [m for m in members if m.eligible]
            if cleaned_qq is not None:
                allow = set(cleaned_qq)
                invite_members = [m for m in invite_members if m.qq in allow]
                missing = allow - {m.qq for m in invite_members}
                if missing and not invite_members:
                    raise RuntimeError("所选成员均不可邀请（可能已被过滤或缺少 Token）")

            with _state_lock:
                _state.total = len(invite_members)
                _state.total_batches = (
                    (len(invite_members) + resolved_batch_size - 1) // resolved_batch_size
                    if invite_members
                    else 0
                )
                _state.results = [
                    InviteResult(qq=m.qq, nickname=m.nickname)
                    for m in invite_members
                ]
                _state.status = TaskRunStatus.RUNNING
                _state.message = "邀请运行中"
                _append_timeline("started", f"total={len(invite_members)}")
            _persist_current_task()

            if not invite_members:
                raise RuntimeError("没有可邀请成员")

            _log("正在准备跨群邀请...")
            live_fe7 = open_cross_group_picker(cap, target_group_id, source_group_id)
            context_token = query_source_context_token(
                cap, source_group_id, live_rsp=live_fe7
            )
            if not context_token:
                raise RuntimeError(
                    "无法获取来源群信息，请确认群号正确，并保留过跨群邀请的抓包记录"
                )

            for idx, member in enumerate(invite_members):
                if _state._stop.is_set():
                    final_status = TaskRunStatus.STOPPED
                    final_message = "已停止"
                    break

                started_at = _now()
                with _state_lock:
                    if idx % resolved_batch_size == 0:
                        batch_no = (idx // resolved_batch_size) + 1
                        remaining = len(invite_members) - idx
                        _state.batch_number = batch_no
                        _state.batch_done = 0
                        _state.batch_total_count = min(resolved_batch_size, remaining)
                        _append_timeline("batch_start", f"batch={batch_no}")
                    _state.current_qq = member.qq
                    _state.current_nickname = member.nickname
                    _state.message = f"邀请 {member.nickname}({member.qq})"
                    _update_result(
                        member.qq,
                        status=InviteResultStatus.INVITING,
                        started_at=started_at,
                    )

                token = member.token
                if not token or not token_owner_safe(cap, member.qq, token):
                    fresh = query_invitee_token(cap, source_group_id, member.qq)
                    if fresh:
                        token = fresh
                        member.token = fresh
                if not token:
                    reason = "找不到该成员的邀请信息"
                    _finish_member(
                        member,
                        status=InviteResultStatus.FAILED,
                        reason=reason,
                        started_at=started_at,
                    )
                    _log(f"失败 {member.nickname}({member.qq}): {reason}")
                elif context_token == token:
                    reason = "来源群信息与成员信息冲突，请重新加载成员"
                    _finish_member(
                        member,
                        status=InviteResultStatus.FAILED,
                        reason=reason,
                        started_at=started_at,
                    )
                    _log(f"失败 {member.nickname}({member.qq}): {reason}")
                else:
                    ok, code, msg = _invite_one(
                        target_group_id=target_group_id,
                        source_group_id=source_group_id,
                        context_token=context_token,
                        member=member,
                        capture_dir=cap,
                    )
                    reason = msg or _failure_reason(code)
                    kind = _classify_failure(code, reason)
                    if ok:
                        _finish_member(
                            member,
                            status=InviteResultStatus.SUCCESS,
                            reason="",
                            started_at=started_at,
                        )
                        _log(f"成功 {member.nickname}({member.qq})")
                    elif kind == "frequent":
                        _finish_member(
                            member,
                            status=InviteResultStatus.RATE_LIMITED,
                            reason=reason,
                            started_at=started_at,
                        )
                        _log(f"频繁 {member.nickname}({member.qq}): {reason}")
                    else:
                        _finish_member(
                            member,
                            status=InviteResultStatus.FAILED,
                            reason=reason,
                            started_at=started_at,
                        )
                        _log(f"失败 {member.nickname}({member.qq}): {reason}")

                if _state._stop.is_set():
                    final_status = TaskRunStatus.STOPPED
                    final_message = "已停止"
                    break

                if interval_ms > 0 and idx < len(invite_members) - 1:
                    with _state_lock:
                        _state.next_invite_at = _now() + (interval_ms / 1000.0)
                    if _interruptible_wait(interval_ms / 1000.0):
                        final_status = TaskRunStatus.STOPPED
                        final_message = "已停止"
                        break
                    with _state_lock:
                        _state.next_invite_at = 0.0

        except Exception as exc:
            final_status = TaskRunStatus.ERROR
            final_message = str(exc)
            error_message = str(exc)
            _log(f"异常终止: {exc}")
        finally:
            with _state_lock:
                _state.running = False
                _state.current_qq = 0
                _state.current_nickname = ""
                _state.next_invite_at = 0.0
                _state.finished_at = _now()
                _state.status = final_status
                _state.message = final_message
                _state.error_message = error_message
                if final_status == TaskRunStatus.STOPPED:
                    _append_timeline("stopped", final_message)
                elif final_status == TaskRunStatus.ERROR:
                    _append_timeline("error", error_message)
                else:
                    _append_timeline("completed", final_message)
            _persist_current_task(
                stop_reason="user" if final_status == TaskRunStatus.STOPPED else ""
            )
            _log("任务结束")

    threading.Thread(target=worker, daemon=True, name="invite-worker").start()
    return task_id


def token_owner_safe(capture_dir, qq: int, token: str) -> bool:
    from capture_utils import lookup_token_owner

    owner = lookup_token_owner(capture_dir, token)
    if owner is not None and owner != qq:
        return False
    return True


def owns_task(task_id: str | None) -> bool:
    with _state_lock:
        return bool(task_id) and task_id == _owned_task_id and _state.running
