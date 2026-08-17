# -*- coding: utf-8 -*-
"""
MyQQ 拉人进群测试工具

重要：MyQQ 公开 API 只有「邀请进群」(Api_AdminInviteGroup / Api_NoAdminInviteGroup)，
文档写的是「邀请对象入群」。手动能直接拉进、API 却要对方同意，是因为客户端「直接拉入」
和框架「发邀请」不是同一条能力；SDK 里没有单独的「强制直接进群」接口。
"""
from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from myqq_api import (
    get_group_add_mode,
    get_online_qq_list,
    invite_friend_to_group,
    is_group_member,
    load_cfg,
    parse_host_port,
    parse_ret,
    port_open,
    save_cfg,
    try_set_group_allow_anyone,
)

ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    "base_url": "http://127.0.0.1:8889/MyQQHTTPAPI",
    "token": "123",
    "qq": "2249237761",
    "group_id": "1103760171",
    "friend_qq": "472336362",
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MyQQ 拉人进群")
        self.geometry("620x700")
        self.minsize(520, 620)

        cfg = {**DEFAULTS, **load_cfg()}
        self.var_base = tk.StringVar(value=str(cfg.get("base_url") or DEFAULTS["base_url"]))
        self.var_token = tk.StringVar(value=str(cfg.get("token") or DEFAULTS["token"]))
        self.var_robot = tk.StringVar(value=str(cfg.get("qq") or DEFAULTS["qq"]))
        self.var_group = tk.StringVar(value=str(cfg.get("group_id") or DEFAULTS["group_id"]))
        self.var_friend = tk.StringVar(value=str(cfg.get("friend_qq") or DEFAULTS["friend_qq"]))
        self.var_admin = tk.BooleanVar(value=True)
        self.var_order = tk.StringVar(value="robot_group_friend")
        self.var_status = tk.StringVar(value="未检测")
        self._busy = False

        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frm,
            text="步骤：MyQQ登录 → HTTPAPI开启 → 检测 → 邀请（API本质是邀请，未必等同手动直接拉入）",
        ).pack(anchor=tk.W)

        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Button(row, text="1. 启动 MyQQ", command=self.start_myqq).pack(side=tk.LEFT)
        self.btn_refresh = ttk.Button(row, text="2. 检测HTTP/群状态", command=self.refresh_online)
        self.btn_refresh.pack(side=tk.LEFT, padx=8)
        ttk.Label(row, textvariable=self.var_status).pack(side=tk.LEFT, padx=8)

        grid = ttk.Frame(frm)
        grid.pack(fill=tk.X, **pad)
        fields = [
            ("HTTP 地址", self.var_base),
            ("Token", self.var_token),
            ("我的QQ（登录号）", self.var_robot),
            ("目标群号", self.var_group),
            ("好友QQ", self.var_friend),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky=tk.W, pady=3)
            ttk.Entry(grid, textvariable=var, width=46).grid(row=i, column=1, sticky=tk.EW, pady=3)
        grid.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            frm,
            text="管理员邀请 Api_AdminInviteGroup（否则 NoAdmin）",
            variable=self.var_admin,
        ).pack(anchor=tk.W, **pad)

        order_row = ttk.Frame(frm)
        order_row.pack(fill=tk.X, **pad)
        ttk.Label(order_row, text="参数顺序").pack(side=tk.LEFT)
        ttk.Radiobutton(
            order_row,
            text="标准 c1登录QQ c2群号 c3好友（推荐）",
            value="robot_group_friend",
            variable=self.var_order,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(
            order_row,
            text="旧版 c1登录QQ c2好友 c3群号",
            value="robot_friend_group",
            variable=self.var_order,
        ).pack(side=tk.LEFT)

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X, **pad)
        self.btn_invite = ttk.Button(btn_row, text="3. 邀请该好友进群", command=self.do_invite)
        self.btn_invite.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="尝试设为允许任何人加群", command=self.do_set_verify).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="保存配置", command=self.save_settings).pack(side=tk.LEFT, padx=8)

        ttk.Label(frm, text="日志").pack(anchor=tk.W, padx=10)
        self.log = tk.Text(frm, height=18, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self._log(
            "【API结论】\n"
            "· Api_AdminInviteGroup / Api_NoAdminInviteGroup =「邀请对象入群」，常需对方同意。\n"
            "· SDK 无「强制直接拉进群、无需同意」的独立接口。\n"
            "· 手动能直接进、API 要同意：属于客户端能力与框架封装不一致，不是 Token 问题。\n"
            f"· 默认 Token {DEFAULTS['token']} / QQ {DEFAULTS['qq']} / 群 {DEFAULTS['group_id']} / 好友 {DEFAULTS['friend_qq']}\n"
        )
        self.save_settings(silent=True)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_refresh.configure(state=state)
        self.btn_invite.configure(state=state)

    def _log(self, msg: str) -> None:
        self.log.insert(tk.END, msg.rstrip() + "\n")
        self.log.see(tk.END)

    def save_settings(self, silent: bool = False) -> None:
        cfg = load_cfg()
        cfg["base_url"] = self.var_base.get().strip() or DEFAULTS["base_url"]
        cfg["token"] = self.var_token.get().strip() or DEFAULTS["token"]
        cfg["qq"] = self.var_robot.get().strip() or DEFAULTS["qq"]
        cfg["group_id"] = self.var_group.get().strip() or DEFAULTS["group_id"]
        cfg["friend_qq"] = self.var_friend.get().strip() or DEFAULTS["friend_qq"]
        save_cfg(cfg)
        if not silent:
            self._log("配置已保存到 config.json")

    def start_myqq(self) -> None:
        cfg = load_cfg()
        path = Path(cfg.get("framework_path") or "") / "MyQQ.exe"
        if not path.exists():
            path = ROOT.parent / "MyQQRuntime" / "MyQQ.exe"
        if not path.exists():
            messagebox.showerror("错误", f"找不到 MyQQ.exe:\n{path}")
            return
        try:
            subprocess.Popen([str(path)], cwd=str(path.parent))
            self._log(f"已启动: {path}")
            self.var_status.set("已启动 MyQQ")
        except OSError as e:
            messagebox.showerror("错误", str(e))

    def refresh_online(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.var_status.set("检测中…")

        def work() -> None:
            try:
                self.save_settings(silent=True)
                base = self.var_base.get().strip()
                host, port = parse_host_port(base)
                if not port_open(host, port, timeout=1.0):
                    raise RuntimeError(f"端口 {host}:{port} 无监听，HTTP 插件未启动。")
                token = self.var_token.get().strip()
                raw = get_online_qq_list(token=token)
                robot = self.var_robot.get().strip()
                group = self.var_group.get().strip()
                friend = self.var_friend.get().strip()
                mode, mode_text = get_group_add_mode(robot, group, token=token)
                in_group = is_group_member(robot, group, friend, token=token) if friend else False
                self.after(0, lambda: self._on_online_ok(raw, mode, mode_text, in_group))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_online_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_online_ok(self, raw: str, mode: str, mode_text: str, in_group: bool) -> None:
        self._set_busy(False)
        self._log(f"Api_GetOnlineQQlist => {raw}")
        self._log(f"群加群方式: {mode_text}")
        self._log(f"好友是否已在群内: {in_group}")
        text = (raw or "").strip().strip('"')
        candidates = []
        for part in text.replace(",", "|").replace("\n", "|").split("|"):
            p = "".join(ch for ch in part if ch.isdigit())
            if len(p) >= 5:
                candidates.append(p)
        ret = parse_ret(raw)
        if isinstance(ret, dict) and not candidates:
            # JSON success but empty list is ok if qq field filled
            pass
        if candidates:
            self.var_robot.set(candidates[0])
        self.var_status.set("HTTP正常")
        if in_group:
            self._log("提示：好友已在群成员列表中，无需再拉。")

    def _on_online_err(self, e: Exception) -> None:
        self._set_busy(False)
        self.var_status.set("HTTP失败")
        self._log(f"检测失败: {e}")
        messagebox.showwarning("检测失败", str(e))

    def do_set_verify(self) -> None:
        if self._busy:
            return
        robot = self.var_robot.get().strip()
        group = self.var_group.get().strip()
        self._set_busy(True)

        def work() -> None:
            try:
                self.save_settings(silent=True)
                raw = try_set_group_allow_anyone(robot, group, token=self.var_token.get().strip())
                mode, mode_text = get_group_add_mode(robot, group, token=self.var_token.get().strip())
                self.after(0, lambda: self._on_set_verify(raw, mode_text))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_set_verify_err(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_set_verify(self, raw: str, mode_text: str) -> None:
        self._set_busy(False)
        self._log(f"Api_SetGroupVerify => {raw}")
        self._log(f"当前加群方式: {mode_text}")
        messagebox.showinfo("结果", f"{raw}\n\n当前加群方式: {mode_text}")

    def _on_set_verify_err(self, e: Exception) -> None:
        self._set_busy(False)
        self._log(f"设置失败: {e}")
        messagebox.showerror("失败", str(e))

    def do_invite(self) -> None:
        if self._busy:
            return
        robot = self.var_robot.get().strip()
        group = self.var_group.get().strip()
        friend = self.var_friend.get().strip()
        if not robot or not group or not friend:
            messagebox.showwarning("缺参数", "请填写：我的QQ、目标群号、好友QQ")
            return
        if not robot.isdigit() or not group.isdigit() or not friend.isdigit():
            messagebox.showwarning("格式", "QQ号和群号请填纯数字")
            return

        self.save_settings()
        self._set_busy(True)
        as_admin = self.var_admin.get()
        order = self.var_order.get()

        def work() -> None:
            try:
                before = is_group_member(robot, group, friend, token=self.var_token.get().strip())
                raw = invite_friend_to_group(
                    robot,
                    group,
                    friend,
                    as_admin=as_admin,
                    param_order=order,
                    token=self.var_token.get().strip(),
                )
                after = is_group_member(robot, group, friend, token=self.var_token.get().strip())
                self.after(0, lambda: self._on_invite_done(True, raw, as_admin, before, after))
            except Exception as e:
                err = e
                self.after(0, lambda: self._on_invite_done(False, str(err), as_admin, False, False))

        self._log(
            f"调用 {'Api_AdminInviteGroup' if as_admin else 'Api_NoAdminInviteGroup'} "
            f"order={order} robot={robot} group={group} friend={friend}"
        )
        threading.Thread(target=work, daemon=True).start()

    def _on_invite_done(self, ok: bool, raw: str, as_admin: bool, before: bool, after: bool) -> None:
        self._set_busy(False)
        self._log(f"结果: {raw}")
        self._log(f"邀请前在群: {before} → 邀请后在群: {after}")
        if ok:
            if after and not before:
                messagebox.showinfo("成功", "好友已出现在群成员列表（直接进群生效）。")
            elif after and before:
                messagebox.showinfo("提示", "好友本来就在群里。")
            else:
                messagebox.showinfo(
                    "接口已返回，但未直接进群",
                    f"返回：{raw}\n\n"
                    "邀请后成员列表仍无此人 → 这是「需对方同意的邀请」。\n"
                    "MyQQ SDK 没有单独的强制拉人 API；手动能直接拉是客户端行为。\n"
                    f"模式: {'管理员邀请' if as_admin else '非管理员邀请'}",
                )
        else:
            messagebox.showerror("失败", raw)


if __name__ == "__main__":
    os.chdir(ROOT)
    App().mainloop()
