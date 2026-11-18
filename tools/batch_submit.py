# -*- coding: utf-8 -*-
"""batch_submit.py — 非阻塞批量提交器(子进程隔离 / 超时看门狗 / 退避重试 / 状态落盘)

为什么要另起一层, 而不直接走 webapp 的 /upload:
  webapp 用一个进程级 RUN_LOCK 把所有任务串成一队(threading), 单篇卡在渠道 API
  的排队等待里时, 后面所有任务只会一直"排队中", 且没有取消入口 —— 只能整个进程杀掉。
  本脚本让每篇跑在**独立子进程**里, 因此:
    * 提交即返回(Popen), 不阻塞调用方;
    * 单篇可被单独 kill(整棵进程树), 不影响其他篇;
    * 有墙钟超时与"日志静默"看门狗, 卡住必被发现而不是无限等;
    * 失败/超时按篇重试, 汇总到状态文件, 断线也能看进度。

用法(在项目根目录, 用装好依赖的 3.11 解释器):
  python tools/batch_submit.py --docs-file ops/batch15.txt --workers 2 \\
      --timeout 1800 --idle-timeout 600 --retries 1 --max-wall 7200

产物:
  <status>  原子写入的 JSON 快照(每次状态变化即刷新), 供外部轮询
  <logdir>/ 每篇一份 stdout+stderr 日志, 外加 events.jsonl 事件流
"""
from __future__ import print_function

import argparse
import datetime
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS = os.path.join(ROOT, "uploads")
OUT = os.path.join(ROOT, "out")

STATE_LOCK = threading.Lock()
FLUSH_LOCK = threading.Lock()   # 多 worker 同时落盘会撞同一个 .tmp, 必须整体串行


def now_s():
    return time.strftime("%H:%M:%S")


def iso(ts=None):
    return datetime.datetime.fromtimestamp(ts if ts else time.time()).isoformat(timespec="seconds")


def _pid_alive(pid):
    """PID 是否仍存在；Windows 不能用 os.kill(pid, 0)。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not h:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_run_lock(status_fp):
    """单实例锁：同一状态文件只允许一个 batch_submit 进程。"""
    fp = status_fp + ".lock"
    for _ in range(2):
        try:
            fd = os.open(fp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = io.open(fp, encoding="ascii", errors="replace").read().strip().split()[0]
            except (OSError, IndexError):
                pid = ""
            if pid and _pid_alive(pid):
                return None
            try:
                os.remove(fp)
            except OSError:
                pass
            continue
        except OSError:
            return None
        try:
            os.write(fd, ("%d\n" % os.getpid()).encode("ascii"))
        finally:
            os.close(fd)
        return fp
    return None


def _release_run_lock(fp):
    if fp:
        try:
            os.remove(fp)
        except OSError:
            pass


def _atomic_write_json(fp, obj):
    tmp = "%s.%d.tmp" % (fp, os.getpid() * 1000 + threading.get_ident() % 1000)
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1))
        f.flush()
        os.fsync(f.fileno())
    for i in range(5):   # Windows 上目标被读取方短暂占用时 replace 会抛 WinError 32, 退避重试
        try:
            os.replace(tmp, fp)
            return
        except OSError:
            if i == 4:
                raise
            time.sleep(0.05 * (i + 1))


def kill_tree(pid):
    """整棵进程树终止: pipeline 会 spawn 子进程(渲染/转换), 只杀父会留下孤儿。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=30)
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


