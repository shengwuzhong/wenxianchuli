# -*- coding: utf-8 -*-
"""竖排页面题名/作者候选。

只从已排序的 unified 单元中打分，不直接改 metadata；P1 先输出候选，
P2 再接入 front.py。题名真值仍需人工确认。
"""
import re

from .vertical_layout import detect_page, order_units, _box, _type, FURNITURE

_SECTION_PREFIX = re.compile(
    r"^\s*(?:[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十]+[、.．]|"
    r"はじめに|序|目次|注|〈|（|\(|【|〔|—{2,}|―{2,}|―)")
_TITLEISH = re.compile(r"(?:年譜|目録|について|考|論|研究|序|史|集|記|抄|"
                       r"物語|和歌|資料|分析|考察|概説|説|篇|編|稿)")
_AUTHORISH = re.compile(r"^[\u3040-\u30ff\u3400-\u9fffA-Za-z .・\-]{2,20}$")

# 页眉/版权/会议集等“看起来像题名”的固定噪声。保留 Page-header 候选
# （部分竖排题名确实落在 Page-header），只排除明显的版面噪声。
_BOILER_TITLE = re.compile(
    r"^(?:Copyright|©|ISSN|DOI|https?://|第\s*\d+\s*回|EDITORIAL\b|"
    r"Journal of\b|Vol\.?\s*\d|No\.?\s*\d|Proceedings\b|NII-Electronic\b)",
    re.I)


def _text(u):
    return str(u.get("main_text") or u.get("text") or "").strip()


def _first_line(u):
    """空文本块（Picture/空 Text）返回空串，调用方必须跳过。
    2026-11-17: 原实现直接 splitlines()[0]，9/30 文档因此 IndexError。"""
    lines = _text(u).splitlines()
    return lines[0].strip() if lines else ""


def _looks_like_person(t):
    """判断短文本是否像日本人名；带助词/长句的不算。"""
    if not t or len(t) > 20:
        return False
    if _TITLEISH.search(t):
        return False
    if re.search(r"(?:について|による|および|から|まで|として|という|の|と|に|を|は|が|で|へ)", t):
        return False
    plain = re.sub(r"[\s・·]", "", t)
    if not re.fullmatch(r"[\u3040-\u30ff\u3400-\u9fff]{2,8}", plain):
        return False
    return True


def _clean_name(t):
    toks = re.split(r"[\s\u3000]+", t.strip())
    if len(toks) >= 3 and all(len(x) == 1 for x in toks):
        return "".join(toks)
    return " ".join(x for x in toks if x)


def _score_title(u, W, H):
    t = _text(u)
    if not t or len(t) > 120:
        return -99
    typ = _type(u)
    if typ == "Page-number":
        return -99
    if _SECTION_PREFIX.search(t):
        return -99
    x0, y0, x1, y1 = _box(u)
    score = 0.0
    score += 3.0 if typ == "Section-header" else (2.5 if typ == "Page-header" else 0.0)
    score += 4.0 * (x1 / float(W or 1))
    score += 1.5 if (y1 - y0) >= 2.0 * max(1.0, x1 - x0) else 0.0
    score += 2.0 if 6 <= len(t) <= 80 else 0.0
    if len(t) > 80:
        score -= 2.0
    if re.search(r"[。！？!?]\s*$", t):
        score -= 1.5
    if _looks_like_person(t) and typ != "Page-header":
        score -= 4.0
    return score


def title_candidates(units, W, H, limit=5):
    rows = []
    for u in units:
        if _type(u) == "Page-number":
            continue
        t = _text(u)
        if not t or _BOILER_TITLE.search(t) or t.startswith("<"):
            continue
        s = _score_title(u, W, H)
        if s > 0:
            rows.append((s, u))
    rows.sort(key=lambda x: (-x[0], -_box(x[1])[2]), reverse=False)
    return [{"uid": u.get("uid"), "type": _type(u), "text": _text(u),
             "score": round(s, 2), "box": _box(u)}
            for s, u in rows[:limit]]


