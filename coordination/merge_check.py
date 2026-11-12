# -*- coding: utf-8 -*-
"""Pre-merge gate for a task branch.

Checks:
  1. task exists and is in review;
  2. reviews/<task>.json exists with verdict=approve;
  3. working tree is clean;
  4. current branch is not main;
  5. changed files are within allowed_files (if set);
  6. no generated/secret/m3 paths; unify.py only with allow_frozen;
  7. baseline tests pass (unless --no-tests).

Examples:
  python coordination/merge_check.py T-20261112-001
  python coordination/merge_check.py T-20261112-001 --no-tests
"""
import argparse
import os
import subprocess
import sys

from _util import (
    COORD, REPO, fail, get_git, read_json, run_git,
)

TASKS = os.path.join(COORD, "tasks")
REVIEWS = os.path.join(COORD, "reviews")

GLOBAL_FORBIDDEN = [
    "metapy/m3.py",
    "out/", "uploads/", "inbox/", "out_llm_trial/",
    "channels.local.json", "_server.lock",
    ".workbuddy/", ".worktrees/", "__pycache__/",
]
UNIFY = "unify.py"

# Coordination metadata may be untracked while a task is in flight; it is not
# part of the code diff and must not block the merge gate.
STATUS_IGNORE = (
    "coordination/tasks/",
    "coordination/reviews/",
    "coordination/merges/",
    "coordination/patches/",
)


def _match(path, patterns):
    for p in patterns:
        if p.endswith("/"):
            if path.startswith(p):
                return True
        elif path == p:
            return True
    return False


def _dirty_lines(porcelain):
    dirty = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().replace("\\", "/")
        if path.startswith(STATUS_IGNORE):
            continue
        dirty.append(line)
    return dirty


def _tests():
    cmds = [
        [sys.executable, "-m", "unittest", "-v", "test_pipeline.py"],
        [sys.executable, "-c", "import ner_lite; assert ner_lite.selfcheck() == 0"],
    ]
    for cmd in cmds:
        print("RUN", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=REPO, text=True, encoding="utf-8",
                              errors="replace")
        if proc.returncode != 0:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--base", default="main")
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args()

    task = read_json(os.path.join(TASKS, a.task + ".json"))
    if not task:
        fail("task not found: %s" % a.task, 2)
    if task.get("status") not in ("review", "done"):
        fail("task status is %r; expected review" % task.get("status"), 2)

    review = read_json(os.path.join(REVIEWS, a.task + ".json"))
    if not review:
        fail("review not found: reviews/%s.json" % a.task, 2)
    if review.get("verdict") != "approve":
        fail("review verdict is %r; expected approve" % review.get("verdict"), 2)

    status = run_git(["status", "--porcelain"])
    if status.returncode != 0:
        fail("git status failed: %s" % status.stderr, 3)
    dirty = _dirty_lines(status.stdout)
    if dirty:
        fail("working tree is not clean:\n%s" % "\n".join(dirty), 3)

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if branch in ("main", "master"):
        fail("refusing to merge from %s; use a task branch" % branch, 3)
    print("branch:", branch)

    diff = run_git(["diff", "--name-only", "%s...HEAD" % a.base])
    if diff.returncode != 0:
        fail("git diff failed: %s" % diff.stderr, 3)
    changed = [x for x in diff.stdout.splitlines() if x.strip()]
    if not changed:
        fail("no changed files vs %s" % a.base, 3)

    forbidden = list(GLOBAL_FORBIDDEN) + list(task.get("forbidden") or [])
    allow_frozen = set(task.get("allow_frozen") or [])
    bad = []
    for path in changed:
        if _match(path, forbidden):
            bad.append("%s (forbidden)" % path)
        if path == UNIFY and UNIFY not in allow_frozen:
            bad.append("%s (frozen; add to allow_frozen after review)" % path)
    if bad:
        fail("forbidden changes:\n  " + "\n  ".join(bad), 4)

    allowed = list(task.get("allowed_files") or [])
    if allowed:
        outside = [p for p in changed if not _match(p, allowed)]
        if outside:
            fail("changes outside allowed_files:\n  " + "\n  ".join(outside), 4)

    print("changed files (%d):" % len(changed))
    for p in changed:
        print("  ", p)

    if not a.no_tests:
        if not _tests():
            fail("baseline tests failed", 5)

    print("MERGE CHECK OK: %s (%s -> %s)" % (a.task, branch, a.base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
