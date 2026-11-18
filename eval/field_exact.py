# -*- coding: utf-8 -*-
"""逐字段 exact match 评估（只读）。

用法:
  py eval/field_exact.py --gold eval/ja_gold.json --pred out
  py eval/field_exact.py --gold eval/vertical_gold_10.json --pred out

口径:
  - title/journal/year/volume/issue/pages: NFKC + lower + 去空白/标点后完全相等。
  - authors: 规范化后的姓名列表完全相等（顺序敏感）；gold 为空则跳过。
  - gold 没有值的字段不计入分母，不把“未标注”算成失败。
  - abstract / references 不做 exact：摘要用相似度、参考文献用条目匹配，另行报告。
"""
import argparse
import io
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUNCT = re.compile(r"[\s\u3000.,;:!?，。；：！？、·・\-—–‐/\\()\[\]{}<>「」『』（）【】〈〉《》“”\"'’‘]+")
FIELDS = ["title", "authors", "journal", "year", "volume", "issue", "pages"]


def fold(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return PUNCT.sub("", s)


def meta_value(m, key):
    o = m.get(key)
    if isinstance(o, dict):
        return o.get("value")
    return o


def gold_value(g, key):
    if key == "pages":
        return g.get("pages_range", g.get("pages"))
    return g.get(key)


def pred_value(m, key):
    if key == "authors":
        out = []
        for a in (m.get("authors") or []):
            if isinstance(a, dict):
                out.append(a.get("name"))
            else:
                out.append(a)
        return [x for x in out if x]
    return meta_value(m, key)


def norm(key, v):
    if key == "authors":
        return tuple(fold(x) for x in (v or []) if fold(x))
    if key == "pages":
        return fold(v)
    return fold(v)


def is_empty(key, v):
    if key == "authors":
        return not any(fold(x) for x in (v or []))
    return v is None or fold(v) == ""


def eval_doc(g, pred_dir):
    doc = g.get("doc")
    fp = os.path.join(pred_dir, doc, "metadata.json")
    row = {"doc": doc, "exists": os.path.isfile(fp), "fields": {}}
    if not row["exists"]:
        return row
    with io.open(fp, encoding="utf-8-sig") as f:
        m = json.load(f)
    for key in FIELDS:
        gv = gold_value(g, key)
        pv = pred_value(m, key)
        if is_empty(key, gv):
            row["fields"][key] = {"applicable": False, "ok": None, "gold": gv, "pred": pv}
            continue
        ok = norm(key, gv) == norm(key, pv)
        row["fields"][key] = {"applicable": True, "ok": ok, "gold": gv, "pred": pv}
    return row


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " / ".join(str(x) for x in v)
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", default=os.path.join(ROOT, "out"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    args = ap.parse_args()

    with io.open(args.gold, encoding="utf-8-sig") as f:
        gold = json.load(f)
    docs = gold.get("docs") or []
    rows = [eval_doc(g, args.pred) for g in docs]

    totals = {k: {"ok": 0, "n": 0} for k in FIELDS}
    for r in rows:
        for k, v in (r.get("fields") or {}).items():
            if v.get("applicable"):
                totals[k]["n"] += 1
                totals[k]["ok"] += 1 if v.get("ok") else 0

    lines = []
    lines.append("# 字段 exact match 评估")
    lines.append("")
    lines.append("- gold: `%s`" % os.path.relpath(args.gold, ROOT).replace(os.sep, "/"))
    lines.append("- pred: `%s`" % os.path.relpath(os.path.abspath(args.pred), ROOT).replace(os.sep, "/"))
    lines.append("- docs: %d" % len(rows))
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 字段 | exact | 可评 | 准确率 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for k in FIELDS:
        t = totals[k]
        acc = (t["ok"] / t["n"]) if t["n"] else None
        lines.append("| %s | %d | %d | %s |" % (
            k, t["ok"], t["n"], ("%.3f" % acc) if acc is not None else "-"))
    lines.append("")
    lines.append("## 逐篇")
    lines.append("")
    lines.append("| doc | " + " | ".join(FIELDS) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in FIELDS) + " |")
    for r in rows:
        if not r["exists"]:
            lines.append("| %s | %s |" % (r["doc"], "MISSING"))
            continue
        cells = []
        for k in FIELDS:
            v = r["fields"].get(k, {})
            cells.append("OK" if v.get("ok") else ("-" if not v.get("applicable") else "X"))
        lines.append("| %s | %s |" % (r["doc"], " | ".join(cells)))
    lines.append("")

    md = "\n".join(lines) + "\n"
    print(md)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
        with io.open(args.md, "w", encoding="utf-8") as f:
            f.write(md)
    payload = {"gold": args.gold, "pred": args.pred, "totals": totals, "docs": rows}
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with io.open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print("json ->", args.json)


if __name__ == "__main__":
    main()
