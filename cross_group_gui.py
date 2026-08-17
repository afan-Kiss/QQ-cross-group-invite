# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from cross_group_batch import (
    get_cached_members,
    get_state,
    load_source_members,
    start_batch,
    stop_batch,
)
from myqq_api import load_cfg, save_cfg

C = {
    "bg": "#FFFAF3",
    "panel": "#FFF8EE",
    "card": "#FFFDF9",
    "accent": "#D4A574",
    "accent2": "#E8C9A0",
    "text": "#5C483A",
    "muted": "#A08C7D",
    "success": "#76B284",
    "warn": "#E6A858",
    "error": "#DA766C",
    "border": "#EBDCC8",
    "btn": "#F0DCC0",
    "btn_hover": "#E8CFAE",
}


class CreamTheme:
    @staticmethod
    def apply(root: tk.Tk) -> ttk.Style:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        root.configure(bg=C["bg"])
        style.configure(".", background=C["bg"], foreground=C["text"], font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=C["bg"])
        style.configure("Panel.TFrame", background=C["panel"])
        style.configure("Card.TLabelframe", background=C["panel"], foreground=C["text"], bordercolor=C["border"])
        style.configure("Card.TLabelframe.Label", background=C["panel"], foreground=C["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabel", background=C["bg"], foreground=C["text"])
        style.configure("Panel.TLabel", background=C["panel"], foreground=C["text"])
        style.configure("Muted.TLabel", background=C["panel"], foreground=C["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Title.TLabel", background=C["panel"], foreground=C["text"], font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("TEntry", fieldbackground=C["card"], foreground=C["text"], bordercolor=C["border"])
        style.configure("TCheckbutton", background=C["panel"], foreground=C["text"])
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["btn"], foreground=C["text"], padding=[14, 6])
        style.map("TNotebook.Tab", background=[("selected", C["accent2"])])
        style.configure("Treeview", background=C["card"], fieldbackground=C["card"], foreground=C["text"], rowheight=26, bordercolor=C["border"])
        style.configure("Treeview.Heading", background=C["btn"], foreground=C["text"], font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("Accent.TButton", background=C["accent"], foreground="#FFFFFF", font=("Microsoft YaHei UI", 10, "bold"), padding=[12, 6])
        style.map("Accent.TButton", background=[("active", C["accent2"])])
        style.configure("TButton", background=C["btn"], foreground=C["text"], padding=[10, 5])
        style.map("TButton", background=[("active", C["btn_hover"])])
        style.configure("Warn.TLabel", background=C["panel"], foreground=C["warn"])
        style.configure("Error.TLabel", background=C["panel"], foreground=C["error"])
        style.configure("cream.Horizontal.TProgressbar", troughcolor=C["border"], background=C["accent"], thickness=14)
        return style


class CrossGroupApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b")
        self.root.minsize(960, 700)
        self.root.geometry("1020x740")
        self.style = CreamTheme.apply(self.root)
        self._pulse = False
        self._busy = False
        self._load_config()
        self._build()
        self._animate_pulse()
        self._poll_status()

    def _load_config(self) -> None:
        cfg = load_cfg()
        self.cfg_target = tk.StringVar(value=str(cfg.get("target_group_id") or ""))
        self.cfg_source = tk.StringVar(value=str(cfg.get("source_group_id") or ""))
        self.cfg_count = tk.StringVar(value=str(cfg.get("batch_count") or "10"))
        self.cfg_interval = tk.StringVar(value=str(cfg.get("interval_ms") or "2000"))
        self.cfg_filter = tk.BooleanVar(value=bool(cfg.get("filter_staff", True)))
        self.status_var = tk.StringVar(value="\u5c31\u7eea")
        self.stat_var = tk.StringVar(value="\u7b49\u5f85\u5f00\u59cb")
        self.conn_var = tk.StringVar(value="\u25cf \u672c\u5730\u5f15\u64ce")

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer, style="Panel.TFrame", padding=(16, 12))
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b", style="Title.TLabel").pack(side=tk.LEFT)
        self.conn_lbl = ttk.Label(header, textvariable=self.conn_var, style="Muted.TLabel")
        self.conn_lbl.pack(side=tk.RIGHT)

        params = ttk.LabelFrame(outer, text="\u7fa4\u4e0e\u53c2\u6570", style="Card.TLabelframe", padding=12)
        params.pack(fill=tk.X, pady=(0, 10))
        grid = ttk.Frame(params, style="Panel.TFrame")
        grid.pack(fill=tk.X)
        labels = [
            ("\u8981\u62c9\u8fdb\u54ea\u4e2a\u7fa4", self.cfg_target),
            ("\u4ece\u54ea\u4e2a\u7fa4\u62c9\u4eba", self.cfg_source),
            ("\u4e00\u6b21\u62c9\u51e0\u4e2a\u4eba", self.cfg_count),
            ("\u6bcf\u6b21\u95f4\u9694\uff08\u6beb\u79d2\uff09", self.cfg_interval),
        ]
        for i, (lab, var) in enumerate(labels):
            r, c = divmod(i, 2)
            ttk.Label(grid, text=lab, style="Panel.TLabel").grid(row=r, column=c * 2, sticky=tk.W, padx=(0, 6), pady=4)
            ttk.Entry(grid, textvariable=var, width=22).grid(row=r, column=c * 2 + 1, sticky=tk.W, padx=(0, 24), pady=4)
        ttk.Checkbutton(
            grid, text="\u8fc7\u6ee4\u7fa4\u4e3b\u548c\u7ba1\u7406\u5458", variable=self.cfg_filter, style="TCheckbutton"
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=6)

        btns = ttk.Frame(outer, style="Panel.TFrame")
        btns.pack(fill=tk.X, pady=(0, 10))
        self.btn_load = ttk.Button(btns, text="\u52a0\u8f7d\u6210\u5458\u5217\u8868", command=self._on_load)
        self.btn_load.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_start = ttk.Button(btns, text="\u5f00\u59cb\u9080\u8bf7", style="Accent.TButton", command=self._on_start)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(btns, text="\u505c\u6b62", command=self._on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        ttk.Label(btns, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.RIGHT)

        members = ttk.LabelFrame(outer, text="\u53ef\u9080\u8bf7\u6210\u5458", style="Card.TLabelframe", padding=8)
        members.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        cols = ("qq", "nickname", "role")
        self.tree = ttk.Treeview(members, columns=cols, show="headings", height=8)
        self.tree.heading("qq", text="QQ")
        self.tree.heading("nickname", text="\u6635\u79f0")
        self.tree.heading("role", text="\u8eab\u4efd")
        self.tree.column("qq", width=130)
        self.tree.column("nickname", width=220)
        self.tree.column("role", width=80)
        vsb = ttk.Scrollbar(members, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        progress = ttk.LabelFrame(outer, text="\u8fd0\u884c\u72b6\u6001", style="Card.TLabelframe", padding=10)
        progress.pack(fill=tk.X, pady=(0, 10))
        self.pbar = ttk.Progressbar(progress, style="cream.Horizontal.TProgressbar", mode="determinate")
        self.pbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(progress, textvariable=self.stat_var, style="Panel.TLabel").pack(anchor=tk.W)

        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)
        self.log_text = self._make_text_tab(nb, "\u8fd0\u884c\u65e5\u5fd7")
        self.freq_list = self._make_list_tab(nb, "\u9891\u7e41\u9650\u5236", "Warn.TLabel", "\u64cd\u4f5c\u9891\u7e41 / \u9650\u6d41")
        self.err_list = self._make_list_tab(nb, "\u5f02\u5e38\u540d\u5355", "Error.TLabel", "\u9080\u8bf7\u5931\u8d25")

    def _make_text_tab(self, nb: ttk.Notebook, title: str) -> tk.Text:
        frame = ttk.Frame(nb, style="Panel.TFrame", padding=6)
        nb.add(frame, text=title)
        txt = tk.Text(
            frame, height=8, wrap=tk.WORD, bg=C["card"], fg=C["text"],
            relief=tk.FLAT, font=("Consolas", 9), insertbackground=C["accent"],
        )
        txt.pack(fill=tk.BOTH, expand=True)
        return txt

    def _make_list_tab(self, nb: ttk.Notebook, title: str, style: str, hint: str) -> tk.Listbox:
        frame = ttk.Frame(nb, style="Panel.TFrame", padding=6)
        nb.add(frame, text=title)
        ttk.Label(frame, text=hint + "\uff08QQ \u00b7 \u6635\u79f0 \u00b7 \u539f\u56e0\uff09", style=style).pack(anchor=tk.W, pady=(0, 4))
        lb = tk.Listbox(
            frame, height=8, bg=C["card"], fg=C["text"], relief=tk.FLAT,
            font=("Microsoft YaHei UI", 9), selectbackground=C["accent2"],
        )
        lb.pack(fill=tk.BOTH, expand=True)
        return lb

    def _animate_pulse(self) -> None:
        self._pulse = not self._pulse
        st = get_state()
        if st.get("running"):
            dot = "\u25c9" if self._pulse else "\u25cf"
            self.conn_var.set(f"{dot} \u9080\u8bf7\u8fdb\u884c\u4e2d...")
            self.conn_lbl.configure(foreground=C["success"])
        else:
            self.conn_var.set("\u25cf \u672c\u5730\u5f15\u64ce\u5c31\u7eea")
            self.conn_lbl.configure(foreground=C["muted"])
        self.root.after(480, self._animate_pulse)

    def _poll_status(self) -> None:
        st = get_state()
        total = int(st.get("total") or 0)
        done = int(st.get("done") or 0)
        if total > 0:
            self.pbar.configure(mode="determinate", maximum=total, value=done)
        elif st.get("running"):
            self.pbar.configure(mode="indeterminate")
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.configure(mode="determinate", maximum=100, value=0)

        self.stat_var.set(
            f"{st.get('message', '')}  |  \u8fdb\u5ea6 {done}/{total}  \u6210\u529f {st.get('success', 0)}  "
            f"\u9891\u7e41 {len(st.get('frequent', []))}  \u5f02\u5e38 {len(st.get('errors', []))}"
        )
        logs = st.get("logs") or []
        if logs:
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "\n".join(logs))
            self.log_text.see(tk.END)

        self._fill_list(self.freq_list, st.get("frequent") or [])
        self._fill_list(self.err_list, st.get("errors") or [])

        if st.get("running"):
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
            self.btn_load.configure(state=tk.DISABLED)
            cur = st.get("current_nickname") or ""
            qq = st.get("current_qq") or 0
            self.status_var.set(f"\u9080\u8bf7\u4e2d: {cur} ({qq})")
        else:
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
            self.btn_load.configure(state=tk.NORMAL)

        self.root.after(400, self._poll_status)

    @staticmethod
    def _fill_list(lb: tk.Listbox, items: list) -> None:
        rows = [f"{x.get('qq', '')}  {x.get('nickname', '')}  \u2014  {x.get('reason', '')}" for x in items]
        if list(lb.get(0, tk.END)) == tuple(rows):
            return
        lb.delete(0, tk.END)
        for r in rows:
            lb.insert(tk.END, r)

    def _save_config(self) -> None:
        cfg = load_cfg()
        cfg["target_group_id"] = self.cfg_target.get().strip()
        cfg["source_group_id"] = self.cfg_source.get().strip()
        cfg["batch_count"] = self.cfg_count.get().strip()
        cfg["interval_ms"] = self.cfg_interval.get().strip()
        cfg["filter_staff"] = self.cfg_filter.get()
        save_cfg(cfg)

    def _refresh_tree(self, members) -> None:
        self.tree.delete(*self.tree.get_children())
        role_map = {"owner": "\u7fa4\u4e3b", "admin": "\u7ba1\u7406\u5458", "member": "\u6210\u5458"}
        for m in members:
            self.tree.insert("", tk.END, values=(m.qq, m.nickname, role_map.get(m.role.value, "\u672a\u77e5")))

    def _on_load(self) -> None:
        if self._busy:
            return
        try:
            source = int(self.cfg_source.get().strip())
            if source <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u586b\u5199\u6765\u6e90\u7fa4\u53f7")
            return
        self._save_config()
        self._busy = True
        self.status_var.set("\u6b63\u5728\u52a0\u8f7d\u6210\u5458...")
        self.btn_load.configure(state=tk.DISABLED)

        def work() -> None:
            try:
                members = load_source_members(int(source), filter_staff=self.cfg_filter.get())
                self.root.after(0, lambda: self._load_done(members, None))
            except Exception as exc:
                self.root.after(0, lambda: self._load_done([], exc))

        threading.Thread(target=work, daemon=True).start()

    def _load_done(self, members, err) -> None:
        self._busy = False
        self.btn_load.configure(state=tk.NORMAL)
        if err:
            self.status_var.set("\u52a0\u8f7d\u5931\u8d25")
            messagebox.showerror("\u9519\u8bef", str(err))
            return
        self._refresh_tree(members)
        self.status_var.set(f"\u5df2\u52a0\u8f7d {len(members)} \u4eba")

    def _on_start(self) -> None:
        try:
            target = int(self.cfg_target.get().strip())
            source = int(self.cfg_source.get().strip())
            count = int(self.cfg_count.get().strip())
            interval = int(self.cfg_interval.get().strip())
            if target <= 0 or source <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u586b\u5199\u6709\u6548\u7684\u7fa4 ID \u548c\u53c2\u6570")
            return
        if count == 0:
            count = len(get_cached_members())
        if count <= 0:
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u5148\u52a0\u8f7d\u6210\u5458\u5217\u8868")
            return
        self._save_config()
        self.status_var.set("\u542f\u52a8\u4e2d...")
        try:
            start_batch(
                target_group_id=target,
                source_group_id=source,
                count=count,
                interval_ms=interval,
                filter_staff=self.cfg_filter.get(),
            )
        except RuntimeError as exc:
            messagebox.showerror("\u9519\u8bef", str(exc))

    def _on_stop(self) -> None:
        stop_batch()
        self.status_var.set("\u6b63\u5728\u505c\u6b62...")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    CrossGroupApp().run()


if __name__ == "__main__":
    main()