class Batch(object):
    def __init__(self, docs, args):
        self.docs = docs
        self.args = args
        self.started = time.time()
        self.records = []
        for d in docs:
            self.records.append({
                "doc": d,
                "pdf": os.path.join(UPLOADS, d + ".pdf"),
                "state": "pending",      # pending/running/retrying/ok/failed/timeout/skipped
                "attempt": 0,
                "pid": None,
                "started_at": None,
                "finished_at": None,
                "elapsed_s": None,
                "rc": None,
                "reason": "",
                "warnings": [],
                "log": "",
            })
        self.by_doc = {r["doc"]: r for r in self.records}
        self.events_fp = os.path.join(args.logdir, "events.jsonl")
        self._counter = 0

    # ---------- 状态持久化 ----------
    def snapshot(self):
        with STATE_LOCK:
            recs = [dict(r) for r in self.records]
        done = [r for r in recs if r["state"] in ("ok", "failed", "timeout", "skipped")]
        summary = {
            "total": len(recs),
            "ok": sum(1 for r in recs if r["state"] == "ok"),
            "failed": sum(1 for r in recs if r["state"] == "failed"),
            "timeout": sum(1 for r in recs if r["state"] == "timeout"),
            "skipped": sum(1 for r in recs if r["state"] == "skipped"),
            "running": sum(1 for r in recs if r["state"] == "running"),
            "pending": sum(1 for r in recs if r["state"] == "pending"),
            "done": len(done),
        }
        return {
            "batch_id": self.args.batch_id,
            "started_at": iso(self.started),
            "updated_at": iso(),
            "finished_at": iso() if summary["done"] == summary["total"] else None,
            "workers": self.args.workers,
            "timeout_s": self.args.timeout,
            "idle_timeout_s": self.args.idle_timeout,
            "max_wall_s": self.args.max_wall,
            "summary": summary,
            "docs": recs,
        }

    def flush(self):
        with FLUSH_LOCK:
            _atomic_write_json(self.args.status, self.snapshot())

    def event(self, kind, rec=None, **extra):
        ev = {"ts": iso(), "event": kind}
        if rec is not None:
            ev["doc"] = rec["doc"]
            ev["state"] = rec["state"]
        ev.update(extra)
        try:
            with io.open(self.events_fp, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------- 单篇执行 ----------
    def _set(self, rec, **kw):
        with STATE_LOCK:
            rec.update(kw)
        self.flush()

    def run_doc(self, rec):
        args = self.args
        doc = rec["doc"]
        pdf = rec["pdf"]
        out_dir = os.path.join(OUT, doc)
        idx = os.path.join(out_dir, "index.html")
        attempts = 1 + max(0, args.retries)
        for attempt in range(1, attempts + 1):
            if args.max_wall and (time.time() - self.started) > args.max_wall:
                self._set(rec, state="skipped", reason="超出批次总时长上限, 未启动")
                self.event("skipped", rec, reason=rec["reason"])
                return
            logf = os.path.join(args.logdir, "%02d_%s.a%d.log" % (
                self.docs.index(doc) + 1, doc.replace("/", "_"), attempt))
            t0 = time.time()
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            fh = io.open(logf, "wb")
            self._set(rec, state="running" if attempt == 1 else "retrying",
                      attempt=attempt, started_at=iso(t0), log=os.path.relpath(logf, ROOT),
                      reason="" if attempt == 1 else rec["reason"])
            self.event("start", rec, attempt=attempt, log=rec["log"])
            print("[%s] [%d/%d] %s 启动 (第%d次, 超时 %ds, 静默 %ds)" % (
                now_s(), self.docs.index(doc) + 1, len(self.docs), doc, attempt,
                args.timeout, args.idle_timeout), flush=True)
            try:
                proc = subprocess.Popen(
                    [sys.executable, os.path.join(ROOT, "pipeline.py"), pdf],
                    cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env=env,
                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
                    start_new_session=(os.name != "nt"))
            except Exception as e:
                fh.close()
                self._set(rec, state="failed", reason="无法启动子进程: %s" % e,
                          finished_at=iso(), elapsed_s=round(time.time() - t0, 1))
                self.event("spawn_error", rec, err=str(e))
                return
            self._set(rec, pid=proc.pid)
            self.event("pid", rec, pid=proc.pid)

            # 看门狗: 墙钟超时 + 日志静默(paddle 排队时进程完全静默, 只能靠这个发现)
            last_size, last_growth = -1, time.time()
            killed = None
            while True:
                rc = proc.poll()
                if rc is not None:
                    break
                time.sleep(2)
                try:
                    sz = os.path.getsize(logf)
                except OSError:
                    sz = -1
                if sz != last_size:
                    last_size, last_growth = sz, time.time()
                elapsed = time.time() - t0
                if elapsed > args.timeout:
                    killed = "墙钟超时(>%ds)" % args.timeout
                elif time.time() - last_growth > args.idle_timeout:
                    killed = "日志静默超过 %ds(疑似渠道排队/卡死)" % args.idle_timeout
                if killed:
                    kill_tree(proc.pid)
                    try:
                        proc.wait(timeout=15)
                    except Exception:
                        pass
                    break
            rc = proc.poll()
            el = round(time.time() - t0, 1)
            fh.close()
            rec_warn = self._scan_warnings(logf)
            with STATE_LOCK:
                rec["warnings"] = rec_warn

            if killed:
                self._set(rec, state="timeout", rc=rc, finished_at=iso(), elapsed_s=el,
                          reason=killed, pid=None)
                self.event("timeout", rec, reason=killed, elapsed=el)
                print("[%s] [%d/%d] %s 超时终止: %s (%.0fs)" % (
                    now_s(), self.docs.index(doc) + 1, len(self.docs), doc, killed, el), flush=True)
            else:
                ok = (rc == 0 and os.path.isfile(idx)
                      and os.path.getmtime(idx) >= t0 - 2)
                if ok:
                    self._set(rec, state="ok", rc=rc, finished_at=iso(), elapsed_s=el, pid=None,
                              reason="")
                    self.event("ok", rec, elapsed=el)
                    print("[%s] [%d/%d] %s 完成 (%.0fs)%s" % (
                        now_s(), self.docs.index(doc) + 1, len(self.docs), doc, el,
                        (" | 告警: " + "; ".join(rec_warn[:2])) if rec_warn else ""), flush=True)
                    return
                why = ("退出码 %s" % rc) if rc != 0 else "未生成本次 index.html"
                self._set(rec, state="failed", rc=rc, finished_at=iso(), elapsed_s=el,
                          pid=None, reason=why)
                self.event("failed", rec, reason=why, elapsed=el)
                print("[%s] [%d/%d] %s 失败: %s (%.0fs)" % (
                    now_s(), self.docs.index(doc) + 1, len(self.docs), doc, why, el), flush=True)

            if attempt < attempts:
                self._set(rec, state="pending", reason=rec["reason"] + " → 准备重试")
                time.sleep(args.retry_backoff)
            else:
                return

    @staticmethod
    def _scan_warnings(logf):
        warn = []
        try:
            with io.open(logf, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    s = line.strip()
                    if ("失败" in s or "页数不匹配" in s or "超时" in s) and len(warn) < 8:
                        warn.append(s[:160])
        except OSError:
            pass
        return warn

    # ---------- 调度 ----------
    def run(self):
        args = self.args
        os.makedirs(args.logdir, exist_ok=True)
        self.flush()
        self.event("batch_start", total=len(self.docs), workers=args.workers)
        print("=" * 64)
        print("批次 %s | %d 篇 | 并发 %d | 单篇超时 %ds | 静默看门狗 %ds | 重试 %d" % (
            args.batch_id, len(self.docs), args.workers, args.timeout,
            args.idle_timeout, args.retries))
        print("状态文件: %s" % args.status)
        print("=" * 64, flush=True)

        pending = list(self.docs)
        lock = threading.Lock()
        threads = []

        def worker():
            while True:
                with lock:
                    if not pending:
                        return
                    doc = pending.pop(0)
                try:
                    self.run_doc(self.by_doc[doc])
                except Exception as e:
                    with STATE_LOCK:
                        rec = self.by_doc[doc]
                        rec.update(state="failed", reason="调度异常: %s" % e,
                                   finished_at=iso())
                    self.event("worker_error", self.by_doc[doc], err=traceback.format_exc()[-800:])
                    print("[%s] %s 调度异常: %s" % (now_s(), doc, e), flush=True)
                finally:
                    try:
                        self.flush()
                    except Exception as e:   # 状态落盘失败不能带走整个 worker
                        print("[%s] 状态落盘失败: %s" % (now_s(), e), flush=True)

        for i in range(min(args.workers, len(self.docs))):
            t = threading.Thread(target=worker, name="w%d" % i, daemon=True)
            t.start()
            threads.append(t)

        # 心跳: 让外部轮询者看到"还活着"(固定间隔, 不用 join 超时, 避免线程提前退出后空转)
        last_beat = 0.0
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            if time.time() - last_beat < args.heartbeat:
                continue
            last_beat = time.time()
            snap = self.snapshot()          # 自带 STATE_LOCK, 外层不得再持有(普通 Lock 不可重入会死锁)
            with STATE_LOCK:
                running = [r for r in self.records if r["state"] in ("running", "retrying")]
            self.flush()
            msg = ", ".join("%s(%.0fs)" % (r["doc"], time.time() - time.mktime(
                time.strptime(r["started_at"], "%Y-%m-%dT%H:%M:%S"))) for r in running) or "无运行中"
            print("[%s] 进度 %d/%d 完成 | 运行中: %s" % (
                now_s(), snap["summary"]["done"], snap["summary"]["total"], msg), flush=True)

        self.flush()
        snap = self.snapshot()
        s = snap["summary"]
        self.event("batch_end", **s)
        print("=" * 64)
        print("批次结束: 成功 %d / 失败 %d / 超时 %d / 跳过 %d (总 %.1f 分钟)" % (
            s["ok"], s["failed"], s["timeout"], s["skipped"],
            (time.time() - self.started) / 60.0))
        for r in self.records:
            print("  %-32s %-8s %6s  %s" % (
                r["doc"], r["state"],
                "%.0fs" % r["elapsed_s"] if r["elapsed_s"] else "-",
                r["reason"] or ""))
        print("=" * 64, flush=True)
        return 0 if (s["ok"] == s["total"]) else 1


def load_docs(args):
    if args.docs_file:
        raw = io.open(args.docs_file, encoding="utf-8").read().splitlines()
    else:
        raw = (args.docs or "").replace(",", "\n").splitlines()
    docs = []
    for line in raw:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        docs.append(s)
    if not docs:
        raise SystemExit("没有可提交的文档")
    seen, uniq = set(), []
    for d in docs:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def main(argv=None):
    ap = argparse.ArgumentParser(description="非阻塞批量提交(子进程隔离 + 超时看门狗)")
    ap.add_argument("--docs-file", help="每行一个文档名(不含 .pdf), # 开头为注释")
    ap.add_argument("--docs", help="逗号分隔的文档名")
    ap.add_argument("--workers", type=int, default=2, help="并发篇数(默认 2, 渠道 API 名额为 3)")
    ap.add_argument("--timeout", type=int, default=1800, help="单篇墙钟超时秒")
    ap.add_argument("--idle-timeout", type=int, default=600, help="日志静默多少秒判定卡死")
    ap.add_argument("--retries", type=int, default=1, help="单篇失败/超时后的重试次数")
    ap.add_argument("--retry-backoff", type=int, default=10, help="重试前等待秒")
    ap.add_argument("--max-wall", type=int, default=0, help="批次总时长上限秒(0=不限)")
    ap.add_argument("--heartbeat", type=int, default=30, help="心跳输出间隔秒")
    ap.add_argument("--status", default=os.path.join(ROOT, ".workbuddy", "ops", "batch_status.json"))
    ap.add_argument("--logdir", default=os.path.join(ROOT, ".workbuddy", "ops", "logs"))
    ap.add_argument("--batch-id", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--dry-run", action="store_true", help="只校验输入与路径, 不启动子进程")
    args = ap.parse_args(argv)

    docs = load_docs(args)
    missing = [d for d in docs if not os.path.isfile(os.path.join(UPLOADS, d + ".pdf"))]
    if missing:
        print("以下文档在 uploads 下找不到 PDF, 已中止(不做部分提交):")
        for m in missing:
            print("  - %s" % m)
        return 2
    print("待提交 %d 篇:" % len(docs))
    for i, d in enumerate(docs, 1):
        sz = os.path.getsize(os.path.join(UPLOADS, d + ".pdf")) / 1024.0
        print("  %2d. %-32s %8.0f KB" % (i, d, sz))
    if args.dry_run:
        print("dry-run: 未启动任何子进程")
        return 0
    os.makedirs(os.path.dirname(args.status) or ".", exist_ok=True)
    lock_fp = _acquire_run_lock(args.status)
    if not lock_fp:
        print("已有同一状态的批处理在运行，拒绝重复启动: %s" % args.status)
        return 3
    try:
        return Batch(docs, args).run()
    finally:
        _release_run_lock(lock_fp)


if __name__ == "__main__":
    sys.exit(main())
