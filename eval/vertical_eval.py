# -*- coding: utf-8 -*-
"""10 篇竖排论文的字段评测。

用法:
  python eval/vertical_eval.py --after out --before out_llm_trial/vertical_ab/before_009b5bc
  python eval/vertical_eval.py --selfcheck
"""
import argparse
import difflib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "eval", "vertical_gold_10.json")
sys.path.insert(0, ROOT)
from metapy.ja_names import name_key  # noqa: E402


def _val(meta, key):
    x = meta.get(key)
    return x.get("value") if isinstance(x, dict) else x


def _norm_title(s):
    s = re.sub(r"[\s\u3000]+", "", str(s or ""))
    s = s.replace("—", "—").replace("―", "—").replace("-", "—")
    return s


def _doc_metrics(gold, meta):
    t = str(_val(meta, "title") or "")
    g = str(gold.get("title") or "")
    tn, gn = _norm_title(t), _norm_title(g)
    ratio = difflib.SequenceMatcher(None, tn, gn).ratio() if gn else 0.0
    exact = bool(gn) and tn == gn
    expected = {name_key(a) for a in (gold.get("authors") or []) if a}
    got = {name_key(a.get("name")) for a in (meta.get("authors") or [])
           if isinstance(a, dict) and a.get("name")}
    tp = len(expected & got)
    prec = tp / len(got) if got else (1.0 if not expected else 0.0)
    rec = tp / len(expected) if expected else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    gold_refs = [str(x.get("title") or "") for x in (gold.get("references") or []) if x.get("title")]
    got_refs = [str(x.get("title") or "") for x in (meta.get("references") or []) if x.get("title")]
    rg = {_norm_title(x) for x in gold_refs}
    rt = {_norm_title(x) for x in got_refs}
    rtp = len(rg & rt)
    ref_prec = rtp / len(rt) if rt else (1.0 if not rg else 0.0)
    ref_rec = rtp / len(rg) if rg else 1.0
    ref_ok = (not rg) or (rg <= rt)
    abstract_expected = bool(gold.get("abstract_expected", False))
    refs_expected = bool(gold.get("refs_expected", False))
    cspan_expected = bool(gold.get("cspan_expected", False))
    applicable_ok = bool(exact and ((not expected) or (expected <= got))
                         and ((not abstract_expected) or len(str(_val(meta, "abstract") or "")) > 0)
                         and ((not refs_expected) or ref_ok)
                         and ((not cspan_expected) or len(meta.get("citation_spans") or []) > 0))
    return {
        "title": t, "title_norm": tn, "gold_title": g,
        "title_exact": exact, "title_ratio": round(ratio, 3),
        "authors": sorted(got), "gold_authors": sorted(expected),
        "author_precision": round(prec, 3),
        "author_recall": round(rec, 3),
        "author_f1": round(f1, 3),
        "authors_ok": (not expected) or (expected <= got),
        "abstract_len": len(str(_val(meta, "abstract") or "")),
        "refs": len(meta.get("references") or []),
        "refs_f1": round(2 * ref_prec * ref_rec / (ref_prec + ref_rec), 3) if (ref_prec + ref_rec) else 0.0,
        "refs_ok": ref_ok,
        "cspan": len(meta.get("citation_spans") or []),
        "keywords": len(meta.get("keywords") or []),
        "footnotes": len(meta.get("footnote_candidates") or []),
        "applicable_ok": applicable_ok,
    }


