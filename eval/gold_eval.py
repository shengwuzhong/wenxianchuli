# -*- coding: utf-8 -*-
r"""日文金标准比对（只读）。

用法:
  py eval/gold_eval.py                       # 默认比对 out/（10 篇有 metadata）
  py eval/gold_eval.py --pred out_llm_trial/ja_status_1112
  py eval/gold_eval.py --doc 2025_1 --json eval/reports/latest.json --md eval/reports/latest.md

口径:
  - 文本比对先做 NFKC + 小写 + 去空白/标点折叠；摘要用 difflib 相似度 + 长度。
  - 参考文献 recall = 匹配到的 GT 条目 / GT 唯一条目（2025_1 #22 与 #6 重复，按标题去重）。
  - title/author 是硬字段；journal/volume/issue/pages/doi 允许噪声，只报 non-null 命中。
  - 不写 out/；只读 metadata.json。
"""
import argparse, difflib, hashlib, io, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "eval", "ja_gold.json")

PUNCT = re.compile(r"[\s\u3000.,;:!?，。；：！？、·・\-—―‐–_/\\()\[\]{}<>「」『』（）【】〈〉《》“”\"'’‘]+")
KANA = re.compile(r"[\u3040-\u30ff]")
HAN = re.compile(r"[\u4e00-\u9fff]")

