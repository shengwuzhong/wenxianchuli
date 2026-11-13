# -*- coding: utf-8 -*-
r"""日文版面金标准比对（只读）。

用法:
  py eval/layout_eval.py --pred out_llm_trial/wb_layout_v2_review
  py eval/layout_eval.py --pred out --json eval/reports/layout_v2.json --md eval/reports/layout_v2.md

口径:
  - gold: eval/layout_gold_99.csv（Trae truth99，99 页；42_103 p13 = ambiguous）
  - pred: <pred>/<doc>/unified/_layout_ja.json 的 stats.per_page[*].ncols
  - recall = 真 double 中判 double 的比例；false_positives = 真 single 判 double；
    ambiguous 不参与 recall/FP，只单列 pred 结果。
"""
import argparse, csv, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "eval", "layout_gold_99.csv")

def load_gold(fp):
    with io.open(fp, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_pred(pred_root):
    out = {}
    for doc in sorted(os.listdir(pred_root)):
        fp = os.path.join(pred_root, doc, "unified", "_layout_ja.json")
        if not os.path.exists(fp):
            continue
        with io.open(fp, encoding="utf-8") as f:
            stats = json.load(f).get("stats") or {}
        for p, v in (stats.get("per_page") or {}).items():
            out[(doc, int(p))] = "double" if v.get("ncols") == 2 else "single"
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--min-recall", type=float, default=None,
                    help="低于该 recall 时退出码为 1")
    ap.add_argument("--max-fp", type=int, default=None,
                    help="假阳性超过该值时退出码为 1")
    a = ap.parse_args()
    gold = load_gold(a.gold)
    pred = load_pred(a.pred)

    rows, miss, fp, amb = [], [], [], []
    gd = gs = ga = 0
    pd = ps = 0
    for g in gold:
        doc, page = g["doc"], int(g["page"])
        actual = g["actual"]
        p = pred.get((doc, page))
        if actual == "double":
            gd += 1
        elif actual == "single":
            gs += 1
        else:
            ga += 1
        if p == "double":
            pd += 1
        elif p == "single":
            ps += 1
        ok = (p == actual)
        if actual == "double" and p != "double":
            miss.append((doc, page, p))
        if actual == "single" and p == "double":
            fp.append((doc, page))
        if actual == "ambiguous":
            amb.append((doc, page, p))
        rows.append({"doc": doc, "page": page, "gold": actual, "pred": p,
                     "status": g.get("status"), "ok": ok,
                     "boundary_x": g.get("boundary_x"), "note": g.get("note")})

    recall = (gd - len(miss)) / gd if gd else None
    precision = (pd - len(fp)) / pd if pd else None
    lines = [
        "# Layout 真值比对",
        "",
        "- gold: `%s` (%d 页: double %d / single %d / ambiguous %d)" % (
            os.path.relpath(a.gold, ROOT).replace(os.sep, "/"), len(gold), gd, gs, ga),
        "- pred: `%s` (double %d / single %d)" % (
            os.path.relpath(os.path.abspath(a.pred), ROOT).replace(os.sep, "/"), pd, ps),
        "- recall(double): **%.4f** (%d/%d)" % (recall, gd - len(miss), gd),
        "- false positive(single→double): **%d**" % len(fp),
        "- precision(double): %.4f" % precision if precision is not None else "- precision: -",
        "- 未判: %d 页" % (len(gold) - pd - ps),
        "",
        "## 漏判 double（%d）" % len(miss),
    ]
    for x in miss:
        lines.append("- `%s` p%d：pred=%s" % (x[0], x[1], x[2] or "missing"))
    lines += ["", "## 误判 single→double（%d）" % len(fp)]
    for x in fp:
        lines.append("- `%s` p%d" % x)
    lines += ["", "## ambiguous（%d）" % len(amb)]
    for x in amb:
        lines.append("- `%s` p%d：pred=%s（允许 double/single）" % (x[0], x[1], x[2] or "missing"))
    md = "\n".join(lines) + "\n"
    print(md)
    failed = False
    if a.min_recall is not None and (recall is None or recall < a.min_recall):
        print("FAIL: recall %.4f < %.4f" % (recall or 0.0, a.min_recall))
        failed = True
    if a.max_fp is not None and len(fp) > a.max_fp:
        print("FAIL: false_positives %d > %d" % (len(fp), a.max_fp))
        failed = True
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        io.open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump({"gold": a.gold, "pred": a.pred,
                   "thresholds": {"min_recall": a.min_recall, "max_fp": a.max_fp},
                   "summary": {"pages": len(gold), "gold_double": gd, "gold_single": gs,
                               "gold_ambiguous": ga, "pred_double": pd, "pred_single": ps,
                               "recall": recall, "precision": precision,
                               "false_positives": len(fp), "misses": len(miss)},
                   "misses": miss, "false_positives": fp, "ambiguous": amb,
                   "rows": rows}, io.open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("json ->", a.json)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
