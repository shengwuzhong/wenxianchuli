# -*- coding: utf-8 -*-
"""Read-only aggregation of tasks, locks and per-tool boards.

Examples:
  python coordination/status.py
  python coordination/status.py --json
"""
import argparse
import datetime
import json
import os
import sys

from _util import COORD, now, parse_iso, print_table, read_json

TASKS = os.path.join(COORD, "tasks")
LOCKS = os.path.join(COORD, "locks")
BOARD = os.path.join(COORD, "board")
REVIEWS = os.path.join(COORD, "reviews")
MERGES = os.path.join(COORD, "merges")


def tasks():
    out = []
    if os.path.isdir(TASKS):
        for name in sorted(os.listdir(TASKS)):
            if name.endswith(".json"):
                t = read_json(os.path.join(TASKS, name), {})
                t["_file"] = name
                out.append(t)
    return out


def locks():
    out = []
    if os.path.isdir(LOCKS):
        for name in sorted(os.listdir(LOCKS)):
            if not name.endswith(".json"):
                continue
            rec = read_json(os.path.join(LOCKS, name), {})
            exp = parse_iso(rec.get("expires_at"))
            rec["_stale"] = bool(exp and exp <= now())
            out.append(rec)
    return out


def boards():
    out = []
    if os.path.isdir(BOARD):
        for name in sorted(os.listdir(BOARD)):
            if name.endswith(".json"):
                rec = read_json(os.path.join(BOARD, name), {})
                hb = parse_iso(rec.get("last_heartbeat"))
                rec["_stale"] = bool(hb and (now() - hb) > datetime.timedelta(minutes=30))
                out.append(rec)
    return out


def counts():
    return {
        "reviews": len([x for x in os.listdir(REVIEWS) if x.endswith(".json")])
        if os.path.isdir(REVIEWS) else 0,
        "merges": len([x for x in os.listdir(MERGES) if x.endswith(".json")])
        if os.path.isdir(MERGES) else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    data = {
        "tasks": tasks(),
        "locks": locks(),
        "boards": boards(),
        "counts": counts(),
    }
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0

    print("== tasks ==")
    if data["tasks"]:
        print_table(
            [[t.get("id", "-"), t.get("owner", "-"), t.get("status", "-"),
              t.get("priority", "-"), t.get("updated_at", "-"),
              ",".join(t.get("allowed_files") or [])[:70]] for t in data["tasks"]],
            ["TASK", "OWNER", "STATUS", "PRI", "UPDATED", "FILES"],
        )
    else:
        print("(none)")

    print("\n== locks ==")
    if data["locks"]:
        print_table(
            [[l.get("path", "-"), l.get("owner", "-"), l.get("task", "-"),
              l.get("expires_at", "-"), "STALE" if l.get("_stale") else "ok"]
             for l in data["locks"]],
            ["PATH", "OWNER", "TASK", "EXPIRES", "STATE"],
        )
    else:
        print("(none)")

    print("\n== boards ==")
    if data["boards"]:
        print_table(
            [[b.get("tool", "-"), b.get("task", "-"), b.get("state", "-"),
              b.get("last_heartbeat", "-"), "STALE" if b.get("_stale") else "ok"]
             for b in data["boards"]],
            ["TOOL", "TASK", "STATE", "HEARTBEAT", "STATE"],
        )
    else:
        print("(none)")

    print("\nreviews=%d merges=%d" % (data["counts"]["reviews"], data["counts"]["merges"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
