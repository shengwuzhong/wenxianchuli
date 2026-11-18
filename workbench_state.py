# -*- coding: utf-8 -*-
"""Workbench P0 state: physical zones, durable queue, Paddle page budget, entity audit.

This module deliberately has no tkinter dependency so it can be unit-tested and
reused by future headless workers.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass

CH = ("mineru", "dots", "paddle")
ENTITY_KINDS = ("dataset", "funding", "software")
ENTITY_LABEL = {"dataset": "数据集", "funding": "基金", "software": "软件"}


def _today():
    return datetime.date.today().isoformat()


def pid_alive(pid):
    """Windows-safe liveness check for an old OCR child (no psutil dependency)."""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            k32.CloseHandle(h)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def run_lock(doc, out_root):
    return os.path.join(out_root, doc, ".run.lock")


def running_pid(doc, out_root):
    try:
        with open(run_lock(doc, out_root), encoding="utf-8") as fh:
            return int((fh.read() or "0").strip())
    except Exception:
        return 0


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Zone:
    """A physically isolated work area.

    Zone A keeps the existing repository roots so existing results stay usable.
    Zone B gets a new ``zones/zone_b`` tree.
    """

    zid: str
    label: str
    root: str
    up: str
    out: str
    arch: str
    hist: str
    prefs: str
    db: str
    ner: str
    account: str = "shared"

    def ensure(self):
        for d in (self.up, self.out, self.arch, self.ner,
                  os.path.dirname(self.db), os.path.join(self.root, "logs")):
            os.makedirs(d, exist_ok=True)
        return self

    def paths(self):
        return {"up": self.up, "out": self.out, "arch": self.arch,
                "hist": self.hist, "prefs": self.prefs, "db": self.db,
                "ner": self.ner}


def make_zones(repo_root, account_a="shared", account_b="shared"):
    a = Zone(
        "A", "区 A · 主库",
        repo_root,
        os.path.join(repo_root, "uploads"),
        os.path.join(repo_root, "out"),
        os.path.join(repo_root, "archive"),
        os.path.join(repo_root, "gui_runs.jsonl"),
        os.path.join(repo_root, ".gui_prefs.json"),
        os.path.join(repo_root, ".workbench", "state_a.db"),
        os.path.join(repo_root, "out_llm_trial"),
        account_a,
    )
    broot = os.path.join(repo_root, "zones", "zone_b")
    b = Zone(
        "B", "区 B · 分库",
        broot,
        os.path.join(broot, "uploads"),
        os.path.join(broot, "out"),
        os.path.join(broot, "archive"),
        os.path.join(broot, "gui_runs.jsonl"),
        os.path.join(broot, "prefs.json"),
        os.path.join(broot, ".workbench", "state.db"),
        os.path.join(broot, "out_llm_trial"),
        account_b,
    )
    return {"A": a.ensure(), "B": b.ensure()}


class TaskStore:
    """Durable task journal. One DB per zone; no cross-zone task writes."""

    def __init__(self, fp):
        self.fp = fp
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(fp, timeout=15, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc TEXT NOT NULL,
                    pdf TEXT,
                    ids TEXT NOT NULL,
                    clear_json TEXT NOT NULL DEFAULT '[]',
                    trigger TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    pages INTEGER NOT NULL DEFAULT 0,
                    created TEXT NOT NULL,
                    started TEXT,
                    finished TEXT,
                    error TEXT,
                    pid INTEGER
                )
            """)
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status)")
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_tasks_doc ON tasks(doc)")
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()

    def _row(self, row):
        if row is None:
            return None
        d = dict(row)
        try:
            d["ids"] = json.loads(d.get("ids") or "[]")
        except ValueError:
            d["ids"] = []
        try:
            d["clear"] = json.loads(d.pop("clear_json", "[]") or "[]")
        except ValueError:
            d["clear"] = []
        return d

    def active_for(self, doc):
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM tasks WHERE doc=? AND status IN ('queued','running','interrupted') "
                "ORDER BY id DESC LIMIT 1", (doc,)).fetchone()
        return self._row(row)

    def enqueue(self, doc, pdf, ids, clear=(), trigger="重跑", pages=0, status="queued"):
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM tasks WHERE doc=? AND status IN ('queued','running','interrupted') "
                "ORDER BY id DESC LIMIT 1", (doc,)).fetchone()
            if row:
                return None, self._row(row)
            cur = self.db.execute(
                "INSERT INTO tasks(doc,pdf,ids,clear_json,trigger,status,pages,created) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (doc, pdf, json.dumps(list(ids), ensure_ascii=False),
                 json.dumps(list(clear), ensure_ascii=False), trigger, status,
                 int(pages or 0), _now()))
            self.db.commit()
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._row(row), None

    def mark_running(self, task_id, pid=None):
        with self.lock:
            self.db.execute(
                "UPDATE tasks SET status='running', started=?, pid=?, attempts=attempts+1 "
                "WHERE id=?", (_now(), pid, task_id))
            self.db.commit()

    def finish(self, task_id, ok, error=None):
        with self.lock:
            self.db.execute(
                "UPDATE tasks SET status=?, finished=?, error=? WHERE id=?",
                ("done" if ok else "failed", _now(), (error or None), task_id))
            self.db.commit()

    def requeue(self, task_id):
        with self.lock:
            self.db.execute(
                "UPDATE tasks SET status='queued', error=NULL, finished=NULL WHERE id=?",
                (task_id,))
            self.db.commit()

    def mark_interrupted_running(self):
        """A GUI restart cannot reattach stdout to old child processes.

        Keep the row visible as interrupted; the user can continue it explicitly.
        """
        with self.lock:
            n = self.db.execute(
                "UPDATE tasks SET status='interrupted' WHERE status='running'").rowcount
            self.db.commit()
        return n

    def pending(self, limit=10000):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM tasks WHERE status IN ('queued','interrupted') "
                "ORDER BY id LIMIT ?", (int(limit),)).fetchall()
        return [self._row(r) for r in rows]

    def counts(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    def recent(self, limit=200):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._row(r) for r in rows]