def _name_like(u, t=None):
    t = _text(u) if t is None else t
    if not (2 <= len(t) <= 20):
        return False
    if _SECTION_PREFIX.search(t) or re.search(r"[。！？!?]", t):
        return False
    if not _AUTHORISH.match(t):
        return False
    if re.fullmatch(r"[一二三四五六七八九十百千]+", t):
        return False
    # 纯假名/汉字/拉丁姓名，排除明显正文词
    if re.search(r"(?:について|による|および|から|まで|として|という)", t):
        return False
    return True


def author_candidates(units, W, H, title_uids=(), limit=8):
    title_uids = set(title_uids or ())
    rows = []
    for u in units:
        if u.get("uid") in title_uids:
            continue
        t = _first_line(u)
        if not t:
            continue
        if not _name_like(u, t):
            continue
        x0, y0, x1, y1 = _box(u)
        if H and y0 < 0.35 * H:
            continue
        s = 2.0 * (x1 / float(W or 1)) + (1.0 if _type(u) == "Section-header" else 0.0)
        rows.append((s, u, t))
    rows.sort(key=lambda x: (-x[0], _box(x[1])[1]))
    out = []
    for s, u, t in rows[:limit]:
        out.append({"uid": u.get("uid"), "type": _type(u), "name": _clean_name(t),
                    "score": round(s, 2), "box": _box(u)})
    return out


def _subtitle_for(title, units, W, H):
    """找题名附近的副题（——…——），返回首行文本或 None。"""
    if not title or not W or not H:
        return None
    tx0, ty0, tx1, ty1 = title["box"]
    best = None
    for u in units:
        if u.get("uid") == title.get("uid"):
            continue
        if _type(u) in ("Page-number", "Page-header", "Page-footer",
                        "Picture", "Table", "Formula"):
            continue
        t = _first_line(u)
        if not t:
            continue
        if not re.match(r"^[—―-]{2,}.+[—―-]{2,}$", t):
            continue
        if len(t) > 80:
            continue
        x0, y0, x1, y1 = _box(u)
        if abs(x1 - tx1) > 0.2 * W or abs(y0 - ty0) > 0.3 * H:
            continue
        d = abs(x1 - tx1) + abs(y0 - ty0)
        if best is None or d < best[0]:
            best = (d, t)
    return best[1] if best else None


def extract_page(units, W, H):
    info = detect_page(units, W, H)
    # 非竖排页不应进入竖排题名/作者链路。此前横向页也会走到 _subtitle_for，
    # 9/30 文档因空 Picture 触发 IndexError；也避免把横排页眉误当竖排题名。
    if not info["vertical"]:
        return {"vertical": False, "confidence": info["confidence"],
                "title": None, "title_candidates": [],
                "author_candidates": []}
    ordered, _ = order_units(units, W, H)
    titles = title_candidates(ordered, W, H)
    if titles:
        sub = _subtitle_for(titles[0], ordered, W, H)
        if sub:
            titles[0]["subtitle"] = sub
            titles[0]["text"] = titles[0]["text"].rstrip("。") + sub
    authors = author_candidates(ordered, W, H,
                                [titles[0]["uid"]] if titles else [])
    return {"vertical": info["vertical"], "confidence": info["confidence"],
            "title": titles[0] if titles else None,
            "title_candidates": titles,
            "author_candidates": authors}


def _selftest():
    units = [
        {"uid": "p", "type": "Page-number", "box": [95, 116, 126, 136], "main_text": "226"},
        {"uid": "body", "type": "Text", "box": [303, 154, 454, 1097],
         "main_text": "西行は、元永元年に生れ、数多くの歌を詠んだ。"},
        {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702],
         "main_text": "『月詣和歌集』所載西行歌本文小考"},
        {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053],
         "main_text": "犬井善壽"},
    ]
    out = extract_page(units, 793, 1192)
    assert out["vertical"]
    assert out["title"]["text"] == "『月詣和歌集』所載西行歌本文小考", out
    assert any(a["name"] == "犬井善壽" for a in out["author_candidates"]), out
    # 章节标题不能当题名
    units2 = [{"uid": "s", "type": "Section-header", "box": [160, 195, 187, 382],
               "main_text": "一、「恋の詞」の分析"}]
    assert not title_candidates(units2, 875, 1241)
    print("front_vertical selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
