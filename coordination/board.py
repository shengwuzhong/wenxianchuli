# -*- coding: utf-8 -*-
"""Per-tool status board. One writer per file, so no shared-board contention.

Examples:
  python coordination/board.py set --tool deepseek --task T-001 \
      --state in_progress --files viewer.py --branch agent/deepseek/T-001
  python coordination/board.py show
  python coordination/board.py show --tool trae
"""
import argparse
import json
import os
import sys

from _util import COORD, atomic_write_json, fail, iso, print_table, read_json

BOARD = os.path.join(COORD, "board")
STATES = ("idle", "claimed", "in_progress", "review", "blocked", "done", "error")


def _path(tool):
    if not tool or "/" in tool or "\\" in tool:
        fail("invalid tool name: %r" % tool, 2)
    return os.path.join(BOARD, tool + ".json")


def cmd_set(a):
    if a.state not in STATES:
        fail("invalid state: %s" % a.state, 2)
    rec = read_json(_path(a.tool)) or {"tool": a.tool}
    rec.update({
        "tool": a.tool,
        "task": a.task,
        "state": a.state,
        "branch": a.branch or rec.get("branch", ""),
        "commit": a.commit or rec.get("commit", ""),
        "files_locked": [x for x in (a.files or "").split(",") if x],
        "last_heartbeat": iso(),
    })
    atomic_write_json(_path(a.tool), rec)
    print("board %s -> %s (task=%s)" % (a.tool, a.state, a.task))


def cmd_show(a):
    tools = [a.tool] if a.tool else (
        [f[:-5] for f in sorted(os.listdir(BOARD)) if f.endswith(".json")]
        if os.path.isdir(BOARD) else []
    )
    if not tools:
        print("no boards")
        return
    if a.json:
        out = {}
        for t in tools:
            out[t] = read_json(_path(t), {})
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    rows = []
    for t in tools:
        rec = read_json(_path(t), {})
        rows.append([t, rec.get("task", "-"), rec.get("state", "-"),
                     rec.get("branch", "-"), rec.get("last_heartbeat", "-"),
                     ",".join(rec.get("files_locked") or [])[:60]])
    print_table(rows, ["TOOL", "TASK", "STATE", "BRANCH", "HEARTBEAT", "FILES"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("set")
    s.add_argument("--tool", required=True)
    s.add_argument("--task", default="")
    s.add_argument("--state", required=True)
    s.add_argument("--files", default="")
    s.add_argument("--branch", default="")
    s.add_argument("--commit", default="")
    s.set_defaults(func=cmd_set)

    sh = sub.add_parser("show")
    sh.add_argument("--tool", default="")
    sh.add_argument("--json", action="store_true")
    sh.set_defaults(func=cmd_show)

    a = ap.parse_args()
    return a.func(a) or 0


if __name__ == "__main__":
    sys.exit(main())
