# -*- coding: utf-8 -*-
"""Rebuild viewer/index for docs that have metadata but no index.html.

No OCR, no network. Safe to run repeatedly; only calls the viewer/index stages
for docs that already have metadata.json.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import stages  # noqa: E402
import workbench_state as wb  # noqa: E402


def missing(zones):
    out = []
    for z in zones:
        if not os.path.isdir(z.out):
            continue
        for name in sorted(os.listdir(z.out)):
            d = os.path.join(z.out, name)
            if not os.path.isfile(os.path.join(d, "metadata.json")):
                continue
            if not os.path.isfile(os.path.join(d, "index.html")):
                out.append((z, name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", choices=("A", "B"), help="only one zone")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    zones = list(wb.make_zones(ROOT).values())
    if args.zone:
        zones = [z for z in zones if z.zid == args.zone]
    docs = missing(zones)
    if args.limit:
        docs = docs[:args.limit]
    print("待补 index: %d" % len(docs))
    if args.dry_run:
        for z, name in docs:
            print("%s %s" % (z.zid, name))
        return 0

    ok = fail = 0
    for z, name in docs:
        try:
            res = stages.run(name, ["viewer", "index"], out_root=z.out)
            good = bool(res.get("ok"))
        except Exception as exc:  # keep going; report per doc
            print("ERR %s %s: %s" % (z.zid, name, exc))
            good = False
        if good:
            ok += 1
            print("OK  %s %s" % (z.zid, name))
        else:
            fail += 1
            print("ERR %s %s" % (z.zid, name))
    print("完成: ok=%d fail=%d" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
