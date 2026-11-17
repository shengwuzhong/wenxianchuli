# -*- coding: utf-8 -*-
"""日文引文消歧：同書/前掲/ibid/同著者同年。

只改 citation_spans 的 linked_refs 与解析标记；不重写正文。
优先保留 cspan 已给出的 exact 链接，只处理未链接或候选歧义。
"""
import copy
import re

from .ja_date import normalize_year
from .ja_names import name_key
from .ja_tokenize import content_words

_IBID = re.compile(r"(?:ibid|op\.?\s*cit|前掲|同書|同上|同著|同論文|既掲|前述)", re.I)
_YEAR = re.compile(r"(?<!\d)((?:18|19|20|21)\d{2})(?!\d)")


def _text(s):
    return str(s or "")


def _author_matches(ref, authors):
    if not authors:
        return False
    ra = _text(ref.get("authors_raw") or ref.get("authors"))
    if not ra:
        return False
    rk = name_key(ra)
    for a in authors if isinstance(authors, (list, tuple)) else [authors]:
        ak = name_key(a)
        if ak and (ak in rk or rk.startswith(ak)):
            return True
    return False


def _ref_year(ref):
    return normalize_year(ref.get("year"))


def _title_overlap(ref, sentence):
    title = _text(ref.get("title"))
    if not title or not sentence:
        return 0
    words = {w["word"] for w in content_words(title)}
    if not words:
        return 0
    return sum(1 for w in words if w and w in sentence)


def _prev_span(spans, i):
    for j in range(i - 1, -1, -1):
        if spans[j].get("linked_refs"):
            return spans[j]
    return None


def resolve_citations(meta):
    """返回带解析结果的 metadata 副本；原地调用也可。"""
    out = copy.deepcopy(meta)
    refs = out.get("references") or []
    spans = out.get("citation_spans") or []
    by_index = {i: r for i, r in enumerate(refs)}
    unresolved = 0
    ambiguous = 0
    for i, s in enumerate(spans):
        if s.get("linked_refs"):
            continue
        ct = _text(s.get("citation_text")) + " " + _text(s.get("sentence"))
        # 1) 同書/前掲/ibid/同上：继承上一条已解析引文
        if _IBID.search(ct):
            prev = _prev_span(spans, i)
            if prev:
                s["linked_refs"] = copy.deepcopy(prev.get("linked_refs") or [])
                s["resolve_method"] = "ibid"
                s["resolve_confidence"] = "exact" if prev.get("confidence") == "exact" else "partial"
                s["confidence"] = s.get("confidence") or "partial"
                s["prev_uid"] = prev.get("uid")
                continue
        authors = s.get("authors") or []
        year = normalize_year(s.get("year")) or (
            _YEAR.search(ct).group(1) if _YEAR.search(ct) else None)
        if not authors or not year:
            unresolved += 1
            continue
        cands = [r for r in refs
                 if _ref_year(r) == year and _author_matches(r, authors)]
        if not cands:
            unresolved += 1
            s["resolve_note"] = "no_ref_for_author_year"
            continue
        if len(cands) > 1:
            ambiguous += 1
            # 先前引用优先，再按题名重叠/页距
            prev = _prev_span(spans, i)
            prev_idx = None
            for lr in (prev or {}).get("linked_refs") or []:
                if isinstance(lr, dict) and lr.get("index") is not None:
                    prev_idx = lr.get("index")
            scored = []
            for r in cands:
                idx = refs.index(r)
                score = _title_overlap(r, _text(s.get("sentence")))
                if idx == prev_idx:
                    score += 5
                try:
                    score += max(0, 3 - abs(int(r.get("page") or 0) - int(s.get("page") or 0)))
                except Exception:
                    pass
                scored.append((score, idx, r))
            scored.sort(key=lambda x: (-x[0], x[1]))
            best = scored[0][2]
            s["resolve_method"] = "author_year"
            s["resolve_confidence"] = "partial"
            s["resolve_note"] = "ambiguous:%d; picked_index:%d" % (len(cands), refs.index(best))
            s["ambiguous"] = True
        else:
            best = cands[0]
            s["resolve_method"] = "author_year"
            s["resolve_confidence"] = "exact"
        s["linked_refs"] = [{"index": refs.index(best),
                             "num": best.get("num"),
                             "uid": best.get("uid")}]
    out["citation_spans"] = spans
    out["citation_resolve"] = {"total": len(spans),
                               "unresolved": unresolved,
                               "ambiguous": ambiguous}
    return out


def apply_to_meta(meta):
    return resolve_citations(meta)


def _selftest():
    refs = [
        {"num": 1, "authors_raw": "山田 太郎", "year": "2020", "title": "地震探査", "page": 5,
         "uid": "u1"},
        {"num": 2, "authors_raw": "山田 太郎", "year": "2020", "title": "地中レーダ", "page": 6,
         "uid": "u2"},
        {"num": 3, "authors_raw": "佐藤 花子", "year": "2021", "title": "断層", "page": 7,
         "uid": "u3"},
    ]
    spans = [
        {"page": 1, "uid": "a", "sentence": "山田 (2020) の地震探査", "citation_text": "山田 (2020)",
         "authors": ["山田"], "year": "2020", "linked_refs": []},
        {"page": 2, "uid": "b", "sentence": "前掲の手法", "citation_text": "前掲",
         "authors": [], "year": None, "linked_refs": []},
        {"page": 2, "uid": "c", "sentence": "佐藤 (2021)", "citation_text": "佐藤 (2021)",
         "authors": ["佐藤"], "year": "2021", "linked_refs": []},
    ]
    out = resolve_citations({"references": refs, "citation_spans": spans})
    assert out["citation_spans"][0]["linked_refs"][0]["index"] in (0, 1)
    assert out["citation_spans"][1]["resolve_method"] == "ibid"
    assert out["citation_spans"][2]["linked_refs"][0]["index"] == 2
    assert out["citation_resolve"]["total"] == 3
    print("cite_resolve selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
