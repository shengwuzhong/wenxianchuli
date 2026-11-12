# -*- coding: utf-8 -*-
"""Task claim / status helper.

Examples:
  python coordination/claim.py create T-20261112-001 --owner deepseek \
      --title "column-aware reading order" --files merge_out.py,test_pipeline.py
  python coordination/claim.py set-status T-20261112-001 --owner deepseek --status in_progress
  python coordination/claim.py show T-20261112-001
  python coordination/claim.py list
"""
import argparse
import os
import sys

from _util import (
    COORD, atomic_write_json, create_json_exclusive, fail, iso, print_table,
    read_json,
)

TASKS = os.path.join(COORD, "tasks")
STATUSES = ("claimed", "in_progress", "review", "blocked", "done", "abandoned")
DEFAULT_FORBIDDEN = [
    "metapy/m3.py", "out/", "uploads/", "inbox/", "out_llm_trial/",
    "channels.local.json", "_server.lock", ".workbuddy/", "__pycache__/",
]


def _path(task_id):
    if not task_id or "/" in task_id or "\\" in task_id:
        fail("invalid task id: %r" % task_id, 2)
    return os.path.join(TASKS, task_id + ".json")


def cmd_create(a):
    path = _path(a.task_id)
    task = {
        "id": a.task_id,
        "title": a.title,
        "priority": a.priority,
        "owner": a.owner,
        "status": "claimed",
        "depends_on": [x for x in (a.depends_on or "").split(",") if x],
        "allowed_files": [x for x in (a.files or "").split(",") if x],
        "forbidden": list(DEFAULT_FORBIDDEN) + [x for x in (a.forbidden or "").split(",") if x],
        "allow_frozen": [x for x in (a.allow_frozen or "").split(",") if x],
        "branch": a.branch or ("agent/%s/%s" % (a.owner, a.task_id)),
        "base_commit": a.base,
        "acceptance": [x for x in (a.acceptance or "").split(";") if x],
        "handoff_to": a.handoff_to or "",
        "created_at": iso(),
        "updated_at": iso(),
    }
    if not create_json_exclusive(path, task):
        existing = read_json(path, {})
        fail(
            "task already exists: %s (owner=%s status=%s)"
            % (a.task_id, existing.get("owner"), existing.get("status")),
            3,
        )
    print("created %s -> %s" % (a.task_id, path))


def cmd_set_status(a):
    path = _path(a.task_id)
    task = read_json(path)
    if not task:
        fail("task not found: %s" % a.task_id, 2)
    if task.get("owner") != a.owner:
        fail("owner mismatch: %s owned by %s" % (a.task_id, task.get("owner")), 3)
    if a.status not in STATUSES:
        fail("invalid status: %s" % a.status, 2)
    task["status"] = a.status
    task["updated_at"] = iso()
    if a.handoff_to:
        task["handoff_to"] = a.handoff_to
    atomic_write_json(path, task)
    print("updated %s -> %s" % (a.task_id, a.status))


def cmd_show(a):
    task = read_json(_path(a.task_id))
    if not task:
        fail("task not found: %s" % a.task_id, 2)
    import json
    print(json.dumps(task, ensure_ascii=False, indent=1))


def cmd_list(a):
    rows = []
    if os.path.isdir(TASKS):
        for name in sorted(os.listdir(TASKS)):
            if not name.endswith(".json"):
                continue
            t = read_json(os.path.join(TASKS, name), {})
            rows.append([
                t.get("id", name[:-5]), t.get("owner", "-"), t.get("status", "-"),
                t.get("priority", "-"), t.get("updated_at", "-"),
                ",".join(t.get("allowed_files") or [])[:80],
            ])
    if not rows:
        print("no tasks")
        return
    print_table(rows, ["TASK", "OWNER", "STATUS", "PRI", "UPDATED", "FILES"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("task_id")
    c.add_argument("--owner", required=True)
    c.add_argument("--title", required=True)
    c.add_argument("--priority", default="P1")
    c.add_argument("--files", default="", help="comma-separated allowed file prefixes")
    c.add_argument("--forbidden", default="", help="extra forbidden prefixes")
    c.add_argument("--allow-frozen", default="", help="e.g. unify.py")
    c.add_argument("--depends-on", default="")
    c.add_argument("--branch", default="")
    c.add_argument("--base", default="main")
    c.add_argument("--acceptance", default="", help="semicolon-separated acceptance items")
    c.add_argument("--handoff-to", default="")
    c.set_defaults(func=cmd_create)

    s = sub.add_parser("set-status")
    s.add_argument("task_id")
    s.add_argument("--owner", required=True)
    s.add_argument("--status", required=True, choices=STATUSES)
    s.add_argument("--handoff-to", default="")
    s.set_defaults(func=cmd_set_status)

    sh = sub.add_parser("show")
    sh.add_argument("task_id")
    sh.set_defaults(func=cmd_show)

    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)

    a = ap.parse_args()
    return a.func(a) or 0


if __name__ == "__main__":
    sys.exit(main())
