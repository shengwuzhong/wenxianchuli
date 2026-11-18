# -*- coding: utf-8 -*-
"""桌面工作台(tkinter, 零依赖): 任务状态 + 运行历史 + 一键重跑。

动机(2026-11-12): webapp 每次调试要新开浏览器窗口, 且 JOBS 是内存态, 服务一重启全部归 0。
本 GUI 的两条硬约束:
  状态从文件系统派生 — out/<doc>/index.html + raw/<ch>{,_api} 就是真值, 重启/断电都不丢;
  历史落盘追加 — gui_runs.jsonl 每跑一篇记一行(文档/起止/结果/渠道状态/触发方式)。

用法:  python gui.py   (或双击 启动GUI.bat)
"""
import io
import json
import os
import queue
import re
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import archive
import field_audit as fa
import qc
import stages
import workbench_state as wb
from docid import doc_of

ROOT = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(ROOT, "uploads")
OUT = os.path.join(ROOT, "out")
HIST_FP = os.path.join(ROOT, "gui_runs.jsonl")
SINGLE_PORT = 8790   # 单实例互斥端口: bind 由内核原子完成, 无文件锁的 check-then-act 竞态窗
CH = ("mineru", "dots", "paddle")
CH_ZH = {"mineru": "MinerU", "dots": "dots.ocr", "paddle": "PaddleOCR"}
NER_ROOT = os.path.join(ROOT, "out_llm_trial")   # ner_lite 产物, 仅用于"机构"的口径对齐
DEFAULT_DAILY_PAGES = 20000


def _local_paddle_token():
    """从本机私有配置取 Paddle token，仅用于首次建账号；之后以账号库为准。"""
    tok = (os.environ.get("PADDLE_API_TOKEN") or "").strip()
    if tok:
        return tok
    for name in ("channels.local.json", "channels.json"):
        try:
            with io.open(os.path.join(ROOT, name), encoding="utf-8-sig") as f:
                cfg = json.load(f)
            tok = str((cfg.get("paddle_api") or {}).get("token") or "").strip()
            if tok:
                return tok
        except Exception:
            continue
    return ""

# 质检口径已抽到 qc.py(2026-11-13): 归档要在**搬走产物之前**把质检状态快照进索引,
# 而归档是 CLI 也能跑的路径, 不能为此把 tkinter 拖进依赖链。
# 判定内容未变: 必抽项齐全性, 缺任一即红, 不看置信度, 三类实体可选。
qc_of = qc.qc_of
QC_REQUIRED, QC_ONE_OF = qc.QC_REQUIRED, qc.QC_ONE_OF
QC_OPTIONAL = ("dataset", "funding", "software")   # 实体三类可选, 不参与报红


def _acquire_instance_sock(attempts=15, wait=0.3):
    """单实例: 独占本机端口即存活证明。bind 由内核原子完成, 无文件锁的 check-then-act 竞态窗。
    attempts>1: 一键重启时新老进程交接端口有空窗, 新进程重试等待(老进程退出即释放)。"""
    import socket
    for i in range(attempts):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", SINGLE_PORT))
            s.listen(1)
            return s
        except OSError:
            s.close()
            if i < attempts - 1:
                time.sleep(wait)
    return None


_WEBAPP_CACHE = [0.0, False]


def webapp_alive():
    """旧 web 服务(8765)与 GUI 同时监视 uploads 会并发跑同一篇、写坏产物(13563526 实证)——检出即提醒。

    2026-11-12 卡顿修复: 原来是 urllib urlopen(timeout=1.5), 对端不响应时每次"刷新"都卡满
    1.5s(实测 1.574s, 而刷新其余部分合计仅 0.05s)。改成 0.15s 的 TCP 连接探测(不发 HTTP,
    不做请求往返), 结果再缓存 30s, 连续点刷新不再重复探测。
    """
    import socket
    now = time.time()
    if now - _WEBAPP_CACHE[0] < 30:
        return _WEBAPP_CACHE[1]
    s = socket.socket()
    s.settimeout(0.15)
    try:
        s.connect(("127.0.0.1", 8765))
        alive = True
    except OSError:
        alive = False
    finally:
        s.close()
    _WEBAPP_CACHE[:] = [now, alive]
    return alive




def _dir_has_files(d):
    if not os.path.isdir(d):
        return False
    with os.scandir(d) as it:   # 迭代器必须关闭, 否则 Windows 拖住目录句柄
        return any(True for _ in it)


def _ch_done(doc, ch, out_root=None):
    out_root = out_root or OUT
    return (_dir_has_files(os.path.join(out_root, doc, "raw", ch))
            or _dir_has_files(os.path.join(out_root, doc, "raw", ch + "_api")))


def scan_docs(up_root=None, out_root=None, arch_root=None):
    """文件系统派生的文档状态(真值): 未跑/未完成/缺渠道/完成 + 渠道勾选 + 完成时间。

    已归档的文档不出现在工作台(2026-11-13): 归档把 PDF 与 out/ 都移走了, 但索引是权威凭据,
    所以先按索引过滤一遍——否则手工把产物挪回来、或只归档了 PDF, 就会漏成一条"无PDF"的僵尸行。

    2026-11-18: 增加 up_root/out_root/arch_root, 让物理隔离的 A/B 区共用同一套扫描逻辑。
    """
    up_root = up_root or UP
    out_root = out_root or OUT
    arch_root = arch_root or os.path.join(ROOT, "archive")
    try:
        done_docs = archive.archived_set(arch_root)
    except ValueError:
        done_docs = set()      # 索引损坏: 宁可多显示几条, 也不能让所有文档凭空消失
    docs = {}
    for f in sorted(os.listdir(up_root)) if os.path.isdir(up_root) else []:
        if not f.lower().endswith(".pdf"):
            continue
        doc = doc_of(f)
        if doc in done_docs:
            continue
        dd = os.path.join(out_root, doc)
        idx = os.path.join(dd, "index.html")
        ch = {c: _ch_done(doc, c, out_root) for c in CH}
        done_at = os.path.getmtime(idx) if os.path.exists(idx) else None
        miss = [c for c in CH if not ch[c]]
        if done_at is None:
            state = "未完成" if _dir_has_files(dd) else "未跑"
        elif miss:
            state = "缺渠道"
        elif not os.path.isfile(os.path.join(dd, "metadata.json")):
            state = "未完成"
        else:
            state = "完成"
        docs[doc] = {"pdf": os.path.join(up_root, f), "state": state, "ch": ch,
                     "done_at": done_at, "miss": miss}
    # out/ 里有产物但 uploads 里 PDF 已没了的(清库残留), 也列出来只读展示
    if os.path.isdir(out_root):
        for d in sorted(os.listdir(out_root)):
            if d in docs or d.startswith("_") or d in done_docs:
                continue
            if not os.path.isdir(os.path.join(out_root, d)):
                continue
            idx = os.path.join(out_root, d, "index.html")
            if not os.path.exists(idx):
                continue
            docs[d] = {"pdf": None, "state": "无PDF",
                       "ch": {c: _ch_done(d, c, out_root) for c in CH},
                       "done_at": os.path.getmtime(idx), "miss": []}
    return docs