def evaluate(gold_fp, after_root, before_root=None):
    gold = json.load(io.open(gold_fp, encoding="utf-8"))
    rows = []
    for g in gold.get("docs") or []:
        p = os.path.join(after_root, g["doc"], "metadata.json")
        if not os.path.exists(p):
            rows.append({"doc": g["doc"], "missing": True})
            continue
        meta = json.load(io.open(p, encoding="utf-8-sig"))
        r = _doc_metrics(g, meta)
        r["doc"] = g["doc"]
        if before_root:
            bp = os.path.join(before_root, g["doc"], "metadata.json")
            if os.path.exists(bp):
                b = json.load(io.open(bp, encoding="utf-8-sig"))
                rb = _doc_metrics(g, b)
                r["before_title_exact"] = rb["title_exact"]
                r["before_title_ratio"] = rb["title_ratio"]
                r["before_authors_ok"] = rb["authors_ok"]
        rows.append(r)
    total = len(rows)
    expected_author_docs = sum(1 for g in gold.get("docs") or [] if g.get("authors"))
    author_expected_ok = sum(1 for r in rows if r.get("gold_authors") and r.get("authors_ok"))
    author_na = sum(1 for r in rows if not r.get("gold_authors"))
    summary = {
        "docs": total,
        "title_exact": sum(1 for r in rows if r.get("title_exact")),
        "title_acceptable": sum(1 for r in rows if r.get("title_ratio", 0) >= 0.8),
        "title_avg_ratio": round(sum(r.get("title_ratio", 0) for r in rows) / total, 3) if total else 0,
        "author_docs_ok": author_expected_ok,
        "author_docs_expected": expected_author_docs,
        "author_not_applicable": author_na,
        "author_f1_avg": round(sum(r.get("author_f1", 0) for r in rows if r.get("gold_authors")) /
                               max(1, expected_author_docs), 3),
        "abstract_docs": sum(1 for r in rows if r.get("abstract_len", 0) > 0),
        "refs_docs": sum(1 for r in rows if r.get("refs", 0) > 0),
        "cspan_docs": sum(1 for r in rows if r.get("cspan", 0) > 0),
        "keywords_docs": sum(1 for r in rows if r.get("keywords", 0) > 0),
        "footnote_docs": sum(1 for r in rows if r.get("footnotes", 0) > 0),
        "refs_f1_avg": round(sum(r.get("refs_f1", 0) for r in rows if r.get("refs", 0) > 0) /
                             max(1, sum(1 for r in rows if r.get("refs", 0) > 0)), 3),
        "applicable_core_ok": sum(1 for r in rows if r.get("applicable_ok")),
        "strict_core_ok": 0,
    }
    summary["strict_core_ok"] = sum(
        1 for r in rows
        if r.get("title_exact") and r.get("authors_ok")
        and r.get("abstract_len", 0) > 0
        and r.get("refs", 0) > 0 and r.get("cspan", 0) > 0)
    summary["field_coverage"] = sum((
        summary["title_acceptable"],
        summary["author_docs_ok"],
        summary["abstract_docs"], summary["refs_docs"],
        summary["cspan_docs"], summary["keywords_docs"]))
    summary["field_coverage_max"] = total * 6
    if before_root:
        summary["before_title_exact"] = sum(1 for r in rows if r.get("before_title_exact"))
        summary["before_authors_ok"] = sum(
            1 for r in rows if r.get("before_authors_ok") and r.get("gold_authors"))
    return {"summary": summary, "rows": rows}


def to_md(res):
    s = res["summary"]
    lines = [
        "# 竖排 10 篇评测",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        "| 文档数 | %d |" % s["docs"],
        "| 题名 exact | %d/%d |" % (s["title_exact"], s["docs"]),
        "| 题名可接受(r>=0.8) | %d/%d |" % (s["title_acceptable"], s["docs"]),
        "| 题名平均相似度 | %.3f |" % s["title_avg_ratio"],
        "| 作者文档正确 | %d/%d |" % (s["author_docs_ok"], s["author_docs_expected"]),
        "| 作者 F1 平均 | %.3f |" % s["author_f1_avg"],
        "| 有摘要 | %d/%d |" % (s["abstract_docs"], s["docs"]),
        "| 有 refs | %d/%d |" % (s["refs_docs"], s["docs"]),
        "| refs F1 平均(有 refs 文档) | %.3f |" % s["refs_f1_avg"],
        "| 有 cspan | %d/%d |" % (s["cspan_docs"], s["docs"]),
        "| 有关键词 | %d/%d |" % (s["keywords_docs"], s["docs"]),
        "| 有脚注候选 | %d/%d |" % (s["footnote_docs"], s["docs"]),
        "| 六字段覆盖 | %d/%d |" % (s["field_coverage"], s["field_coverage_max"]),
        "| 适用字段核心通过 | %d/%d |" % (s["applicable_core_ok"], s["docs"]),
        "| 严格核心完整 | %d/%d |" % (s["strict_core_ok"], s["docs"]),
        "",
        "## 逐篇",
        "",
        "| 文档 | title exact | ratio | authors_ok | refs | cspan | kw | notes | applicable |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in res["rows"]:
        lines.append("| %s | %s | %.3f | %s | %d | %d | %d | %d | %s |" % (
            r.get("doc"), "Y" if r.get("title_exact") else "N",
            r.get("title_ratio", 0), "Y" if r.get("authors_ok") else "N",
            r.get("refs", 0), r.get("cspan", 0), r.get("keywords", 0),
            r.get("footnotes", 0), "Y" if r.get("applicable_ok") else "N"))
    return "\n".join(lines) + "\n"


def _selftest():
    g = {"title": "元の韻の構造に就いて", "authors": ["大島 正健"]}
    m = {"title": {"value": "元の韻の構造に就いて"},
         "authors": [{"name": "大島正健"}], "abstract": {"value": ""},
         "references": [], "citation_spans": [], "keywords": ["x"],
         "footnote_candidates": []}
    r = _doc_metrics(g, m)
    assert r["title_exact"] and r["authors_ok"], r
    assert r["author_f1"] == 1.0, r
    print("vertical_eval selftest: PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--after", default=os.path.join(ROOT, "out"))
    ap.add_argument("--before", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selftest()
    res = evaluate(a.gold, a.after, a.before)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    md = to_md(res)
    if a.md:
        io.open(a.md, "w", encoding="utf-8").write(md)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
