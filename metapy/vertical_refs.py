# -*- coding: utf-8 -*-
"""从竖排脚注候选提取参考文献候选。

只做保守解析：必须有明确题名（「」或『』）及来源/年份线索；
不把“参见某某”的说明性注记硬写成 references。
"""
import re

from .ja_date import normalize_year

_NUM = re.compile(r"^\s*注?\s*[0-9一二三四五六七八九十百〇]+\s*[、.．:：]?\s*")
_TITLE = re.compile(r"「([^」]{2,120})」")
_TITLE2 = re.compile(r"『([^』]{2,120})』")
_SOURCE = re.compile(r"《([^》]{1,100})》")
_YEAR = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
_KANJI_YEAR = re.compile(r"[〇一二三四五六七八九]{4}")
_KAN = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _kanji_num(s):
    n = 0
    for ch in s:
        if ch not in _KAN:
            return None
        n = n * 10 + _KAN[ch]
    return n


def _year(s):
    y = normalize_year(s)
    if y:
        return y
    m = _YEAR.search(s)
    if m:
        return m.group(1)
    m = _KANJI_YEAR.search(s)
    if m:
        n = _kanji_num(m.group(0))
        if n and 1800 <= n <= 2100:
            return str(n)
    return None


def _parse_line(line, page, uid):
    raw = line.strip()
    if not raw:
        return None
    body = _NUM.sub("", raw)
    mt = _TITLE.search(body) or _TITLE2.search(body)
    if not mt:
        return None
    title = mt.group(1).strip()
    authors = body[:mt.start()].strip(" ,，、;；:：")
    authors = re.sub(r"^(?:注|※|＊|\*)\s*", "", authors).strip()
    rest = body[mt.end():]
    ms = _SOURCE.search(rest)
    source = ms.group(1).strip() if ms else None
    # 第二个『』常是所收书名
    books = _TITLE2.findall(rest)
    if not source and books:
        source = books[0].strip()
    year = _year(rest)
    pages = None
    mp = re.search(r"(?<!\d)([A-Za-z]?\d{1,5})\s*[-–—~～]\s*([A-Za-z]?\d{1,5})(?!\d)", rest)
    if mp:
        pages = "%s-%s" % mp.groups()
    conf = "high" if (title and year and source) else ("medium" if title and source else "low")
    return {"num": None, "title": title, "authors_raw": authors or None,
            "year": year, "source": source, "pages": pages,
            "raw": raw, "page": page, "uid": uid,
            "confidence": conf, "source_kind": "vertical_note"}


def build_candidates(doc, out_root):
    from .vertical_notes import collect
    rows = []
    for n in collect(doc, out_root):
        for line in str(n.get("text") or "").splitlines():
            r = _parse_line(line, n.get("page"), n.get("uid"))
            if r:
                # 同一块内多行注记可能共享 uid；用 raw 去重
                if not any(x["raw"] == r["raw"] for x in rows):
                    rows.append(r)
    return rows


def to_references(rows):
    """严格过滤后写入 references；宁可少写，不把说明性注记当文献。"""
    out = []
    bad_author = re.compile(r"(?:原載|で開かれ|した|によれば|以下|参照|については)")
    for r in rows:
        if r.get("confidence") != "high":
            continue
        t = str(r.get("title") or "")
        raw = str(r.get("raw") or "")
        a = str(r.get("authors_raw") or "")
        if not (4 <= len(t) <= 60):
            continue
        if len(raw) > 320:
            continue
        if a and (len(a) > 20 or bad_author.search(a)):
            continue
        if not r.get("source"):
            continue
        out.append({"num": r.get("num"), "title": t,
                    "authors_raw": a or None, "year": r.get("year"),
                    "source": r.get("source"), "volume": None, "issue": None,
                    "pages": r.get("pages"), "doi": None, "raw": raw,
                    "page": r.get("page"), "uid": r.get("uid"),
                    "verified": False, "source_kind": "vertical_note"})
    return out


def _selftest():
    import json
    import os
    import tempfile
    import shutil
    from .vertical_notes import collect
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "d", "unified")
        os.makedirs(d)
        page = {"w": 1000, "h": 1200, "unified": [
            {"uid": "n", "type": "Text", "box": [100, 900, 500, 980],
             "main_text": "注一 郭沫若「編輯余談」《創造》季刊二卷二期（一九二四年二月）"},
        ]}
        open(os.path.join(d, "page_0.json"), "w", encoding="utf-8").write(
            json.dumps(page, ensure_ascii=False))
        rows = build_candidates("d", root)
        assert rows and rows[0]["title"] == "編輯余談", rows
        assert rows[0]["year"] == "1924" and rows[0]["source"] == "創造", rows
        refs = to_references(rows)
        assert refs and refs[0]["title"] == "編輯余談", refs
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("vertical_refs selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