def load_history(fp=None):
    """gui_runs.jsonl → {doc: [记录...]}(按时间序); 文件损坏时跳过坏行。"""
    hist = {}
    fp = fp or HIST_FP
    if not os.path.exists(fp):
        return hist
    for ln in io.open(fp, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        hist.setdefault(r.get("doc") or "", []).append(r)
    return hist


# 并发: 篇与篇互不依赖(各写自己的 out/<doc>/), 所以能同时跑。
# 上限不是 CPU 决定的, 是三类共享资源决定的(见 crossproc.py): LLM 默认 2 路、
# 渠道 API 默认 3 路、LLM 默认 2 路。并发数调大到 8 也不会让这些资源变多,
# 只会让排队发生在更里面一层 —— 所以给 8 就够了, 再大只是把等待换个地方排。
DEFAULT_PARALLEL = 5
MAX_PARALLEL = 8
PREFS_FP = os.path.join(ROOT, ".gui_prefs.json")


def load_prefs(fp=None):
    try:
        with io.open(fp or PREFS_FP, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def save_prefs(d, fp=None):
    try:
        fp = fp or PREFS_FP
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with io.open(fp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def append_history(rec, fp=None):
    with io.open(fp or HIST_FP, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


class Runner(object):
    """串行跑阶段子集: 队列依次执行; 成功渠道走缓存, 只有 clear 指定的渠道重取。

    状态控制三原则(2026-11-12 全面检修):
      同 doc 去重 — 运行中/排队中的文档拒绝重复入队(连点防并发写同一产物);
      单任务异常隔离 — BaseException 级捕获 + finally task_done, 一个任务崩了工作线程照跑;
      忙→闲转换压后 — 查看器重建完成才置闲, 下一任务不会撞上上一任务 trailing 写盘,
      自动刷新也只会看到落定状态。

    阶段化(2026-11-12 晚): 入队单位从"整条链"变成"阶段子集", 由 stages.py 执行并按序
    依赖校验; 全链预设等价于原 pipeline.main, 后链子集秒级完成。
    """

    def __init__(self, zone, quota, log, parallel=None, paused=True, accounts=None):
        self.zone = zone
        self.quota = quota
        self.accounts = accounts
        self.log = log
        self.q = queue.Queue()          # (task_id, doc, pdf, ids, clear, trigger, account_key)
        self.running = {}               # doc -> (trigger, started): 并发下"当前在跑"是一个集合
        self.queued = set()             # 运行中+排队中的 doc(去重)
        self.parallel = int(parallel or DEFAULT_PARALLEL)   # 同时跑几篇(可在界面调)
        self.lock = threading.Lock()
        self._hist_lock = threading.Lock()   # gui_runs.jsonl 追加: 并发下多线程同时写会交错
        self.store = wb.TaskStore(zone.db)
        self.store.mark_interrupted_running()
        self.paused = bool(paused)
        threading.Thread(target=self._loop, daemon=True).start()

    # 热更新(2026-11-12 加的模块级 importlib.reload)已随"一篇一子进程"取消:
    # 每个任务都在新进程里跑, 天然 import 到磁盘上的最新代码, 不必再靠 mtime 猜。
    # 这里只留一条提醒 —— 代码改动在**下次任务**生效, 不影响正在跑的进程。

    def submit(self, doc, pdf, ids, trigger="重跑", clear=(), account=None):
        acct = account or self.zone.account
        row, dup = self.store.enqueue(doc, pdf, ids, clear, trigger, account=acct)
        if row is None:
            self.log("[队列] %s 已有任务在跑/排队, 跳过重复提交" % doc)
            return False
        with self.lock:
            self.queued.add(doc)
        self.q.put((row["id"], doc, pdf, tuple(ids), tuple(clear), trigger, acct))
        self.log("[队列] %s 已加入 (%s · %d 段 · 账号 %s)%s" % (
            doc, trigger, len(ids), acct, " · 等待「继续」" if self.paused else ""))
        return True

    def _completed_since(self, r):
        try:
            started = time.mktime(time.strptime(r.get("started") or "", "%Y-%m-%d %H:%M:%S"))
            fp = os.path.join(self.zone.out, r["doc"], "index.html")
            return os.path.isfile(fp) and os.path.getmtime(fp) >= started
        except Exception:
            return False

    def resume(self):
        """把持久账本里的排队/中断任务重新放回内存队列。"""
        rows = self.store.pending()
        n = 0
        for r in rows:
            pid = wb.running_pid(r["doc"], self.zone.out)
            if pid and wb.pid_alive(pid):
                self.log("[继续] %s 仍有旧子进程 pid=%s 在跑，先不重复提交" % (r["doc"], pid))
                continue
            if r["status"] == "interrupted" and self._completed_since(r):
                self.store.finish(r["id"], True, "旧子进程已完成")
                self.log("[继续] %s 检测到旧子进程已完成，不重复跑" % r["doc"])
                continue
            if r["status"] == "interrupted":
                self.store.requeue(r["id"])
            with self.lock:
                if r["doc"] in self.queued:
                    continue
                self.queued.add(r["doc"])
            self.q.put((r["id"], r["doc"], r.get("pdf"), tuple(r.get("ids") or []),
                        tuple(r.get("clear") or []), r.get("trigger") or "断点续跑",
                        r.get("account") or self.zone.account))
            n += 1
        self.paused = False
        if n:
            self.log("[继续] %s 恢复 %d 个排队/中断任务" % (self.zone.label, n))
        return n

    def pause(self):
        self.paused = True

    def set_parallel(self, n):
        """改并发数。只影响**之后**的调度: 已在跑的不动, 排队里的下一拍按新值放行。"""
        n = max(1, min(int(n), MAX_PARALLEL))
        old = self.parallel
        self.parallel = n
        if n != old:
            self.log("[并发] %d -> %d 篇同时跑" % (old, n))
        return n

    def _loop(self):
        """调度线程: 只负责起任务线程, 不管任务内容。

        为什么不让每个 worker 线程自己去 q.get(): 那样并发数就绑死在"开了几个线程"上,
        运行期改不了。这里由 _active 计数决定是否放行 —— 并发数变成可调参数而不是线程数。
        """
        while True:
            while self.paused:
                time.sleep(0.2)
            while self._active_count() >= self.parallel:
                time.sleep(0.15)
            task_id, doc, pdf, ids, clear, trigger, account = self.q.get()
            self.store.mark_running(task_id)
            t = threading.Thread(target=self._task,
                                 args=(task_id, doc, pdf, ids, clear, trigger, account),
                                 daemon=True)
            t.start()

    def _active_count(self):
        with self.lock:
            return len(self.running)

    def _task(self, task_id, doc, pdf, ids, clear, trigger, account=""):
        ok, err = False, ""
        try:
            ok, err = self._run_one(doc, pdf, ids, clear, trigger, account)
        except BaseException as e:   # 单任务异常不许杀死调度线程
            err = str(e)[:200]
            self.log("[异常] %s 任务抛出: %s" % (doc, e))
        finally:
            self.store.finish(task_id, ok, err)
            with self.lock:
                self.queued.discard(doc)
                self.running.pop(doc, None)
            self.q.task_done()

    def _run_one(self, doc, pdf, ids, clear, trigger, account=""):
        account = account or self.zone.account
        token = ""
        if self.accounts is not None:
            rec = self.accounts.get(account)
            token = (rec or {}).get("token") or ""
            if "paddle" in ids and not token:
                self.log("[账号] %s 缺少 Paddle token，拒绝提交 (账号 %s)" % (doc, account))
                return False, "账号 %s 缺少 Paddle token" % account
        try:
            snap = wb.snapshot_doc(self.zone, doc, "%s · %s" % (trigger, ",".join(ids)))
        except Exception as e:
            self.log("[快照] %s 版本快照失败，拒绝覆盖: %s" % (doc, e))
            return False, "版本快照失败: %s" % str(e)[:160]
        if snap:
            self.log("[快照] %s 已保存到 %s" % (doc, snap))
        for ch in clear:
            for sub in (ch, ch + "_api"):
                d = os.path.join(self.zone.out, doc, "raw", sub)
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            self.log("[重取] %s 渠道 %s 缓存已清" % (doc, ch))
        with self.lock:
            self.running[doc] = (trigger, time.time())
        t0 = time.time()

        # 一篇一子进程: 子进程里 stdout/stderr 全部经 queue 回流, 所以这里只需给日志加篇名,
        # 并发时才知道哪一行属于哪篇。pipeline.log 的猴补丁不再需要(全局状态不能跨进程)。
        def _hook(s):
            self.log("[%s] %s" % (doc, str(s)))

        res = {"ok": False, "results": {}, "error": ""}
        job = {"doc": doc, "ids": list(ids), "pdf": pdf}
        if token:
            job["paddle_token"] = token
        try:
            res = stages.run_one_child(job, log=_hook, out_root=self.zone.out,
                                       ner_root=os.path.join(self.zone.ner, "fds_extract", "ner_lite"))
        except Exception as e:   # stages.run_one_child 内部已兜异常; 这里兜它自己(如进程起不来)
            res = {"ok": False, "results": {}, "error": str(e)[:200]}
        ok = bool(res.get("ok"))
        rec = {"doc": doc, "trigger": trigger, "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
               "elapsed_s": int(time.time() - t0), "ok": ok, "err": res.get("error") or None,
               "selected": list(ids), "parallel": self.parallel, "account": account,
               "stages": {k: ("ok" if v.get("ok") else ("skip" if v.get("skipped") else "fail"))
                          for k, v in (res.get("results") or {}).items()},
               "channels": {c: _ch_done(doc, c, self.zone.out) for c in CH}}
        with self._hist_lock:
            append_history(rec, self.zone.hist)
        # 不替用户补跑未勾选的阶段(2026-11-12 用户定: 耦合的地方不要一起重跑)。
        # 元数据/NER 变了而没勾 viewer, 只在日志里提醒一句, 由人决定要不要补一段。
        if "viewer" not in ids and any(i in ids for i in stages.META_IDS + ("ner",)):
            self.log("[提示] %s 元数据/实体已变但未勾选「对照查看器」段, HTML 仍是上一版" % doc)
        self.log("[完成] %s %s (耗时 %ds · %d 段)%s" % (
            doc, "成功" if ok else "失败", rec["elapsed_s"], len(ids),
            (" · " + rec["err"]) if rec["err"] else ""))
        with self.lock:
            self.running.pop(doc, None)
        return ok, rec.get("err") or ""

    def status(self):
        with self.lock:
            docs = sorted(self.running)
        n = self.q.qsize()
        paused = "已暂停 · " if self.paused else ""
        if docs:
            head = ", ".join(docs[:3]) + (" …" if len(docs) > 3 else "")
            return "%s正在跑 %d/%d 篇 (并发 %d): %s · 排队 %d" % (
                paused, len(docs), self.parallel, self.parallel, head, n)
        return "%s空闲 · 并发 %d · 排队 %d" % (paused, self.parallel, n)

    def is_busy(self):
        with self.lock:
            busy = bool(self.running)
        return busy or self.q.qsize() > 0

    def elapsed(self):
        """最久那篇已跑几秒(心跳用它: 并发下每篇起点不同, 报最大值才知道有没有真卡住)。"""
        with self.lock:
            ts = [v[1] for v in self.running.values()]
        return int(time.time() - min(ts)) if ts else 0

    def cur_doc(self):
        with self.lock:
            docs = sorted(self.running)
        return (", ".join(docs[:3]) + (" …" if len(docs) > 3 else "")) if docs else ""


class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("KCI 解析工作台")
        self.geometry("1180x720")
        self.minsize(900, 560)
        self.q = queue.Queue()
        self.zones = wb.make_zones(ROOT)
        zid = os.environ.get("KCI_ACTIVE_ZONE", "A")
        self.zone_id = zid if zid in self.zones else "A"
        self.zone = self.zones[self.zone_id]
        self._prefs = load_prefs(self.zone.prefs)
        daily = int(self._prefs.get("paddle_daily_pages") or DEFAULT_DAILY_PAGES)
        self.accounts = wb.AccountStore(os.path.join(ROOT, ".workbench", "accounts.json"),
                                        DEFAULT_DAILY_PAGES)
        tok = _local_paddle_token()
        if tok:
            self.accounts.bootstrap(tok, "本机账号", daily_pages=daily)
        self.qbook = wb.QuotaBook(os.path.join(ROOT, ".workbench", "quota.json"), daily)
        self.runners = {}
        for z in self.zones.values():
            p = load_prefs(z.prefs)
            z.account = self.accounts.assignment(z.zid) or "primary"
            rec = self.accounts.get(z.account) or {}
            zq = self.qbook.account(z.account, rec.get("daily_pages") or DEFAULT_DAILY_PAGES)
            self.runners[z.zid] = Runner(z, zq, self._log, parallel=p.get("parallel"),
                                         paused=True, accounts=self.accounts)
        self.runner = self.runners[self.zone_id]
        self.quota = self.runner.quota
        self._was_busy = False
        self._webapp_on = False
        self._entity_cache = {}
        self._page_cache = {}
        self._last_unrun = None
        self._audit_win = None
        self._acct_win = None
        self._paused = True
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.after(100, self._drain)
        self.after(500, self.refresh)
        self.after(700, self._startup_prompt)
        self._log("就绪: 当前 %s; 拖 PDF 到该区 uploads; Ctrl/Shift 多选可批量。"
                  "打开后先确认「继续」，再恢复上次排队/中断任务。" % self.zone.label)

    # ---------- 界面 ----------
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="工作区").pack(side="left")
        self.zone_var = tk.StringVar(value=self.zone.label)
        self.zone_box = ttk.Combobox(top, textvariable=self.zone_var, width=12,
                                     state="readonly",
                                     values=[z.label for z in self.zones.values()])
        self.zone_box.pack(side="left", padx=(4, 8))
        self.zone_box.bind("<<ComboboxSelected>>", self._on_zone)
        self.btn_resume = ttk.Button(top, text="继续", command=self._toggle_run)
        self.btn_resume.pack(side="left", padx=(0, 6))
        ttk.Button(top, text="刷新", command=self.refresh).pack(side="left")
        ttk.Button(top, text="重启", command=self._restart).pack(side="left", padx=6)
        ttk.Button(top, text="打开 uploads 目录",
                   command=lambda: self._open(self.zone.up)).pack(side="left", padx=6)
        ttk.Button(top, text="打开 out 目录",
                   command=lambda: self._open(self.zone.out)).pack(side="left")
        # 归档清单是全局视图(不依赖选中), 所以入口在顶栏而不是操作条
        ttk.Button(top, text="已归档…", command=self._open_archive_list).pack(side="left", padx=6)
        # 浏览器工作台(拖拽上传 + 三渠道并排调参)也收进这里: 用户只记"打开这个工作台"一个动作,
        # 不必再分辨该双击 start.bat 还是 启动GUI.bat(2026-11-13 入口收口)。
        ttk.Button(top, text="浏览器工作台", command=self._open_webapp).pack(side="left")
        # 并发数: 这是"同时跑几篇", 不是"一篇跑多快"。调大只影响排队位置, 见 crossproc.py。
        ttk.Label(top, text="并发").pack(side="left", padx=(12, 2))
        self.par_var = tk.StringVar(value=str(self.runner.parallel))
        self.par_box = ttk.Combobox(top, textvariable=self.par_var, width=3, state="readonly",
                                    values=[str(i) for i in range(1, MAX_PARALLEL + 1)])
        self.par_box.pack(side="left")
        self.par_box.bind("<<ComboboxSelected>>", self._on_parallel)

        # 账号单独一行: P2 起 Paddle 额度按账号计, 不能让 A/B 的 token 与页数混在一起。
        acct = ttk.Frame(self)
        acct.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Label(acct, text="Paddle 账号").pack(side="left")
        self.acct_var = tk.StringVar(value="")
        self.acct_box = ttk.Combobox(acct, textvariable=self.acct_var, width=24,
                                     state="readonly", values=[])
        self.acct_box.pack(side="left", padx=(4, 6))
        self.acct_box.bind("<<ComboboxSelected>>", self._on_account)
        ttk.Button(acct, text="账号与额度…", command=self._open_accounts).pack(side="left")
        self.acct_hint = ttk.Label(acct, text="", foreground="#555")
        self.acct_hint.pack(side="left", padx=12)

        # 状态栏单独占窗口底部一行: 并发跑 5 篇时它要报"哪几篇在跑", 挤在顶栏右侧会跟
        # 6 个按钮抢宽度(实测被压到 0 宽, 整条状态直接消失)。
        self.status_lbl = ttk.Label(self, text="", anchor="w")
        self.status_lbl.pack(side="bottom", fill="x", padx=12, pady=(0, 6))

        mid = ttk.Panedwindow(self, orient="vertical")
        mid.pack(fill="both", expand=True, padx=10)

        # 文档表(多选: Ctrl/Shift 批量, 操作按钮对选中集生效)
        wrap = ttk.Frame(mid)
        cols = ("state", "qc", "entity", "mineru", "dots", "paddle", "done_at", "runs")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings", height=12,
                                 selectmode="extended")
        self.tree.heading("#0", text="文档")
        for c, w, t in (("state", 70, "状态"), ("qc", 280, "质检 · 必抽项"),
                        ("entity", 58, "实体"),
                        ("mineru", 58, "MinerU"), ("dots", 58, "dots"),
                        ("paddle", 62, "Paddle"), ("done_at", 118, "上次完成"),
                        ("runs", 86, "历史")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center")
        self.tree.column("#0", width=180)
        self.tree.column("qc", anchor="w")   # 缺项名要能读, 左对齐; 其余列居中
        self.tree.tag_configure("qc_bad", foreground="#b03030")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._sync_buttons())
        self.tree.bind("<Double-1>", lambda e: self._open_viewer())
        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<Control-a>", self._select_all)
        mid.add(wrap, weight=3)

        # 操作条(对选中文档)
        act = ttk.Frame(mid)
        self.stage_vars = {}
        for sid in stages.ORDER:
            self.stage_vars[sid] = tk.BooleanVar(value=(sid in stages.DEFAULT_IDS))
        # 一个键两个热区(2026-11-12 用户定):
        #   主区(左)   = 执行「阶段菜单」里当前勾选的阶段, 与菜单里的"执行选中阶段"完全等价;
        #   右端小箭头 = 只负责打开菜单改勾选。
        # 必须是同一个控件——拆成两个按钮会变成"两个键", 用 Menubutton 又会让点哪都弹菜单、
        # 逼用户再确认一次。所以用单个 Button + 按下坐标判断落在哪个热区。
        # 「快速重跑(跳NER)」仍是独立键: 它存在的目的就是不重复调 LLM。
        grp = ttk.Frame(act)
        grp.pack(side="left", padx=(4, 8))
        self.btn_rerun = ttk.Button(grp, text="一键重跑  ▾", command=self._on_rerun_click)
        self.btn_rerun.pack(side="left")
        self.btn_rerun.bind("<ButtonPress-1>", self._note_click_x)
        self.btn_quick = ttk.Button(grp, text="快速重跑(跳NER)", command=self._rerun_fast)
        self.btn_quick.pack(side="left", padx=(4, 0))
        self.stage_menu = tk.Menu(self, tearoff=0, postcommand=self._build_stage_menu)
        self.btn_gaps = ttk.Button(act, text="重跑缺口", command=self._rerun_gaps)
        self.btn_retry = ttk.Button(act, text="重试缺失渠道", command=self._retry_missing)
        self.btn_view = ttk.Button(act, text="对照查看器", command=self._open_viewer)
        self.btn_audit = ttk.Button(act, text="字段审计…", command=self._open_audit)
        self.btn_index = ttk.Button(act, text="结果总览", command=self._open_index)
        # 归档与"查看已归档"是两个独立键: 前者对选中集生效, 后者是全局清单(顶栏), 不合并
        self.btn_archive = ttk.Button(act, text="归档选中", command=self._archive_selected)
        for b in (self.btn_gaps, self.btn_retry, self.btn_view, self.btn_audit,
                  self.btn_index, self.btn_archive):
            b.pack(side="left", padx=4)
        self.sel_lbl = ttk.Label(act, text="未选中")
        self.sel_lbl.pack(side="left", padx=12)
        mid.add(act, weight=0)

        # 日志
        logw = ttk.Frame(mid)
        self.logtxt = scrolledtext.ScrolledText(logw, height=10, state="disabled", font=("Consolas", 9))
        self.logtxt.pack(fill="both", expand=True)
        mid.add(logw, weight=2)

        self._sync_accounts()
        self.after(1000, self._tick_status)

    def _on_parallel(self, _ev=None):
        try:
            n = self.runner.set_parallel(int(self.par_var.get()))
        except (TypeError, ValueError):
            return
        self.par_var.set(str(n))
        self._prefs["parallel"] = n
        save_prefs(self._prefs, self.zone.prefs)

    def _account_items(self):
        return self.accounts.list_accounts()

    def _sync_accounts(self):
        """刷新账号下拉; 选中项跟随当前工作区分配。"""
        items = self._account_items()
        vals = ["%s · %s" % (a["label"], a["key"]) for a in items]
        self.acct_box["values"] = vals
        key = self.zone.account
        idx = next((i for i, a in enumerate(items) if a["key"] == key), -1)
        if idx >= 0:
            self.acct_var.set(vals[idx])
        elif vals:
            self.acct_var.set(vals[0])
        self._refresh_account_hint()

    def _refresh_account_hint(self):
        key = self.zone.account
        if not self.accounts.list_accounts():
            self.acct_hint.configure(text="未配置 Paddle 账号；点「账号与额度…」新增")
            return
        s = self.runner.quota.summary()
        zones = self.accounts.zones_of(key)
        shared = "A/B 共用" if len(zones) > 1 else ("区 %s" % zones[0] if zones else "未分配")
        self.acct_hint.configure(
            text="%s · 今日 %d/%d 页 · 余 %d · %s" %
                 (key, s["used"], s["limit"], s["remaining"], shared))

    def _on_account(self, _ev=None):
        items = self._account_items()
        idx = self.acct_box.current()
        if idx < 0 or idx >= len(items):
            return
        key = items[idx]["key"]
        if key == self.zone.account:
            return
        self.accounts.assign(self.zone.zid, key)
        rec = self.accounts.get(key) or {}
        self.zone.account = key
        self.runner.quota = self.qbook.account(key, rec.get("daily_pages") or DEFAULT_DAILY_PAGES)
        self.quota = self.runner.quota
        self._refresh_account_hint()
        self._log("[账号] %s 改用 %s（新任务生效；已排队任务保留原账号）" %
                  (self.zone.label, key))

    def _open_accounts(self):
        try:
            if self._acct_win is not None and self._acct_win.winfo_exists():
                self._acct_win.lift()
                self._acct_win.focus_force()
                return
        except tk.TclError:
            pass
        try:
            self._acct_win = AccountsWindow(self)
        except tk.TclError:
            self._acct_win = None

    def _on_zone(self, _ev=None):
        label = self.zone_var.get()
        z = next((x for x in self.zones.values() if x.label == label), None)
        if z is None:
            return
        self.zone = z
        self.zone_id = z.zid
        try:
            if self._audit_win is not None and self._audit_win.winfo_exists():
                self._audit_win.destroy()
        except tk.TclError:
            pass
        self._audit_win = None
        self.runner = self.runners[z.zid]
        self.quota = self.runner.quota
        self._prefs = load_prefs(z.prefs)
        self.par_var.set(str(self.runner.parallel))
        self._entity_cache = {}
        self._sync_accounts()
        self.refresh()
        self._log("[工作区] 切换到 %s（%s）" % (z.label, z.out))

    def _startup_prompt(self):
        if os.environ.get("KCI_NO_STARTUP_PROMPT") == "1":
            self._continue_all()
            return
        lines = []
        total = 0
        for z in self.zones.values():
            c = self.runners[z.zid].store.counts()
            pending = c.get("queued", 0) + c.get("interrupted", 0)
            total += pending
            if pending or c.get("running"):
                lines.append("· %s：排队 %d，中断 %d，运行 %d" % (
                    z.label, c.get("queued", 0), c.get("interrupted", 0),
                    c.get("running", 0)))
        seen = set()
        for z in self.zones.values():
            key = z.account
            if key in seen:
                continue
            seen.add(key)
            q = self.qbook.account(key).summary()
            zones = self.accounts.zones_of(key)
            lines.append("· Paddle 账号 %s（%s）：已用 %d / %d，剩余 %d" % (
                key, "+".join(zones) or "-", q["used"], q["limit"], q["remaining"]))
        if not total and not any(self.runners[z].running for z in self.runners):
            body = "没有需要恢复的任务。\n\n点击「继续」后解锁批量执行。"
        else:
            body = "检测到上次未完成任务：\n\n%s\n\n点击「继续」恢复；选择「暂不继续」则只浏览，不启动新任务。" % "\n".join(lines)
        if self._ask_continue(body):
            self._continue_all()
        else:
            self._paused = True
            self.btn_resume.configure(text="继续")
            self._sync_buttons()
            self.status_lbl.configure(text="已暂停：任务已持久化，可稍后点「继续」恢复")

    def _ask_continue(self, body):
        """自绘启动闸门：按钮文案必须是「继续 / 暂不继续」，不用系统 OK/取消。"""
        dlg = tk.Toplevel(self)
        dlg.title("继续上次任务")
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()
        ttk.Label(dlg, text=body, justify="left", wraplength=520).pack(
            padx=18, pady=(16, 10), anchor="w")
        bar = ttk.Frame(dlg)
        bar.pack(fill="x", padx=18, pady=(0, 14))
        choice = {"go": False}

        def choose(go):
            choice["go"] = bool(go)
            dlg.destroy()

        ttk.Button(bar, text="暂不继续", command=lambda: choose(False)).pack(side="right")
        ttk.Button(bar, text="继续", command=lambda: choose(True)).pack(
            side="right", padx=(0, 8))
        dlg.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        dlg.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - dlg.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - dlg.winfo_height()) // 2)
        dlg.geometry("+%d+%d" % (x, y))
        dlg.wait_window()
        return choice["go"]

    def _continue_all(self):
        for r in self.runners.values():
            r.resume()
        self._paused = False
        self.btn_resume.configure(text="暂停")
        self.refresh()
        self._log("[继续] 已恢复两区持久任务")

    def _toggle_run(self):
        if any(r.paused for r in self.runners.values()):
            self._continue_all()
        else:
            for r in self.runners.values():
                r.pause()
            self._paused = True
            self.btn_resume.configure(text="继续")
            self._sync_buttons()
            self._log("[暂停] 不再放行新任务；正在跑的子进程会跑完")

    # ---------- 阶段菜单 ----------
    _ARROW_W = 20          # 键右侧箭头热区宽度(px): 落在这一段内=开菜单, 其余=执行

    def _note_click_x(self, ev):
        self._click_x = ev.x

    def _on_rerun_click(self):
        x = getattr(self, "_click_x", None)
        self._click_x = None            # 用完即清, 防键盘触发时读到上次的旧坐标
        if x is not None and x >= self.btn_rerun.winfo_width() - self._ARROW_W:
            self._post_stage_menu()
        else:
            self._run_selected()

    def _post_stage_menu(self):
        """菜单贴在这个键的右端下方(箭头正下方)。"""
        x = self.btn_rerun.winfo_rootx() + self.btn_rerun.winfo_width() - 6
        y = self.btn_rerun.winfo_rooty() + self.btn_rerun.winfo_height()
        try:
            self.stage_menu.tk_popup(x, y)
        finally:
            self.stage_menu.grab_release()

    def _build_stage_menu(self):
        """每次弹出前重建: 依赖状态随当前文档产物变化, 不能只建一次。

        缺依赖的条目置灰并在标签后写明缺什么——置灰只是提示, 真正的闸门在 stages.run()。
        """
        m = self.stage_menu
        m.delete(0, "end")
        docs = self._selected() or ([self.tree.focus()] if self.tree.focus() else [])
        probe = docs[0] if docs else None
        avail = stages.availability(probe, self.zone.out, self.zone.up) if probe else {}

        pre = tk.Menu(m, tearoff=0)
        for name, ids in stages.PRESETS:
            pre.add_command(label=name, command=lambda i=list(ids), n=name: self._run_stages(i, n))
        m.add_cascade(label="预设", menu=pre)
        m.add_separator()

        groups = []
        for sid, group, label, hint, req, npdf in stages.STAGES:
            if group not in groups:
                groups.append(group)
        for g in groups:
            gm = tk.Menu(m, tearoff=0)
            for sid, group, label, hint, req, npdf in stages.STAGES:
                if group != g:
                    continue
                ok, miss, _ = avail.get(sid, (True, [], None))
                text = "%s — %s" % (label, hint)
                if not ok and probe:
                    text += "   (缺 %s)" % "、".join(miss)
                gm.add_checkbutton(label=text, variable=self.stage_vars[sid],
                                   state="normal" if (ok or not probe) else "disabled")
            m.add_cascade(label=g, menu=gm)
        m.add_separator()
        m.add_command(label="执行选中阶段", command=self._run_selected)
        m.add_separator()
        m.add_command(label="全选", command=lambda: self._set_all_stages(True))
        m.add_command(label="全不选", command=lambda: self._set_all_stages(False))
        m.add_command(label="只选后链(元数据+实体)",
                      command=lambda: self._set_stages(list(stages.META_IDS) + ["ner"]))

    def _set_all_stages(self, on):
        for sid in stages.ORDER:
            self.stage_vars[sid].set(bool(on))

    def _set_stages(self, ids):
        ids = set(ids)
        for sid in stages.ORDER:
            self.stage_vars[sid].set(sid in ids)

    def _checked_stages(self):
        return [sid for sid in stages.ORDER if self.stage_vars[sid].get()]

    # ---------- 数据 ----------
    def refresh(self):
        self.docs = scan_docs(self.zone.up, self.zone.out, self.zone.arch)
        self.hist = load_history(self.zone.hist)
        self._webapp_on = webapp_alive()
        sels = [d for d in self._selected() if d in self.docs]   # 多选保留
        self.tree.delete(*self.tree.get_children())
        for doc, d in sorted(self.docs.items()):
            h = self.hist.get(doc, [])
            runs = "%d 次%s" % (len(h), "(末次失败)" if (h and not h[-1]["ok"]) else "")
            # 变量名不用 qc: 会把模块 qc 遮蔽掉, 后面再想调 qc.clear_cache 就炸在这里
            qr = qc_of(doc, out_dir=self.zone.out, ner_root=self.zone.ner) \
                if d["state"] != "未跑" else {"label": "-", "level": "", "issues": []}
            est = wb.entity_summary(doc, self.zone)[0] if d["state"] != "未跑" else "—"
            tags = ("qc_bad",) if qr["level"] == "bad" else ()
            self.tree.insert("", "end", iid=doc, text=doc, tags=tags, values=(
                d["state"],
                qr["label"],
                est,
                "✔" if d["ch"]["mineru"] else "—",
                "✔" if d["ch"]["dots"] else "—",
                "✔" if d["ch"]["paddle"] else "—",
                time.strftime("%m-%d %H:%M", time.localtime(d["done_at"])) if d["done_at"] else "-",
                runs))
        if sels:
            self.tree.selection_set(sels)
        unrun = sum(1 for d in self.docs.values() if d.get("state") == "未跑")
        if unrun and unrun != self._last_unrun:
            self._log("[扫描] 当前区有 %d 篇 PDF 未跑；选中后点「一键重跑」（Ctrl+A 全选）。" % unrun)
        self._last_unrun = unrun
        self._sync_buttons()

    def _selected(self):
        return list(self.tree.selection())

    def _select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        self._sync_buttons()
        return "break"

    def _sync_buttons(self):
        docs = self._selected()
        has = bool(docs)
        runnable = bool(self._paused is False) and any(
            self.docs.get(d, {}).get("pdf") for d in docs)
        retryable = bool(self._paused is False) and any(
            self.docs.get(d, {}).get("pdf") and self.docs[d]["miss"] for d in docs)
        self.btn_rerun.configure(state="normal" if runnable else "disabled")
        self.btn_quick.configure(state="normal" if runnable else "disabled")
        self.btn_gaps.configure(state="normal" if runnable else "disabled")
        self.btn_retry.configure(state="normal" if retryable else "disabled")
        self.btn_view.configure(state="normal" if has else "disabled")
        self.btn_audit.configure(state="normal" if has else "disabled")
        self.btn_index.configure(state="normal" if has else "disabled")
        self.btn_archive.configure(state="normal" if has else "disabled")
        n = len(self._checked_stages()) if hasattr(self, "stage_vars") else 0
        if has:
            self.sel_lbl.configure(text="已选 %d 篇: %s ｜ 菜单勾选 %d 段" % (
                len(docs), ", ".join(docs[:3]) + (" …" if len(docs) > 3 else ""), n))
        else:
            self.sel_lbl.configure(text="未选中")

    # ---------- 动作(对选中集批量) ----------
    def _pages(self, doc):
        if doc not in self._page_cache:
            d = self.docs.get(doc) or {}
            self._page_cache[doc] = wb.page_count(d.get("pdf"))
        return self._page_cache[doc]

    def _reserve_quota(self, docs, ids):
        """按 PDF 页数预留 Paddle 日额度；缺 Paddle 的文档才算。"""
        if "paddle" not in ids:
            return True
        rec = self.accounts.get(self.zone.account) or {}
        if not (rec.get("token") or "").strip():
            messagebox.showwarning(
                "未配置 Paddle token",
                "当前区使用账号 %s，但没有 Paddle token。\n\n"
                "请点「账号与额度…」补齐 token；本次不预留页数、不提交任务。" %
                self.zone.account, parent=self)
            return False
        todo = []
        need = 0
        for doc in docs:
            d = self.docs.get(doc) or {}
            if d.get("ch", {}).get("paddle"):
                continue
            pages = self._pages(doc)
            if not pages:
                messagebox.showwarning(
                    "无法读取页数",
                    "无法读取 %s 的 PDF 页数，不能做 Paddle 页配额预留，已取消本次提交。" % doc,
                    parent=self)
                return False
            todo.append((doc, pages))
            need += pages
        if need > self.quota.remaining():
            messagebox.showwarning(
                "Paddle 配额不足",
                "本次预计需要 Paddle %d 页，账号 %s 今日剩余 %d 页。\n\n"
                "请缩小选中范围，或在「账号与额度…」中调整该账号日额度。" % (
                    need, self.zone.account, self.quota.remaining()), parent=self)
            return False
        for doc, pages in todo:
            key = "%s/%s" % (self.zone.zid, doc)
            if not self.quota.reserve(key, pages):
                messagebox.showwarning("Paddle 配额不足", "预留 %s 的 %d 页失败。" % (doc, pages),
                                       parent=self)
                return False
        return True

    def _run_stages(self, ids, trigger=None):
        """按给定阶段子集批量提交(预设/自定义走同一入口)。"""
        if self._paused:
            messagebox.showinfo("尚未继续", "请先点顶部「继续」解锁执行；当前仅可浏览。", parent=self)
            return
        ids = [i for i in stages.ORDER if i in set(ids)]   # 规范顺序 + 去重
        if not ids:
            self._log("[阶段] 未选择任何阶段")
            return
        docs = [d for d in self._selected() if self.docs.get(d, {}).get("pdf")]
        busy = [d for d in docs if self.runner.store.active_for(d)]
        docs = [d for d in docs if d not in busy]
        if busy:
            self._log("[批量] 跳过 %d 篇(已在队列/运行): %s" % (
                len(busy), ", ".join(busy[:5])))
        if not docs:
            if not busy:
                messagebox.showinfo(
                    "未选择文档",
                    "请先在表格中选中要解析的 PDF（Ctrl+A 全选），再点「一键重跑」。",
                    parent=self)
                self._log("[批量] 未选择文档；未提交任务")
            return
        if not self._reserve_quota(docs, ids):
            return
        n = 0
        for doc in docs:
            pdf = self.docs[doc]["pdf"]
            if self.runner.submit(doc, pdf, ids, trigger or ("执行选中 %d 段" % len(ids))):
                n += 1
        if n:
            self._log("[批量] 已提交 %d 篇 · %d 段: %s" % (
                n, len(ids), "→".join(stages.BY_ID[i][2] for i in ids)))

    def _rerun_gaps(self):
        """只重跑缺渠道 + 实体未查/失败的文档。"""
        if self._paused:
            messagebox.showinfo("尚未继续", "请先点顶部「继续」解锁执行；当前仅可浏览。", parent=self)
            return
        docs = [d for d in self._selected() if self.docs.get(d, {}).get("pdf")]
        if not docs:
            messagebox.showinfo(
                "未选择文档",
                "请先选中要补缺口的 PDF（Ctrl+A 全选），再点「重跑缺口」。",
                parent=self)
            return
        todo = []
        for doc in docs:
            d = self.docs[doc]
            est = wb.entity_statuses(doc, self.zone)
            ent_bad = any(v["status"] in ("not_checked", "extraction_failed")
                          for v in est.values())
            if not d["miss"] and not ent_bad:
                continue
            ids = list(stages.ORDER) if d["miss"] else ["ner"]
            todo.append((doc, ids, tuple(d["miss"])))
        busy = [doc for doc, _, _ in todo if self.runner.store.active_for(doc)]
        if busy:
            todo = [t for t in todo if t[0] not in busy]
            self._log("[缺口] 跳过 %d 篇(已在队列/运行): %s" % (
                len(busy), ", ".join(busy[:5])))
        if not todo:
            messagebox.showinfo("没有缺口", "选中文档的渠道和实体状态都没有需要重跑的缺口。",
                                parent=self)
            return
        pages = sum(self._pages(doc) for doc, ids, _ in todo if "paddle" in ids
                    and not self.docs[doc]["ch"]["paddle"])
        msg = "将重跑 %d 篇：\n\n" % len(todo)
        msg += "· 缺渠道 %d 篇\n· 仅实体缺口 %d 篇\n· 预计 Paddle %d 页（剩余 %d 页）" % (
            sum(1 for _, ids, _ in todo if len(ids) > 1),
            sum(1 for _, ids, _ in todo if len(ids) == 1),
            pages, self.quota.remaining())
        if not messagebox.askokcancel("重跑缺口", msg, parent=self):
            return
        if not self._reserve_quota([doc for doc, ids, _ in todo if "paddle" in ids],
                                   ["paddle"]):
            return
        n = 0
        for doc, ids, clear in todo:
            if self.runner.submit(doc, self.docs[doc]["pdf"], ids,
                                  "重跑缺口:" + ("缺渠道" if clear else "实体"), clear=clear):
                n += 1
        self._log("[缺口] 已提交 %d 篇" % n)

    def _run_selected(self):
        self._run_stages(self._checked_stages())


    def _rerun_fast(self):
        """快速重跑(跳NER): 全链减实体抽取——这个键存在的唯一目的就是不重复烧 LLM。

        不改动菜单里的勾选状态: 菜单勾选是另一条路(自定义子集), 替用户改勾选
        会让他下一次"执行选中阶段"跑出没预期的集合。
        """
        ids = [i for i in stages.ORDER if i != "ner"]
        self._run_stages(ids, "快速重跑(跳NER)")

    def _retry_missing(self):
        if self._paused:
            messagebox.showinfo("尚未继续", "请先点顶部「继续」解锁执行；当前仅可浏览。", parent=self)
            return
        docs = [d for d in self._selected()
                if self.docs.get(d, {}).get("pdf") and self.docs[d]["miss"]]
        busy = [d for d in docs if self.runner.store.active_for(d)]
        docs = [d for d in docs if d not in busy]
        if busy:
            self._log("[重试] 跳过 %d 篇(已在队列/运行): %s" % (
                len(busy), ", ".join(busy[:5])))
        if not docs:
            if not busy:
                messagebox.showinfo(
                    "未选择文档",
                    "请先选中缺少渠道的 PDF（Ctrl+A 全选），再点「重试缺失渠道」。",
                    parent=self)
            return
        if not self._reserve_quota(docs, ["paddle"]):
            return
        n = 0
        for doc in docs:
            d = self.docs[doc]
            # 清掉缺失渠道的 raw/ 缓存后跑全链: 已有渠道走缓存, 只补缺失那路
            if self.runner.submit(doc, d["pdf"], stages.ORDER,
                                  "重试缺失:" + "/".join(d["miss"]), clear=tuple(d["miss"])):
                n += 1
        if n:
            self._log("[批量] 重试缺失渠道已提交 %d 篇" % n)


    def _context_menu(self, ev):
        iid = self.tree.identify_row(ev.y)
        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
        if not iid:
            return
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="字段 / 实体审计…", command=self._open_audit)
        m.add_separator()
        m.add_command(label="打开对照查看器", command=self._open_viewer)
        m.add_command(label="打开结果总览", command=lambda: self._open(os.path.join(self.zone.out, iid, "index.html"))
                      if os.path.exists(os.path.join(self.zone.out, iid, "index.html")) else None)
        m.add_command(label="打开产物目录", command=lambda: self._open(os.path.join(self.zone.out, iid)))
        m.add_command(label="归档选中…", command=self._archive_selected)
        m.add_separator()
        m.add_command(label="复制文档 ID", command=lambda: (self.clipboard_clear(),
                                                            self.clipboard_append(iid),
                                                            self._log("[复制] %s" % iid)))
        m.add_separator()
        sub = tk.Menu(m, tearoff=0)
        for name, ids in stages.PRESETS:
            sub.add_command(label=name, command=lambda i=list(ids), n=name: (
                self.tree.selection_set(iid), self._run_stages(i, n)))
        m.add_cascade(label="按预设重跑", menu=sub)
        try:
            m.tk_popup(ev.x_root, ev.y_root)
        finally:
            m.grab_release()

    def _audit_alive(self):
        try:
            return self._audit_win is not None and self._audit_win.winfo_exists()
        except tk.TclError:
            return False

    def _open_audit(self):
        doc = self.tree.focus() or (self._selected()[0] if self._selected() else None)
        if not doc:
            return
        if self._audit_alive() and self._audit_win.zone is self.zone:
            self._audit_win.set_doc(doc)
            self._audit_win.lift()
            self._audit_win.focus_force()
            return
        self._audit_win = AuditWindow(self, self.zone, doc)

    def _open_viewer(self):
        doc = self.tree.focus() or (self._selected()[0] if self._selected() else None)
        if not doc:
            return
        fp = os.path.join(self.zone.out, doc, "viewer_compare.html")
        if os.path.exists(fp):
            self._open(fp)

    def _open_index(self):
        for doc in self._selected():
            fp = os.path.join(self.zone.out, doc, "index.html")
            if os.path.exists(fp):
                self._open(fp)

    # ---------- 归档 ----------
    def _archive_selected(self):
        """对选中集归档。一次确认, 不逐篇问——但把"含几篇红的"写在确认框里。

        红项必须在确认框里说出来: 归档后文档从工作台消失, 缺项只剩归档清单里那一行,
        将来回看容易误以为都通过了。
        """
        docs = [d for d in self._selected() if d in self.docs]
        if not docs:
            return
        busy = [d for d in docs if d in getattr(self.runner, "queued", set())]
        if busy:
            messagebox.showwarning(
                "正在运行", "以下文档正在运行/排队，先等它跑完再归档：\n\n" +
                "\n".join("· " + d for d in busy[:10]), parent=self)
            return
        rows, bad = [], []
        for d in docs:
            q = qc_of(d, out_dir=self.zone.out, ner_root=self.zone.ner)
            if q["issues"]:
                bad.append(d)
                rows.append("· %s    ✘ 缺 %s" % (d, "/".join(q["issues"])))
            else:
                rows.append("· %s    ✔ 质检通过" % d)
        msg = "归档 %d 篇：\n\n%s" % (len(docs), "\n".join(rows[:12]))
        if len(rows) > 12:
            msg += "\n… 其余 %d 篇" % (len(rows) - 12)
        if bad:
            msg += ("\n\n⚠ 其中 %d 篇质检未通过。归档后它们不再出现在工作台，"
                    "缺项只会留在归档清单里。" % len(bad))
        msg += "\n\nPDF 与 out/ 产物会移到 archive/，之后可在「已归档…」里恢复。"
        if not messagebox.askokcancel("确认归档", msg, parent=self):
            return
        try:
            r = archive.archive_docs(docs, out_root=self.zone.out,
                                     up_root=self.zone.up, arch_root=self.zone.arch)
        except Exception as e:
            messagebox.showerror("归档失败", str(e), parent=self)
            return
        for d in r["ok"]:
            self._log("[归档] %s" % d)
            qc.clear_cache(d)      # 产物已搬走, 正文判定的缓存留着会误用
        for d, why in r["skipped"]:
            self._log("[归档·跳过] %s: %s" % (d, why))
        for d, why in r["warnings"]:
            self._log("[归档·提示] %s: %s" % (d, why))
        self._log("[归档] 完成 %d 篇 · 跳过 %d 篇" % (len(r["ok"]), len(r["skipped"])))
        if r["warnings"]:
            messagebox.showinfo("归档完成，但有提示",
                                "已归档 %d 篇。\n\n" % len(r["ok"]) +
                                "\n".join("%s: %s" % (d, w) for d, w in r["warnings"]),
                                parent=self)
        self.refresh()

    def _open_archive_list(self):
        ArchiveWindow(self, self.zone)

    def _open_webapp(self):
        """浏览器工作台的唯一入口。已在跑就开浏览器; 没跑就起一个(新控制台窗口)。

        两者都会监视 uploads, 同时解析同一篇会写坏产物(13563526 实证), 所以 GUI 有任务在跑时
        先问一句——不是怕它崩, 是怕两份进程交替写同一批文件。
        """
        import subprocess
        import sys
        if webapp_alive():
            messagebox.showwarning(
                "旧浏览器工作台正在运行",
                "检测到 8765 端口的旧浏览器工作台。\n"
                "它会和 GUI 同时监视 uploads，并可能自动补跑循环。\n"
                "请先在任务管理器结束 webapp.py，再使用 GUI 的“对照查看器/结果总览”。",
                parent=self)
            self._log("[web] 检测到旧 webapp 在运行，已拒绝并行打开；请先结束 webapp.py")
            return
        if not messagebox.askyesno(
                "浏览器工作台（旧入口）",
                "浏览器工作台是旧入口，会自动监视 uploads 并补跑缺失渠道；\n"
                "与 GUI 同时运行会争抢同一篇文档，历史上已出现补跑死循环。\n\n"
                "建议只用桌面版。仍要单独启动旧浏览器工作台吗？",
                icon="warning", default=messagebox.NO, parent=self):
            return
        subprocess.Popen([sys.executable, os.path.join(ROOT, "webapp.py")],
                         creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        self._log("[web] 已启动旧浏览器工作台(新窗口)，稍候打开 http://127.0.0.1:8765")

    def _restart(self):
        """一键重启: 拉新进程替自己, 以加载 gui.py 等外壳改动(热更新只覆盖流水线模块)。
        新老进程交接端口互斥有空窗——新进程 bind 自带重试(_acquire_instance_sock)。"""
        if any(r.is_busy() for r in self.runners.values()):
            if not messagebox.askyesno("重启", "有任务正在运行/排队。\n"
                                                "正在跑的会在后台跑完(子进程独立)，排队任务已持久化，重启后可继续。\n确定要重启吗?"):
                return
        import subprocess, sys
        env = os.environ.copy()
        env["KCI_ACTIVE_ZONE"] = self.zone_id
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)],
                             close_fds=True, env=env,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        except Exception as e:
            messagebox.showerror("重启失败", str(e))
            return
        self._log("[重启] 新进程已拉起, 本进程退出(端口随退出释放, 新进程重试接管)")
        self.after(300, self.destroy)   # 让日志先刷出去再退

    def _on_close(self):
        busy = [r for r in self.runners.values() if r.is_busy()]
        if busy:
            n = sum(r._active_count() for r in busy)
            if not messagebox.askyesno("任务仍在运行",
                                       "两区共有 %d 篇正在跑，会在后台继续完成（子进程独立）。\n"
                                       "排队任务已写入持久账本，重新打开后可点「继续」恢复。\n\n"
                                       "确定要关闭吗?" % n):
                return
        self.destroy()

    @staticmethod
    def _open(path):
        if os.name == "nt":
            os.startfile(path)  # noqa: S606 - 本地工作台双击等价物
        else:
            import webbrowser
            webbrowser.open("file://" + path)

    # ---------- 日志/状态 ----------
    def _log(self, s):
        self.q.put(s)

    def _drain(self):
        try:
            n = 0
            while n < 300:   # 单次回调限量: 日志洪峰不许把 UI 线程钉死
                s = self.q.get_nowait()
                n += 1
                self.logtxt.configure(state="normal")
                self.logtxt.insert("end", time.strftime("%H:%M:%S ") + s + "\n")
                # 日志上限: 只保留最后 ~3000 行, 防长会话内存膨胀
                tail = self.logtxt.index("end-1c")
                if tail and int(tail.split(".")[0]) > 3000:
                    self.logtxt.delete("1.0", "2000.0")
                self.logtxt.see("end")
                self.logtxt.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain)

    def _tick_status(self):
        q = self.quota.summary()
        txt = "%s · 账号 %s · Paddle %d/%d 页（余 %d）" % (
            self.runner.status(), self.zone.account, q["used"], q["limit"], q["remaining"])
        self._refresh_account_hint()
        other = [r for zid, r in self.runners.items() if zid != self.zone_id and r.is_busy()]
        if other:
            txt += " · 另一区运行中 %d 篇" % sum(r._active_count() for r in other)
        if self._webapp_on:
            txt = "⚠ 检测到 web 服务(8765)也在运行, 勿与 GUI 同时解析同一篇 · " + txt
        self.status_lbl.configure(text=txt)
        busy = self.runner.is_busy()
        if busy:
            el = self.runner.elapsed()
            # 任务心跳: 长跑阶段(OCR/LLM 网络等待)日志静默, 每 15s 报一次"还在跑", 防误判卡死
            if el // 15 != getattr(self, "_last_beat", -1):
                self._last_beat = el // 15
                self._log("[心跳] 正在跑 %s, 已 %ds" % (self.runner.cur_doc(), el))
        if self._was_busy and not busy:
            self._was_busy = busy   # 先翻转再刷新: 杜绝 refresh↔_tick_status 互相递归
            self.refresh()
        else:
            self._was_busy = busy
        self.after(1000, self._tick_status)


