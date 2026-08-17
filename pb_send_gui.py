# -*- coding: utf-8 -*-
"""Paste PB log line -> auto parse -> customize params -> send packet."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from myqq_api import (
    get_online_qq_list,
    group_no_to_gid,
    is_empty_api_response,
    load_cfg,
    parse_host_port,
    parse_ret,
    port_open,
    save_cfg,
    send_onebot_packet,
    send_pack,
)
from pb_utils import (
    PACK_FORMATS,
    SAMPLE_LOG,
    ParsedPacket,
    analyze_oidb_packet,
    apply_custom_params,
    build_pack_payload,
    parse_log_line,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_FRAMEWORK = "E:/我的软件源码/QQ框架/框架/cbot64-win-x64"

DEFAULTS = {
    "api_mode": "onebot",
    "base_url": "http://127.0.0.1:8889/MyQQHTTPAPI",
    "onebot_url": "http://127.0.0.1:6099/api",
    "onebot_token": "c5a05069e568",
    "token": "123",
    "pack_format": "json",
    "framework_path": DEFAULT_FRAMEWORK,
    "qq": "",
    "group_id": "",
    "group_code": "",
    "invitee_qq": "",
}


def _load_framework_auth(framework_path: str) -> dict[str, str]:
    app_json = Path(framework_path) / "config" / "app.json"
    if not app_json.exists():
        return {}
    try:
        obj = json.loads(app_json.read_text(encoding="utf-8"))
        auth = obj.get("auth") or {}
        qq = str(auth.get("qq") or "").strip()
        return {"qq": qq} if qq else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_onebot_token(framework_path: str) -> str:
    webui = Path(framework_path) / "bin" / "config" / "webui.json"
    if not webui.exists():
        return ""
    try:
        obj = json.loads(webui.read_text(encoding="utf-8"))
        return str(obj.get("token") or "").strip()
    except (OSError, json.JSONDecodeError):
        return ""


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PB 发包测试")
        self.geometry("860x960")
        self.minsize(720, 820)

        cfg = {**DEFAULTS, **load_cfg()}
        fw = str(cfg.get("framework_path") or DEFAULT_FRAMEWORK)
        fw_auth = _load_framework_auth(fw)
        ob_token = str(cfg.get("onebot_token") or _load_onebot_token(fw) or DEFAULTS["onebot_token"])

        self.var_mode = tk.StringVar(value=str(cfg.get("api_mode") or "onebot"))
        self.var_onebot = tk.StringVar(value=str(cfg.get("onebot_url") or DEFAULTS["onebot_url"]))
        self.var_ob_token = tk.StringVar(value=ob_token)
        self.var_base = tk.StringVar(value=str(cfg.get("base_url") or DEFAULTS["base_url"]))
        self.var_token = tk.StringVar(value=str(cfg.get("token") or DEFAULTS["token"]))
        self.var_format = tk.StringVar(value=str(cfg.get("pack_format") or DEFAULTS["pack_format"]))
        self.var_framework = tk.StringVar(value=fw)
        self.var_status = tk.StringVar(value="未检测")

        self.var_robot_qq = tk.StringVar(value=str(cfg.get("qq") or cfg.get("sender_qq") or fw_auth.get("qq") or ""))
        self.var_group_no = tk.StringVar(value=str(cfg.get("group_id") or ""))
        self.var_group_code = tk.StringVar(value=str(cfg.get("group_code") or ""))
        self.var_invitee_qq = tk.StringVar(value=str(cfg.get("invitee_qq") or ""))
        self.var_pull = tk.BooleanVar(value=bool(cfg.get("invite_pull")))

        self._parsed: ParsedPacket | None = None
        self._busy = False

        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frm,
            text="粘贴框架日志里的 [PB数据] 行，自动解析后可修改登录QQ / 群号 / 被邀请人，再发包",
        ).pack(anchor=tk.W)

        ttk.Label(frm, text="粘贴日志（支持整行复制）").pack(anchor=tk.W, padx=10)
        self.txt_log = scrolledtext.ScrolledText(frm, height=5, wrap=tk.WORD, font=("Consolas", 10))
        self.txt_log.pack(fill=tk.X, padx=10, pady=4)
        self.txt_log.insert(tk.END, SAMPLE_LOG)

        parse_row = ttk.Frame(frm)
        parse_row.pack(fill=tk.X, **pad)
        ttk.Button(parse_row, text="自动解析", command=self.do_parse).pack(side=tk.LEFT)
        ttk.Button(parse_row, text="载入示例日志", command=self.load_sample).pack(side=tk.LEFT, padx=8)

        parse_frm = ttk.LabelFrame(frm, text="解析结果（只读）", padding=8)
        parse_frm.pack(fill=tk.X, padx=10, pady=6)
        self._parse_labels: dict[str, ttk.Label] = {}
        for key, title in [
            ("dir", "方向"),
            ("cmd", "cmd"),
            ("oidb", "OIDB / 子命令"),
            ("token", "邀请 token"),
            ("pb", "pb 长度"),
        ]:
            row = ttk.Frame(parse_frm)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=title, width=14).pack(side=tk.LEFT)
            lb = ttk.Label(row, text="-", wraplength=620, font=("Consolas", 10))
            lb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._parse_labels[key] = lb

        custom = ttk.LabelFrame(frm, text="自定义参数（可编辑，发包前自动重写 PB）", padding=8)
        custom.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(
            custom,
            text="登录QQ 用于 MyQQ 发包账号；0x758 邀请包 PB 内不含登录QQ，由当前框架登录号发送",
            wraplength=780,
        ).pack(anchor=tk.W, pady=(0, 4))

        ttk.Checkbutton(
            custom,
            text="直接拉群（管理员，PB 内含被邀请人 QQ；否则为需对方同意的邀请）",
            variable=self.var_pull,
        ).pack(anchor=tk.W, pady=(0, 4))

        for label, var in [
            ("登录QQ", self.var_robot_qq),
            ("群号", self.var_group_no),
            ("群内部码", self.var_group_code),
            ("被邀请人QQ", self.var_invitee_qq),
        ]:
            row = ttk.Frame(custom)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        custom_btns = ttk.Frame(custom)
        custom_btns.pack(fill=tk.X, pady=4)
        ttk.Button(custom_btns, text="群号 → 内部码", command=self.convert_group_no).pack(side=tk.LEFT)
        ttk.Button(custom_btns, text="应用参数重写 PB", command=self.apply_patch).pack(side=tk.LEFT, padx=8)

        conn = ttk.LabelFrame(frm, text="连接设置", padding=8)
        conn.pack(fill=tk.X, padx=10, pady=4)
        mode_row = ttk.Frame(conn)
        mode_row.pack(fill=tk.X, pady=2)
        ttk.Label(mode_row, text="发包").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_row, text="OneBot (推荐)", value="onebot", variable=self.var_mode).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(mode_row, text="MyQQ Api_SendPack", value="myqq", variable=self.var_mode).pack(side=tk.LEFT)
        for label, var in [
            ("框架路径", self.var_framework),
            ("OneBot URL", self.var_onebot),
            ("OneBot Token", self.var_ob_token),
            ("MyQQ HTTP", self.var_base),
            ("MyQQ Token", self.var_token),
        ]:
            r = ttk.Frame(conn)
            r.pack(fill=tk.X, pady=2)
            ttk.Label(r, text=label, width=14).pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Button(row, text="1. 启动框架", command=self.start_framework).pack(side=tk.LEFT)
        self.btn_refresh = ttk.Button(row, text="2. 检测连接", command=self.refresh_online)
        self.btn_refresh.pack(side=tk.LEFT, padx=8)
        self.btn_send = ttk.Button(row, text="3. 发包", command=self.do_send)
        self.btn_send.pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="保存配置", command=lambda: self.save_settings()).pack(side=tk.LEFT)
        ttk.Label(row, textvariable=self.var_status).pack(side=tk.LEFT, padx=8)

        ttk.Label(frm, text="详细日志").pack(anchor=tk.W, padx=10)
        self.log = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD, font=("Consolas", 10))
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self.do_parse(silent=True)
        self.save_settings(silent=True)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_refresh.configure(state=state)
        self.btn_send.configure(state=state)

    def _log(self, msg: str) -> None:
        self.log.insert(tk.END, msg.rstrip() + "\n")
        self.log.see(tk.END)

    def _show_parsed(self, pkt: ParsedPacket) -> None:
        oidb_txt = "-"
        if pkt.oidb is not None:
            oidb_txt = f"0x{pkt.oidb:x}"
            if pkt.subcmd is not None:
                oidb_txt += f" / subcmd {pkt.subcmd}"
        self._parse_labels["dir"].configure(text=pkt.direction or "-")
        self._parse_labels["cmd"].configure(text=pkt.cmd)
        self._parse_labels["oidb"].configure(text=oidb_txt)
        self._parse_labels["token"].configure(text=pkt.invite_token or "-")
        self._parse_labels["pb"].configure(text=f"{len(pkt.pb_hex)//2} bytes ({len(pkt.pb_hex)} hex)")

    def _fill_custom_from_pkt(self, pkt: ParsedPacket) -> None:
        if pkt.group_code is not None:
            self.var_group_code.set(str(pkt.group_code))
        if pkt.invitee_uin is not None:
            self.var_invitee_qq.set(str(pkt.invitee_uin))
            self.var_pull.set(True)
        else:
            self.var_pull.set(False)

    def _resolve_group_code(self) -> int:
        raw = self.var_group_code.get().strip()
        if not raw:
            raise ValueError("请填写群内部码，或先用「群号→内部码」转换")
        return int(raw)

    def _resolve_invitee_uin(self) -> int | None:
        raw = self.var_invitee_qq.get().strip()
        if not raw:
            return None
        return int(raw)

    def _build_send_packet(self) -> ParsedPacket:
        # Always re-parse log so pasted/edited log text is not ignored by stale _parsed.
        base = parse_log_line(self.txt_log.get("1.0", tk.END))
        group_code = self._resolve_group_code()
        invitee_uin = self._resolve_invitee_uin()
        pull = bool(self.var_pull.get())
        if pull and invitee_uin is None:
            raise ValueError("直接拉群模式请填写被邀请人 QQ")
        if (
            group_code == base.group_code
            and invitee_uin == base.invitee_uin
            and pull == (base.invitee_uin is not None)
        ):
            return base
        return apply_custom_params(
            base, group_code=group_code, invitee_uin=invitee_uin, pull=pull
        )

    def save_settings(self, silent: bool = False) -> None:
        cfg = load_cfg()
        cfg["api_mode"] = self.var_mode.get().strip() or "onebot"
        cfg["onebot_url"] = self.var_onebot.get().strip() or DEFAULTS["onebot_url"]
        cfg["onebot_token"] = self.var_ob_token.get().strip() or DEFAULTS["onebot_token"]
        cfg["base_url"] = self.var_base.get().strip() or DEFAULTS["base_url"]
        cfg["token"] = self.var_token.get().strip() or DEFAULTS["token"]
        cfg["pack_format"] = self.var_format.get().strip() or DEFAULTS["pack_format"]
        cfg["framework_path"] = self.var_framework.get().strip() or DEFAULT_FRAMEWORK
        cfg["qq"] = self.var_robot_qq.get().strip()
        cfg["sender_qq"] = cfg["qq"]
        cfg["group_id"] = self.var_group_no.get().strip()
        cfg["group_code"] = self.var_group_code.get().strip()
        cfg["invitee_qq"] = self.var_invitee_qq.get().strip()
        cfg["invite_pull"] = bool(self.var_pull.get())
        save_cfg(cfg)
        if not silent:
            self._log("配置已保存")

    def load_sample(self) -> None:
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.insert(tk.END, SAMPLE_LOG)
        self.do_parse()

    def do_parse(self, silent: bool = False) -> None:
        try:
            raw = self.txt_log.get("1.0", tk.END)
            pkt = parse_log_line(raw)
            self._parsed = pkt
            self._show_parsed(pkt)
            self._fill_custom_from_pkt(pkt)
            detail = analyze_oidb_packet(pkt.cmd, pkt.pb_hex)
            self._log("----- 解析成功 -----\n" + detail)
            if not silent:
                messagebox.showinfo("解析成功", pkt.summary_text())
        except Exception as e:
            self._parsed = None
            for lb in self._parse_labels.values():
                lb.configure(text="-")
            if not silent:
                messagebox.showerror("解析失败", str(e))
            self._log(f"解析失败: {e}")

    def apply_patch(self) -> None:
        try:
            pkt = self._build_send_packet()
            self._parsed = pkt
            self._show_parsed(pkt)
            self.save_settings(silent=True)
            self._log("----- PB 已按自定义参数重写 -----\n" + pkt.summary_text())
            messagebox.showinfo("重写成功", pkt.summary_text())
        except Exception as e:
            messagebox.showerror("重写失败", str(e))
            self._log(f"重写失败: {e}")

    def convert_group_no(self) -> None:
        group_no = self.var_group_no.get().strip()
        robot = self.var_robot_qq.get().strip()
        if not group_no:
            messagebox.showwarning("缺少群号", "请先填写群号")
            return
        if not robot:
            messagebox.showwarning("缺少登录QQ", "请先填写登录QQ（用于 Api_GNTransGID）")
            return
        if self._busy:
            return
        self._set_busy(True)
        self._log(f"群号转内部码: group={group_no}, robot={robot}")

        def work() -> None:
            try:
                raw = group_no_to_gid(
                    robot,
                    group_no,
                    token=self.var_token.get().strip(),
                    base_url=self.var_base.get().strip(),
                )
                gid = parse_ret(raw)
                if not gid or gid in ("0", "null", "None", ""):
                    raise RuntimeError(f"转换失败，返回: {raw}")
                self.after(0, lambda: self._on_gid_ok(str(gid), raw))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_gid_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_gid_ok(self, gid: str, raw: str) -> None:
        self._set_busy(False)
        self.var_group_code.set(gid)
        self.save_settings(silent=True)
        self._log(f"群内部码 => {gid}\n原始返回: {raw}")
        messagebox.showinfo("转换成功", f"群内部码: {gid}")

    def _on_gid_err(self, e: Exception) -> None:
        self._set_busy(False)
        self._log(f"群号转内部码失败: {e}")
        messagebox.showwarning(
            "转换失败",
            f"{e}\n\n若 Api_GNTransGID 不可用，请手动填写「群内部码」（从日志解析出的 field4.body.field1）。",
        )

    def start_framework(self) -> None:
        path = Path(self.var_framework.get().strip() or DEFAULT_FRAMEWORK) / "cbot64.exe"
        if not path.exists():
            alt = ROOT.parent / "MyQQRuntime" / "MyQQ.exe"
            path = alt if alt.exists() else path
        if not path.exists():
            messagebox.showerror("错误", f"找不到框架:\n{path}")
            return
        subprocess.Popen([str(path)], cwd=str(path.parent))
        self._log(f"已启动: {path}")
        self.var_status.set("已启动")

    def refresh_online(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.var_status.set("检测中…")

        def work() -> None:
            try:
                self.save_settings(silent=True)
                url = self.var_onebot.get().strip() if self.var_mode.get() == "onebot" else self.var_base.get().strip()
                host, port = parse_host_port(url)
                if not port_open(host, port, timeout=1.5):
                    raise RuntimeError(f"端口 {host}:{port} 无监听")
                if self.var_mode.get() == "onebot":
                    self.after(0, lambda: self._on_online_ok("OneBot OK"))
                    return
                raw = get_online_qq_list(token=self.var_token.get().strip(), base_url=self.var_base.get().strip())
                self.after(0, lambda: self._on_online_ok(raw))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_online_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_online_ok(self, raw: str) -> None:
        self._set_busy(False)
        self._log(f"检测 => {raw}")
        self.var_status.set("OK")

    def _on_online_err(self, e: Exception) -> None:
        self._set_busy(False)
        self.var_status.set("FAIL")
        messagebox.showwarning("检测失败", str(e))

    def do_send(self) -> None:
        if self._busy:
            return
        try:
            pkt = self._build_send_packet()
            self._parsed = pkt
            self._show_parsed(pkt)
        except Exception as e:
            messagebox.showwarning("参数错误", str(e))
            return

        self.save_settings()
        self._set_busy(True)
        mode = self.var_mode.get()
        robot = self.var_robot_qq.get().strip() or "0"
        self._log(
            "发包\n"
            + f"登录QQ: {robot}\n"
            + pkt.summary_text()
            + f"\npb preview: {pkt.pb_hex[:80]}..."
        )

        def work() -> None:
            try:
                if mode == "onebot":
                    raw = send_onebot_packet(
                        pkt.cmd,
                        pkt.pb_hex,
                        api_url=self.var_onebot.get().strip(),
                        token=self.var_ob_token.get().strip(),
                        wait_rsp=True,
                        timeout=25,
                    )
                else:
                    fmt = self.var_format.get().strip() or "json"
                    payload = build_pack_payload(pkt.cmd, pkt.pb_hex, fmt)
                    raw = send_pack(
                        robot,
                        payload,
                        token=self.var_token.get().strip(),
                        base_url=self.var_base.get().strip(),
                        timeout=25,
                        use_post=True,
                    )
                self.after(0, lambda: self._on_send_ok(raw))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_send_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_send_ok(self, raw: str) -> None:
        self._set_busy(False)
        self._log(f"return:\n{raw}")
        if is_empty_api_response(raw):
            messagebox.showwarning("返回异常", "返回为空或失败，请检查 PacketBackend / Token")
        else:
            messagebox.showinfo("完成", f"return:\n{raw}")

    def _on_send_err(self, e: Exception) -> None:
        self._set_busy(False)
        messagebox.showerror("发包失败", str(e))


if __name__ == "__main__":
    os.chdir(ROOT)
    App().mainloop()