class QuotaStore:
    """Paddle page budget shared by zones that use the same account.

    Entries are reservations, not just completed pages: a retry or a failed
    request still consumes the provider's daily page allowance in the worst case.
    """

    def __init__(self, fp, account="shared", daily_pages=20000):
        self.fp = fp
        self.account = account
        self.daily_pages = int(daily_pages or 20000)
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        self.data = self._load()

    def _empty(self):
        return {"date": _today(), "limit": self.daily_pages,
                "accounts": {self.account: {"entries": {}}}}

    def _load(self):
        try:
            with open(self.fp, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = self._empty()
        if data.get("date") != _today():
            data = self._empty()
        data.setdefault("accounts", {}).setdefault(self.account, {"entries": {}})
        data["limit"] = int(data.get("limit") or self.daily_pages)
        return data

    def _save(self):
        tmp = self.fp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.fp)

    def _roll(self):
        if self.data.get("date") != _today():
            self.data = self._empty()
            self._save()

    def _entries(self):
        return self.data["accounts"][self.account].setdefault("entries", {})

    def used(self):
        self._roll()
        return sum(int(v.get("pages") or 0) for v in self._entries().values())

    def remaining(self):
        return max(0, int(self.data["limit"]) - self.used())

    def set_limit(self, n):
        with self.lock:
            self.data["limit"] = max(1, int(n))
            self._save()

    def reserve(self, key, pages):
        pages = max(0, int(pages or 0))
        with self.lock:
            self._roll()
            e = self._entries()
            if key and key in e:
                return True
            if self.used() + pages > int(self.data["limit"]):
                return False
            if key:
                e[key] = {"pages": pages, "at": _now()}
            self._save()
            return True

    def release(self, key):
        with self.lock:
            self._roll()
            if key in self._entries():
                self._entries().pop(key, None)
                self._save()

    def summary(self):
        with self.lock:
            self._roll()
        return {"account": self.account, "date": self.data["date"],
                "used": self.used(), "limit": self.data["limit"],
                "remaining": self.remaining()}


