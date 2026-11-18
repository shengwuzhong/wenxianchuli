# -*- coding: utf-8 -*-
"""Folder ingest: detect new PDFs in a zone's uploads directory.

Design rules (2026-11-18):
  * only *new* files are auto-queued; existing files at first start are a
    baseline and are never auto-run (a 1000-doc historical backlog must not
    start OCR by accident);
  * a file must keep the same size/mtime for ``stable_scans`` scans before it
    is considered complete (Windows copy/download often shows partial files);
  * SHA-256 is the identity: a second name with the same bytes is a duplicate,
    and a changed file under an existing name is a conflict (never overwrite);
  * a PDF that cannot be opened is marked ``bad`` and never queued.

The GUI owns submission/quota; this module only does filesystem discovery and
the durable per-zone state.  It has no tkinter dependency and is unit-testable.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time

import workbench_state as wb
from docid import doc_of

STABLE_SCANS = 2
STATE_VERSION = 1


def _mtime_ns(st):
    return int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1000000000)))


def sha256_file(fp, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class IngestStore:
    """Durable per-zone ingest registry (JSON, atomic replace)."""

    def __init__(self, fp):
        self.fp = fp
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self):
        try:
            with io.open(self.fp, encoding="utf-8") as fh:
                d = json.load(fh) or {}
        except Exception:
            d = {}
        if not isinstance(d, dict):
            d = {}
        d.setdefault("version", STATE_VERSION)
        d.setdefault("baseline", False)
        d.setdefault("files", {})
        return d

    def _save(self):
        os.makedirs(os.path.dirname(self.fp), exist_ok=True)
        tmp = self.fp + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.fp)

    def entry(self, name):
        with self.lock:
            return dict(self.data["files"].get(name) or {})

    def set_entry(self, name, **fields):
        with self.lock:
            rec = dict(self.data["files"].get(name) or {})
            rec.update(fields)
            rec["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.data["files"][name] = rec
            self._save()
            return dict(rec)

    def mark_baseline(self, entries):
        with self.lock:
            self.data["files"].update(entries)
            self.data["baseline"] = True
            self._save()

    def statuses(self):
        """doc -> status; conflicts win over normal statuses."""
        out = {}
        rank = {"conflict": 9, "bad": 8, "duplicate": 7, "waiting_quota": 6,
                "waiting_account": 5, "waiting_pause": 4, "waiting_confirm": 4,
                "queued": 3, "pending": 2, "baseline": 1, "removed": 0}
        with self.lock:
            for rec in self.data["files"].values():
                doc = rec.get("doc") or ""
                st = rec.get("status") or "baseline"
                if not doc:
                    continue
                if doc not in out or rank.get(st, 0) > rank.get(out[doc], 0):
                    out[doc] = st
        return out

    def entries_by_status(self, *wanted):
        wanted = set(wanted)
        with self.lock:
            rows = []
            for name, rec in self.data["files"].items():
                if rec.get("status") in wanted:
                    d = dict(rec)
                    d["name"] = name
                    rows.append(d)
        return rows

    def sha_owner(self, sha, exclude=None):
        with self.lock:
            for name, rec in self.data["files"].items():
                if name == exclude:
                    continue
                if rec.get("sha") == sha:
                    return name
        return None


class IngestScanner:
    """Scan one zone's uploads; return events for the GUI.

    ``events`` are dicts with ``name/pdf/doc/sha/size/mtime/pages/status``.
    Only ``pending`` events should be auto-submitted.  ``conflict``, ``bad``
    and ``duplicate`` are surfaced as terminal rows for manual action.
    """

    def __init__(self, store, up_root, stable_scans=STABLE_SCANS,
                 page_counter=None, hasher=None):
        self.store = store
        self.up_root = up_root
        self.stable_scans = max(1, int(stable_scans))
        self.page_counter = page_counter or wb.page_count
        self.hasher = hasher or sha256_file
        self._stable = {}      # name -> [size, mtime, count]

    def _pdfs(self):
        try:
            names = sorted(os.listdir(self.up_root))
        except OSError:
            return []
        return [n for n in names
                if n.lower().endswith(".pdf") and os.path.isfile(os.path.join(self.up_root, n))]

    def _baseline(self):
        entries = {}
        for name in self._pdfs():
            fp = os.path.join(self.up_root, name)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            entries[name] = {
                "size": st.st_size, "mtime": int(st.st_mtime),
                "mtime_ns": _mtime_ns(st), "doc": doc_of(name), "status": "baseline",
            }
        self.store.mark_baseline(entries)
        return len(entries)

    def scan(self):
        if not self.store.data.get("baseline"):
            n = self._baseline()
            return [{"status": "baseline", "count": n}]
        events = []
        present = set(self._pdfs())
        for name in list(self._stable):
            if name not in present:
                self._stable.pop(name, None)
        for name in sorted(present):
            fp = os.path.join(self.up_root, name)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rec = self.store.entry(name)
            mtime_ns = _mtime_ns(st)
            same_meta = bool(rec and rec.get("size") == st.st_size)
            if same_meta and rec.get("mtime_ns") is not None:
                same_meta = rec.get("mtime_ns") == mtime_ns
            elif same_meta:
                same_meta = rec.get("mtime") == int(st.st_mtime)
            if same_meta:
                self._stable.pop(name, None)
                continue
            key = [st.st_size, mtime_ns]
            cur = self._stable.get(name)
            if cur and cur[0] == key[0] and cur[1] == key[1]:
                cur[2] += 1
            else:
                cur = [key[0], key[1], 1]
                self._stable[name] = cur
            if cur[2] < self.stable_scans:
                continue
            self._stable.pop(name, None)
            try:
                sha = self.hasher(fp)
            except Exception as e:
                self.store.set_entry(name, size=st.st_size, mtime=int(st.st_mtime), mtime_ns=mtime_ns,
                                     doc=doc_of(name), status="bad",
                                     error="读取失败: %s" % str(e)[:120])
                events.append({"status": "bad", "name": name, "doc": doc_of(name),
                               "pdf": fp, "error": "读取失败"})
                continue
            owner = self.store.sha_owner(sha, exclude=name)
            doc = doc_of(name)
            if owner:
                self.store.set_entry(name, size=st.st_size, mtime=int(st.st_mtime), mtime_ns=mtime_ns,
                                     sha=sha, doc=doc, status="duplicate", duplicate_of=owner)
                events.append({"status": "duplicate", "name": name, "doc": doc,
                               "pdf": fp, "duplicate_of": owner})
                continue
            pages = 0
            try:
                pages = int(self.page_counter(fp) or 0)
            except Exception:
                pages = 0
            # baseline entries intentionally have no SHA (hashing a 1000-PDF
            # backlog is expensive), so any later size/mtime change of a
            # baseline name is a conflict rather than a silent first run.
            changed = (bool(rec.get("sha") and rec.get("sha") != sha)
                       or rec.get("status") == "baseline")
            if not pages:
                self.store.set_entry(name, size=st.st_size, mtime=int(st.st_mtime), mtime_ns=mtime_ns,
                                     sha=sha, doc=doc, status="bad", error="PDF 无法打开或 0 页")
                events.append({"status": "bad", "name": name, "doc": doc, "pdf": fp,
                               "error": "PDF 无法打开或 0 页"})
                continue
            if changed:
                self.store.set_entry(name, size=st.st_size, mtime=int(st.st_mtime), mtime_ns=mtime_ns,
                                     sha=sha, doc=doc, pages=pages, status="conflict",
                                     error="同名文件内容已变化；不自动覆盖")
                events.append({"status": "conflict", "name": name, "doc": doc,
                               "pdf": fp, "sha": sha, "pages": pages})
                continue
            self.store.set_entry(name, size=st.st_size, mtime=int(st.st_mtime), mtime_ns=mtime_ns,
                                 sha=sha, doc=doc, pages=pages, status="pending")
            events.append({"status": "pending", "name": name, "doc": doc,
                           "pdf": fp, "sha": sha, "pages": pages})
        return events
