# -*- coding: utf-8 -*-
"""日文学术术语表检查（后端）。

glossary JSON:
  {"推奨表記": ["揺れ1", "揺れ2"]}
  ["用語1", "用語2"]  # 只统计出现次数

用途：在检索/翻译前统一术语写法，输出各文档的术语命中与未统一写法。
"""
import argparse
import io
import json
import os
import re


def load_glossary(fp):
    if not fp:
        return {}
    obj = json.load(io.open(fp, encoding="utf-8-sig"))
    if isinstance(obj, dict):
        return {str(k): [str(x) for x in (v if isinstance(v, list) else [v])]
                for k, v in obj.items()}
    return {str(x): [] for x in (obj or [])}


def _texts(doc_dir):
    out = []
    mfp = os.path.join(doc_dir, "metadata.json")
    if os.path.exists(mfp):
        try:
            meta = json.load(io.open(mfp, encoding="utf-8-sig"))
        except Exception:
            meta = {}
        for k in ("title", "abstract", "keywords"):
            v = meta.get(k)
            if isinstance(v, dict):
                v = v.get("value")
            if isinstance(v, list):
                out.extend(str(x.get("name") if isinstance(x, dict) else x) for x in v)
            elif v:
                out.append(str(v))
    udir = os.path.join(doc_dir, "unified")
    if os.path.isdir(udir):
        for f in sorted(os.listdir(udir)):
            if not re.match(r"page_\d+\.json$", f):
                continue
            try:
                page = json.load(io.open(os.path.join(udir, f), encoding="utf-8-sig"))
            except Exception:
                continue
            for u in page.get("unified") or []:
                out.append(str(u.get("main_text") or ""))
    return out


def scan_text(text, glossary):
    res = []
    for canon, variants in glossary.items():
        hits = len(re.findall(re.escape(canon), text or ""))
        var_hits = {v: len(re.findall(re.escape(v), text or "")) for v in variants}
        var_hits = {k: n for k, n in var_hits.items() if n}
        if hits or var_hits:
            res.append({"term": canon, "canonical": hits, "variants": var_hits})
    return res


def scan(out_root, glossary, doc=None):
    docs = [doc] if doc else sorted(
        d for d in os.listdir(out_root)
        if os.path.isdir(os.path.join(out_root, d)) and os.path.exists(
            os.path.join(out_root, d, "metadata.json")))
    rows = []
    for d in docs:
        text = "\n".join(_texts(os.path.join(out_root, d)))
        hits = scan_text(text, glossary)
        if hits:
            rows.append({"doc": d, "terms": hits})
    return rows


def _selftest():
    g = {"プロテオミクス": ["プロテオーム解析", "プロテオミクス解析"]}
    r = scan_text("プロテオミクスとプロテオーム解析", g)
    assert r and r[0]["term"] == "プロテオミクス" and r[0]["canonical"] == 1, r
    assert r[0]["variants"].get("プロテオーム解析") == 1, r
    print("ja_terms selftest: PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glossary", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--doc", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    rows = scan(a.out, load_glossary(a.glossary), a.doc)
    body = json.dumps({"docs": rows, "count": len(rows)}, ensure_ascii=False, indent=1)
    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(body)
    print(body)
    return 0


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