def fold(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    s = PUNCT.sub("", s)
    return s

def ratio(a, b):
    a, b = fold(a), fold(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def kana_count(s):
    return len(KANA.findall(s or ""))

def val(m, k):
    o = m.get(k)
    if isinstance(o, dict):
        return o.get("value")
    return o

def gt_refs_unique(refs):
    seen, out = set(), []
    for r in refs or []:
        key = fold(r.get("title"))
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(r)
    return out

def ref_match(gt, pred, used):
    """Return (index, entry, title_ok, author_ok) or (None, None, False, False).

    An entry can be consumed only once.  Title similarity is the primary key;
    author+year is a fallback only when both agree strongly (this avoids
    matching every GT entry to the same wrong pred entry).
    """
    gt_title = fold(gt.get("title"))
    gt_auth = fold(gt.get("authors"))
    best_i, best, best_score = None, None, 0.0
    for i, p in enumerate(pred):
        if i in used:
            continue
        pt = fold(p.get("title"))
        pa = fold(p.get("authors_raw") or p.get("authors"))
        score = 0.0
        if gt_title and pt:
            score = difflib.SequenceMatcher(None, gt_title, pt).ratio()
        if score < 0.82 and gt_auth and pa:
            toks = [t for t in re.split(r"[,，・]", gt.get("authors") or "") if fold(t)]
            hit = sum(1 for t in toks if fold(t) and fold(t) in pa)
            auth_ratio = hit / len(toks) if toks else 0.0
            year_ok = bool(gt.get("year")) and str(gt["year"]) in (str(p.get("year")) + " " + (p.get("raw") or ""))
            if auth_ratio >= 0.8 and year_ok:
                score = 0.50 + 0.2 * auth_ratio
        if score > best_score:
            best_i, best, best_score = i, p, score
    if best is None or best_score < 0.60:
        return None, None, False, False
    title_ok = bool(gt_title) and ratio(gt.get("title"), best.get("title")) >= 0.90
    # author: each GT author token (split on comma / ・) should appear in pred authors string
    toks = [t for t in re.split(r"[,，・]", gt.get("authors") or "") if fold(t)]
    pa = fold(best.get("authors_raw") or best.get("authors"))
    hit = sum(1 for t in toks if fold(t) and fold(t) in pa)
    author_ok = bool(toks) and (hit / len(toks)) >= 0.60
    return best_i, best, title_ok, author_ok

def eval_doc(g, pred_dir):
    doc = g["doc"]
    fp = os.path.join(pred_dir, doc, "metadata.json")
    if not os.path.exists(fp):
        return {"doc": doc, "pred": fp, "exists": False}
    with io.open(fp, encoding="utf-8") as f:
        m = json.load(f)
    out = {"doc": doc, "exists": True, "fields": {}, "refs": {}}
    for k, gk in (("title", "title"), ("title_en", "title_en"),
                  ("journal", "journal"), ("year", "year"),
                  ("volume", "volume"), ("issue", "issue"),
                  ("pages", "pages_range")):
        gv, pv = g.get(gk), val(m, k)
        out["fields"][k] = {
            "gold": gv, "pred": pv,
            "ok": fold(gv) == fold(pv) if (gv is not None or pv is not None) else True,
        }
    # authors
    ga = [a for a in (g.get("authors") or []) if a]
    pa = [a.get("name") if isinstance(a, dict) else a for a in (m.get("authors") or [])]
    hit = 0
    for a in ga:
        if any(fold(a) in fold(p) or fold(p) in fold(a) for p in pa if p):
            hit += 1
    out["fields"]["authors"] = {
        "gold": ga, "pred": pa,
        "recall": hit / len(ga) if ga else None,
        "count_ok": len(ga) == len(pa),
    }
    # abstract
    for key, gkey in (("abstract", "abstract"), ("abstract_en", "abstract_en")):
        gv, pv = g.get(gkey), val(m, key)
        if not gv:
            out["fields"][key] = {"gold_len": 0, "pred_len": len(pv or ""), "skipped": True}
            continue
        out["fields"][key] = {
            "gold_len": len(gv), "pred_len": len(pv or ""),
            "ratio": round(ratio(gv, pv), 4),
            "pred_kana": kana_count(pv),
            "gold_kana": kana_count(gv),
        }
    # refs
    gt = gt_refs_unique(g.get("references") or [])
    pr = m.get("references") or []
    matched, title_ok, author_ok = 0, 0, 0
    missing = []
    used = set()
    for r in gt:
        i, p, t_ok, a_ok = ref_match(r, pr, used)
        if p is not None:
            used.add(i)
            matched += 1
            title_ok += 1 if t_ok else 0
            author_ok += 1 if a_ok else 0
        else:
            missing.append({"num": r.get("num"), "title": r.get("title"), "authors": r.get("authors")})
    out["refs"] = {
        "gold": len(gt), "pred": len(pr),
        "recall": round(matched / len(gt), 4) if gt else None,
        "title_ok": round(title_ok / len(gt), 4) if gt else None,
        "author_ok": round(author_ok / len(gt), 4) if gt else None,
        "matched": matched,
        "missing": missing,
    }
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--pred", default=os.path.join(ROOT, "out"))
    ap.add_argument("--doc", action="append", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    a = ap.parse_args()
    with io.open(a.gold, encoding="utf-8") as f:
        gold = json.load(f)
    docs = gold["docs"]
    if a.doc:
        docs = [d for d in docs if d["doc"] in set(a.doc)]
    results = [eval_doc(d, a.pred) for d in docs]

    # markdown
    lines = []
    lines.append("# 日文金标准比对")
    lines.append("")
    lines.append("- gold: `%s`" % os.path.relpath(a.gold, ROOT).replace(os.sep, "/"))
    lines.append("- pred: `%s`" % os.path.relpath(os.path.abspath(a.pred), ROOT).replace(os.sep, "/"))
    lines.append("- docs: %d" % len(results))
    lines.append("")
    lines.append("| doc | title | authors | journal | year | vol | issue | pages | abstract ratio | abstract_en ratio | refs recall | refs title | refs author |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        if not r.get("exists"):
            lines.append("| %s | MISSING | | | | | | | | | | | |" % r["doc"])
            continue
        f = r["fields"]
        def mark(k):
            return "OK" if f.get(k, {}).get("ok") else "X"
        au = f.get("authors", {})
        ab = f.get("abstract", {})
        ae = f.get("abstract_en", {})
        rf = r.get("refs", {})
        lines.append("| %s | %s | %s/%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["doc"], mark("title"), au.get("recall") if au.get("recall") is not None else "-", len(au.get("pred") or []),
            mark("journal"), mark("year"), mark("volume"), mark("issue"), mark("pages"),
            ("%.3f" % ab["ratio"]) if "ratio" in ab else "-",
            ("%.3f" % ae["ratio"]) if "ratio" in ae else "-",
            ("%.3f" % rf["recall"]) if rf.get("recall") is not None else "-",
            ("%.3f" % rf["title_ok"]) if rf.get("title_ok") is not None else "-",
            ("%.3f" % rf["author_ok"]) if rf.get("author_ok") is not None else "-",
        ))
    lines.append("")
    lines.append("## 参考文献缺口（2025_1 / 40_10569 / 52_230725）")
    lines.append("")
    for r in results:
        if not r.get("exists") or r.get("refs", {}).get("recall") is None:
            continue
        miss = r["refs"]["missing"]
        lines.append("- **%s**: recall %.3f, pred %d / gold %d, missing %d" % (
            r["doc"], r["refs"]["recall"], r["refs"]["pred"], r["refs"]["gold"], len(miss)))
        for x in miss[:8]:
            lines.append("  - #%s %s — %s" % (x.get("num"), (x.get("title") or "")[:60], (x.get("authors") or "")[:40]))
        if len(miss) > 8:
            lines.append("  - ... 其余 %d 条" % (len(miss) - 8))
    md = "\n".join(lines) + "\n"
    print(md)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with io.open(a.md, "w", encoding="utf-8") as f:
            f.write(md)
    payload = {"gold": a.gold, "pred": a.pred, "docs": results}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with io.open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print("json ->", a.json)

if __name__ == "__main__":
    main()
