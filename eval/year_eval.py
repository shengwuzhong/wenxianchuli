# -*- coding: utf-8 -*-
"""Exact-match evaluation for publication year gold.

Gold schema: {"docs": [{"doc","zone":"A|B","year":int|null,...}]}
Unknown (null) docs are excluded from the denominator.
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _year(meta):
    v = (meta or {}).get("year")
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return int(v) if v not in (None, "", []) else None
    except (TypeError, ValueError):
        return None


def _source(meta):
    v = (meta or {}).get("year")
    if isinstance(v, dict):
        return (v.get("confidence") or {}).get("source") or ""
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=os.path.join(ROOT, "eval", "year_gold_33.json"))
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    with io.open(a.gold, encoding="utf-8") as fh:
        gold = json.load(fh)
    docs = gold.get("docs") or []
    known = [d for d in docs if d.get("year") is not None]
    errors = []
    by_source = {}
    for d in known:
        zone = "B" if d.get("zone") == "B" else "A"
        ddir = os.path.join(a.root, "zones", "zone_b", "out", d["doc"]) if zone == "B" \
            else os.path.join(a.root, "out", d["doc"])
        meta = {}
        fp = os.path.join(ddir, "metadata.json")
        if os.path.isfile(fp):
            with io.open(fp, encoding="utf-8-sig") as fh:
                meta = json.load(fh) or {}
        pred = _year(meta)
        src = _source(meta) or "none"
        row = by_source.setdefault(src, {"n": 0, "ok": 0})
        row["n"] += 1
        ok = pred == int(d["year"])
        row["ok"] += int(ok)
        if not ok:
            errors.append({"doc": d["doc"], "zone": zone, "gold": d["year"],
                           "pred": pred, "source": src})
    n = len(known)
    correct = n - len(errors)
    out = {
        "gold": os.path.relpath(a.gold, a.root),
        "docs_total": len(docs),
        "known": n,
        "correct": correct,
        "accuracy": (correct / float(n)) if n else None,
        "by_source": by_source,
        "errors": errors,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.json:
        with io.open(a.json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
