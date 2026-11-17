# -*- coding: utf-8 -*-
"""日文语料级检索索引（后端，无 UI）。

构建 out/*/metadata.json + unified 正文的规范化索引；查询时做 NFKC/旧字体/
送假名/全半角归一，并可用 glossary 固定术语写法。

用法:
  python -m metapy.ja_search build --out out --index out_llm_trial/ja_index.json
  python -m metapy.ja_search search --index out_llm_trial/ja_index.json "アプタマー"
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

if __package__:
    from .normalize import normalize_text
    from .ja_tokenize import content_words
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from metapy.normalize import normalize_text
    from metapy.ja_tokenize import content_words


def _val(meta, key):
    x = meta.get(key)
    return x.get("value") if isinstance(x, dict) else x


def _read_glossary(fp):
    if not fp:
        return []
    try:
        obj = json.load(io.open(fp, encoding="utf-8-sig"))
        if isinstance(obj, dict):
            return [str(k) for k in obj]
        return [str(x) for x in obj if x]
    except Exception:
        return []


def _doc_text(doc, ddir):
    parts = []
    mfp = os.path.join(ddir, "metadata.json")
    if os.path.exists(mfp):
        try:
            meta = json.load(io.open(mfp, encoding="utf-8-sig"))
        except Exception:
            meta = {}
        for k in ("title", "abstract", "keywords", "authors"):
            v = _val(meta, k)
            if isinstance(v, list):
                parts.extend(str(x.get("name") if isinstance(x, dict) else x) for x in v)
            elif v:
                parts.append(str(v))
        for r in meta.get("references") or []:
            parts.append(str(r.get("title") or ""))
            parts.append(str(r.get("authors_raw") or ""))
    udir = os.path.join(ddir, "unified")
    if os.path.isdir(udir):
        for f in sorted(os.listdir(udir)):
            if not re.match(r"page_\d+\.json$", f):
                continue
            try:
                page = json.load(io.open(os.path.join(udir, f), encoding="utf-8-sig"))
            except Exception:
                continue
            for u in page.get("unified") or []:
                parts.append(str(u.get("main_text") or ""))
    return "\n".join(p for p in parts if p)


def build_index(out_root, index_fp, glossary=()):
    docs = []
    for doc in sorted(os.listdir(out_root)):
        ddir = os.path.join(out_root, doc)
        if not os.path.isdir(ddir) or doc.startswith("_"):
            continue
        if not os.path.exists(os.path.join(ddir, "metadata.json")):
            continue
        raw = _doc_text(doc, ddir)
        if not raw:
            continue
        try:
            norm = normalize_text(raw, list(glossary))["normalized"]
        except Exception:
            norm = raw
        docs.append({"doc": doc, "text": raw, "normalized": norm,
                     "tokens": content_words(raw, limit=400)})
    payload = {"schema_version": 1,
               "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "docs": docs}
    os.makedirs(os.path.dirname(os.path.abspath(index_fp)), exist_ok=True)
    io.open(index_fp, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, indent=1))
    return {"docs": len(docs), "index": index_fp}


def _query_tokens(q):
    return [w["word"] for w in content_words(q, limit=20)]


def search(index_fp, query, limit=10, glossary=()):
    payload = json.load(io.open(index_fp, encoding="utf-8-sig"))
    q = normalize_text(query, list(glossary))["normalized"]
    toks = _query_tokens(query)
    rows = []
    for d in payload.get("docs") or []:
        text = d.get("normalized") or ""
        score = 0.0
        if q and q in text:
            score += 5.0
        for t in toks:
            if not t:
                continue
            if t in (d.get("doc") or ""):
                score += 1.0
            score += min(4, text.count(t)) * 1.0
        if score <= 0:
            continue
        # 标题/文件名命中加权
        title = str(d.get("doc") or "")
        for t in toks:
            if t in title:
                score += 2.0
        rows.append({"doc": d.get("doc"), "score": round(score, 2),
                     "snippet": _snippet(d.get("text") or "", toks)})
    rows.sort(key=lambda x: (-x["score"], x["doc"]))
    return rows[:limit]


def _snippet(text, toks, width=120):
    for t in toks:
        if not t:
            continue
        i = text.find(t)
        if i >= 0:
            a = max(0, i - width // 3)
            return text[a:a + width].replace("\n", " ")
    return text[:width].replace("\n", " ")


def _selftest():
    import shutil
    import tempfile
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "d1")
        os.makedirs(d)
        meta = {"title": {"value": "アプタマー技術"},
                "abstract": {"value": "血液中の蛋白質を解析する。"},
                "authors": [{"name": "山田 太郎"}],
                "keywords": ["アプタマー"]}
        io.open(os.path.join(d, "metadata.json"), "w", encoding="utf-8").write(
            json.dumps(meta, ensure_ascii=False))
        fp = os.path.join(root, "index.json")
        r = build_index(root, fp)
        assert r["docs"] == 1, r
        hits = search(fp, "アプタマー")
        assert hits and hits[0]["doc"] == "d1", hits
        print("ja_search selftest: PASS")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out"))
    b.add_argument("--index", default=os.path.join("out_llm_trial", "ja_index.json"))
    b.add_argument("--glossary", default=None)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--index", default=os.path.join("out_llm_trial", "ja_index.json"))
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--glossary", default=None)
    a = ap.parse_args()
    if a.cmd == "build":
        print(json.dumps(build_index(a.out, a.index, _read_glossary(a.glossary)),
                         ensure_ascii=False, indent=1))
    else:
        for r in search(a.index, a.query, a.limit, _read_glossary(a.glossary)):
            print("%-6.2f %s\n  %s" % (r["score"], r["doc"], r["snippet"]))
    return 0


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
