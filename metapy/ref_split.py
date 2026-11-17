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
    s = str(s or "").replace("\u00ad", "-")
    return unicodedata.normalize("NFKC", s).strip()


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
    # 刊名缺失通常意味着字段串位，值得用 raw 重新解析。
    if not ref.get("source"):
        return True
    # 已有字段缺失但 raw 明确有页/卷：值得二次切分
    if not ref.get("pages") and (_PAGES.search(raw)
                                 or re.search(r"\((?:\d{4})\)", raw)):
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


_TAIL_PAGES = re.compile(
    r"(?P<pages>[A-Za-z]?\d{1,6}(?:\s*[-–—~～]\s*[A-Za-z]?\d{1,6})?"
    r"(?:\([A-Z]\))?)\s*$")


def _journal_ok(s):
    s = str(s or "").strip(" ,，、;；:：.．")
    if len(s) < 3 or len(s) > 90:
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    if re.search(r"\b(?:and|et al)\b", s, re.I):
        return False
    return True


def _bare_parse(raw):
    """解析“作者, 刊名, 卷, 页 (年)”与“作者. 刊名 年;卷:页”两种常见格式。

    这类格式通常没有论文题名（只有作者/刊名/卷页），旧逻辑会把作者姓氏
    当作 title；这里返回 title=None，让下游知道“题名确实不存在”。
    """
    s = _nfkc(raw)
    s = _NUM.sub("", s).strip()
    s = s.strip(" .．。")

    # A) Authors: [Title.] Journal Vol (Year) Pages
    m = re.match(r"^(?P<authors>.+?):\s*(?P<rest>.+)$", s)
    if m:
        authors = m.group("authors").strip(" ,，、;；")
        rest = m.group("rest").strip()
        j = re.search(
            r"(?P<journal>[A-Z][A-Za-z.&'’\- ]{2,80}?)\s+"
            r"(?P<vol>\d{1,4})\s*\((?P<year>(?:18|19|20|21)\d{2})\)\s*"
            r"(?P<pages>[A-Za-z]?\d{1,6}(?:\s*[-–—~～]\s*[A-Za-z]?\d{1,6})?)",
            rest)
        if j and _journal_ok(j.group("journal")):
            title = rest[:j.start()].strip(" .．。")
            return {"authors_raw": authors, "title": title if len(title) >= 4 else None,
                    "source": j.group("journal").strip(" ,，、;；.．"),
                    "year": j.group("year"), "volume": j.group("vol"),
                    "pages": re.sub(r"\s+", "", j.group("pages")),
                    "no_title": len(title) < 4}

    # B) Authors. Journal Year; Vol: Pages  (e.g. "Lommel S, et al. EMBO Rep. 2001;2:850-857.")
    m = re.match(
        r"^(?P<authors>.+?)\.\s+(?P<journal>[A-Z][A-Za-z.&'’\- ]{2,80}?)\.?\s+"
        r"(?P<year>(?:18|19|20|21)\d{2})\s*;\s*(?P<vol>\d{1,4})\s*:\s*"
        r"(?P<pages>[A-Za-z]?\d{1,6}(?:\s*[-–—~～]\s*[A-Za-z]?\d{1,6})?)", s)
    if m and _journal_ok(m.group("journal")):
        return {"authors_raw": m.group("authors").strip(" ,，、;；"),
                "title": None,
                "source": m.group("journal").strip(" ,，、;；.．"),
                "year": m.group("year"), "volume": m.group("vol"),
                "pages": re.sub(r"\s+", "", m.group("pages")),
                "no_title": True}

    # C) Authors, Journal, Vol, Pages (Year)  /  Authors, Journal Vol, Pages (Year)
    my = re.search(r"\((?P<year>(?:18|19|20|21)\d{2})\)\s*\.?$", s)
    if my:
        prefix = s[:my.start()].strip(" ,，、;；")
        mp = _TAIL_PAGES.search(prefix)
        if mp:
            pages = re.sub(r"\s+", "", mp.group("pages"))
            before_pages = prefix[:mp.start()].strip(" ,，、;；")
            mv = re.search(r"(?P<vol>\d{1,4})\s*$", before_pages)
            if mv:
                vol = mv.group("vol")
                head = before_pages[:mv.start()].strip(" ,，、;；")
                idx = head.rfind(", ")
                if idx > 0:
                    authors = head[:idx].strip(" ,，、;；")
                    journal = head[idx + 2:].strip(" ,，、;；.．")
                    if authors and _journal_ok(journal):
                        return {"authors_raw": authors, "title": None,
                                "source": journal, "year": my.group("year"),
                                "volume": vol, "pages": pages, "no_title": True}
    return None


def normalize_ref(ref):
    """按需修复单条 ref；返回是否有改动。"""
    if not _suspicious(ref):
        return False
    got = _bare_parse(ref.get("raw")) or split_ref(ref)
    if not got:
        return False
    changed = False
    for k in ("authors_raw", "title", "year", "volume", "issue", "pages", "doi"):
        v = got.get(k)
        if v:
            if str(ref.get(k) or "") != str(v):
                ref[k] = v
                changed = True
    if got.get("title") is None and got.get("no_title"):
        if ref.get("title"):
            ref["title"] = None
            changed = True
    if got.get("source"):
        if str(ref.get("source") or "") != str(got["source"]):
            ref["source"] = got["source"]
            changed = True
    if changed:
        ref["ref_split"] = True
        ref["ref_split_raw"] = ref.get("raw")
    return changed


def raw(ref):
    return ref.get("raw") or ""


def normalize_refs(refs):
    n = 0
    keep = []
    for r in refs or []:
        if not isinstance(r, dict):
            keep.append(r)
            continue
        raw = str(r.get("raw") or "")
        # 明显是正文段落而非参考文献（53_7 首条实证）：无编号、无页码、
        # 超长且以叙述词开头。只删这一种高置信噪声，不动普通无编号条目。
        if not r.get("num") and not r.get("pages") and len(raw) > 220 \
                and re.match(r"^(?:Regarding|The|In|This|These|We|It)\b", raw):
            continue
        if normalize_ref(r):
            n += 1
        keep.append(r)
    if isinstance(refs, list):
        refs[:] = keep
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
