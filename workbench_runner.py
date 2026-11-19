# -*- coding: utf-8 -*-
"""Non-Tk local A/B task runner used by the upstream GUI sidecar.

This module deliberately contains no tkinter code: the merged upstream GUI owns
the document table, QC, notes and entity views; this runner owns only the local
durable queue, A/B paths, Paddle account/page-ledger and one-page-child calls.
"""
import io
import json
import os
import queue
import shutil
import threading
import time

import archive
import stages
import workbench_state as wb
from docid import doc_of

ROOT = os.path.dirname(os.path.abspath(__file__))
CH = ("mineru", "dots", "paddle")
CH_ZH = {"mineru": "MinerU", "dots": "dots.ocr", "paddle": "PaddleOCR"}
DEFAULT_PARALLEL = 5
MAX_PARALLEL = 8


def _local_paddle_token():
    tok = (os.environ.get("PADDLE_API_TOKEN") or "").strip()
    if tok:
        return tok
    for name in ("channels.local.json", "channels.json"):
        try:
            with io.open(os.path.join(ROOT, name), encoding="utf-8-sig") as fh:
                cfg = json.load(fh)
            tok = str((cfg.get("paddle_api") or {}).get("token") or "").strip()
            if tok:
                return tok
        except Exception:
            continue
    return ""


def _dir_has_files(path):
    if not os.path.isdir(path):
        return False
    with os.scandir(path) as it:
        return any(True for _ in it)


def _ch_done(doc, ch, out_root=None):
    root = out_root or os.path.join(ROOT, "out")
    return (_dir_has_files(os.path.join(root, doc, "raw", ch))
            or _dir_has_files(os.path.join(root, doc, "raw", ch + "_api")))


