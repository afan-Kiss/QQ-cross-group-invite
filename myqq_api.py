# -*- coding: utf-8 -*-
"""MyQQ HTTPAPI helper (params use c1/c2/c3... per official plugin)."""
from __future__ import annotations

import hashlib
import threading
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


_cfg_io_lock = threading.RLock()


def _cfg_bak_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def _write_cfg_atomic(path: Path, cfg: dict[str, Any], *, rotate_bak: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    bak = _cfg_bak_path(path)
    try:
        if rotate_bak and path.is_file():
            try:
                # Only promote a readable primary to .bak.
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            else:
                try:
                    shutil.copy2(path, bak)
                except OSError:
                    pass
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass
        raise


def _restore_primary_from_backup(path: Path, data: dict[str, Any]) -> None:
    """Rewrite corrupt primary from already-parsed backup data without clobbering .bak."""
    _write_cfg_atomic(path, data, rotate_bak=False)


def load_cfg() -> dict[str, Any]:
    path = cfg_path()
    with _cfg_io_lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            bak = _cfg_bak_path(path)
            if bak.is_file():
                try:
                    data = json.loads(bak.read_text(encoding="utf-8"))
                    _restore_primary_from_backup(path, data)
                    return data
                except Exception as bak_exc:
                    raise RuntimeError(
                        f"config.json corrupt and backup unreadable: {exc}"
                    ) from bak_exc
            raise RuntimeError(f"config.json corrupt and no backup: {exc}") from exc


def save_cfg(cfg: dict[str, Any]) -> None:
    path = cfg_path()
    with _cfg_io_lock:
        _write_cfg_atomic(path, cfg, rotate_bak=True)



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
            f"端口 {parse_host_port(url)[1]}，请检查 HTTP API Token 配置。"
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
            f"端口 {parse_host_port(url)[1]}，请检查 HTTP API Token 配置。"
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
    tok = _default_fanfan_token(cfg, webui_token)
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
        raise RuntimeError("缺少饭饭定制 Token（请在设置中填写）")
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
        raise RuntimeError(f"饭饭定制登录失败: code={obj.get('code')}")
    cred = obj.get("data", {}).get("Credential")
    if not cred:
        raise RuntimeError("饭饭定制登录响应无效")
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
        raise RuntimeError(f"无法连接饭饭定制 API: {e.reason}") from e


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
    tok = _default_fanfan_token(cfg, token)
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
        hint="请确认野生框架已登录，且饭饭定制 HTTP 已开启（默认 6099，见 bin/config/webui.json）。",
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


DEFAULT_FANFAN_TOKEN = "123456"


def _is_webui_api(url: str) -> bool:
    u = (url or "").rstrip("/")
    return u.endswith("/api")


def _default_fanfan_token(cfg: dict[str, Any], explicit: str | None = None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    return str(
        cfg.get("napcat_webui_token")
        or cfg.get("onebot_token")
        or cfg.get("token")
        or DEFAULT_FANFAN_TOKEN
    ).strip() or DEFAULT_FANFAN_TOKEN


def _webui_debug_call(
    action: str,
    params: dict | None = None,
    *,
    api_url: str,
    token: str | None,
    timeout: float = 15,
) -> dict[str, Any]:
    """Call OneBot-style actions through Framework WebUI Debug API."""
    cred = napcat_webui_login(token, api_url=api_url, timeout=min(timeout, 10))
    debug_url = getattr(napcat_webui_login, "_debug_url", "")
    if not debug_url:
        base = api_url.rstrip("/")
        debug_url = base + "/Debug/call" if base.endswith("/api") else base + "/api/Debug/call"
    payload = {"action": action, "params": params or {}}
    req = urllib.request.Request(
        debug_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cred}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        obj = json.loads(r.read().decode("utf-8", errors="replace"))
    if not isinstance(obj, dict):
        return {"raw": obj}
    code = obj.get("code")
    if code not in (None, 0, "0"):
        raise RuntimeError(str(obj.get("message") or obj.get("msg") or f"WebUI error code={code}"))
    if "data" in obj:
        data = obj.get("data")
        if isinstance(data, dict):
            return data
        return {"data": data}
    return obj


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
    tok = _default_fanfan_token(cfg, token)
    if _is_webui_api(url):
        obj = _webui_debug_call(action, params, api_url=url, token=tok, timeout=timeout)
    else:
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


def _onebot_full_response(
    action: str,
    params: dict | None = None,
    *,
    api_url: str | None = None,
    token: str | None = None,
    timeout: float = 15,
) -> dict[str, Any]:
    """Call OneBot HTTP and return the full JSON object (not only data)."""
    cfg = load_cfg()
    url = (api_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    tok = _default_fanfan_token(cfg, token)
    if _is_webui_api(url):
        obj = _webui_debug_call(action, params, api_url=url, token=tok, timeout=timeout)
        return obj if isinstance(obj, dict) else {"raw": obj}
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
    return obj if isinstance(obj, dict) else {"raw": obj}


def _login_uid_from_mapping(data: dict[str, Any]) -> str:
    for key in ("user_id", "uin", "self_id"):
        if key not in data:
            continue
        raw = data.get(key)
        if raw in (None, "", 0, "0"):
            continue
        text = str(raw).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _extract_login_identity(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("OneBot get_login_info returned no data")
    cur: Any = payload
    for _ in range(5):
        if not isinstance(cur, dict):
            break
        code = cur.get("code")
        if code not in (None, 0, "0"):
            raise RuntimeError(
                str(cur.get("message") or cur.get("msg") or f"get_login_info error code={code}")
            )
        status = str(cur.get("status") or "").lower()
        if status in {"failed", "error"}:
            raise RuntimeError(
                str(cur.get("message") or cur.get("wording") or f"OneBot get_login_info failed: status={status}")
            )
        retcode = cur.get("retcode")
        if retcode is not None and str(retcode) not in {"0", "ok"}:
            raise RuntimeError(
                str(cur.get("message") or cur.get("wording") or f"OneBot get_login_info retcode={retcode}")
            )
        uid = _login_uid_from_mapping(cur)
        if uid:
            return uid
        inner = cur.get("data")
        if isinstance(inner, dict):
            cur = inner
            continue
        break
    raise RuntimeError("OneBot get_login_info missing user_id/uin")


def _webui_root(api_url: str) -> str:
    u = str(api_url or "").rstrip("/")
    if u.endswith("/api"):
        return u[: -len("/api")]
    return u


def _probe_webui_alive(api_url: str, timeout: float = 2.0) -> bool:
    """True when Framework/Shell WebUI responds (OneBot HTTP may be disabled)."""
    root = _webui_root(api_url)
    for u in (root + "/", root + "/webui/", str(api_url).rstrip("/") + "/"):
        try:
            req = urllib.request.Request(u, method="GET", headers={"User-Agent": "qq-cross-group"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if 200 <= int(r.status) < 500:
                    return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            continue
    try:
        auth = root + "/api/auth/login"
        data = json.dumps({"hash": "0"}).encode("utf-8")
        req = urllib.request.Request(
            auth,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "qq-cross-group"},
        )
        try:
            urllib.request.urlopen(req, timeout=timeout)
            return True
        except urllib.error.HTTPError:
            return True
    except Exception:
        return False


def check_napcat_online(
    timeout: float = 3.0, *,
    onebot_url: str | None = None,
) -> tuple[bool, str]:
    """Return (online, message). Accepts OneBot HTTP or Framework WebUI on the same URL."""
    try:
        cfg = load_cfg()
        url = str(onebot_url or cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
        host, port = parse_host_port(url)
        if not port_open(host, port, timeout=min(timeout, 1.5)):
            return False, f"饭饭定制 offline ({host}:{port} no response)"
        try:
            payload = _onebot_full_response("get_login_info", timeout=timeout, api_url=url)
            uid = _extract_login_identity(payload)
            return True, f"饭饭定制 online (QQ {uid})"
        except Exception as onebot_exc:
            if _probe_webui_alive(url, timeout=min(timeout, 2.0)):
                return True, "饭饭定制 online (WebUI)"
            return False, f"饭饭定制 offline: {onebot_exc}"
    except Exception as exc:
        return False, f"饭饭定制 offline: {exc}"


def test_napcat_connection(
    *,
    onebot_url: str | None = None,
    napcat_webui_token: str | None = None,
    timeout: float = 8.0,
) -> tuple[bool, str, str]:
    """Probe invite-critical connectivity without save_cfg.

    Returns (ok, message, error_code).
    error_code examples: PORT_UNREACHABLE, ONEBOT_UNAVAILABLE, WEBUI_TOKEN_INVALID,
    WEBUI_TOKEN_MISSING, NOT_LOGGED_IN, NAPCAT_OFFLINE.
    """
    cfg = load_cfg()
    url = str(onebot_url or "").strip() or str(cfg.get("onebot_url") or "http://127.0.0.1:6099/api").rstrip("/")
    url = url.rstrip("/")
    req_tok = str(napcat_webui_token or "").strip()
    token = req_tok if req_tok else str(cfg.get("napcat_webui_token") or cfg.get("onebot_token") or DEFAULT_FANFAN_TOKEN)

    host, port = parse_host_port(url)
    if not port_open(host, port, timeout=min(timeout, 1.5)):
        return False, f"饭饭定制 port unreachable ({host}:{port})", "PORT_UNREACHABLE"

    if not token:
        return False, "饭饭定制 Token missing", "WEBUI_TOKEN_MISSING"

    if _is_webui_api(url):
        try:
            napcat_webui_login(token, api_url=url, timeout=min(timeout, 10), force=True)
        except Exception as exc:
            # Never include raw token in message.
            return False, f"饭饭定制 Token 不正确: {exc}", "WEBUI_TOKEN_INVALID"

    try:
        payload = _onebot_full_response(
            "get_login_info", timeout=timeout, api_url=url, token=token
        )
        uid = _extract_login_identity(payload)
    except Exception as exc:
        msg = str(exc)
        if "登录失败" in msg or "Token invalid" in msg or "Token 不正确" in msg:
            return False, f"饭饭定制 Token 不正确: {exc}", "WEBUI_TOKEN_INVALID"
        if "未初始化" in msg:
            return False, "Token 正确，但 OneBot 尚未就绪。请等 QQ 登录完成后再测。", "ONEBOT_UNAVAILABLE"
        if "missing user_id" in msg or "NOT_LOGGED" in msg.upper():
            return False, "Token 正确，但 QQ 尚未登录（get_login_info 没有账号）。", "NOT_LOGGED_IN"
        if not _probe_webui_alive(url, timeout=min(timeout, 2.0)):
            return False, f"OneBot API unavailable: {exc}", "ONEBOT_UNAVAILABLE"
        return False, f"无法获取登录号: {exc}", "NOT_LOGGED_IN"

    return True, f"饭饭定制 connection ok (QQ {uid})", "OK"
