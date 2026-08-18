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
    scan_capture_fe7_token_map,
)
from myqq_api import load_cfg, onebot_action
from pb_utils import describe_token, parse_758_recv_status
from pull_cross_group import (
    PickerSession,
    PickerStopped,
    _rsp_hex,
    open_cross_group_picker,
    probe_source_group_fe7,
    query_invitee_token,
    resolve_capture_dir,
    send_cross_group_invite,
    sync_fe1_selection,
    wait_target_membership,
)

RATE_BUCKET_SEC = 5
RATE_RETENTION_SEC = 5 * 60
# UI batch_count stays 1-1000. Per-packet size is the largest verified FE1 list (10 tokens / 276B).
# Captured 758 success is 2 and 6 blocks; the repeated-block builder allows N>=1 including a final packet of 1.
PROTOCOL_INVITE_PACKET_MAX = 10
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
    CANCELLED = "cancelled"


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

    def to_public_dict(self) -> dict[str, Any]:
        """API-safe member row: raw invite token never leaves the backend."""
        return {
            "qq": self.qq,
            "nickname": self.nickname,
            "token": "",
            "has_token": bool(self.token),
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
    context_token: str = ""

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
    token_map, context, _rsp = probe_source_group_fe7(capture_dir, source_group_id)
    fetch_fe7_token_map_live.last_context = (int(source_group_id), context or "")
    return token_map


def _onebot_error_message(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    code = raw.get("code")
    status = str(raw.get("status") or "").lower()
    retcode = raw.get("retcode")
    failed = False
    if code not in (None, 0, "0"):
        failed = True
    if status in {"failed", "error"}:
        failed = True
    if retcode not in (None, 0, "0") and status != "ok":
        failed = True
    if not failed:
        return ""
    return str(raw.get("message") or raw.get("wording") or raw.get("msg") or raw)


def _onebot_members(source_group_id: int) -> list[dict[str, Any]]:
    try:
        raw = onebot_action(
            "get_group_member_list",
            {"group_id": int(source_group_id)},
            timeout=60,
        )
    except Exception as exc:
        raise RuntimeError(f"拉取成员列表失败: {exc}") from exc
    err = _onebot_error_message(raw)
    if err:
        raise RuntimeError(f"拉取成员列表失败: {err}")
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        inner = raw.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("data"), list):
            inner = inner.get("data")
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

    ob_list = _onebot_members(source_group_id)
    token_map: dict[int, str] = {}
    try:
        token_map = fetch_fe7_token_map_live(cap, source_group_id) or {}
    except Exception as exc:
        log(f"实时邀请 Token 拉取失败，继续用来源群成员列表: {exc}")
        token_map = {}
    if not token_map:
        try:
            token_map = scan_capture_fe7_token_map(cap) or {}
            if token_map:
                log("实时拉不到 Token，已从抓包记录恢复")
        except Exception:
            token_map = {}
    if not ob_list and not token_map:
        log("拉取成员列表失败，请确认来源群号正确且饭饭定制在线")
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
            # No OneBot roles available: when filtering staff, unknowns must not be invitible.
            eligible = not bool(filter_staff)
            by_qq[qq] = SourceMember(
                qq=qq,
                nickname=str(qq),
                token=token,
                role=MemberRole.UNKNOWN,
                eligible=eligible,
                filter_reason="角色未知" if filter_staff else "",
            )

    members = sorted(by_qq.values(), key=lambda m: m.qq)
    context_token = ""
    last_ctx = getattr(fetch_fe7_token_map_live, "last_context", None)
    if (
        isinstance(last_ctx, tuple)
        and len(last_ctx) == 2
        and last_ctx[0] == int(source_group_id)
    ):
        context_token = str(last_ctx[1] or "")
    snapshot = MembersCacheSnapshot(
        source_group_id=int(source_group_id),
        filter_staff=bool(filter_staff),
        members=tuple(members),
        context_token=context_token,
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


def _invite_batch(
    *,
    target_group_id: int,
    source_group_id: int,
    members: list[SourceMember],
    tokens: list[str],
    capture_dir,
) -> list[tuple[SourceMember, str, int | None, str]]:
    """One FE1 + one N-block 758 for this batch. Tokens must be picker-fresh.

    Outcome kind: success | failed | rate_limited | cancelled
    cancelled = stopped before 758 was sent (not a protocol failure).
    After 758 is sent, membership verify always completes for this batch.
    """
    results: list[tuple[SourceMember, str, int | None, str]] = []
    if len(members) != len(tokens) or not members:
        return [
            (m, "failed", None, "当前选择器会话没有返回该成员的邀请凭证")
            for m in members
        ]
    stop_event = _state._stop
    packet_max = max(1, int(PROTOCOL_INVITE_PACKET_MAX))
    for offset in range(0, len(members), packet_max):
        sub_members = members[offset : offset + packet_max]
        sub_tokens = tokens[offset : offset + packet_max]
        if stop_event.is_set():
            results.extend(
                (m, "cancelled", None, "已停止，未发送邀请") for m in sub_members
            )
            continue
        try:
            if not sync_fe1_selection(capture_dir, sub_tokens, stop_event=stop_event):
                if stop_event.is_set():
                    results.extend(
                        (m, "cancelled", None, "已停止，未发送邀请") for m in sub_members
                    )
                    continue
                reason = "跨群选择同步失败，未发送邀请"
                results.extend((m, "failed", None, reason) for m in sub_members)
                continue
            if stop_event.is_set():
                results.extend(
                    (m, "cancelled", None, "已停止，未发送邀请") for m in sub_members
                )
                continue
            ok, resp = send_cross_group_invite(
                target_group_id=target_group_id,
                source_group_id=source_group_id,
                invitee_tokens=sub_tokens,
                capture_dir=capture_dir,
                stop_event=stop_event,
            )
        except PickerStopped:
            results.extend(
                (m, "cancelled", None, "已停止，未发送邀请") for m in sub_members
            )
            continue
        rsp_hex = _rsp_hex(resp)
        code, _ = parse_758_recv_status(rsp_hex) if rsp_hex else (None, False)
        msg = _extract_error_text(rsp_hex)
        if not ok:
            if isinstance(resp, dict) and resp.get("error") == "stopped":
                results.extend(
                    (m, "cancelled", None, "已停止，未发送邀请") for m in sub_members
                )
                continue
            if not msg and isinstance(resp, dict):
                msg = str(resp.get("message") or resp.get("wording") or resp.get("error") or "")
            if not msg and code is None:
                msg = "758 返回无法确认邀请成功"
            results.extend((m, "failed", code, msg) for m in sub_members)
            continue
        # 758 already sent: finish membership verify even if stop was requested.
        for member in sub_members:
            present = wait_target_membership(
                target_group_id,
                member.qq,
                stop_event=None,
            )
            if present is True:
                results.append((member, "success", code, ""))
            elif present is False:
                results.append(
                    (member, "failed", code, "服务器响应已返回，但目标群成员未出现")
                )
            else:
                results.append(
                    (member, "failed", code, "758 已返回，但无法确认目标群成员")
                )
    return results


def _update_result(qq: int, **fields: Any) -> None:
    for r in _state.results:
        if r.qq == qq:
            for k, v in fields.items():
                setattr(r, k, v)
            return


def _mark_unsent_cancelled(member: SourceMember, *, reason: str, started_at: float) -> None:
    """Stop before 758: not a protocol failure, do not increment failed_count."""
    finished = _now()
    duration = int(max(0, (finished - started_at) * 1000)) if started_at else 0
    with _state_lock:
        already = next((r for r in _state.results if r.qq == member.qq), None)
        if already and already.status not in (
            InviteResultStatus.WAITING,
            InviteResultStatus.INVITING,
        ):
            return
        counted = already is None or already.status in (
            InviteResultStatus.WAITING,
            InviteResultStatus.INVITING,
        )
        _update_result(
            member.qq,
            status=InviteResultStatus.CANCELLED,
            reason=reason,
            started_at=started_at,
            finished_at=finished,
            duration_ms=duration,
        )
        if counted:
            _state.done += 1
            if _state.batch_size > 0:
                _state.batch_done += 1
        _append_timeline("stopped", f"{member.nickname}({member.qq}): {reason}")


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
        elif status == InviteResultStatus.CANCELLED:
            _append_timeline("stopped", f"{member.nickname}({member.qq}): {reason}")


def _cancel_remaining_unsent(reason: str = "已停止，未发送邀请") -> None:
    """Mark WAITING/INVITING rows cancelled without counting them as protocol failures."""
    with _state_lock:
        pending = [
            r
            for r in _state.results
            if r.status in (InviteResultStatus.WAITING, InviteResultStatus.INVITING)
        ]
    for row in pending:
        member = SourceMember(qq=row.qq, nickname=row.nickname, token="")
        _mark_unsent_cancelled(member, reason=reason, started_at=row.started_at or _now())


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
    if resolved_batch_size < 1 or resolved_batch_size > 1000:
        raise ValueError("batch_count must be 1-1000")
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
        cache_key = (int(source_group_id), bool(filter_staff))
        with _members_lock:
            snap = _members_snapshot
        if snap is not None and snap.key == cache_key and snap.members:
            by_qq = {m.qq: m for m in snap.members}
            for q in cleaned_qq:
                m = by_qq.get(q)
                if m is None or not m.eligible:
                    raise ValueError("所选成员状态已变化，请重新加载成员后再试")

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
        _append_timeline("created", "任务已创建")

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
                with _members_lock:
                    snap = _members_snapshot
                with _state_lock:
                    _append_timeline("members_loaded", f"已加载 {len(members)} 名成员")

            # Only invite eligible members; honor qq_list selection.
            # Never silently drop selected QQs: any invalid selection rejects the whole start.
            invite_members = [m for m in members if m.eligible]
            if cleaned_qq is not None:
                allow = set(cleaned_qq)
                invite_members = [m for m in invite_members if m.qq in allow]
                missing = allow - {m.qq for m in invite_members}
                if missing:
                    raise RuntimeError("所选成员状态已变化，请重新加载成员后再试")

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
                _append_timeline("started", f"开始邀请，一共 {len(invite_members)} 人")
            _persist_current_task()

            if not invite_members:
                raise RuntimeError("没有可邀请成员")

            batches = [
                invite_members[i : i + resolved_batch_size]
                for i in range(0, len(invite_members), resolved_batch_size)
            ]
            for batch_idx, chunk in enumerate(batches):
                if _state._stop.is_set():
                    final_status = TaskRunStatus.STOPPED
                    final_message = "已停止"
                    break

                started_at_by_qq: dict[int, float] = {}
                with _state_lock:
                    _state.batch_number = batch_idx + 1
                    _state.batch_done = 0
                    _state.batch_total_count = len(chunk)
                    _append_timeline("batch_start", f"开始第 {batch_idx + 1} 批")
                    if chunk:
                        _state.current_qq = chunk[0].qq
                        _state.current_nickname = chunk[0].nickname
                        _state.message = f"邀请 {chunk[0].nickname}({chunk[0].qq})"

                for member in chunk:
                    started_at = _now()
                    started_at_by_qq[member.qq] = started_at
                    with _state_lock:
                        _update_result(
                            member.qq,
                            status=InviteResultStatus.INVITING,
                            started_at=started_at,
                        )

                desired = [m.qq for m in chunk]
                _log(f"正在准备第 {batch_idx + 1} 批跨群邀请凭证...")
                try:
                    picker = open_cross_group_picker(
                        cap,
                        target_group_id,
                        source_group_id,
                        desired_qqs=desired,
                        stop_event=_state._stop,
                    )
                except PickerStopped:
                    for member in chunk:
                        _mark_unsent_cancelled(
                            member,
                            reason="已停止，未发送邀请",
                            started_at=started_at_by_qq.get(member.qq, _now()),
                        )
                    final_status = TaskRunStatus.STOPPED
                    final_message = "已停止"
                    break

                if picker is None:
                    raise RuntimeError(
                        "来源群成员已加载，但跨群邀请凭证未准备成功"
                    )
                picker_map = dict(getattr(picker, "token_map", None) or {})

                ready: list[SourceMember] = []
                ready_tokens: list[str] = []
                for member in chunk:
                    started_at = started_at_by_qq.get(member.qq, _now())
                    fresh = picker_map.get(int(member.qq)) or ""
                    if member.token and fresh and member.token != fresh:
                        _log(
                            f"picker token 覆盖旧凭证 {member.nickname}({member.qq}) "
                            f"stale={describe_token(member.token)} fresh={describe_token(fresh)}"
                        )
                    if not fresh:
                        reason = "当前选择器会话没有返回该成员的邀请凭证"
                        if getattr(picker, "hit_page_limit", False):
                            reason = (
                                "FE7 分页达到安全上限，当前选择器会话没有返回该成员的邀请凭证"
                            )
                        _finish_member(
                            member,
                            status=InviteResultStatus.FAILED,
                            reason=reason,
                            started_at=started_at,
                        )
                        _log(f"失败 {member.nickname}({member.qq}): {reason}")
                        continue
                    ready.append(member)
                    ready_tokens.append(fresh)

                if _state._stop.is_set():
                    for member in ready:
                        _mark_unsent_cancelled(
                            member,
                            reason="已停止，未发送邀请",
                            started_at=started_at_by_qq.get(member.qq, _now()),
                        )
                    final_status = TaskRunStatus.STOPPED
                    final_message = "已停止"
                    break

                if ready:
                    batch_results = _invite_batch(
                        target_group_id=target_group_id,
                        source_group_id=source_group_id,
                        members=ready,
                        tokens=ready_tokens,
                        capture_dir=cap,
                    )
                    for member, kind_or_ok, code, msg in batch_results:
                        if isinstance(kind_or_ok, bool):
                            if kind_or_ok:
                                kind = "success"
                            elif _classify_failure(code, msg or "") == "frequent":
                                kind = "rate_limited"
                            else:
                                kind = "failed"
                        else:
                            kind = str(kind_or_ok or "failed")
                        reason = msg or _failure_reason(code)
                        started_at = started_at_by_qq.get(member.qq, _now())
                        if kind == "success":
                            _finish_member(
                                member,
                                status=InviteResultStatus.SUCCESS,
                                reason="",
                                started_at=started_at,
                            )
                            _log(f"成功 {member.nickname}({member.qq})")
                        elif kind == "cancelled":
                            _mark_unsent_cancelled(
                                member,
                                reason=reason or "已停止，未发送邀请",
                                started_at=started_at,
                            )
                            _log(f"已停止 {member.nickname}({member.qq}): {reason}")
                        elif kind == "rate_limited":
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

                if interval_ms > 0 and batch_idx < len(batches) - 1:
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
            if final_status == TaskRunStatus.STOPPED:
                _cancel_remaining_unsent()
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
