# -*- coding: utf-8 -*-
"""Compare-and-swap guard: record a file hash before editing, check before commit.

Examples:
  python coordination/guard.py record viewer.py --owner trae
  python coordination/guard.py check viewer.py
  python coordination/guard.py show viewer.py
"""
import argparse
import os
import sys

from _util import (
    COORD, atomic_write_json, fail, iso, key_hash, print_table, read_json,
    rel_key, resolve_path, sha256_file,
)

GUARDS = os.path.join(COORD, "guards")


def _guard_path(path):
    rel = rel_key(path)
    return os.path.join(GUARDS, key_hash(rel) + ".json"), rel


def cmd_record(a):
    absolute = resolve_path(a.path)
    if not os.path.exists(absolute):
        fail("file not found: %s" % absolute, 2)
    rec = {
        "path": rel_key(a.path),
        "sha256": sha256_file(absolute),
        "owner": a.owner,
        "recorded_at": iso(),
    }
    atomic_write_json(_guard_path(a.path)[0], rec)
    print("recorded %s %s" % (rec["path"], rec["sha256"][:16]))


def cmd_check(a):
    path, rel = _guard_path(a.path)
    rec = read_json(path)
    if not rec:
        fail("no guard record for %s (run guard.py record first)" % rel, 5)
    absolute = resolve_path(a.path)
    if not os.path.exists(absolute):
        fail("file not found: %s" % absolute, 2)
    current = sha256_file(absolute)
    if current != rec.get("sha256"):
        fail(
            "hash mismatch for %s\n  recorded: %s (%s)\n  current : %s\n"
            "STOP: another tool changed this file after you read it."
            % (rel, rec.get("sha256"), rec.get("owner"), current),
            4,
        )
    print("guard ok %s (owner=%s)" % (rel, rec.get("owner")))


def cmd_show(a):
    rec = read_json(_guard_path(a.path)[0])
    if not rec:
        fail("no guard record for %s" % a.path, 2)
    import json
    print(json.dumps(rec, ensure_ascii=False, indent=1))


def cmd_list(a):
    rows = []
    if os.path.isdir(GUARDS):
        for name in sorted(os.listdir(GUARDS)):
            if name.endswith(".json"):
                rec = read_json(os.path.join(GUARDS, name)) or {}
                rows.append([rec.get("path", name), rec.get("owner", "-"),
                             rec.get("sha256", "-")[:16], rec.get("recorded_at", "-")])
    if not rows:
        print("no guards")
        return
    print_table(rows, ["PATH", "OWNER", "SHA256", "RECORDED"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record")
    r.add_argument("path")
    r.add_argument("--owner", required=True)
    r.set_defaults(func=cmd_record)

    c = sub.add_parser("check")
    c.add_argument("path")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("show")
    s.add_argument("path")
    s.set_defaults(func=cmd_show)

    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)

    a = ap.parse_args()
    return a.func(a) or 0


if __name__ == "__main__":
    sys.exit(main())
