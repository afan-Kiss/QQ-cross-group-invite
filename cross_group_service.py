# -*- coding: utf-8 -*-
"""HTTP API for cross-group batch invite (desktop sidecar)."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import signal
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cross_group_batch import (
    TaskIdMismatch,
    clear_failed,
    clear_logs,
    clear_rate_limits,
    clear_state,
    get_cached_members,
    get_state,
    get_task,
    list_tasks,
    load_source_members,
    recover_stale_tasks,
    start_batch,
    stop_batch,
)
from myqq_api import check_napcat_online, load_cfg, onebot_action, save_cfg, test_napcat_connection
from napcat_health import get_napcat_cache, refresh_napcat_cache, start_napcat_health_refresh, stop_napcat_health_refresh
from log_settings import parse_log_settings, validate_log_settings_payload
from service_logger import setup_service_logger

WEB_DIR = Path(__file__).resolve().parent / "web"
PORT = 17888
SERVICE_ID = "cross-group-invite"
SERVICE_VERSION = "1.0.0"
HOST = "127.0.0.1"

SESSION_ID = ""
SESSION_REQUIRED = False
_server: ThreadingHTTPServer | None = None
logger = setup_service_logger()

ALLOWED_ORIGINS = {
    "http://wails.localhost",
    "https://wails.localhost",
    "http://wails.localhost:34115",
    "",
}

MUTATING_PATHS = frozenset(
    {
        "/config",
        "/members/load",
        "/invite/start",
        "/invite/stop",
        "/state/clear-logs",
        "/state/clear-failed",
        "/state/clear-rate-limits",
        "/state/clear",
        "/test-connection",
        "/napcat/refresh",
        "/shutdown",
    }
)

SENSITIVE_GET_PATHS = frozenset(
    {
        "/config",
        "/status",
        "/members",
        "/tasks",
    }
)


def _is_sensitive_get(path: str) -> bool:
    if path in SENSITIVE_GET_PATHS:
        return True
    if path.startswith("/tasks/"):
        return True
    return False


def _cors_headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    origin = handler.headers.get("Origin") or ""
    if origin in ALLOWED_ORIGINS:
        allow = origin
    else:
        allow = "http://wails.localhost"
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-App-Session",
        "Vary": "Origin",
    }


def _error(code: str, message: str, http_status: int = 400) -> tuple[int, dict[str, Any]]:
    return http_status, {"ok": False, "code": code, "message": message, "error": message}


def _ok(payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = {"ok": True}
    if payload:
        data.update(payload)
    return 200, data


def _json_response(handler: BaseHTTPRequestHandler, code: int, obj: Any) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    for k, v in _cors_headers(handler).items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _file_response(handler: BaseHTTPRequestHandler, path: Path) -> bool:
    if not path.is_file():
        return False
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "application/octet-stream"
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header(
        "Content-Type",
        f"{mime}; charset=utf-8" if mime.startswith("text/") or mime.endswith("javascript") else mime,
    )
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(data)
    return True


def _check_session(handler: BaseHTTPRequestHandler, required: bool = True) -> tuple[int, dict[str, Any]] | None:
    header = handler.headers.get("X-App-Session") or ""
    if not SESSION_ID:
        return None
    if header == SESSION_ID:
        return None
    if not required:
        # When ownership is optional: only reject if a wrong header was sent.
        if not header:
            return None
    return _error("UNAUTHORIZED", "会话校验失败，拒绝操作", 403)


def _require_owned_read(handler: BaseHTTPRequestHandler) -> bool:
    """When SESSION_REQUIRED, deny sensitive GET without valid X-App-Session."""
    if not SESSION_REQUIRED:
        return False
    denied = _check_session(handler, required=True)
    if denied is not None:
        code, body = denied
        _json_response(handler, code, body)
        return True
    return False


def _member_public_dict(m: Any) -> dict[str, Any]:
    if hasattr(m, "to_public_dict"):
        return m.to_public_dict()
    d = m.to_dict()
    tok = d.get("token")
    d["token"] = ""
    d["has_token"] = bool(tok)
    return d


def _session_fingerprint(session: str) -> str:
    if not session:
        return ""
    import hashlib
    return hashlib.sha256(session.encode("utf-8")).hexdigest()[:8]


def build_health_payload(caller_session: str = "") -> dict[str, Any]:
    napcat_online, napcat_message, _checked_at = get_napcat_cache()
    payload = {
        "ok": True,
        "service": SERVICE_ID,
        "version": SERVICE_VERSION,
        "session_required": SESSION_REQUIRED,
        "owned": SESSION_REQUIRED,
        "pid": os.getpid(),
        "napcat_online": napcat_online,
        "napcat_message": napcat_message,
    }
    # Never echo raw SESSION_ID. Callers prove ownership via X-App-Session.
    if caller_session:
        payload["session_match"] = bool(SESSION_ID) and caller_session == SESSION_ID
    else:
        payload["session_match"] = False
    return payload


def _validate_group_id(value: Any, label: str) -> int:
    try:
        gid = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须为纯数字") from None
    if gid <= 0:
        raise ValueError(f"{label}必须大于 0")
    return gid


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        for k, v in _cors_headers(self).items():
            self.send_header(k, v)
        self.end_headers()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return obj if isinstance(obj, dict) else {}

    def _serve_static(self, req_path: str) -> bool:
        if req_path in ("", "/"):
            return _file_response(self, WEB_DIR / "index.html")
        rel = req_path.lstrip("/")
        root = WEB_DIR.resolve()
        target = (WEB_DIR / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return False
        return _file_response(self, target)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            caller = self.headers.get("X-App-Session") or ""
            _json_response(self, 200, build_health_payload(caller))
            return
        if _is_sensitive_get(path):
            if _require_owned_read(self):
                return
        if path == "/config":
            cfg = load_cfg()
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "target_group_id": str(cfg.get("target_group_id") or ""),
                    "source_group_id": str(cfg.get("source_group_id") or ""),
                    "batch_count": str(cfg.get("batch_count") or "20"),
                    "interval_ms": str(cfg.get("interval_ms") or "2000"),
                    "filter_staff": bool(cfg.get("filter_staff", True)),
                    "onebot_url": str(cfg.get("onebot_url") or ""),
                    "napcat_webui_token": "",
                    "has_napcat_token": bool(cfg.get("napcat_webui_token")),
                },
            )
            return
        if path == "/status":
            state = get_state()
            napcat_online, napcat_message, _checked = get_napcat_cache()
            state["ok"] = True
            state["napcat_online"] = napcat_online
            state["napcat_message"] = napcat_message
            _json_response(self, 200, state)
            return
        if path == "/members":
            members = get_cached_members()
            eligible = sum(1 for m in members if m.eligible)
            safe = [_member_public_dict(m) for m in members]
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "members": safe,
                    "total": len(members),
                    "eligible": eligible,
                    "filtered": len(members) - eligible,
                },
            )
            return
        if path == "/tasks":
            _json_response(self, 200, {"ok": True, "tasks": list_tasks()})
            return
        if path.startswith("/tasks/"):
            tid = path[len("/tasks/") :]
            task = get_task(tid)
            if not task:
                code, body = _error("MEMBER_NOT_FOUND", "任务不存在", 404)
                _json_response(self, code, body)
                return
            _json_response(self, 200, {"ok": True, "task": task})
            return
        if self._serve_static(path):
            return
        code, body = _error("NOT_FOUND", "not found", 404)
        _json_response(self, code, body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json()
        try:
            if path == "/shutdown":
                # Always validate when header present; require match when owned.
                denied = _check_session(self, required=SESSION_REQUIRED)
                if denied is not None:
                    code, body = denied
                    _json_response(self, code, body)
                    return
            elif path in MUTATING_PATHS:
                if SESSION_REQUIRED:
                    denied = _check_session(self, required=True)
                    if denied is not None:
                        code, body = denied
                        _json_response(self, code, body)
                        return
                elif self.headers.get("X-App-Session"):
                    denied = _check_session(self, required=True)
                    if denied is not None:
                        code, body = denied
                        _json_response(self, code, body)
                        return

            if path == "/config":
                validate_log_settings_payload(data)
                cfg = load_cfg()
                for k in (
                    "target_group_id",
                    "source_group_id",
                    "batch_count",
                    "interval_ms",
                    "filter_staff",
                    "onebot_url",
                    "napcat_webui_token",
                    "log_level",
                    "max_log_file_mb",
                    "log_retention_days",
                    "auto_clean_logs",
                ):
                    if k in data:
                        if k == "napcat_webui_token" and data[k] == "":
                            continue
                        cfg[k] = data[k]
                save_cfg(cfg)
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/members/load":
                online, msg = check_napcat_online()
                if not online:
                    code, body = _error("NAPCAT_OFFLINE", msg or "饭饭定制未连接")
                    _json_response(self, code, body)
                    return
                source = _validate_group_id(data.get("source_group_id") or 0, "来源群号")
                filter_staff = bool(data.get("filter_staff", True))
                members = load_source_members(
                    source, filter_staff=filter_staff, record_logs=False
                )
                eligible = sum(1 for m in members if m.eligible)
                code, body = _ok(
                    {
                        "count": len(members),
                        "eligible": eligible,
                        "filtered": len(members) - eligible,
                        "members": [_member_public_dict(m) for m in members],
                    }
                )
                _json_response(self, code, body)
                return

            if path == "/invite/start":
                online, msg = check_napcat_online()
                if not online:
                    code, body = _error("NAPCAT_OFFLINE", msg or "饭饭定制未连接")
                    _json_response(self, code, body)
                    return
                target = _validate_group_id(data.get("target_group_id") or 0, "目标群号")
                source = _validate_group_id(data.get("source_group_id") or 0, "来源群号")
                if target == source:
                    code, body = _error("INVALID_ARGUMENT", "目标群和来源群不能相同")
                    _json_response(self, code, body)
                    return
                if "batch_count" in data or "batch_size" in data or "count" in data:
                    raw_batch = data.get("batch_count", data.get("batch_size", data.get("count")))
                    try:
                        batch_size = int(raw_batch)
                    except (TypeError, ValueError):
                        code, body = _error("INVALID_ARGUMENT", "batch_count must be 1-1000")
                        _json_response(self, code, body)
                        return
                else:
                    batch_size = 20
                if "interval_ms" in data:
                    try:
                        interval_ms = int(data.get("interval_ms"))
                    except (TypeError, ValueError):
                        code, body = _error("INVALID_ARGUMENT", "interval_ms must be 100-600000")
                        _json_response(self, code, body)
                        return
                else:
                    interval_ms = 1500
                if batch_size < 1 or batch_size > 1000:
                    code, body = _error("INVALID_ARGUMENT", "batch_count must be 1-1000")
                    _json_response(self, code, body)
                    return
                if interval_ms < 100 or interval_ms > 600000:
                    code, body = _error("INVALID_ARGUMENT", "interval_ms must be 100-600000")
                    _json_response(self, code, body)
                    return
                filter_staff = bool(data.get("filter_staff", True))
                qq_list = data.get("qq_list")
                if qq_list is None:
                    code, body = _error("INVALID_ARGUMENT", "请至少选择一名成员")
                    _json_response(self, code, body)
                    return
                qq_list = [int(x) for x in qq_list]
                if not qq_list:
                    code, body = _error("INVALID_ARGUMENT", "请至少选择一名成员")
                    _json_response(self, code, body)
                    return
                try:
                    task_id = start_batch(
                        target_group_id=target,
                        source_group_id=source,
                        count=0,
                        interval_ms=interval_ms,
                        filter_staff=filter_staff,
                        qq_list=qq_list,
                        batch_size=batch_size,
                    )
                except RuntimeError as exc:
                    code, body = _error("TASK_RUNNING", str(exc))
                    _json_response(self, code, body)
                    return
                except ValueError as exc:
                    code, body = _error("INVALID_ARGUMENT", str(exc))
                    _json_response(self, code, body)
                    return
                code, body = _ok({"task_id": task_id})
                _json_response(self, code, body)
                return

            if path == "/invite/stop":
                req_tid = data.get("task_id")
                if req_tid is not None and req_tid != "":
                    req_tid = str(req_tid)
                else:
                    req_tid = None
                state = get_state()
                if not state.get("running") and state.get("status") not in (
                    "preparing",
                    "running",
                    "stopping",
                ):
                    code, body = _error("TASK_NOT_RUNNING", "当前没有运行中的任务")
                    _json_response(self, code, body)
                    return
                try:
                    stop_batch(task_id=req_tid)
                except TaskIdMismatch:
                    code, body = _error(
                        "TASK_MISMATCH",
                        "task_id 与当前运行任务不匹配",
                    )
                    body["ok"] = False
                    _json_response(self, code, body)
                    return
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/state/clear-logs":
                clear_logs()
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/state/clear-failed":
                clear_failed()
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/state/clear-rate-limits":
                clear_rate_limits()
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/state/clear":
                kinds = data.get("kinds")
                if isinstance(kinds, list):
                    clear_state([str(x) for x in kinds])
                else:
                    clear_state()
                code, body = _ok()
                _json_response(self, code, body)
                return

            if path == "/test-connection":
                # Transient probe: never save_cfg. Validates OneBot + WebUI token.
                probe_url = str(data.get("onebot_url") or "").strip() or None
                probe_token = data.get("napcat_webui_token")
                if probe_token is not None:
                    probe_token = str(probe_token)
                else:
                    probe_token = None
                ok, msg, err = test_napcat_connection(
                    onebot_url=probe_url,
                    napcat_webui_token=probe_token,
                )
                if not ok:
                    code_name = err if err in {
                        "PORT_UNREACHABLE",
                        "ONEBOT_UNAVAILABLE",
                        "WEBUI_TOKEN_INVALID",
                        "WEBUI_TOKEN_MISSING",
                        "NOT_LOGGED_IN",
                    } else "NAPCAT_OFFLINE"
                    code, body = _error(code_name, msg or "饭饭定制连接失败")
                    _json_response(self, code, body)
                    return
                refresh_napcat_cache()
                code, body = _ok({"message": msg, "napcat_online": True})
                _json_response(self, code, body)
                return

            if path == "/napcat/refresh":
                online, message = refresh_napcat_cache(wait_if_busy=True)
                code, body = _ok({"napcat_online": online, "napcat_message": message})
                _json_response(self, code, body)
                return

            if path == "/shutdown":
                logger.info("shutdown requested")
                stop_batch()
                code, body = _ok({"message": "shutting down"})
                _json_response(self, code, body)

                def _stop() -> None:
                    global _server
                    if _server is not None:
                        _server.shutdown()

                threading.Thread(target=_stop, daemon=True).start()
                return

            code, body = _error("NOT_FOUND", "not found", 404)
            _json_response(self, code, body)
        except ValueError as exc:
            code, body = _error("INVALID_ARGUMENT", str(exc))
            _json_response(self, code, body)
        except Exception as exc:
            logger.exception("request failed: %s", path)
            code, body = _error("INTERNAL_ERROR", str(exc), 500)
            _json_response(self, code, body)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, wintypes.DWORD(pid))
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return True


def _start_parent_watchdog(parent_pid: int) -> None:
    if parent_pid <= 0:
        return

    def _watch() -> None:
        global _server
        while True:
            time.sleep(1.0)
            if not _pid_alive(parent_pid):
                logger.info("parent pid %s exited; shutting down sidecar", parent_pid)
                stop_batch()
                if _server is not None:
                    _server.shutdown()
                break

    threading.Thread(target=_watch, daemon=True, name="parent-watchdog").start()


def main(
    open_browser: bool = False,
    session_id: str = "",
    parent_pid: int = 0,
    port: int = PORT,
) -> None:
    global SESSION_ID, SESSION_REQUIRED, _server, logger
    bind_port = int(port) if port else PORT
    if bind_port <= 0 or bind_port > 65535:
        raise ValueError(f"invalid port: {port}")
    if session_id:
        SESSION_ID = session_id
        SESSION_REQUIRED = True
    else:
        SESSION_ID = str(uuid.uuid4())
        SESSION_REQUIRED = False
    cfg = load_cfg()
    log_cfg = parse_log_settings(cfg)
    try:
        logger = setup_service_logger(
            level=log_cfg["log_level"],
            max_bytes=log_cfg["max_log_file_mb"] * 1024 * 1024,
            backup_count=log_cfg["backup_count"],
            retention_days=log_cfg["log_retention_days"],
            auto_clean_logs=log_cfg["auto_clean_logs"],
        )
    except Exception:
        logger = setup_service_logger()
        logger.warning("log settings invalid or unusable; using defaults")

    recovered = recover_stale_tasks()
    if recovered:
        logger.info("recovered %s stale task(s) as interrupted", recovered)

    start_napcat_health_refresh()

    _server = ThreadingHTTPServer((HOST, bind_port), Handler)
    url = f"http://{HOST}:{bind_port}/"
    logger.info(
        "cross-group service started at %s (service=%s host=%s port=%s session_fp=%s session_required=%s pid=%s parent=%s)",
        url,
        SERVICE_ID,
        HOST,
        bind_port,
        _session_fingerprint(SESSION_ID),
        SESSION_REQUIRED,
        os.getpid(),
        parent_pid or "-",
    )
    if open_browser:
        logger.info("browser open requested, but sidecar mode should pass --no-browser")

    _start_parent_watchdog(parent_pid)

    def _on_signal(signum: int, _frame: Any) -> None:
        logger.info("signal %s received", signum)
        stop_batch()
        if _server is not None:
            _server.shutdown()

    try:
        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    except (ValueError, OSError):
        pass

    try:
        _server.serve_forever()
    except KeyboardInterrupt:
        logger.info("service interrupted")
    finally:
        stop_batch()
        stop_napcat_health_refresh()
        if _server is not None:
            _server.server_close()
        logger.info("service stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-group invite local API service")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on start")
    parser.add_argument("--session-id", default="", help="Ownership session id from host app")
    parser.add_argument("--parent-pid", type=int, default=0, help="Host app PID for watchdog")
    parser.add_argument("--port", type=int, default=PORT, help="Listen port (default 17888)")
    args = parser.parse_args()
    main(
        open_browser=args.open_browser and not args.no_browser,
        session_id=args.session_id,
        parent_pid=args.parent_pid,
        port=args.port,
    )
