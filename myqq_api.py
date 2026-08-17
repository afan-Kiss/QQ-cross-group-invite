# -*- coding: utf-8 -*-
"""MyQQ HTTPAPI helper (params use c1/c2/c3... per official plugin)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return ROOT


def cfg_path() -> Path:
    if getattr(sys, "frozen", False):
        data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "QQCrossGroupInvite"
        data.mkdir(parents=True, exist_ok=True)
        target = data / "config.json"
        if not target.exists():
            bundled = _bundle_dir() / "config.json"
            if bundled.is_file():
                shutil.copy2(bundled, target)
            else:
                target.write_text("{}", encoding="utf-8")
        return target
    return ROOT / "config.json"


CFG_PATH = cfg_path()

# 群验证方式（Api_GetGroupAddMode / Ex 文档）
GROUP_ADD_MODE = {
    "0": "0=群号不存在/取失败",
    "1": "1=允许任何人",
    "2": "2=需要验证消息",
    "3": "3=不允许任何人加群",
    "4": "4=需要正确回答问题",
    "5": "5=需要回答问题并由管理员审核",
    "6": "6=付费群",
}


def load_cfg() -> dict[str, Any]:
    path = cfg_path()
    return json.loads(path.read_text(encoding="utf-8"))


def save_cfg(cfg: dict[str, Any]) -> None:
    path = cfg_path()
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_host_port(base_url: str) -> tuple[str, int]:
    u = urlparse(base_url if "://" in base_url else "http://" + base_url)
    host = u.hostname or "127.0.0.1"
    port = u.port or 80
    return host, port


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_url(base_url: str | None) -> str:
    cfg = load_cfg()
    return (base_url or cfg["base_url"]).rstrip("/")


def _ensure_port(url: str, *, hint: str, timeout: float = 1.0) -> None:
    host, port = parse_host_port(url)
    if not port_open(host, port, timeout=timeout):
        raise RuntimeError(f"端口 {host}:{port} 没有服务在听。\n{hint}")


def call(func: str, *args: Any, token: str | None = None, base_url: str | None = None, timeout: float = 5) -> str:
    cfg = load_cfg()
    url = _resolve_url(base_url)
    _ensure_port(
        url,
        hint=(
            "请在 MyQQ / CBot64 中开启 HTTP API，"
            f"端口 {parse_host_port(url)[1]}，Token={cfg.get('token', '123')}。"
        ),
    )

    q: dict[str, str] = {
        "function": func,
        "token": str(token if token is not None else cfg.get("token", "123")),
    }
    for i, v in enumerate(args, start=1):
        if v is None:
            continue
        q[f"c{i}"] = str(v)
    sep = "&" if "?" in url else "?"
    full = url + sep + urllib.parse.urlencode(q)
    req = urllib.request.Request(full, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except TimeoutError as e:
        raise RuntimeError(f"请求超时（{timeout}s）。") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 HTTP API: {e.reason}") from e


def call_post(func: str, params: dict[str, Any], *, token: str | None = None, base_url: str | None = None, timeout: float = 5) -> str:
    """MyQQ HTTPAPI JSON POST（适合 Api_SendPack 等大参数）。"""
    cfg = load_cfg()
    url = _resolve_url(base_url)
    _ensure_port(
        url,
        hint=(
            "请在 MyQQ / CBot64 中开启 HTTP API，"
            f"端口 {parse_host_port(url)[1]}，Token={cfg.get('token', '123')}。"
        ),
    )
    payload = {
        "function": func,
        "token": str(token if token is not None else cfg.get("token", "123")),
        "params": params,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except TimeoutError as e:
        raise RuntimeError(f"请求超时（{timeout}s）。") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 HTTP API: {e.reason}") from e


def parse_ret(raw: str) -> Any:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        if isinstance(data, dict) and "ret" in data:
            return data["ret"]
        return data
    return obj


def get_online_qq_list(token: str | None = None, base_url: str | None = None) -> str:
    return call("Api_GetOnlineQQlist", token=token, base_url=base_url)


def get_group_add_mode(robot_qq: str, group_id: str, token: str | None = None) -> tuple[str, str]:
    """Return (mode_code, human_text). Prefer Ex."""
    raw_ex = call("Api_GetGroupAddModeEx", robot_qq, group_id, token=token)
    mode = str(parse_ret(raw_ex)).strip()
    if mode in ("", "None"):
        raw = call("Api_GetGroupAddMode", robot_qq, group_id, token=token)
        mode = str(parse_ret(raw)).strip()
    text = GROUP_ADD_MODE.get(mode, f"未知({mode})")
    return mode, text


def is_group_member(robot_qq: str, group_id: str, user_qq: str, token: str | None = None) -> bool:
    raw = call("Api_GetGroupMemberList_B", robot_qq, group_id, token=token)
    text = str(parse_ret(raw))
    return user_qq in text


def invite_friend_to_group(
    robot_qq: str,
    group_id: str,
    friend_qq: str,
    *,
    as_admin: bool = True,
    param_order: str = "robot_group_friend",
    token: str | None = None,
) -> str:
    """Invite friend into group (SDK wording: 邀请 — may require accept).

    Official HTTP/Java order: c1=机器人QQ c2=群号 c3=对象QQ
    Old Go stub order: c1=机器人QQ c2=对象QQ c3=群号
    """
    func = "Api_AdminInviteGroup" if as_admin else "Api_NoAdminInviteGroup"
    if param_order == "robot_friend_group":
        return call(func, robot_qq, friend_qq, group_id, token=token)
    return call(func, robot_qq, group_id, friend_qq, token=token)


def try_set_group_allow_anyone(robot_qq: str, group_id: str, token: str | None = None) -> str:
    """Api_SetGroupVerify: mode 1=允许任何人. Returns raw response."""
    return call("Api_SetGroupVerify", robot_qq, group_id, "1", "", "", token=token)


def send_pack(
    robot_qq: str,
    pack_content: str,
    *,
    token: str | None = None,
    base_url: str | None = None,
    timeout: float = 20,
    use_post: bool = True,
) -> str:
    """Api_SendPack: c1=机器人QQ, c2=封包内容。

    注意：CBot64 野生框架的 HTTP 桥通常未暴露 Api_SendPack，请优先用 send_onebot_packet。
    """
    if use_post:
        return call_post(
            "Api_SendPack",
            {"c1": robot_qq, "c2": pack_content},
            token=token,
            base_url=base_url,
            timeout=timeout,
        )
    return call("Api_SendPack", robot_qq, pack_content, token=token, base_url=base_url, timeout=timeout)


def napcat_webui_login(
    webui_token: str | None = None,
    *,
    api_url: str | None = None,
    timeout: float = 10,
    force: bool = False,
) -> str:
    """Login NapCat WebUI, return base64 Credential for /api/Debug/call."""
    cfg = load_cfg()
    base = (api_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    tok = str(webui_token if webui_token is not None else cfg.get("napcat_webui_token") or cfg.get("onebot_token") or "")
    cache_key = (base, tok)
    cached = getattr(napcat_webui_login, "_cache", {}).get(cache_key)
    if cached and not force:
        napcat_webui_login._debug_url = cached["debug_url"]  # type: ignore[attr-defined]
        return cached["cred"]
    if base.endswith("/api"):
        auth_url = base[: -len("/api")] + "/api/auth/login"
        debug_url = base + "/Debug/call"
    else:
        auth_url = base + "/auth/login"
        debug_url = base + "/Debug/call"
    if not tok:
        raise RuntimeError("missing NapCat WebUI token (config.json napcat_webui_token)")
    pwd_hash = hashlib.sha256((tok + ".napcat").encode()).hexdigest()
    req = urllib.request.Request(
        auth_url,
        data=json.dumps({"hash": pwd_hash}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        obj = json.loads(r.read().decode("utf-8", errors="replace"))
    if obj.get("code") != 0:
        raise RuntimeError(f"NapCat WebUI login failed: {obj}")
    cred = obj.get("data", {}).get("Credential")
    if not cred:
        raise RuntimeError(f"NapCat WebUI login response missing Credential: {obj}")
    napcat_webui_login._cache = {cache_key: {"cred": str(cred), "debug_url": debug_url}}  # type: ignore[attr-defined]
    napcat_webui_login._debug_url = debug_url  # type: ignore[attr-defined]
    return str(cred)


def send_napcat_packet(
    cmd: str,
    data_hex: str,
    *,
    api_url: str | None = None,
    webui_token: str | None = None,
    wait_rsp: bool = True,
    timeout: float = 20,
) -> str:
    """Send raw OIDB packet via NapCat WebUI Debug API (Framework 默认走这个)."""
    cfg = load_cfg()
    base = (api_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    cred = napcat_webui_login(webui_token, api_url=base, timeout=min(timeout, 10))
    debug_url = getattr(napcat_webui_login, "_debug_url", base + "/Debug/call")
    payload = {
        "action": "send_packet",
        "params": {"cmd": cmd, "data": data_hex, "rsp": wait_rsp},
    }
    req = urllib.request.Request(
        debug_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cred}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except TimeoutError as e:
        raise RuntimeError(f"请求超时（{timeout}s）。") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 NapCat API: {e.reason}") from e


def send_onebot_packet(
    cmd: str,
    data_hex: str,
    *,
    api_url: str | None = None,
    token: str | None = None,
    wait_rsp: bool = True,
    timeout: float = 20,
) -> str:
    """NapCat/OneBot send_packet。Framework 未开 OneBot HTTP 时自动走 WebUI Debug。"""
    cfg = load_cfg()
    url = (api_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    tok = str(token if token is not None else cfg.get("onebot_token") or cfg.get("token") or "")
    if url.endswith("/api") and len(tok) <= 20:
        return send_napcat_packet(
            cmd,
            data_hex,
            api_url=url,
            webui_token=tok or cfg.get("napcat_webui_token"),
            wait_rsp=wait_rsp,
            timeout=timeout,
        )
    _ensure_port(
        url,
        hint="请确认野生框架已登录，且 NapCat HTTP 已开启（默认 6099，见 bin/config/webui.json）。",
    )
    payload = {
        "action": "send_packet",
        "params": {
            "cmd": cmd,
            "data": data_hex,
            "rsp": wait_rsp,
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except TimeoutError as e:
        raise RuntimeError(f"请求超时（{timeout}s）。") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 OneBot API: {e.reason}") from e


def onebot_action(
    action: str,
    params: dict | None = None,
    *,
    api_url: str | None = None,
    token: str | None = None,
    timeout: float = 15,
) -> dict:
    """Call NapCat OneBot HTTP action (e.g. get_friend_list)."""
    cfg = load_cfg()
    url = (api_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    tok = str(token if token is not None else cfg.get("onebot_token") or "")
    payload = {"action": action, "params": params or {}}
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        obj = json.loads(r.read().decode("utf-8", errors="replace"))
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        return obj["data"]
    return obj if isinstance(obj, dict) else {"raw": obj}


def find_friend_uid_by_qq(friend_qq: int, *, no_cache: bool = False) -> str | None:
    """Resolve NT uid (u_xxx) for a friend QQ via OneBot get_friend_list."""
    raw = onebot_action("get_friend_list", {"no_cache": no_cache})
    friends: list = []
    if isinstance(raw, list):
        friends = raw
    elif isinstance(raw, dict):
        inner = raw.get("data")
        if isinstance(inner, list):
            friends = inner
        elif isinstance(inner, dict) and isinstance(inner.get("data"), list):
            friends = inner["data"]
    target = str(friend_qq)
    for f in friends:
        if not isinstance(f, dict):
            continue
        uin = str(f.get("user_id") or f.get("uin") or "")
        if uin != target:
            continue
        uid = str(f.get("uid") or f.get("user_uid") or f.get("raw_uid") or "")
        if uid.startswith("u_"):
            return uid
        # NapCat may only return user_id; uid in nested raw
        raw = f.get("raw")
        if isinstance(raw, dict):
            uid = str(raw.get("uid") or raw.get("user_id") or "")
            if uid.startswith("u_"):
                return uid
    return None


def is_empty_api_response(raw: str) -> bool:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        text = (raw or "").strip()
        return text in ("", "null", "None", '""')
    if not isinstance(obj, dict):
        return not str(obj).strip()
    status = str(obj.get("status", "")).lower()
    retcode = obj.get("retcode")
    if status == "ok" or retcode == 0:
        return False
    if status == "failed" or (isinstance(retcode, int) and retcode not in (0, None)):
        return True
    data = obj.get("data")
    if "data" in obj and data in ("", None, {}, []):
        return True
    ret = parse_ret(raw)
    return ret in ("", None, "null", "None")


def group_no_to_gid(
    robot_qq: str,
    group_no: str,
    token: str | None = None,
    base_url: str | None = None,
) -> str:
    """Api_GNTransGID: 群号 -> 内部 GID。CBot64 当前 MyQQApi.dll 可能无此接口。"""
    return call("Api_GNTransGID", robot_qq, group_no, token=token, base_url=base_url)


def gid_to_group_no(robot_qq: str, gid: str, token: str | None = None) -> str:
    """Api_GIDTransGN: 内部 GID -> 群号。"""
    return call("Api_GIDTransGN", robot_qq, gid, token=token)


def check_napcat_online(timeout: float = 3.0) -> tuple[bool, str]:
    """Return (online, message) for NapCat OneBot HTTP."""
    try:
        cfg = load_cfg()
        url = str(cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
        host, port = parse_host_port(url)
        if not port_open(host, port, timeout=min(timeout, 1.5)):
            return False, f"NapCat 未连接（{host}:{port} 无响应）"
        data = onebot_action("get_login_info", timeout=timeout)
        if isinstance(data, dict):
            uid = str(data.get("user_id") or data.get("uin") or "")
            if uid:
                return True, f"NapCat 在线（QQ {uid}）"
        return True, "NapCat 在线"
    except Exception as exc:
        return False, f"NapCat 未连接：{exc}"