class AccountsWindow(tk.Toplevel):
    """Paddle 账号库: token 只显示掩码，日额度按账号分别记账。"""

    COLS = (("key", 92, "账号"), ("label", 120, "名称"), ("mask", 130, "Token"),
            ("limit", 82, "日额度"), ("used", 72, "今日已用"),
            ("remain", 72, "剩余"), ("zones", 80, "使用区"))

    def __init__(self, app):
        tk.Toplevel.__init__(self, app)
        self.app = app
        self.store = app.accounts
        self.book = app.qbook
        self.items = []
        self.editing = None
        self.title("Paddle 账号与日额度")
        self.geometry("820x520")
        self.minsize(760, 480)
        self.transient(app)
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(top, text="账号库", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        ttk.Label(top, text="Token 存于 .workbench/accounts.json（不入库），界面只显示首尾。",
                  foreground="#666").pack(side="left", padx=10)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS],
                                 show="headings", height=9, selectmode="browse")
        for c, w, t in self.COLS:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c not in ("label", "mask") else "w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        form = ttk.LabelFrame(self, text="编辑 / 新增")
        form.pack(fill="x", padx=12, pady=8)
        r1 = ttk.Frame(form)
        r1.pack(fill="x", padx=8, pady=(6, 3))
        ttk.Label(r1, text="账号 key").pack(side="left")
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(r1, textvariable=self.key_var, width=13)
        self.key_entry.pack(side="left", padx=(4, 10))
        ttk.Label(r1, text="名称").pack(side="left")
        self.label_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.label_var, width=16).pack(side="left", padx=(4, 10))
        ttk.Label(r1, text="日额度").pack(side="left", padx=(4, 0))
        self.daily_var = tk.StringVar(value=str(DEFAULT_DAILY_PAGES))
        ttk.Entry(r1, textvariable=self.daily_var, width=10).pack(side="left", padx=4)

        r2 = ttk.Frame(form)
        r2.pack(fill="x", padx=8, pady=3)
        ttk.Label(r2, text="Paddle token").pack(side="left")
        self.token_var = tk.StringVar()
        self.token_entry = ttk.Entry(r2, textvariable=self.token_var, width=46, show="*")
        self.token_entry.pack(side="left", padx=(4, 6))
        ttk.Button(r2, text="读取本机配置", command=self._read_local).pack(side="left")
        ttk.Label(r2, text="编辑时留空 = 保留原 token", foreground="#666").pack(side="left", padx=8)

        bar = ttk.Frame(form)
        bar.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(bar, text="新增", command=self._new).pack(side="left")
        ttk.Button(bar, text="保存", command=self._save).pack(side="left", padx=6)
        ttk.Button(bar, text="删除", command=self._delete).pack(side="left")
        ttk.Button(bar, text="刷新", command=self.refresh).pack(side="left", padx=(18, 0))
        ttk.Button(bar, text="关闭", command=self.destroy).pack(side="right")
        self.note = ttk.Label(self, text="日额度单位为 PDF 页。一个账号可同时分配给 A/B 两区；共用时日额度也共用。",
                              foreground="#555")
        self.note.pack(fill="x", padx=14, pady=(0, 8))

    def refresh(self):
        self.items = self.store.list_accounts()
        self.tree.delete(*self.tree.get_children())
        for a in self.items:
            q = self.book.account(a["key"], a["daily_pages"]).summary()
            self.tree.insert("", "end", iid=a["key"], values=(
                a["key"], a["label"], a["token_mask"], q["limit"],
                q["used"], q["remaining"], ",".join(self.store.zones_of(a["key"])) or "-"))
        if self.editing and self.editing in self.tree.get_children():
            self.tree.selection_set(self.editing)

    def _on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        a = self.store.get(key) or {}
        self.editing = key
        self.key_var.set(key)
        self.key_entry.configure(state="disabled")
        self.label_var.set(a.get("label") or key)
        self.daily_var.set(str(a.get("daily_pages") or DEFAULT_DAILY_PAGES))
        self.token_var.set("")

    def _new(self):
        self.editing = None
        self.key_entry.configure(state="normal")
        self.key_var.set("")
        self.label_var.set("")
        self.daily_var.set(str(DEFAULT_DAILY_PAGES))
        self.token_var.set("")
        self.key_entry.focus_set()

    def _read_local(self):
        tok = _local_paddle_token()
        if tok:
            self.token_var.set(tok)
        else:
            messagebox.showinfo("本机配置", "没有找到 Paddle token。", parent=self)

    def _save(self):
        key = (self.key_var.get() or "").strip()
        label = (self.label_var.get() or "").strip() or key
        tok = (self.token_var.get() or "").strip()
        try:
            daily = int(self.daily_var.get())
        except ValueError:
            messagebox.showwarning("参数错误", "日额度必须是整数页数。", parent=self)
            return
        if daily < 1 or daily > 200000:
            messagebox.showwarning("参数错误", "日额度应在 1–200000 页之间。", parent=self)
            return
        if not re.match(r"^[A-Za-z0-9_-]{1,32}$", key):
            messagebox.showwarning("参数错误", "账号 key 只能用字母/数字/下划线/短横线。",
                                   parent=self)
            return
        if self.editing is None:
            if not tok:
                messagebox.showwarning("缺少 token", "新账号必须填写 Paddle token。", parent=self)
                return
            self.store.upsert(key, label, tok, daily)
            self.book.account(key, daily).set_limit(daily)
            self.app._log("[账号] 新增 %s（日额度 %d 页）" % (key, daily))
        else:
            if key != self.editing:
                messagebox.showwarning("不可改 key", "账号 key 建好后不可改；请新增账号。",
                                       parent=self)
                return
            self.store.upsert(key, label, tok or None, daily)
            self.book.set_limit(key, daily)
            self.app._log("[账号] 更新 %s（日额度 %d 页%s）" %
                          (key, daily, "，token 已更新" if tok else ""))
        self.editing = key
        self.key_entry.configure(state="disabled")
        self.token_var.set("")
        self.refresh()
        self.app._sync_accounts()

    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("删除账号", "先选中一个账号。", parent=self)
            return
        key = sel[0]
        busy = []
        for zid, runner in self.app.runners.items():
            if key in runner.store.accounts_in_use():
                busy.append(zid)
        if busy:
            messagebox.showwarning(
                "不能删除", "账号 %s 仍有排队/运行任务（工作区 %s）；先处理这些任务。" %
                (key, "/".join(sorted(busy))), parent=self)
            return
        if not messagebox.askyesno("删除账号", "删除账号 %s？" % key, parent=self):
            return
        ok, msg = self.store.remove(key)
        if not ok:
            messagebox.showwarning("不能删除", msg, parent=self)
            return
        self.app._log("[账号] 删除 %s" % key)
        self.editing = None
        self._new()
        self.refresh()
        self.app._sync_accounts()


