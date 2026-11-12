# -*- coding: utf-8 -*-
"""Per-file lease locks for the shared working tree.

The lock is an atomic-create JSON file; it is cooperative, not an OS lock.
Always pair it with guard.py: lock prevents simultaneous writes, guard detects
"someone changed the file after I read it".

Examples:
  python coordination/lock.py acquire viewer.py --owner trae --task T-001 --ttl 1800
  python coordination/lock.py heartbeat viewer.py --owner trae
  python coordination/lock.py release viewer.py --owner trae
  python coordination/lock.py list
"""
import argparse
import os
import sys

from _util import (
    COORD, atomic_write_json, ensure_dir, fail, iso, key_hash, now, parse_iso,
    print_table, read_json, rel_key,
)

LOCKS = os.path.join(COORD, "locks")
STALE = os.path.join(LOCKS, "_stale")


def _lock_path(path):
    rel = rel_key(path)
    return os.path.join(LOCKS, key_hash(rel) + ".json"), rel


def _load(path):
    return read_json(path)


def _expired(rec):
    exp = parse_iso(rec.get("expires_at"))
    return exp is not None and exp <= now()


def _save(path, rec):
    atomic_write_json(path, rec)


def _stale_move(path):
    ensure_dir(STALE)
    dest = os.path.join(STALE, os.path.basename(path) + "." + str(int(now().timestamp())))
    try:
        os.replace(path, dest)
        return dest
    except OSError:
        return None


def cmd_acquire(a):
    path, rel = _lock_path(a.path)
    ensure_dir(LOCKS)
    for _ in range(3):
        rec = _load(path)
        if rec:
            if _expired(rec):
                moved = _stale_move(path)
                print("stale lock moved: %s" % moved)
                continue
            if rec.get("owner") == a.owner:
                rec["heartbeat_at"] = iso()
                rec["expires_at"] = _expiry(a.ttl)
                if a.task:
                    rec["task"] = a.task
                _save(path, rec)
                print("renewed %s by %s" % (rel, a.owner))
                return 0
            fail(
                "locked by %s (task=%s) until %s"
                % (rec.get("owner"), rec.get("task"), rec.get("expires_at")),
                3,
            )
        rec = {
            "path": rel,
            "owner": a.owner,
            "task": a.task or "",
            "pid": os.getpid(),
            "acquired_at": iso(),
            "heartbeat_at": iso(),
            "expires_at": _expiry(a.ttl),
        }
        try:
            from _util import create_json_exclusive
            if create_json_exclusive(path, rec):
                print("acquired %s by %s (ttl=%ss)" % (rel, a.owner, a.ttl))
                return 0
        except OSError as exc:
            fail("lock create failed: %s" % exc, 1)
    fail("could not acquire lock for %s" % rel, 3)


def _expiry(ttl):
    import datetime
    return (now() + datetime.timedelta(seconds=int(ttl))).isoformat(timespec="seconds")


def cmd_heartbeat(a):
    path, rel = _lock_path(a.path)
    rec = _load(path)
    if not rec:
        fail("no lock: %s" % rel, 2)
    if rec.get("owner") != a.owner:
        fail("owner mismatch: locked by %s" % rec.get("owner"), 3)
    rec["heartbeat_at"] = iso()
    rec["expires_at"] = _expiry(a.ttl)
    _save(path, rec)
    print("heartbeat %s by %s" % (rel, a.owner))


def cmd_release(a):
    path, rel = _lock_path(a.path)
    rec = _load(path)
    if not rec:
        print("no lock: %s" % rel)
        return 0
    if rec.get("owner") != a.owner:
        fail("owner mismatch: locked by %s" % rec.get("owner"), 3)
    os.remove(path)
    print("released %s by %s" % (rel, a.owner))


def cmd_list(a):
    rows = []
    if os.path.isdir(LOCKS):
        for name in sorted(os.listdir(LOCKS)):
            if not name.endswith(".json"):
                continue
            rec = _load(os.path.join(LOCKS, name)) or {}
            rows.append([
                rec.get("path", name), rec.get("owner", "-"), rec.get("task", "-"),
                rec.get("expires_at", "-"), "STALE" if _expired(rec) else "ok",
            ])
    if not rows:
        print("no locks")
        return
    print_table(rows, ["PATH", "OWNER", "TASK", "EXPIRES", "STATE"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ac = sub.add_parser("acquire")
    ac.add_argument("path")
    ac.add_argument("--owner", required=True)
    ac.add_argument("--task", default="")
    ac.add_argument("--ttl", type=int, default=1800)
    ac.set_defaults(func=cmd_acquire)

    hb = sub.add_parser("heartbeat")
    hb.add_argument("path")
    hb.add_argument("--owner", required=True)
    hb.add_argument("--ttl", type=int, default=1800)
    hb.set_defaults(func=cmd_heartbeat)

    rl = sub.add_parser("release")
    rl.add_argument("path")
    rl.add_argument("--owner", required=True)
    rl.set_defaults(func=cmd_release)

    ls = sub.add_parser("list")
    ls.set_defaults(func=cmd_list)

    a = ap.parse_args()
    return a.func(a) or 0


if __name__ == "__main__":
    sys.exit(main())
