# -*- coding: utf-8 -*-
"""Sidecar for the merged upstream GUI: local A/B queue, accounts and quota.

The upstream GUI remains the main workbench.  This window only owns the parts
that were local to this fork: durable A/B queues, Paddle account assignment,
the page ledger and optional uploads auto-ingest.  It never edits the upstream
document table or its Runner.
"""
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import ingest
import stages
import workbench_state as wb
from workbench_runner import (CH, CH_ZH, DEFAULT_PARALLEL, MAX_PARALLEL,
                              RunnerHub, _ch_done, _local_paddle_token,
                              load_history, scan_docs)

STATE_RANK = {"未跑": 0, "未完成": 1, "部分异常": 2, "已完成": 3}
CH_SHORT = {"mineru": "M", "dots": "D", "paddle": "P"}


def _fmt_time(ts):
    if not ts:
        return "-"
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "-"


class AccountWindow(tk.Toplevel):
    def __init__(self, master, hub, zone_id, on_change=None):
        tk.Toplevel.__init__(self, master)
        self.title("Paddle 账号与额度")
        self.geometry("820x560")
        self.hub = hub
        self.zone_id = zone_id
        self.on_change = on_change
        self.accounts = hub.accounts
        self.qbook = hub.quota_book
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(top, text="Token 存于 .workbench/accounts.json（不入库），界面只显示首尾。",
                  foreground="#555").pack(side="left")
        cols = ("key", "label", "mask", "limit", "used", "left", "zones")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=9)
        for c, t, w, a in (("key", "账号", 120, "w"), ("label", "名称", 150, "w"),
                           ("mask", "Token", 130, "center"), ("limit", "日额度", 80, "center"),
                           ("used", "今日已用", 80, "center"), ("left", "剩余", 80, "center"),
                           ("zones", "使用区", 90, "center")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        self.tree.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.LabelFrame(self, text="编辑 / 新增")
        form.pack(fill="x", padx=12, pady=6)
        r1 = ttk.Frame(form)
        r1.pack(fill="x", pady=4)
        ttk.Label(r1, text="账号 key").pack(side="left")
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(r1, textvariable=self.key_var, width=14)
        self.key_entry.pack(side="left", padx=(4, 12))
        ttk.Label(r1, text="名称").pack(side="left")
        self.label_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.label_var, width=20).pack(side="left", padx=(4, 12))
        ttk.Label(r1, text="日额度").pack(side="left")
        self.limit_var = tk.StringVar(value="20000")
        ttk.Entry(r1, textvariable=self.limit_var, width=9).pack(side="left", padx=4)

        r2 = ttk.Frame(form)
        r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="Paddle token").pack(side="left")
        self.token_var = tk.StringVar()
        self.token_entry = ttk.Entry(r2, textvariable=self.token_var, width=52, show="*")
        self.token_entry.pack(side="left", padx=4)
        ttk.Button(r2, text="读取本机配置", command=self._read_local).pack(side="left", padx=4)
        ttk.Label(r2, text="编辑时留空 = 保留原 token", foreground="#555").pack(side="left")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Button(buttons, text="新增", command=self._new).pack(side="left")
        ttk.Button(buttons, text="保存", command=self._save).pack(side="left", padx=6)
        ttk.Button(buttons, text="删除", command=self._delete).pack(side="left")
        ttk.Button(buttons, text="刷新", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(buttons, text="关闭", command=self.destroy).pack(side="right")
        ttk.Label(self, text="日额度单位为 PDF 页。一个账号可同时分配给 A/B；共用时日额度也共用。"
                            "本地账本只记预扣，不是 AI Studio 服务端用量。",
                  foreground="#555").pack(fill="x", padx=12, pady=(0, 8))

    def refresh(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for a in self.accounts.list_accounts():
            key = a["key"]
            self.tree.insert("", "end", iid=key, values=(
                key, a["label"], a["token_mask"],
                self.qbook.limit(key), self.qbook.used(key), self.qbook.remaining(key),
                ",".join(self.accounts.zones_of(key)) or "-"))
        if self.zone_id:
            key = self.accounts.assignment(self.zone_id)
            if key in self.tree.get_children():
                self.tree.selection_set(key)
                self.tree.see(key)

    def _selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else ""

    def _on_select(self, _event=None):
        key = self._selected()
        if not key:
            return
        a = self.accounts.get(key) or {}
        self.key_var.set(key)
        self.key_entry.configure(state="disabled")
        self.label_var.set(a.get("label") or key)
        self.limit_var.set(str(self.qbook.limit(key)))
        self.token_var.set("")

    def _new(self):
        self.key_entry.configure(state="normal")
        self.key_var.set("")
        self.label_var.set("")
        self.limit_var.set("20000")
        self.token_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def _read_local(self):
        tok = _local_paddle_token()
        if not tok:
            messagebox.showinfo("读取本机配置", "没有在 PADDLE_API_TOKEN / channels.local.json 找到 token")
            return
        self.token_var.set(tok)
        if not self.label_var.get():
            self.label_var.set("本机账号")

    def _save(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("账号", "请填写账号 key")
            return
        label = self.label_var.get().strip() or key
        try:
            limit = int(self.limit_var.get().strip() or "20000")
        except ValueError:
            messagebox.showwarning("账号", "日额度必须是整数")
            return
        tok = self.token_var.get().strip() or None
        try:
            self.accounts.upsert(key, label, tok, limit)
            self.qbook.set_limit(key, limit)
        except Exception as exc:
            messagebox.showerror("账号", str(exc))
            return
        self.token_var.set("")
        self.refresh()
        if self.on_change:
            self.on_change()

    def _delete(self):
        key = self._selected()
        if not key:
            return
        if not messagebox.askokcancel("删除账号", "删除账号 %s？" % key):
            return
        ok, why = self.accounts.remove(key)
        if not ok:
            messagebox.showwarning("删除账号", why)
            return
        self.refresh()
        if self.on_change:
            self.on_change()


class LocalTaskWindow(tk.Toplevel):
    """Local sidecar: A/B queue, accounts/quota, optional uploads ingest."""

    def __init__(self, master, hub, log):
        tk.Toplevel.__init__(self, master)
        self.title("本地任务台 · A/B")
        self.geometry("1080x620")
        self.minsize(900, 520)
        self.hub = hub
        self.log = log
        self._closing = False
        self._auto = False
        self._auto_thread = None
        self._scanners = {}
        self._stores = {}
        self._auto_pending = []
        self._auto_lock = threading.Lock()
        self._page_cache = {}
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(200, self.refresh)
        self.after(800, self._tick)

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="区").pack(side="left")
        self.zone_var = tk.StringVar(value=self.hub.zones["A"].zid)
        self.zone_box = ttk.Combobox(top, textvariable=self.zone_var, width=10,
                                     state="readonly", values=("A", "B"))
        self.zone_box.pack(side="left", padx=(4, 12))
        self.zone_box.bind("<<ComboboxSelected>>", lambda _e: self._on_zone())
        ttk.Label(top, text="Paddle 账号").pack(side="left")
        self.account_var = tk.StringVar()
        self.account_box = ttk.Combobox(top, textvariable=self.account_var, width=26,
                                        state="readonly")
        self.account_box.pack(side="left", padx=4)
        self.account_box.bind("<<ComboboxSelected>>", lambda _e: self._on_account())
        ttk.Button(top, text="账号与额度…", command=self._open_accounts).pack(side="left", padx=6)
        self.auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="自动监视 uploads", variable=self.auto_var,
                       command=self._toggle_auto).pack(side="left", padx=(12, 0))
        ttk.Button(top, text="打开 uploads", command=self._open_uploads).pack(side="right")
        ttk.Button(top, text="刷新", command=self.refresh).pack(side="right", padx=6)

        self.stat_lbl = ttk.Label(self, text="", foreground="#1d4ed8")
        self.stat_lbl.pack(fill="x", padx=10, pady=(0, 4))

        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, padx=10)
        cols = ("state", "miss", "channels", "pages", "account", "done_at", "runs")
        self.tree = ttk.Treeview(table, columns=cols, show="tree headings", height=16,
                                 selectmode="extended")
        self.tree.heading("#0", text="文档")
        self.tree.column("#0", width=330, anchor="w")
        for c, t, w, a in (("state", "状态", 78, "center"),
                           ("miss", "缺口", 120, "center"),
                           ("channels", "渠道", 90, "center"),
                           ("pages", "页", 50, "center"),
                           ("account", "账号", 100, "center"),
                           ("done_at", "上次完成", 100, "center"),
                           ("runs", "历史", 55, "center")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._sync_buttons())

        act = ttk.Frame(self)
        act.pack(fill="x", padx=10, pady=8)
        ttk.Button(act, text="开始解析", command=self._run_selected).pack(side="left")
        ttk.Button(act, text="补跑缺口", command=self._rerun_gaps).pack(side="left", padx=6)
        ttk.Button(act, text="暂停/继续", command=self._toggle_pause).pack(side="left")
        ttk.Button(act, text="全选", command=self._select_all).pack(side="left", padx=6)
        ttk.Button(act, text="快照", command=self._snapshot_selected).pack(side="left")
        ttk.Button(act, text="打开结果", command=self._open_result).pack(side="left", padx=6)
        self.sel_lbl = ttk.Label(act, text="未选中", foreground="#555")
        self.sel_lbl.pack(side="right")

        self.note = ttk.Label(self, text="", foreground="#555")
        self.note.pack(fill="x", padx=10, pady=(0, 6))

    def _zone(self):
        return self.hub.zones[self.zone_var.get()]

    def _runner(self):
        return self.hub.runner(self.zone_var.get())

    def _on_zone(self):
        self.refresh()

    def _account_items(self):
        rows = []
        for a in self.hub.accounts.list_accounts():
            rows.append((a["key"], a["label"], a["token_mask"]))
        return rows

    def _refresh_accounts(self):
        rows = self._account_items()
        self.account_box.configure(values=tuple("%s · %s" % (k, lab) for k, lab, _m in rows))
        key = self._zone().account
        for k, lab, _m in rows:
            if k == key:
                self.account_var.set("%s · %s" % (k, lab))
                return
        self.account_var.set("")

    def _on_account(self):
        val = self.account_var.get()
        key = val.split(" · ", 1)[0].strip()
        if not key:
            return
        try:
            self.hub.set_account(self.zone_var.get(), key)
        except Exception as exc:
            messagebox.showerror("账号", str(exc))
            self._refresh_accounts()
            return
        self.log("[本地任务] %s 区账号 -> %s（已排队任务保留原账号）" % (self.zone_var.get(), key))
        self._refresh_accounts()

    def _open_accounts(self):
        AccountWindow(self, self.hub, self.zone_var.get(), on_change=self._refresh_accounts)

    def _open_uploads(self):
        try:
            os.startfile(self._zone().up)
        except Exception as exc:
            messagebox.showwarning("打开目录", str(exc))

    def refresh(self):
        if self._closing:
            return
        zone = self._zone()
        try:
            docs = scan_docs(zone)
        except Exception as exc:
            self.log("[本地任务] 扫描失败: %s" % exc)
            docs = {}
        runner = self._runner()
        hist = load_history(zone.hist)
        with runner.lock:
            running = set(runner.running)
            queued = set(runner.queued)
        rows = []
        for doc, d in docs.items():
            state = d["state"]
            if doc in running:
                state = "运行中"
            elif doc in queued:
                state = "排队中"
            miss = d["miss"]
            pages = self._page_cache.get(doc)
            if pages is None:
                try:
                    pages = wb.page_count(d["pdf"])
                except Exception:
                    pages = "?"
                self._page_cache[doc] = pages
            rows.append((doc, state, miss, pages,
                         zone.account, _fmt_time(d.get("done_at")),
                         len(hist.get(doc) or [])))
        rows.sort(key=lambda r: (0 if r[0] in running else 1 if r[0] in queued else 2,
                                 STATE_RANK.get(r[1], 9), -len(hist.get(r[0]) or []), r[0]))
        selected = set(self.tree.selection())
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for doc, state, miss, pages, acct, done, runs in rows:
            ch = " ".join(CH_SHORT[c] if c not in miss else "-" for c in CH)
            self.tree.insert("", "end", iid=doc, text=doc,
                             values=(state, ",".join(CH_ZH.get(c, c) for c in miss) or "-",
                                     ch, pages, acct, done, runs))
            if doc in selected:
                self.tree.selection_add(doc)
        self._refresh_accounts()
        self.sel_lbl.configure(text="未选中" if not self.tree.selection()
                                  else "已选 %d 篇" % len(self.tree.selection()))
        self.stat_lbl.configure(text="%s · %s · Paddle 今日 %d/%d 页（余 %d）" % (
            zone.zid + " · " + zone.label, runner.status(),
            runner.quota.used(), runner.quota.book.limit(zone.account),
            runner.quota.remaining()))
        self.note.configure(text="历史基线不会自动跑；新文件需选中后点开始解析。"
                                "当前区 uploads: %s" % zone.up)

    def _drain_auto(self):
        with self._auto_lock:
            pending, self._auto_pending = self._auto_pending, []
        for zid, ev in pending:
            self._auto_one(zid, ev)

    def _tick(self):
        if self._closing:
            return
        self._drain_auto()
        self.refresh()
        self.after(1200, self._tick)

    def _selected(self):
        return list(self.tree.selection())

    def _select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _sync_buttons(self):
        n = len(self.tree.selection())
        self.sel_lbl.configure(text="未选中" if not n else "已选 %d 篇" % n)

    def _toggle_pause(self):
        runners = list(self.hub.runners.values())
        if all(r.paused for r in runners):
            self.hub.resume_all()
            self.log("[本地任务] 已继续两个区的队列")
        else:
            self.hub.pause_all()
            self.log("[本地任务] 已暂停（当前子进程会跑完）")
        self.refresh()

    def _reserve(self, zone, docs):
        rows = scan_docs(zone)
        need = [d for d in docs if not _ch_done(d, "paddle", zone.out)]
        if not need:
            return True
        runner = self.hub.runner(zone.zid)
        if not (self.hub.accounts.get(zone.account) or {}).get("token"):
            messagebox.showwarning("账号", "账号 %s 没有 Paddle token，请先在账号与额度里配置。"
                                   % zone.account)
            return False
        page_map = {}
        total = 0
        for d in need:
            pdf = (rows.get(d) or {}).get("pdf")
            if not pdf:
                messagebox.showwarning("额度", "找不到 %s 的 PDF，无法估算页数" % d)
                return False
            try:
                n = int(wb.page_count(pdf))
            except Exception:
                messagebox.showwarning("额度", "无法读取 %s 页数，拒绝提交" % d)
                return False
            page_map[d] = n
            total += n
        if total > runner.quota.remaining():
            messagebox.showwarning(
                "额度不足", "本批需 %d 页，账号 %s 只剩 %d 页。\n请换账号或等明日额度。"
                % (total, zone.account, runner.quota.remaining()))
            return False
        for d, n in page_map.items():
            runner.quota.reserve("%s/%s" % (zone.zid, d), n)
        return True

    def _submit(self, docs, automatic=False, zone=None, runner=None):
        zone = zone or self._zone()
        runner = runner or self.hub.runner(zone.zid)
        if not docs:
            if not automatic:
                messagebox.showinfo("本地任务", "未选择文档")
            return
        rows = scan_docs(zone)
        missing = [d for d in docs if d in rows and rows[d]["miss"]]
        if not automatic and not missing and all(rows.get(d, {}).get("state") == "已完成" for d in docs):
            if not messagebox.askokcancel("重新解析", "选中文档已完整，仍要重跑整链？"):
                return
        if not self._reserve(zone, docs):
            return
        for d in docs:
            row = rows.get(d)
            if not row:
                continue
            if runner.submit(d, row["pdf"], list(stages.ORDER), trigger="本地任务台",
                             clear=row["miss"]):
                if automatic:
                    self.log("[自动] %s 已入队" % d)
        self.refresh()

    def _run_selected(self):
        self._submit(self._selected())

    def _rerun_gaps(self):
        docs = [d for d in self._selected() if (scan_docs(self._zone()).get(d) or {}).get("miss")]
        if not docs:
            messagebox.showinfo("补跑缺口", "选中文档没有缺失渠道")
            return
        self._submit(docs)

    def _snapshot_selected(self):
        docs = self._selected()
        if not docs:
            messagebox.showinfo("快照", "未选择文档")
            return
        ok = 0
        for d in docs:
            try:
                if wb.snapshot_doc(self._zone(), d, "manual sidecar snapshot"):
                    ok += 1
            except Exception as exc:
                self.log("[快照] %s 失败: %s" % (d, exc))
        messagebox.showinfo("快照", "已快照 %d/%d 篇" % (ok, len(docs)))

    def _open_result(self):
        docs = self._selected()
        if len(docs) != 1:
            messagebox.showinfo("打开结果", "请选中一篇")
            return
        fp = os.path.join(self._zone().out, docs[0], "index.html")
        if not os.path.isfile(fp):
            messagebox.showwarning("打开结果", "还没有 index.html")
            return
        os.startfile(fp)

    def _toggle_auto(self):
        self._auto = bool(self.auto_var.get())
        if self._auto:
            if self._auto_thread is None or not self._auto_thread.is_alive():
                self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
                self._auto_thread.start()
            self.log("[自动] 已开启 uploads 监视（只处理新文件，历史基线不动）")
        else:
            self.log("[自动] 已关闭 uploads 监视")
        self.note.configure(text="自动监视：%s" % ("开" if self._auto else "关"))

    def _auto_loop(self):
        while not self._closing:
            if self._auto:
                for zid, zone in self.hub.zones.items():
                    try:
                        store = self._stores.setdefault(zid, ingest.IngestStore(
                            os.path.join(zone.root, ".workbench", "ingest.json")))
                        scanner = self._scanners.get(zid)
                        if scanner is None:
                            scanner = ingest.IngestScanner(store, zone.up)
                            self._scanners[zid] = scanner
                        events = scanner.scan()
                        for ev in events:
                            if ev.get("status") == "baseline":
                                self.log("[自动] %s 区首次基线 %s 篇，历史文件不自动跑"
                                         % (zid, ev.get("count")))
                            elif ev.get("status") == "pending":
                                if self.hub.runner(zid).paused:
                                    self.log("[自动] %s 发现新文件，但 %s 区队列暂停中"
                                             % (ev.get("doc"), zid))
                                    continue
                                with self._auto_lock:
                                    self._auto_pending.append((zid, ev))
                    except Exception as exc:
                        self.log("[自动] %s 扫描失败: %s" % (zid, exc))
            time.sleep(3)

    def _auto_one(self, zid, ev):
        doc = ev.get("doc")
        if not doc:
            return
        zone = self.hub.zones[zid]
        if doc not in scan_docs(zone):
            return
        self._submit([doc], automatic=True, zone=zone, runner=self.hub.runner(zid))

    def close(self):
        self._closing = True
        self.hub.pause_all()
        self.destroy()
