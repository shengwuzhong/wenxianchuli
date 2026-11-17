# -*- coding: utf-8 -*-
"""竖排正文中的引文候选。

只在正文块里找明确的引文标记：注N、前掲、同書、ibid、作者(年份)。
没有标记时返回空，不伪造 citation_spans。
"""
import io
import json
import os
import re

MARK = re.compile(r"(注\s*[0-9一二三四五六七八九十百]+|前掲|同書|ibid|op\.?\s*cit)", re.I)
NUM = re.compile(r"注\s*([0-9一二三四五六七八九十百]+)")
AUTHOR_YEAR = re.compile(r"([一-鿿ぁ-ゖァ-ヶA-Za-z][^()（）]{0,30})[（(]((?:18|19|20)\d{2})[)）]")


def _text(u):
    return str(u.get("main_text") or u.get("text") or "").strip()


def _sentence(text, start, end):
    a = max(text.rfind("。", 0, start), text.rfind("\n", 0, start)) + 1
    b = text.find("。", end)
    return text[a:b + 1 if b >= 0 else len(text)].strip()


def collect(doc, out_root):
    udir = os.path.join(out_root, doc, "unified")
    if not os.path.isdir(udir):
        return []
    out = []
    for f in sorted(os.listdir(udir), key=lambda x: int(re.search(r"\d+", x).group(0))
                    if re.search(r"\d+", x) else 0):
        if not re.match(r"page_\d+\.json$", f):
            continue
        pno = int(re.search(r"\d+", f).group(0)) + 1
        try:
            page = json.load(io.open(os.path.join(udir, f), encoding="utf-8-sig"))
        except Exception:
            continue
        for u in page.get("unified") or []:
            if u.get("type") in ("Page-header", "Page-footer", "Page-number", "Footnote"):
                continue
            text = _text(u)
            if not text:
                continue
            for m in MARK.finditer(text):
                sent = _sentence(text, m.start(), m.end())
                out.append({"page": pno, "uid": u.get("uid"),
                            "sentence": sent, "citation_text": m.group(0),
                            "kind": "vertical_inline",
                            "authors": [], "year": None,
                            "linked_refs": [], "confidence": "partial",
                            "source": "vertical_cspan"})
            if not MARK.search(text):
                for m in AUTHOR_YEAR.finditer(text):
                    out.append({"page": pno, "uid": u.get("uid"),
                                "sentence": _sentence(text, m.start(), m.end()),
                                "citation_text": m.group(0),
                                "kind": "author_year",
                                "authors": [m.group(1).strip()],
                                "year": m.group(2),
                                "linked_refs": [], "confidence": "partial",
                                "source": "vertical_cspan"})
    return out


def _selftest():
    import shutil
    import tempfile
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "d", "unified")
        os.makedirs(d)
        page = {"w": 800, "h": 1200, "unified": [
            {"uid": "u", "type": "Text", "box": [0, 0, 100, 100],
             "main_text": "これは前掲の説である。"}]}
        io.open(os.path.join(d, "page_0.json"), "w", encoding="utf-8").write(
            json.dumps(page, ensure_ascii=False))
        rows = collect("d", root)
        assert rows and rows[0]["citation_text"] == "前掲", rows
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("vertical_cspan selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
