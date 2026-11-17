# -*- coding: utf-8 -*-
"""日文元号/日期规范化。

支持：
  令和6年 / 令和 6 / 令和元年 / 令和6年度
  平成30年 / 昭和55年 / 大正1年 / 明治45年
  R6 / H30 / S55 / T1 / M45
  2024年 / 2024-03-01 / 2024/3/1 / 2024.3.1

只做确定性的年份/日期转换，不猜模糊文本；返回 None 表示无法确定。
"""
import re
import unicodedata

ERA_START = {
    "令和": 2019,
    "平成": 1989,
    "昭和": 1926,
    "大正": 1912,
    "明治": 1868,
}
ERA_ABBR = {"R": "令和", "H": "平成", "S": "昭和", "T": "大正", "M": "明治"}
MIN_YEAR, MAX_YEAR = 1868, 2100

_ERA_RE = re.compile(r"(令和|平成|昭和|大正|明治)\s*(元|\d{1,2})\s*年?")
_ABBR_RE = re.compile(r"(?<![A-Za-z])([RHSTM])\s*(元|\d{1,2})(?:\s*年)?(?![A-Za-z])", re.I)
_WEST_RE = re.compile(r"(?<!\d)((?:18|19|20|21)\d{2})(?!\d)")
_WEST_DATE_RE = re.compile(
    r"(?<!\d)((?:18|19|20|21)\d{2})\s*[年./-]\s*(\d{1,2})"
    r"(?:\s*[月./-]\s*(\d{1,2})\s*日?)?")
_ERA_DATE_RE = re.compile(
    r"(令和|平成|昭和|大正|明治)\s*(元|\d{1,2})\s*年"
    r"(?:\s*(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日?)?")
_ABBR_DATE_RE = re.compile(
    r"(?<![A-Za-z])([RHSTM])\s*(元|\d{1,2})(?:\s*年)?"
    r"(?:\s*(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日?)?(?![A-Za-z])", re.I)


def _nfkc(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _valid(y):
    return y if MIN_YEAR <= y <= MAX_YEAR else None


def era_to_year(era, n):
    """元号 + 年数 -> 西历；元=1。无效返回 None。"""
    base = ERA_START.get(era)
    if base is None:
        return None
    if str(n) == "元":
        n = 1
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 99:
        return None
    return _valid(base + n - 1)


def normalize_year(value):
    """返回 4 位西历年份字符串；无法确定返回 None。"""
    if value is None:
        return None
    if isinstance(value, int):
        return str(value) if _valid(value) else None
    s = _nfkc(value)
    if not s:
        return None
    m = _ERA_RE.search(s)
    if m:
        y = era_to_year(m.group(1), m.group(2))
        return str(y) if y else None
    m = _ABBR_RE.search(s)
    if m:
        era = ERA_ABBR.get(m.group(1).upper())
        y = era_to_year(era, m.group(2))
        return str(y) if y else None
    m = _WEST_RE.search(s)
    if m:
        y = int(m.group(1))
        return str(y) if _valid(y) else None
    return None


def normalize_date(value):
    """返回 {year, month, day, normalized, era}；无法确定返回 None。

    normalized 形如 YYYY、YYYY-MM、YYYY-MM-DD。
    """
    if value is None:
        return None
    s = _nfkc(value)
    if not s:
        return None
    m = _ERA_DATE_RE.search(s)
    if m:
        y = era_to_year(m.group(1), m.group(2))
        if not y:
            return None
        mo = int(m.group(3)) if m.group(3) else None
        day = int(m.group(4)) if m.group(4) else None
        if mo is not None and not (1 <= mo <= 12):
            mo = None
        if day is not None and not (1 <= day <= 31):
            day = None
        return _date_result(y, mo, day, m.group(1))
    m = _ABBR_DATE_RE.search(s)
    if m:
        era = ERA_ABBR.get(m.group(1).upper())
        y = era_to_year(era, m.group(2))
        if not y:
            return None
        mo = int(m.group(3)) if m.group(3) else None
        day = int(m.group(4)) if m.group(4) else None
        if mo is not None and not (1 <= mo <= 12):
            mo = None
        if day is not None and not (1 <= day <= 31):
            day = None
        return _date_result(y, mo, day, era)
    m = _WEST_DATE_RE.search(s)
    if m:
        y = int(m.group(1))
        if not _valid(y):
            return None
        mo = int(m.group(2)) if m.group(2) else None
        day = int(m.group(3)) if m.group(3) else None
        if mo is not None and not (1 <= mo <= 12):
            mo = None
        if day is not None and not (1 <= day <= 31):
            day = None
        return _date_result(y, mo, day, None)
    y = _WEST_RE.search(s)
    if y:
        yy = int(y.group(1))
        return _date_result(yy, None, None, None) if _valid(yy) else None
    return None


def _date_result(y, mo, day, era):
    norm = "%04d" % y
    if mo is not None:
        norm += "-%02d" % mo
        if day is not None:
            norm += "-%02d" % day
    return {"year": y, "month": mo, "day": day, "normalized": norm, "era": era}


def _selftest():
    cases = [
        ("令和6年", "2024"), ("令和 6", "2024"), ("令和元年", "2019"),
        ("平成30年", "2018"), ("昭和55年", "1980"),
        ("大正1年", "1912"), ("明治45年", "1912"),
        ("R6", "2024"), ("H30", "2018"), ("S55", "1980"),
        ("２０２４年", "2024"), ("2024-03-01", "2024"),
        ("no date", None), ("令和", None),
    ]
    for text, want in cases:
        got = normalize_year(text)
        assert got == want, (text, got, want)
    d = normalize_date("令和6年3月1日")
    assert d and d["normalized"] == "2024-03-01", d
    d = normalize_date("2024/3/1")
    assert d and d["normalized"] == "2024-03-01", d
    d = normalize_date("R6")
    assert d and d["normalized"] == "2024", d
    d = normalize_date("平成30年度")
    assert d and d["normalized"] == "2018", d
    print("ja_date selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