class AuditWindow(tk.Toplevel):
    """字段 / 实体审计: 16 个字段的状态、值与证据。

    这里刻意不做“自动补全”或“猜一个值”：空值只写「未查」，除非有审计证据。
    这样用户看到的红/黄/绿与最终能否交付是同一套口径。
    """

    FCOLS = (("field", 130, "字段"), ("status", 82, "状态"),
             ("group", 62, "组"), ("value", 520, "值 / 摘要"))
    ECOLS = (("kind", 100, "实体"), ("status", 82, "状态"),
             ("count", 58, "数量"), ("reason", 560, "依据"))

    COLORS = {
        "present": "#1a7f37",
        "absent_confirmed": "#1a7f37",
        "not_checked": "#b26a00",
        "uncertain": "#7a4fb0",
        "extraction_failed": "#b03030",
        "not_applicable": "#666666",
    }

    def __init__(self, app, zone, doc):
        tk.Toplevel.__init__(self, app)
        self.app = app
        self.zone = zone
        self.doc = doc
        self.rows = []
        self.title("字段 / 实体审计 · %s" % doc)
        self.geometry("1080x650")
        self.minsize(880, 520)
        self.transient(app)
        self._build()
        self.set_doc(doc)

    def _build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", padx=12, pady=(10, 4))
        self.head = ttk.Label(head, text="", font=("Microsoft YaHei UI", 11, "bold"))
        self.head.pack(side="left")
        self.counts = ttk.Label(head, text="")
        self.counts.pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=4)

        # 字段页
        ftab = ttk.Frame(nb)
        nb.add(ftab, text="字段（13）")
        fp = ttk.Panedwindow(ftab, orient="horizontal")
        fp.pack(fill="both", expand=True)
        fl = ttk.Frame(fp)
        self.ftree = ttk.Treeview(fl, columns=tuple(c[0] for c in self.FCOLS),
                                  show="headings", selectmode="browse", height=15)
        for cid, w, txt in self.FCOLS:
            self.ftree.heading(cid, text=txt)
            self.ftree.column(cid, width=w, anchor="w" if cid in ("field", "value") else "center")
        for st, color in self.COLORS.items():
            self.ftree.tag_configure(st, foreground=color)
        self.ftree.pack(side="left", fill="both", expand=True)
        fsb = ttk.Scrollbar(fl, orient="vertical", command=self.ftree.yview)
        self.ftree.configure(yscrollcommand=fsb.set)
        fsb.pack(side="right", fill="y")
        self.ftree.bind("<<TreeviewSelect>>", lambda e: self._show_field())
        fp.add(fl, weight=3)
        self.fdetail = scrolledtext.ScrolledText(fp, width=46, height=15, wrap="word",
                                                 font=("Microsoft YaHei UI", 9),
                                                 state="disabled")
        fp.add(self.fdetail, weight=2)

        # 实体页
        etab = ttk.Frame(nb)
        nb.add(etab, text="实体（3 类）")
        ep = ttk.Panedwindow(etab, orient="horizontal")
        ep.pack(fill="both", expand=True)
        el = ttk.Frame(ep)
        self.etree = ttk.Treeview(el, columns=tuple(c[0] for c in self.ECOLS),
                                  show="headings", selectmode="browse", height=8)
        for cid, w, txt in self.ECOLS:
            self.etree.heading(cid, text=txt)
            self.etree.column(cid, width=w, anchor="w" if cid in ("kind", "reason") else "center")
        for st, color in self.COLORS.items():
            self.etree.tag_configure(st, foreground=color)
        self.etree.pack(side="left", fill="both", expand=True)
        esb = ttk.Scrollbar(el, orient="vertical", command=self.etree.yview)
        self.etree.configure(yscrollcommand=esb.set)
        esb.pack(side="right", fill="y")
        self.etree.bind("<<TreeviewSelect>>", lambda e: self._show_entity())
        ep.add(el, weight=3)
        self.edetail = scrolledtext.ScrolledText(ep, width=46, height=8, wrap="word",
                                                 font=("Microsoft YaHei UI", 9),
                                                 state="disabled")
        ep.add(self.edetail, weight=2)

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(2, 4))
        ttk.Button(bar, text="打开 metadata.json", command=lambda: self._open(
            fa.metadata_path(self.doc, self.zone))).pack(side="left")
        ttk.Button(bar, text="打开 metadata_audit", command=lambda: self._open(
            fa.audit_path(self.doc, self.zone))).pack(side="left", padx=6)
        ttk.Button(bar, text="打开 NER 目录", command=lambda: self._open(
            os.path.dirname(wb.entity_paths(self.doc, self.zone)[0]))).pack(side="left")
        ttk.Button(bar, text="刷新", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="关闭", command=self.destroy).pack(side="right")
        ttk.Label(self, text="空值 ≠ 缺失；「确认无」必须有逐页/审计证据。缺值默认「未查」，"
                             "不会自动当作不存在。",
                  foreground="#666").pack(fill="x", padx=12, pady=(0, 8))

    def set_doc(self, doc):
        self.doc = doc
        self.title("字段 / 实体审计 · %s · %s" % (doc, self.zone.label))
        self.head.configure(text=doc)
        self.refresh()

    def refresh(self):
        try:
            self.rows = fa.field_statuses(self.doc, self.zone)
            s = fa.summary(self.doc, self.zone)
        except Exception as e:
            messagebox.showerror("审计失败", str(e), parent=self)
            return
        self.counts.configure(
            text="核心 %d/%d 齐 · 待核 %d · 实体 %s" % (
                s["core_present"], s["core_total"], s["needs_audit"],
                "/".join(fa.STATUS_LABEL.get(s["entities"].get(k), "?")
                         for k in wb.ENTITY_KINDS)))
        fsel = self.ftree.selection()
        esel = self.etree.selection()
        self.ftree.delete(*self.ftree.get_children())
        self.etree.delete(*self.etree.get_children())
        for r in self.rows:
            if r["group"] == "entity":
                self.etree.insert("", "end", iid=r["id"], tags=(r["status"],),
                                  values=("%s（%s）" % (r["label"], r["id"]),
                                          r["status_label"],
                                          r["value"].count("；") + 1 if r["value"] else 0,
                                          r["reason"]))
            else:
                self.ftree.insert("", "end", iid=r["id"], tags=(r["status"],),
                                  values=(r["label"], r["status_label"], r["group_label"],
                                          r["value"] or "—"))
        if fsel and self.ftree.exists(fsel[0]):
            self.ftree.selection_set(fsel[0])
        elif self.ftree.get_children():
            self.ftree.selection_set(self.ftree.get_children()[0])
        if esel and self.etree.exists(esel[0]):
            self.etree.selection_set(esel[0])
        elif self.etree.get_children():
            self.etree.selection_set(self.etree.get_children()[0])
        self._show_field()
        self._show_entity()

    def _row(self, iid):
        return next((r for r in self.rows if r["id"] == iid), None)

    @staticmethod
    def _put(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _show_field(self):
        sel = self.ftree.selection()
        r = self._row(sel[0]) if sel else None
        if not r:
            self._put(self.fdetail, "")
            return
        lines = ["状态: %s (%s)" % (r["status_label"], r["status"]),
                 "组: %s" % r["group_label"],
                 "值: %s" % (r["value"] or "（空）"),
                 "依据: %s" % (r["reason"] or "—"),
                 "置信度: %s / %s" % (r["confidence"].get("level") or "—",
                                      r["confidence"].get("source") or "—")]
        if r["basis"]:
            lines.append("抽取依据: %s" % r["basis"])
        if r["flag"]:
            lines.append("标记: %s" % r["flag"])
        neg = r.get("negative") or {}
        if neg:
            lines += ["", "负证据:", "  检查页: %s" % neg.get("pages_checked", ""),
                      "  查询: %s" % neg.get("queries", ""),
                      "  方法: %s" % neg.get("method", ""),
                      "  结果: %s" % neg.get("result", ""),
                      "  置信: %s" % neg.get("confidence", "")]
        lines += ["", "证据文件:", r["evidence"] or "—"]
        self._put(self.fdetail, "\n".join(lines))

    def _show_entity(self):
        sel = self.etree.selection()
        r = self._row(sel[0]) if sel else None
        if not r:
            self._put(self.edetail, "")
            return
        lines = ["状态: %s (%s)" % (r["status_label"], r["status"]),
                 "数量: %d" % (r["value"].count("；") + 1 if r["value"] else 0),
                 "记录: %s" % (r["value"] or "—"),
                 "依据: %s" % (r["reason"] or "—")]
        neg = r.get("negative") or {}
        if neg:
            lines += ["", "负证据:", "  检查页: %s" % neg.get("pages_checked", ""),
                      "  查询: %s" % neg.get("queries", ""),
                      "  方法: %s" % neg.get("method", ""),
                      "  结果: %s" % neg.get("result", ""),
                      "  置信: %s" % neg.get("confidence", "")]
        lines += ["", "证据文件:", r["evidence"] or "—"]
        self._put(self.edetail, "\n".join(lines))

    def _open(self, fp):
        if os.path.exists(fp):
            app_open(fp)
        else:
            messagebox.showinfo("文件不存在", fp, parent=self)


class ArchiveWindow(tk.Toplevel):
    """已归档文献清单: 查、打开产物、恢复、导出。

    独立窗口而非表格的一个筛选档位: 归档后产物不在 out/, 打开路径、恢复动作、导出口径
    都与工作台不同, 混在同一张表里会让"归档"看起来只是打了个标(用户 2026-11-13 要求能查看)。
    """

    COLS = (("title", 380, "标题"), ("journal", 150, "刊名"), ("year", 56, "年"),
            ("qc", 130, "质检"), ("when", 130, "归档时间"))

    def __init__(self, app, zone):
        tk.Toplevel.__init__(self, app)
        self.app = app
        self.zone = zone
        self.title("已归档文献 · %s" % zone.label)
        self.geometry("1020x540")
        self.transient(app)
        self.items = []
        self._build()
        self.refresh()

    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="搜索").pack(side="left")
        self.qvar = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.qvar, width=34)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda ev: self.refresh())
        ttk.Button(bar, text="清空", command=lambda: (self.qvar.set(""), self.refresh())).pack(side="left")
        self.cnt = ttk.Label(bar, text="")
        self.cnt.pack(side="left", padx=12)
        ttk.Button(bar, text="打开归档目录",
                   command=lambda: app_open(self.zone.arch)).pack(side="right")

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=10)
        cols = tuple(c[0] for c in self.COLS)
        self.tree = ttk.Treeview(wrap, columns=("doc",) + cols, show="headings", height=14,
                                 selectmode="extended")
        for cid, w, txt in (("doc", 210, "文档"),) + self.COLS:
            self.tree.heading(cid, text=txt)
            anchor = "w" if cid in ("doc", "title", "journal", "qc") else "center"
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.tag_configure("qc_bad", foreground="#b03030")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda ev: self._open_item())

        act = ttk.Frame(self)
        act.pack(fill="x", padx=10, pady=8)
        ttk.Button(act, text="打开产物", command=self._open_item).pack(side="left")
        ttk.Button(act, text="恢复选中", command=self._restore).pack(side="left", padx=6)
        ttk.Button(act, text="导出清单", command=self._export).pack(side="left")
        ttk.Button(act, text="刷新", command=self.refresh).pack(side="left", padx=6)
        self.hint = ttk.Label(act, text="双击一行 = 打开产物")
        self.hint.pack(side="left", padx=12)

    def refresh(self):
        try:
            self.items = archive.list_items(arch_root=self.zone.arch,
                                            q=self.qvar.get().strip())
        except ValueError as e:
            messagebox.showerror("归档索引损坏", str(e), parent=self)
            self.items = []
        self.tree.delete(*self.tree.get_children())
        for it in self.items:
            miss = it.get("qc_issues") or []
            qtxt = "✔ 通过" if not miss else "✘ 缺 " + "/".join(miss)
            self.tree.insert("", "end", iid=it["doc"], tags=("qc_bad",) if miss else (),
                             values=(it.get("doc"), it.get("title") or "",
                                     it.get("journal") or "", it.get("year") or "",
                                     qtxt, (it.get("archived_at") or "").replace("T", " ")[:16]))
        n_bad = sum(1 for it in self.items if it.get("qc_issues"))
        self.cnt.configure(text="共 %d 篇%s" % (
            len(self.items), "，其中 %d 篇有缺项" % n_bad if n_bad else ""))

    def _sel(self):
        return list(self.tree.selection())

    def _open_item(self):
        docs = self._sel()
        if not docs:
            return
        for doc in docs:
            it = archive.item_of(doc, arch_root=self.zone.arch) or {}
            base = os.path.join(self.zone.arch, doc, "out")
            for name in ("index.html", "viewer_compare.html"):
                fp = os.path.join(base, name)
                if os.path.isfile(fp):
                    app_open(fp)
                    break
            else:
                self.hint.configure(text="%s 只有 PDF，没有产物（归档时 out/ 已不存在）" % doc)

    def _restore(self):
        docs = self._sel()
        if not docs:
            return
        if not messagebox.askokcancel("恢复归档",
                                      "把 %d 篇搬回工作区？\n\n%s" % (
                                          len(docs), "\n".join("· " + d for d in docs[:10])),
                                      parent=self):
            return
        msgs = []
        for doc in docs:
            ok, msg = archive.restore_doc(doc, out_root=self.zone.out,
                                          up_root=self.zone.up, arch_root=self.zone.arch)
            msgs.append(("✔ " if ok else "✘ ") + doc + ": " + msg)
            if ok:
                qc.clear_cache(doc)
        messagebox.showinfo("恢复结果", "\n".join(msgs), parent=self)
        self.refresh()
        self.app.refresh()

    def _export(self):
        if not self.items:
            messagebox.showinfo("没有可导出的内容", "归档为空。", parent=self)
            return
        name = "已归档文献_%s.md" % time.strftime("%Y%m%d")
        fp = filedialog.asksaveasfilename(
            parent=self, title="导出已归档文献清单", initialfile=name,
            defaultextension=".md",
            filetypes=[("Markdown 表格", "*.md"), ("CSV（Excel 可开）", "*.csv")])
        if not fp:
            return
        try:
            body = (archive.export_csv(self.items) if fp.lower().endswith(".csv")
                    else archive.export_markdown(self.items))
            enc = "utf-8-sig" if fp.lower().endswith(".csv") else "utf-8"
            with io.open(fp, "w", encoding=enc) as fh:
                fh.write(body)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)
            return
        self.hint.configure(text="已导出 %d 篇 -> %s" % (len(self.items), fp))


def app_open(path):
    """双击等价物: Windows 用关联程序, 其他平台交给浏览器。"""
    if os.name == "nt":
        os.startfile(path)  # noqa: S606
    else:
        import webbrowser
        webbrowser.open("file://" + path)


def main():
    wb.make_zones(ROOT)      # A 保留旧目录; B 自动建 zones/zone_b
    sock = _acquire_instance_sock()
    if sock is None:
        print("GUI 已在运行(见任务栏另一个窗口), 请勿重复启动。")
        return
    app = App()
    app.mainloop()   # sock 随进程存活, 退出即释放端口


if __name__ == "__main__":
    main()
