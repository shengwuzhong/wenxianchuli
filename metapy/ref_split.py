# -*- coding: utf-8 -*-
"""日文参考文献二次切分。

只处理“字段明显错位/截断”的 refs；raw 保留，已有可信字段不覆盖。
目标格式：
  Authors: Title. Journal Vol: pages, Year
  Authors. Title. Journal Year; Vol: pages.
"""
import re

from .ja_date import normalize_year

_YEAR = re.compile(r"(?<!\d)((?:18|19|20|21)\d{2})(?!\d)")
_PAGES = re.compile(r"(?<!\d)([A-Za-z]?\d{1,5})\s*[-–—~～]\s*([A-Za-z]?\d{1,5})(?!\d)")
_DOI = re.compile(r"(10\.\d{4,9}/[^\s,，;；]+)", re.I)
_NUM = re.compile(r"^\s*[\(（]?\s*\d{1,3}\s*[\)）\.、．]\s*")
_SPLIT = re.compile(r"(?<=[.．。])\s+")


def _nfkc(s):
    import unicodedata
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def _suspicious(ref):
    t = str(ref.get("title") or "").strip()
    a = str(ref.get("authors_raw") or "").strip()
    raw = str(ref.get("raw") or "")
    if not t or len(t) < 6:
        return True
    if t.startswith("http") or ".pdf" in t.lower():
        return True
    # 题名其实是作者名（"Toyoda K" / "Banki NM" 等）
    if re.match(r"^[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]*)?\s+[A-Z]{1,3}\.?$", t):
        return True
    if a and (t == a or (t in a and len(a) > len(t) + 4)):
        return True
    if re.match(r"^\s*\d{1,3}\s*[\)）\.、]", a):
        return True
    # 已有字段缺失但 raw 明确有页/卷：值得二次切分
    if not ref.get("pages") and _PAGES.search(raw):
        return True
    if not ref.get("volume") and re.search(r"(?:Vol\.?|巻)\s*\d", raw, re.I):
        return True
    # 题名把刊名/卷期粘进来：末尾出现明显的刊名/卷期片段
    if re.search(r"(?:J|Proc|Nat|Acad|Sci|Biochim|Biophys|Mol|Ther|Nucleic|"
                 r"Front|Oncol| Med| Biol| Chem| Lett| Res)\s*$", t):
        return True
    # 题名截断：raw 中题名后面还有同句内容，而当前题名以 of/the/and 等结尾
    if re.search(r"\b(?:of|the|and|in|for|with|on|by|from|to)\s*$", t, re.I):
        return True
    return False


def _split_authors_title(body):
    """返回 (authors, title, tail) 或 None。"""
    body = body.strip()
    # 日本式 Authors: Title. ...
    colon = body.find(":")
    first_dot = re.search(r"[.．]\s", body)
    if colon > 0 and (not first_dot or colon < first_dot.start()):
        authors = body[:colon].strip(" ,，、;；")
        rest = body[colon + 1:].strip()
    else:
        m = first_dot
        if not m:
            return None
        authors = body[:m.start()].strip(" ,，、;；")
        rest = body[m.end():].strip()
    # title 到下一个句点/日文句号
    m = re.search(r"[.．。]\s", rest)
    if not m:
        return None
    title = rest[:m.start()].strip(" 「」『』")
    tail = rest[m.end():].strip()
    if not authors or not title:
        return None
    return authors, title, tail


def _tail_fields(tail):
    year = None
    m = _YEAR.search(tail)
    if m:
        year = m.group(1)
    else:
        y = normalize_year(tail)
        year = y
    pages = None
    ms = list(_PAGES.finditer(tail))
    if ms:
        a, b = ms[-1].groups()
        pages = "%s-%s" % (a, b)
    doi = None
    md = _DOI.search(tail)
    if md:
        doi = md.group(1).rstrip(".")
    vol = None
    issue = None
    # Vol. 12(3): 45-67 / 12: 45-67 / 12 (3)
    mv = re.search(r"(?:Vol\.?|巻)?\s*(\d{1,4})\s*(?:\((\d{1,3})\))?\s*[:：]\s*[A-Za-z]?\d", tail)
    if mv:
        vol = mv.group(1)
        issue = mv.group(2)
    else:
        mv = re.search(r"(?:Vol\.?|巻)\s*(\d{1,4})", tail, re.I)
        if mv:
            vol = mv.group(1)
        mi = re.search(r"(?:No\.?|号)\s*(\d{1,3})", tail, re.I)
        if mi:
            issue = mi.group(1)
    journal = tail
    cut = len(journal)
    for pat in (_YEAR, _PAGES, re.compile(r"(?:Vol\.?|巻)\s*\d", re.I),
                re.compile(r"\d{1,4}\s*[:：]\s*[A-Za-z]?\d"), _DOI):
        m = pat.search(journal)
        if m:
            cut = min(cut, m.start())
    journal = journal[:cut].strip(" ,，、;；.．")
    journal = re.sub(r"\s+\d{4}\s*$", "", journal).strip()
    return {"journal": journal or None, "year": year, "volume": vol,
            "issue": issue, "pages": pages, "doi": doi}


def split_ref(ref):
    """返回解析后的字段 dict；解析失败返回 None。"""
    raw = _nfkc(ref.get("raw"))
    if not raw:
        return None
    body = _NUM.sub("", raw)
    got = _split_authors_title(body)
    if not got:
        return None
    authors, title, tail = got
    out = {"authors_raw": authors, "title": title}
    out.update(_tail_fields(tail))
    if not out.get("title") or len(out["title"]) < 4:
        return None
    return out


def normalize_ref(ref):
    """按需修复单条 ref；返回是否有改动。"""
    if not _suspicious(ref):
        return False
    got = split_ref(ref)
    if not got:
        return False
    changed = False
    for k in ("authors_raw", "title", "year", "volume", "issue", "pages", "doi"):
        v = got.get(k)
        if v:
            if str(ref.get(k) or "") != str(v):
                ref[k] = v
                changed = True
    if got.get("journal"):
        if str(ref.get("source") or "") != str(got["journal"]):
            ref["source"] = got["journal"]
            changed = True
    if changed:
        ref["ref_split"] = True
        ref["ref_split_raw"] = ref.get("raw")
    return changed


def raw(ref):
    return ref.get("raw") or ""


def normalize_refs(refs):
    n = 0
    for r in refs or []:
        if isinstance(r, dict) and normalize_ref(r):
            n += 1
    return n


def _selftest():
    r = {"raw": "2) Yoshimura S, Toyoda K, Ohara T, et al: Takotsubo cardiomyopathy in acute ischemic stroke. Ann Neurol 64: 547-554, 2008",
         "title": "Toyoda K", "authors_raw": "Yoshimura S", "source": "Ohara T"}
    assert normalize_ref(r)
    assert r["title"] == "Takotsubo cardiomyopathy in acute ischemic stroke", r
    assert r["authors_raw"].startswith("Yoshimura S"), r
    assert r["year"] == "2008" and r["pages"] == "547-554", r
    r2 = {"raw": "4) 石川俊平. 次世代の病理AI. 病理と臨床2024; 42: 713-716.",
          "title": None, "authors_raw": "石川俊平. 次世代の病理AI"}
    assert normalize_ref(r2)
    assert r2["title"] == "次世代の病理AI", r2
    assert r2["year"] == "2024" and r2["pages"] == "713-716", r2
    print("ref_split selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
