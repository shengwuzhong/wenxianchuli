# -*- coding: utf-8 -*-
r"""日文 metadata 规范化：主字段 normalized + sidecar。

在 <out>/<doc>/metadata.json 的字段旁增加 normalized 值（raw 原值保留），并生成：
  - metadata_normalized.json
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
from .ja_date import normalize_year

SCALAR = ["title", "title_en", "journal", "journal_en", "year", "volume",
          "issue", "pages", "abstract", "abstract_en"]
LIST_TEXT = ["keywords"]
REF_FIELDS = ["title", "authors_raw", "year", "source", "container_title", "publisher", "doi"]


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


def _norm(text, glossary, kind=None):
    r = normalize_text(text, glossary)
    if kind == "year":
        y = normalize_year(text)
        if y:
            r["normalized"] = y
    return {"raw": r["raw"], "normalized": r["normalized"],
            "map": r["map"]}


def _norm_scalar(obj, glossary, kind=None):
    if not isinstance(obj, dict):
        return None
    v = obj.get("value")
    if v is None:
        return None
    return _norm(str(v), glossary, kind)


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
                fields[k] = _norm(str(v), glossary, kind=("year" if k == "year" else None))
        out.append({"index": i, "num": r.get("num"), "page": r.get("page"),
                    "uid": r.get("uid"), "fields": fields})
    return out


def normalize_meta(meta, glossary=()):
    """metadata dict -> sidecar dict（纯函数，便于测试）。"""
    fields = {}
    for k in SCALAR:
        n = _norm_scalar(meta.get(k), glossary, kind=("year" if k == "year" else None))
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
    # 同时把 normalized 写回主字段；raw 值不移除、不覆盖
    applied = apply_normalized(meta, glossary)
    tmp = fp + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(applied, f, ensure_ascii=False, indent=1)
    os.replace(tmp, fp)
    print("== normalize %s == title=%s authors=%d refs=%d -> %s + metadata.json" % (
        doc, bool(side["fields"].get("title")), len(side["fields"]["authors"]),
        len(side["references"]), os.path.basename(dst)))
    return dst


def apply_normalized(meta, glossary=()):
    """把 normalized 值写进主字段的副本；raw/原有字段保持不变。

    - scalar 字段：obj["normalized"] / obj["normalized_map"]
    - authors：每个作者 dict["normalized"]
    - affiliations/keywords：顶层 *_normalized 列表
    - body：顶层 normalized_body
    - references：每条 ref["normalized"] = {字段: 规范值}
    """
    import copy
    out = copy.deepcopy(meta)
    for k in SCALAR:
        obj = out.get(k)
        if not isinstance(obj, dict) or obj.get("value") is None:
            continue
        n = _norm(str(obj.get("value")), glossary, kind=("year" if k == "year" else None))
        obj["normalized"] = n["normalized"]
        obj["normalized_map"] = n["map"]
    authors = out.get("authors") or []
    for a in authors:
        if isinstance(a, dict) and a.get("name"):
            a["normalized"] = _norm(str(a["name"]), glossary)["normalized"]
    aff = []
    for a in out.get("affiliations") or []:
        name = a.get("name") if isinstance(a, dict) else a
        if name:
            aff.append(_norm(str(name), glossary)["normalized"])
    out["affiliations_normalized"] = aff
    out["keywords_normalized"] = [_norm(str(x), glossary)["normalized"]
                                  for x in (out.get("keywords") or []) if x]
    body = out.get("body")
    if body:
        out["normalized_body"] = _norm(str(body), glossary)["normalized"]
    for r in out.get("references") or []:
        if not isinstance(r, dict):
            continue
        nr = {}
        for k in REF_FIELDS:
            v = r.get(k)
            if v:
                nr[k] = _norm(str(v), glossary, kind=("year" if k == "year" else None))["normalized"]
        r["normalized"] = nr
    return out


def _selftest():
    meta = {
        "doc": "d", "title": {"value": "ＡＢＣ 舊"}, "abstract": {"value": "行なう"},
        "year": {"value": "令和6年"},
        "authors": [{"name": "山田 太郎"}], "affiliations": ["東京大学"],
        "keywords": ["ＡＢＣ"], "body": "DOI:10.1234/AbC_Def",
        "references": [{"num": 1, "title": "舊題", "authors_raw": "山田，太郎",
                        "year": "平成30", "source": "10.1234/AbC_Def"}],
    }
    s = normalize_meta(meta, ["東京大学"])
    assert s["fields"]["title"]["normalized"] == "ABC 旧"
    assert s["fields"]["year"]["normalized"] == "2024"
    assert s["references"][0]["fields"]["year"]["normalized"] == "2018"
    assert s["fields"]["abstract"]["normalized"] == "行う"
    assert s["fields"]["authors"][0]["normalized"] == "山田 太郎"
    assert s["fields"]["keywords"][0]["normalized"] == "ABC"
    assert "10.1234/AbC_Def" in s["fields"]["body"]["normalized"]
    assert s["references"][0]["fields"]["title"]["normalized"] == "旧題"
    assert s["references"][0]["fields"]["source"]["normalized"] == "10.1234/AbC_Def"
    assert all("raw" in x and "normalized" in x for x in s["fields"]["authors"])
    m = apply_normalized(meta, ["東京大学"])
    assert m["title"]["value"] == "ＡＢＣ 舊"
    assert m["title"]["normalized"] == "ABC 旧"
    assert m["year"]["normalized"] == "2024"
    assert m["authors"][0]["name"] == "山田 太郎"
    assert m["authors"][0]["normalized"] == "山田 太郎"
    assert m["keywords_normalized"] == ["ABC"]
    assert m["references"][0]["normalized"]["title"] == "旧題"
    assert m["references"][0]["normalized"]["year"] == "2018"
    assert m["references"][0]["normalized"]["source"] == "10.1234/AbC_Def"
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
