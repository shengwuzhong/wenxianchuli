# -*- coding: utf-8 -*-
"""日本人名/机构规范化。

只做确定性清洗和 key 生成，不猜姓名读音、不改写原文：
  - 姓名：NFKC、空白折叠、去边沿分隔符；key 去空白/中黑，用于合并判断
  - 罗马字：小写、去空白/标点
  - 机构：NFKC、去邮编/地址、统一常见法人写法；保留展示值
"""
import re
import unicodedata

_SPACE = re.compile(r"[\s\u3000]+")
_MIDDOT = re.compile(r"[・·･]")
_EDGE = re.compile(r"^[\s,，、;；:：\-–—]+|[\s,，、;；:：\-–—]+$")
_POSTAL = re.compile(r"〒?\s*\d{3}[-－]\d{4}")
_CORP = [
    (re.compile(r"[（(]株[）)]"), "株式会社"),
    (re.compile(r"[（(]有[）)]"), "有限会社"),
    (re.compile(r"[（(]独[）)]"), "独立行政法人"),
    (re.compile(r"[（(]国[）)]"), "国立大学法人"),
]


def _nfkc(s):
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def normalize_person_name(name):
    s = _nfkc(name)
    s = _SPACE.sub(" ", s).strip()
    return _EDGE.sub("", s)


def name_key(name):
    s = normalize_person_name(name)
    s = _SPACE.sub("", s)
    s = _MIDDOT.sub("", s)
    return re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]", "", s).lower()


def normalize_roman(roman):
    s = _nfkc(roman)
    return _SPACE.sub(" ", s).strip()


def roman_key(roman):
    return re.sub(r"[^a-z]", "", normalize_roman(roman).lower())


def normalize_affiliation(aff):
    """保留机构名，去掉邮编和详细地址；用于展示和 key。"""
    s = _nfkc(aff)
    s = _POSTAL.sub("", s)
    s = re.split(r"[：:]", s, 1)[0]
    s = _SPACE.sub(" ", s).strip(" ,，、;；")
    for pat, rep in _CORP:
        s = pat.sub(rep, s)
    return s


def affiliation_key(aff):
    s = normalize_affiliation(aff)
    s = _SPACE.sub("", s)
    s = _MIDDOT.sub("", s)
    s = re.sub(r"[（）()「」『』\[\]【】,，、;；:：・·.]", "", s)
    return s.lower()


def enrich_author(a):
    if not isinstance(a, dict):
        return a
    nm = a.get("name")
    if nm:
        a["normalized"] = normalize_person_name(nm)
        a["name_key"] = name_key(nm)
    if a.get("roman"):
        a["roman_normalized"] = normalize_roman(a["roman"])
        a["roman_key"] = roman_key(a["roman"])
    if a.get("affiliation"):
        a["affiliation_normalized"] = normalize_affiliation(a["affiliation"])
        a["affiliation_key"] = affiliation_key(a["affiliation"])
    return a


def enrich_authors(authors):
    return [enrich_author(a) for a in (authors or []) if isinstance(a, dict)]


def enrich_affiliations(affs):
    out = []
    seen = set()
    for a in affs or []:
        name = a.get("name") if isinstance(a, dict) else a
        if not name:
            continue
        n = normalize_affiliation(name)
        k = affiliation_key(name)
        if not n or k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


def _selftest():
    assert name_key("山田 太郎") == name_key("山田　太郎") == "山田太郎"
    assert normalize_person_name("  森・悠一郎 ") == "森・悠一郎"
    assert roman_key("Yuichiro MORI") == "yuichiromori"
    assert normalize_affiliation("東京大学：113-8654 文京区本郷") == "東京大学"
    assert normalize_affiliation("（株）テスト") == "株式会社テスト"
    assert affiliation_key("東京大学：113-8654 文京区") == affiliation_key("東京大学")
    a = enrich_author({"name": "山田 太郎", "roman": "Taro YAMADA",
                       "affiliation": "東京大学：113-8654 本郷"})
    assert a["name_key"] == "山田太郎" and a["affiliation_key"] == "東京大学"
    print("ja_names selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