def load_history(fp):
    hist = {}
    if not os.path.exists(fp):
        return hist
    try:
        with io.open(fp, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                hist.setdefault(rec.get("doc") or "", []).append(rec)
    except OSError:
        pass
    return hist


def append_history(rec, fp):
    with io.open(fp, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def scan_docs(zone):
    """File-system truth for one zone (same semantics as the pre-merge GUI)."""
    try:
        archived = archive.archived_set(zone.arch)
    except ValueError:
        archived = set()
    docs = {}
    for name in sorted(os.listdir(zone.up)) if os.path.isdir(zone.up) else []:
        if not name.lower().endswith(".pdf"):
            continue
        doc = doc_of(name)
        if doc in archived:
            continue
        dd = os.path.join(zone.out, doc)
        idx = os.path.join(dd, "index.html")
        ch = {c: _ch_done(doc, c, zone.out) for c in CH}
        miss = [c for c in CH if not ch[c]]
        if not os.path.exists(idx):
            state = "未完成" if _dir_has_files(dd) else "未跑"
        elif miss:
            state = "部分异常"
        elif not os.path.isfile(os.path.join(dd, "metadata.json")):
            state = "未完成"
        else:
            state = "已完成"
        docs[doc] = {"doc": doc, "pdf": os.path.join(zone.up, name), "state": state,
                     "ch": ch, "miss": miss,
                     "done_at": os.path.getmtime(idx) if os.path.exists(idx) else None}
    return docs


class Runner(object):
    """One serial scheduler per zone; tasks run in child processes."""

    def __init__(self, zone, quota, log, parallel=None, paused=True, accounts=None):
        self.zone = zone
        self.quota = quota
        self.accounts = accounts
        self.log = log
        self.q = queue.Queue()
        self.running = {}
        self.queued = set()
        self.parallel = max(1, min(int(parallel or DEFAULT_PARALLEL), MAX_PARALLEL))
        self.lock = threading.Lock()
        self._hist_lock = threading.Lock()
        self.store = wb.TaskStore(zone.db)
        self.store.mark_interrupted_running()
        self.paused = bool(paused)
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(self, doc, pdf, ids, trigger="本地任务", clear=(), account=None):
        acct = account or self.zone.account
        pid = wb.running_pid(doc, self.zone.out)
        if pid and wb.pid_alive(pid):
            self.log("[队列] %s 已有子进程 pid=%s，跳过重复提交" % (doc, pid))
            return False
        row, _dup = self.store.enqueue(doc, pdf, ids, clear, trigger, account=acct)
        if row is None:
            self.log("[队列] %s 已在排队/运行，跳过重复提交" % doc)
            return False
        with self.lock:
            self.queued.add(doc)
        self.q.put((row["id"], doc, pdf, tuple(ids), tuple(clear), trigger, acct))
        self.log("[队列] %s 已加入 (%s · %d 段 · 账号 %s)" % (doc, trigger, len(ids), acct))
        return True

    def _completed_since(self, row):
        try:
            started = time.mktime(time.strptime(row.get("started") or "", "%Y-%m-%d %H:%M:%S"))
            idx = os.path.join(self.zone.out, row["doc"], "index.html")
            return os.path.isfile(idx) and os.path.getmtime(idx) >= started
        except Exception:
            return False

    def resume(self):
        rows = self.store.pending()
        n = 0
        for r in rows:
            pid = wb.running_pid(r["doc"], self.zone.out)
            if pid and wb.pid_alive(pid):
                self.log("[继续] %s 仍有子进程 pid=%s，暂不重复提交" % (r["doc"], pid))
                continue
            if r["status"] == "interrupted" and self._completed_since(r):
                self.store.finish(r["id"], True, "旧子进程已完成")
                continue
            if r["status"] == "interrupted":
                self.store.requeue(r["id"])
            with self.lock:
                if r["doc"] in self.queued:
                    continue
                self.queued.add(r["doc"])
            self.q.put((r["id"], r["doc"], r.get("pdf"),
                        tuple(r.get("ids") or []), tuple(r.get("clear") or []),
                        r.get("trigger") or "断点续跑",
                        r.get("account") or self.zone.account))
            n += 1
        self.paused = False
        if n:
            self.log("[继续] %s 恢复 %d 个任务" % (self.zone.label, n))
        return n

    def pause(self):
        self.paused = True

    def set_parallel(self, n):
        self.parallel = max(1, min(int(n), MAX_PARALLEL))
        return self.parallel

    def _loop(self):
        while True:
            while self.paused:
                time.sleep(0.2)
            while self._active_count() >= self.parallel:
                time.sleep(0.15)
            task_id, doc, pdf, ids, clear, trigger, account = self.q.get()
            self.store.mark_running(task_id)
            threading.Thread(target=self._task,
                             args=(task_id, doc, pdf, ids, clear, trigger, account),
                             daemon=True).start()

    def _active_count(self):
        with self.lock:
            return len(self.running)

    def _task(self, task_id, doc, pdf, ids, clear, trigger, account=""):
        ok, err = False, ""
        try:
            ok, err = self._run_one(doc, pdf, ids, clear, trigger, account)
        except BaseException as exc:
            err = str(exc)[:200]
            self.log("[异常] %s: %s" % (doc, exc))
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
            rec = self.accounts.get(account) or {}
            token = rec.get("token") or ""
            if "paddle" in ids and not token:
                self.log("[账号] %s 缺少 Paddle token，拒绝提交 (账号 %s)" % (doc, account))
                return False, "账号 %s 缺少 Paddle token" % account
        try:
            snap = wb.snapshot_doc(self.zone, doc, "%s · %s" % (trigger, ",".join(ids)))
        except Exception as exc:
            self.log("[快照] %s 失败，拒绝覆盖: %s" % (doc, exc))
            return False, "版本快照失败: %s" % str(exc)[:160]
        if snap:
            self.log("[快照] %s -> %s" % (doc, snap))
        for ch in clear:
            for sub in (ch, ch + "_api"):
                d = os.path.join(self.zone.out, doc, "raw", sub)
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            self.log("[重取] %s 渠道 %s 缓存已清" % (doc, ch))
        with self.lock:
            self.running[doc] = (trigger, time.time())
        t0 = time.time()

        def hook(msg):
            self.log("[%s] %s" % (doc, msg))

        job = {"doc": doc, "ids": list(ids), "pdf": pdf}
        if token:
            job["paddle_token"] = token
        try:
            res = stages.run_one_child(
                job, log=hook, out_root=self.zone.out,
                ner_root=os.path.join(self.zone.ner, "fds_extract", "ner_lite"))
        except Exception as exc:
            res = {"ok": False, "results": {}, "error": str(exc)[:200]}
        ok = bool(res.get("ok"))
        rec = {
            "doc": doc, "trigger": trigger,
            "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
            "elapsed_s": int(time.time() - t0), "ok": ok,
            "err": res.get("error") or None, "selected": list(ids),
            "parallel": self.parallel, "account": account,
            "stages": {k: ("ok" if v.get("ok") else ("skip" if v.get("skipped") else "fail"))
                       for k, v in (res.get("results") or {}).items()},
            "channels": {c: _ch_done(doc, c, self.zone.out) for c in CH},
        }
        with self._hist_lock:
            append_history(rec, self.zone.hist)
        self.log("[完成] %s %s (耗时 %ds)%s" % (
            doc, "成功" if ok else "失败", rec["elapsed_s"],
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
            return "%s正在跑 %d 篇 (并发 %d): %s · 排队 %d" % (
                paused, len(docs), self.parallel, head, n)
        return "%s空闲 · 并发 %d · 排队 %d" % (paused, self.parallel, n)

    def is_busy(self):
        with self.lock:
            busy = bool(self.running)
        return busy or self.q.qsize() > 0


class RunnerHub(object):
    """Shared account/quota registry plus one Runner per A/B zone."""

    def __init__(self, root=ROOT, log=print, parallel=DEFAULT_PARALLEL):
        self.root = root
        self.log = log
        self.accounts = wb.AccountStore(os.path.join(root, ".workbench", "accounts.json"))
        tok = _local_paddle_token()
        if not self.accounts.list_accounts() and tok:
            self.accounts.bootstrap(tok, "本机账号")
        account_a = self.accounts.assignment("A")
        account_b = self.accounts.assignment("B")
        self.zones = wb.make_zones(root, account_a=account_a, account_b=account_b)
        self.quota_book = wb.QuotaBook(os.path.join(root, ".workbench", "quota.json"))
        self.quotas = {zid: self.quota_book.account(z.account)
                       for zid, z in self.zones.items()}
        self.runners = {
            zid: Runner(z, self.quotas[zid], log, parallel=parallel,
                        paused=True, accounts=self.accounts)
            for zid, z in self.zones.items()
        }

    def runner(self, zid):
        return self.runners[zid]

    def resume_all(self):
        for runner in self.runners.values():
            runner.resume()

    def pause_all(self):
        for runner in self.runners.values():
            runner.pause()

    def set_account(self, zid, key):
        self.accounts.assign(zid, key)
        zone = self.zones[zid]
        zone.account = key
        quota = self.quota_book.account(key)
        self.quotas[zid] = quota
        self.runners[zid].quota = quota
        return quota

    def close(self):
        self.pause_all()
        for runner in self.runners.values():
            try:
                runner.store.close()
            except Exception:
                pass
