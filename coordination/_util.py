# -*- coding: utf-8 -*-
"""Shared helpers for the three-agent coordination scripts.

Layout:
  coordination/
    tasks/    one JSON per task (tracked)
    reviews/  one JSON per review (tracked)
    merges/   one JSON per merge (tracked)
    patches/  optional patch handoffs (tracked)
    locks/    runtime lock files (ignored)
    guards/   runtime hash guards (ignored)
    board/    per-tool status boards (ignored)

Environment overrides (useful for smoke tests):
  COORD_ROOT  coordination directory (default: this directory)
  REPO_ROOT   repository root (default: parent of coordination)
  GIT_EXE     full path to git.exe (default: bundled PortableGit on this machine)
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COORD = os.path.abspath(os.environ.get("COORD_ROOT") or HERE)
REPO = os.path.abspath(os.environ.get("REPO_ROOT") or os.path.dirname(COORD))

DEFAULT_GIT = r"D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe"


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(dt=None):
    return (dt or now()).isoformat(timespec="seconds")


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def atomic_write_json(path, obj):
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    fd, tmp = tempfile.mkstemp(
        dir=os.path.dirname(os.path.abspath(path)), prefix=".tmp-", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def create_json_exclusive(path, obj):
    """Create a JSON file atomically; return False if it already exists."""
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return True


def resolve_path(path):
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(REPO, path)
    return os.path.abspath(path)


def rel_key(path):
    """Repository-relative key with forward slashes; absolute if outside repo."""
    absolute = resolve_path(path)
    try:
        rel = os.path.relpath(absolute, REPO)
    except ValueError:
        return absolute.replace("\\", "/")
    if rel == ".." or rel.startswith(".." + os.sep):
        return absolute.replace("\\", "/")
    return rel.replace("\\", "/")


def key_hash(rel):
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git():
    explicit = os.environ.get("GIT_EXE")
    if explicit and os.path.exists(explicit):
        return explicit
    if os.path.exists(DEFAULT_GIT):
        return DEFAULT_GIT
    found = shutil.which("git")
    if found:
        return found
    return "git"


def run_git(args, check=False):
    cmd = [get_git()] + list(args)
    proc = subprocess.run(
        cmd, cwd=REPO, text=True, encoding="utf-8",
        errors="replace", capture_output=True
    )
    if check and proc.returncode != 0:
        raise RuntimeError("git failed: %s\n%s" % (" ".join(cmd), proc.stderr))
    return proc


def fail(message, code=1):
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(code)


def print_table(rows, headers):
    rows = [list(map(str, r)) for r in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
