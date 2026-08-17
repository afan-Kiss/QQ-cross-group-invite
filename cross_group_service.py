# -*- coding: utf-8 -*-
"""HTTP API for cross-group batch invite (desktop sidecar)."""
from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cross_group_batch import (
    get_cached_members,
    get_state,
    load_source_members,
    start_batch,
    stop_batch,
)
from myqq_api import check_napcat_online, load_cfg, save_cfg
from service_logger import setup_service_logger

logger = setup_service_logger()

WEB_DIR = Path(__file__).resolve().parent / "web"
PORT = 17888
SERVICE_ID = "cross-group-invite"
SERVICE_VERSION = "1.0.0"
HOST = "127.0.0.1"


def _json_response(handler: BaseHTTPRequestHandler, code: int, obj: Any) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
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
    handler.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") or mime.endswith("javascript") else mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(data)
    return True


def build_health_payload() -> dict[str, Any]:
    napcat_online, napcat_message = check_napcat_online()
    return {
        "ok": True,
        "service": SERVICE_ID,
        "version": SERVICE_VERSION,
        "napcat_online": napcat_online,
        "napcat_message": napcat_message,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())):
            return False
        return _file_response(self, target)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            _json_response(self, 200, build_health_payload())
            return
        if path == "/config":
            cfg = load_cfg()
            _json_response(
                self,
                200,
                {
                    "target_group_id": str(cfg.get("target_group_id") or ""),
                    "source_group_id": str(cfg.get("source_group_id") or ""),
                    "batch_count": str(cfg.get("batch_count") or "10"),
                    "interval_ms": str(cfg.get("interval_ms") or "2000"),
                    "filter_staff": bool(cfg.get("filter_staff", True)),
                },
            )
            return
        if path == "/status":
            state = get_state()
            napcat_online, napcat_message = check_napcat_online()
            state["napcat_online"] = napcat_online
            state["napcat_message"] = napcat_message
            _json_response(self, 200, state)
            return
        if path == "/members":
            _json_response(
                self,
                200,
                {"members": [m.to_dict() for m in get_cached_members()]},
            )
            return
        if self._serve_static(path):
            return
        _json_response(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json()
        try:
            if path == "/config":
                cfg = load_cfg()
                for k in (
                    "target_group_id",
                    "source_group_id",
                    "batch_count",
                    "interval_ms",
                    "filter_staff",
                    "onebot_url",
                    "napcat_webui_token",
                ):
                    if k in data:
                        cfg[k] = data[k]
                save_cfg(cfg)
                _json_response(self, 200, {"ok": True})
                return

            if path == "/members/load":
                source = int(data.get("source_group_id") or 0)
                if source <= 0:
                    raise ValueError("\u8bf7\u586b\u5199\u6765\u6e90\u7fa4\u53f7")
                filter_staff = bool(data.get("filter_staff", True))
                members = load_source_members(
                    source, filter_staff=filter_staff, record_logs=False
                )
                _json_response(
                    self,
                    200,
                    {"count": len(members), "members": [m.to_dict() for m in members]},
                )
                return

            if path == "/invite/start":
                target = int(data.get("target_group_id") or 0)
                source = int(data.get("source_group_id") or 0)
                if target <= 0 or source <= 0:
                    raise ValueError("\u8bf7\u586b\u5199\u76ee\u6807\u7fa4\u53f7\u548c\u6765\u6e90\u7fa4\u53f7")
                if target == source:
                    raise ValueError("\u76ee\u6807\u7fa4\u548c\u6765\u6e90\u7fa4\u4e0d\u80fd\u76f8\u540c")
                count = int(data.get("count") or 0)
                interval_ms = int(data.get("interval_ms") or 1500)
                filter_staff = bool(data.get("filter_staff", True))
                qq_list = data.get("qq_list")
                if qq_list:
                    qq_list = [int(x) for x in qq_list]
                start_batch(
                    target_group_id=target,
                    source_group_id=source,
                    count=count,
                    interval_ms=interval_ms,
                    filter_staff=filter_staff,
                    qq_list=qq_list,
                )
                _json_response(self, 200, {"ok": True})
                return

            if path == "/invite/stop":
                stop_batch()
                _json_response(self, 200, {"ok": True})
                return

            _json_response(self, 404, {"error": "not found"})
        except Exception as exc:
            _json_response(self, 400, {"error": str(exc)})


def main(open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    logger.info("cross-group service started at %s (service=%s)", url, SERVICE_ID)
    if open_browser:
        logger.info("browser open requested, but sidecar mode should pass --no-browser")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("service interrupted")
    finally:
        stop_batch()
        server.server_close()
        logger.info("service stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-group invite local API service")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on start")
    args = parser.parse_args()
    main(open_browser=args.open_browser and not args.no_browser)
