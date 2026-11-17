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
from .vertical_layout import detect_page
from .doc_quality import is_person_name
from .vertical_notes import collect as collect_notes
from .vertical_refs import build_candidates as build_refs, to_references
from .vertical_cspan import collect as collect_cspan
from .vertical_cite_link import link_doc

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
    if re.match(r"^[―—–-].*[―—–-]$", t):
        return True   # 副题/栏目标签，不是主标题
    if t.startswith("【") or t.startswith("##"):
        return True
    if _SECTION.search(t):
        return True
    return False


def _author_bad(a):
    if not isinstance(a, dict):
        return True
    return not is_person_name(a.get("name"))


def _authors_bad(authors):
    return not authors or any(_author_bad(a) for a in authors)


def apply_to_meta(meta, page, page_no=1):
    """meta + unified page dict -> (new_meta, changed, info)。"""
    units = page.get("unified") or []
    W, H = page.get("w"), page.get("h")
    # 先判竖排，避免横向页进入竖排题名/作者链路（原实现会在这里对空
    # Picture 调 splitlines()[0]，9/30 文档因此 IndexError）。
    pinfo = detect_page(units, W, H)
    if not pinfo.get("vertical"):
        return meta, False, {"vertical": False}
    cand = extract_page(units, W, H)
    if not cand.get("vertical"):
        return meta, False, {"vertical": False}
    out = copy.deepcopy(meta)
    cur = str(_value(out, "title") or "")
    new_title = (cand.get("title") or {}).get("text") or ""
    changed = False
    if new_title and _bad_title(cur) and new_title != cur:
        out["title_before_vertical"] = copy.deepcopy(out.get("title"))
        out["title"] = {"value": new_title, "page": page_no,
                        "uid": cand["title"]["uid"],
                        "confidence": {"level": "mid", "source": "vertical_layout"}}
        out["title_source"] = "vertical"
        changed = True
    # 记录候选，便于审计；即使本次没有改动也保留，避免“为什么没采用”无法回查。
    out["vertical_layout"] = {
        "page": page_no,
        "vertical": True,
        "confidence": cand.get("confidence"),
        "title_candidates": cand.get("title_candidates") or [],
        "author_candidates": cand.get("author_candidates") or [],
    }
    # 只补空作者，或在作者明显是正文/注记时替换；正常作者不覆盖。
    authors = out.get("authors") or []
    cand_authors = [a for a in (cand.get("author_candidates") or [])
                    if is_person_name(a.get("name"))]
    if cand_authors and _authors_bad(authors):
        good = [a for a in authors if isinstance(a, dict) and not _author_bad(a)]
        if authors:
            out["authors_before_vertical"] = copy.deepcopy(authors)
        seen = {str((a or {}).get("name_key") or (a or {}).get("name") or "")
                for a in good if isinstance(a, dict)}
        out["authors"] = good
        for a in cand_authors:
            row = {"name": a["name"], "markers": [], "affiliation": None,
                   "role": None, "roman": None, "page": page_no, "uid": a.get("uid")}
            row = enrich_author(row)
            k = row.get("name_key") or row.get("name")
            if k in seen:
                continue
            seen.add(k)
            out["authors"].append(row)
        if out["authors"]:
            out["authors_source"] = "vertical"
            changed = True
    return out, changed, {"vertical": True, "title": new_title,
                          "authors": len(out.get("authors") or []),
                          "page": page_no}


def _pages(ddir):
    udir = os.path.join(ddir, "unified")
    if not os.path.isdir(udir):
        return []
    files = [f for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f)]
    files.sort(key=lambda s: int(re.search(r"(\d+)", s).group(1)))
    out = []
    for f in files:
        try:
            with io.open(os.path.join(udir, f), encoding="utf-8-sig") as fh:
                out.append((f, json.load(fh)))
        except (OSError, ValueError):
            continue
    return out


def apply_doc(doc, out_root):
    ddir = os.path.join(out_root, doc)
    mfp = os.path.join(ddir, "metadata.json")
    if not os.path.exists(mfp):
        return None
    with io.open(mfp, encoding="utf-8-sig") as f:
        meta = json.load(f)
    pages = _pages(ddir)
    if not pages:
        return None

    # 竖排题名可能不在 page_0（封面/目录在前）。扫描所有页，优先取
    # “竖排且有题名候选”的页；只取第一张，避免多页互相覆盖。
    new, changed, info = meta, False, {"vertical": False}
    fallback = None
    for idx, (_fn, page) in enumerate(pages, 1):
        cand_meta, cand_changed, cand_info = apply_to_meta(meta, page, page_no=idx)
        if not cand_info.get("vertical"):
            continue
        if fallback is None:
            fallback = (cand_meta, cand_changed, cand_info)
        if cand_info.get("title"):
            new, changed, info = cand_meta, cand_changed, cand_info
            break
    if not info.get("vertical") and fallback is not None:
        new, changed, info = fallback
    if not info.get("vertical"):
        return info
    # 即使题名/作者未变，也持久化 vertical_layout 候选，便于审计“为什么没采用”。
    if not changed:
        changed = True

    if info.get("vertical"):
        notes = collect_notes(doc, out_root)
        if notes:
            new["footnote_candidates"] = notes
            new["footnote_count"] = len(notes)
            info["notes"] = len(notes)
            changed = True
        refs = build_refs(doc, out_root)
        if refs:
            new["reference_candidates"] = refs
            strict = to_references(refs)
            if strict and (not new.get("references") or
                           new.get("reference_source") == "vertical_notes"):
                new["references"] = strict
                new["reference_source"] = "vertical_notes"
                info["refs"] = len(strict)
                changed = True
        spans = collect_cspan(doc, out_root)
        if spans and not new.get("citation_spans"):
            # 同页/同块/同标记去重
            seen = set()
            uniq = []
            for s in spans:
                k = (s.get("page"), s.get("uid"), s.get("citation_text"), s.get("sentence"))
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(s)
            new["citation_spans"] = uniq
            new["citation_source"] = "vertical_cspan"
            info["cspan"] = len(uniq)
            changed = True
            new, nlink = link_doc(new)
            info["cspan_linked"] = nlink
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