def page_count(pdf):
    if not pdf or not os.path.isfile(pdf):
        return 0
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf)
        try:
            return len(doc)
        finally:
            doc.close()
    except Exception:
        return 0


def snapshot_doc(zone, doc, reason="", keep=3):
    """Copy the current document output before a task may overwrite it.

    A real copy is deliberate: several pipeline stages rewrite existing files in
    place, so hardlinks would not be a point-in-time snapshot.
    """
    src = os.path.join(zone.out, doc)
    if not os.path.isdir(src):
        return None
    base = os.path.join(zone.root, "versions", doc)
    os.makedirs(base, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(base, stamp)
    n = 1
    while os.path.exists(dst):
        n += 1
        dst = os.path.join(base, "%s-%d" % (stamp, n))
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".run.lock"))
    with open(os.path.join(dst, "_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump({"doc": doc, "created": _now(), "reason": reason,
                   "source": src}, fh, ensure_ascii=False, indent=1)
    try:
        snaps = sorted(d for d in os.listdir(base)
                       if os.path.isdir(os.path.join(base, d)))
        for old in snaps[:-max(1, int(keep))]:
            shutil.rmtree(os.path.join(base, old), ignore_errors=True)
    except OSError:
        pass
    return dst


def entity_paths(doc, zone):
    base = os.path.join(zone.ner, "fds_extract", "ner_lite", doc)
    return (os.path.join(base, "ner_lite.json"),
            os.path.join(base, "ner_lite_audit.json"))


def entity_statuses(doc, zone):
    """Return per-kind extraction status plus the evidence path.

    ``absent_confirmed`` is intentionally conservative: it requires an existing
    ner_lite audit with no network/parse failures. A missing product is
    ``not_checked``, never "absent".
    """
    product_fp, audit_fp = entity_paths(doc, zone)
    out = {k: {"status": "not_checked", "count": 0,
               "reason": "未找到 ner_lite 产物", "evidence": product_fp}
           for k in ENTITY_KINDS}
    if not os.path.isfile(product_fp):
        return out
    try:
        with open(product_fp, encoding="utf-8") as fh:
            product = json.load(fh)
        records = product.get("records") or []
    except Exception as e:
        for k in ENTITY_KINDS:
            out[k]["status"] = "extraction_failed"
            out[k]["reason"] = "ner_lite.json 解析失败: %s" % str(e)[:80]
        return out
    counts = {k: 0 for k in ENTITY_KINDS}
    for r in records:
        k = r.get("kind")
        if k in counts:
            counts[k] += 1
    audit = None
    errors = 0
    parse_fail = 0
    if os.path.isfile(audit_fp):
        try:
            with open(audit_fp, encoding="utf-8") as fh:
                audit = json.load(fh)
            c = audit.get("counts") or {}
            errors = int(c.get("errors_network") or 0)
            parse_fail = int(c.get("dropped_parse_fail") or 0)
        except Exception:
            audit = None
    for k in ENTITY_KINDS:
        if counts[k]:
            out[k] = {"status": "present", "count": counts[k],
                      "reason": "已抽取", "evidence": product_fp}
        elif audit is None:
            out[k] = {"status": "not_checked", "count": 0,
                      "reason": "ner_lite 产物存在但缺少审计", "evidence": audit_fp}
        elif errors or parse_fail:
            out[k] = {"status": "extraction_failed", "count": 0,
                      "reason": "网络/解析错误 %d/%d" % (errors, parse_fail),
                      "evidence": audit_fp}
        else:
            out[k] = {"status": "absent_confirmed", "count": 0,
                      "reason": "已检查，未发现该类实体", "evidence": audit_fp}
    return out


def entity_summary(doc, zone):
    st = entity_statuses(doc, zone)
    if any(v["status"] == "present" for v in st.values()):
        return "有", st
    if any(v["status"] == "extraction_failed" for v in st.values()):
        return "失败", st
    if all(v["status"] == "absent_confirmed" for v in st.values()):
        return "无", st
    return "未查", st
