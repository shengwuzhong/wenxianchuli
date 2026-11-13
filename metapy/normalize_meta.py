# -*- coding: utf-8 -*-
r"""日文 metadata 规范化 sidecar。

不修改 metadata.json；在 <out>/<doc>/metadata_normalized.json 生成：
  - title / title_en / journal / journal_en / year / volume / issue / pages
  - abstract / abstract_en
  - authors / affiliations
  - keywords
  - body
  - references（逐条 title / authors_raw / source / container_title / publisher / doi）
每个字段保留 raw + normalized + 段级映射；原文不动。

用法:
  python -m metapy.normalize_meta <doc>... --out out --glossary <terms.json>
  python -m metapy.normalize_meta --selfcheck
"""
import argparse
import datetime
import io
import json
import os
import sys

from .normalize import normalize_text

SCALAR = ["title", "title_en", "journal", "journal_en", "year", "volume",
          "issue", "pages", "abstract", "abstract_en"]
LIST_TEXT = ["keywords"]
REF_FIELDS = ["title", "authors_raw", "source", "container_title", "publisher", "doi"]


def _glossary_terms(path):
    if not path:
        return []
    with io.open(path, encoding="utf-8-sig") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        return [str(x) for x in obj if x]
    if isinstance(obj, dict):
        return [str(k) for k in obj.keys() if k]
    return []


def _norm(text, glossary):
    r = normalize_text(text, glossary)
    return {"raw": r["raw"], "normalized": r["normalized"],
            "map": r["map"]}


def _norm_scalar(obj, glossary):
    if not isinstance(obj, dict):
        return None
    v = obj.get("value")
    if v is None:
        return None
    return _norm(v, glossary)


def _norm_authors(items, glossary):
    out = []
    for a in items or []:
        name = a.get("name") if isinstance(a, dict) else a
        if not name:
            continue
        d = _norm(name, glossary)
        if isinstance(a, dict):
            d["raw_obj"] = {k: a.get(k) for k in ("sup", "roman", "affil", "role") if k in a}
        out.append(d)
    return out


def _norm_refs(refs, glossary):
    out = []
    for i, r in enumerate(refs or []):
        fields = {}
        for k in REF_FIELDS:
            v = r.get(k)
            if v:
                fields[k] = _norm(v, glossary)
        out.append({"index": i, "num": r.get("num"), "page": r.get("page"),
                    "uid": r.get("uid"), "fields": fields})
    return out


def normalize_meta(meta, glossary=()):
    """metadata dict -> sidecar dict（纯函数，便于测试）。"""
    fields = {}
    for k in SCALAR:
        n = _norm_scalar(meta.get(k), glossary)
        if n:
            fields[k] = n
    fields["authors"] = _norm_authors(meta.get("authors"), glossary)
    fields["affiliations"] = _norm_authors(meta.get("affiliations"), glossary)
    fields["keywords"] = [_norm(x, glossary) for x in (meta.get("keywords") or []) if x]
    body = meta.get("body")
    if body:
        fields["body"] = _norm(body, glossary)
    return {
        "doc": meta.get("doc"),
        "source": "metadata.json",
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "field_order": SCALAR + ["authors", "affiliations", "keywords", "body"],
        "fields": fields,
        "references": _norm_refs(meta.get("references"), glossary),
    }


def normalize_doc(doc, out_root, glossary=()):
    dd = os.path.join(out_root, doc)
    fp = os.path.join(dd, "metadata.json")
    if not os.path.exists(fp):
        print("skip %s: no metadata.json" % doc)
        return None
    with io.open(fp, encoding="utf-8-sig") as f:
        meta = json.load(f)
    side = normalize_meta(meta, glossary)
    dst = os.path.join(dd, "metadata_normalized.json")
    with io.open(dst, "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=1)
    print("== normalize %s == title=%s authors=%d refs=%d -> %s" % (
        doc, bool(side["fields"].get("title")), len(side["fields"]["authors"]),
        len(side["references"]), os.path.basename(dst)))
    return dst


def _selftest():
    meta = {
        "doc": "d", "title": {"value": "ＡＢＣ 舊"}, "abstract": {"value": "行なう"},
        "authors": [{"name": "山田 太郎"}], "affiliations": ["東京大学"],
        "keywords": ["ＡＢＣ"], "body": "DOI:10.1234/AbC_Def",
        "references": [{"num": 1, "title": "舊題", "authors_raw": "山田，太郎",
                        "source": "10.1234/AbC_Def"}],
    }
    s = normalize_meta(meta, ["東京大学"])
    assert s["fields"]["title"]["normalized"] == "ABC 旧"
    assert s["fields"]["abstract"]["normalized"] == "行う"
    assert s["fields"]["authors"][0]["normalized"] == "山田 太郎"
    assert s["fields"]["keywords"][0]["normalized"] == "ABC"
    assert "10.1234/AbC_Def" in s["fields"]["body"]["normalized"]
    assert s["references"][0]["fields"]["title"]["normalized"] == "旧題"
    assert s["references"][0]["fields"]["source"]["normalized"] == "10.1234/AbC_Def"
    assert all("raw" in x and "normalized" in x for x in s["fields"]["authors"])
    print("normalize_meta selftest: PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("docs", nargs="*")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out"))
    ap.add_argument("--glossary", default=None)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args(argv)
    if a.selfcheck:
        return _selftest()
    if not a.docs:
        ap.error("need <doc>...")
    gl = _glossary_terms(a.glossary)
    for doc in a.docs:
        normalize_doc(doc, a.out, gl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
