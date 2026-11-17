# -*- coding: utf-8 -*-
"""把竖排题名/作者候选写回 metadata。

只处理 detect_page 判定为竖排的页面，并且只替换明显错误/缺失的题名；
已有可信题名和作者不覆盖。raw/旧值保留在 *_before_vertical 字段。
同时收集有明确标记的脚注候选（footnote_candidates），不伪造 references。
"""
import copy
import io
import json
import os
import re

from .front_vertical import extract_page
from .ja_names import enrich_author
from .vertical_notes import collect as collect_notes

_SECTION = re.compile(r"^\s*(?:[一二三四五六七八九十]+[、.．]|"
                      r"第[一二三四五六七八九十]+[、.．]|はじめに|目次|序)")


def _value(meta, key):
    x = meta.get(key)
    if isinstance(x, dict):
        return x.get("value")
    return x


def _bad_title(t):
    t = str(t or "").strip()
    if not t:
        return True
    if len(t) > 60:
        return True
    if re.search(r"[。！？!?]\s*$", t):
        return True
    if _SECTION.search(t):
        return True
    return False


def apply_to_meta(meta, page):
    """meta + unified page dict -> (new_meta, changed, info)。"""
    units = page.get("unified") or []
    W, H = page.get("w"), page.get("h")
    cand = extract_page(units, W, H)
    if not cand.get("vertical") or not cand.get("title"):
        return meta, False, {"vertical": False}
    out = copy.deepcopy(meta)
    cur = str(_value(out, "title") or "")
    new_title = cand["title"]["text"]
    changed = False
    if new_title and _bad_title(cur) and new_title != cur:
        out["title_before_vertical"] = copy.deepcopy(out.get("title"))
        out["title"] = {"value": new_title, "page": 1, "uid": cand["title"]["uid"],
                        "confidence": {"level": "mid", "source": "vertical_layout"}}
        out["title_source"] = "vertical"
        changed = True
    # 记录候选，便于审计
    out["vertical_layout"] = {
        "vertical": True,
        "confidence": cand.get("confidence"),
        "title_candidates": cand.get("title_candidates") or [],
        "author_candidates": cand.get("author_candidates") or [],
    }
    # 只补空作者，不覆盖已有作者
    authors = out.get("authors") or []
    if not authors and cand.get("author_candidates"):
        out["authors"] = []
        for a in cand["author_candidates"]:
            row = {"name": a["name"], "markers": [], "affiliation": None,
                   "role": None, "roman": None, "page": 1, "uid": a.get("uid")}
            out["authors"].append(enrich_author(row))
        out["authors_source"] = "vertical"
        changed = True
    return out, changed, {"vertical": True, "title": new_title,
                          "authors": len(out.get("authors") or [])}


def apply_doc(doc, out_root):
    ddir = os.path.join(out_root, doc)
    mfp = os.path.join(ddir, "metadata.json")
    pfp = os.path.join(ddir, "unified", "page_0.json")
    if not os.path.exists(mfp) or not os.path.exists(pfp):
        return None
    with io.open(mfp, encoding="utf-8-sig") as f:
        meta = json.load(f)
    with io.open(pfp, encoding="utf-8-sig") as f:
        page = json.load(f)
    new, changed, info = apply_to_meta(meta, page)
    if info.get("vertical"):
        notes = collect_notes(doc, out_root)
        if notes:
            new["footnote_candidates"] = notes
            new["footnote_count"] = len(notes)
            info["notes"] = len(notes)
            changed = True
    if changed:
        tmp = mfp + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=1)
        os.replace(tmp, mfp)
    return info


def _selftest():
    page = {"w": 793, "h": 1192, "unified": [
        {"uid": "body", "type": "Text", "box": [303, 154, 454, 1097],
         "main_text": "西行は、元永元年に生れ、数多くの歌を詠んだ。"},
        {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702],
         "main_text": "『月詣和歌集』所載西行歌本文小考"},
        {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053],
         "main_text": "犬 井 善 壽"},
    ]}
    meta = {"title": {"value": "西行は、元永元年に生れ、数多くの歌を詠んだ。"},
            "authors": []}
    out, changed, info = apply_to_meta(meta, page)
    assert changed and out["title"]["value"] == "『月詣和歌集』所載西行歌本文小考"
    assert out["authors"][0]["name"] == "犬井善壽"
    # 已有正确标题不覆盖
    meta2 = {"title": {"value": "『月詣和歌集』所載西行歌本文小考"},
             "authors": [{"name": "犬井善壽"}]}
    out2, _, _ = apply_to_meta(meta2, page)
    assert out2["title"]["value"] == meta2["title"]["value"]
    print("vertical_meta selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
