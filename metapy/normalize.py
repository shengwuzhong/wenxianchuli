# -*- coding: utf-8 -*-
r"""日文文本规范化核心（独立模块，不接入主链路）。

规则（按用户 2026-11-12 决策）:
  1. NFKC：全角/半角、兼容字符统一；
  2. 新旧字体：常见旧字体 → 新字体；
  3. 送假名：常见「行なう→行う」类表记统一；
  4. 强保护：DOI、KAKENHI 编号、术语表词汇原样保留，不做任何转换；
  5. 输出 raw / normalized / segments / 双向 span 映射。

用法:
  from metapy.normalize import normalize_text
  r = normalize_text("ＡＢＣ 舊 行なう DOI:10.1234/AbC")
  r["normalized"]; r["segments"]; r["raw_to_norm"]; r["norm_to_raw"]

  python -m metapy.normalize   # 自检
"""
import re
import sys
import unicodedata

# 常见旧字体 → 新字体（保守表；只收日文语境常见的成对字）
_OLD_TO_NEW = {
    "舊": "旧", "靑": "青", "敎": "教", "國": "国", "圖": "図",
    "說": "説", "讀": "読", "醫": "医", "學": "学", "會": "会",
    "體": "体", "點": "点", "邊": "辺", "變": "変", "戰": "戦",
    "藝": "芸", "廣": "広", "氣": "気", "區": "区", "驛": "駅",
    "齒": "歯", "縣": "県", "稻": "稲", "鐵": "鉄", "龍": "竜",
    "燈": "灯", "證": "証", "臺": "台", "拂": "払", "佛": "仏",
    "增": "増", "德": "徳", "橫": "横", "檢": "検", "驗": "験",
    "權": "権", "顯": "顕", "觀": "観", "歡": "歓", "歸": "帰",
    "犧": "犠", "藏": "蔵", "處": "処", "號": "号", "覽": "覧",
    "獻": "献", "疊": "畳", "穗": "穂", "粹": "粋",
    "盜": "盗", "碎": "砕", "聽": "聴", "舍": "舎", "莊": "荘",
    "旣": "既", "卽": "即", "狀": "状", "眞": "真",
    "祕": "秘", "竝": "並", "窗": "窓",
}
_OLD_TRANS = {ord(k): v for k, v in _OLD_TO_NEW.items()}

# 送假名统一（长词优先；只收无歧义的常见动词/形容词）
_OKURI = [
    ("行なう", "行う"), ("行なった", "行った"), ("行なって", "行って"),
    ("表わす", "表す"), ("表わした", "表した"), ("表わして", "表して"),
    ("現わす", "現す"), ("現わした", "現した"), ("現われ", "現れ"),
    ("著わす", "著す"), ("著わした", "著した"),
    ("断わる", "断る"), ("断わった", "断った"),
]
_OKURI.sort(key=lambda x: -len(x[0]))

# DOI / KAKENHI / 术语保护
_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)
_KAKENHI = re.compile(
    r"(?<![A-Za-z0-9])(?:JP|jp)\d{6,}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])(?:JP|jp)?\d{2}[KHJ]\d{5,}(?![A-Za-z0-9])"
    r"|課題番号\s*[:：]?\s*[A-Z0-9][A-Z0-9\-]{3,}", re.I)
_PROTECT_PRIORITY = {"doi": 3, "kakenhi": 2, "glossary": 1}


def _find_spans(text, glossary=()):
    if isinstance(glossary, str):
        glossary = [glossary]
    spans = []
    for m in _DOI.finditer(text):
        spans.append((m.start(), m.end(), "doi"))
    for m in _KAKENHI.finditer(text):
        spans.append((m.start(), m.end(), "kakenhi"))
    for term in glossary or ():
        term = (term or "").strip()
        if len(term) < 2:
            continue
        start = 0
        while True:
            i = text.find(term, start)
            if i < 0:
                break
            spans.append((i, i + len(term), "glossary"))
            start = i + len(term)
    # 去重叠：按起点、长度、优先级排序，重叠区域合并为高优先级 kind
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0]), -_PROTECT_PRIORITY[x[2]]))
    merged = []
    for s, e, kind in spans:
        if not merged or s >= merged[-1][1]:
            merged.append([s, e, kind])
        else:
            prev = merged[-1]
            if e > prev[1]:
                prev[1] = e
            if _PROTECT_PRIORITY[kind] > _PROTECT_PRIORITY[prev[2]]:
                prev[2] = kind
    return [(s, e, k) for s, e, k in merged]


def _transform(s):
    if not s:
        return s
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_OLD_TRANS)
    for a, b in _OKURI:
        if a in s:
            s = s.replace(a, b)
    return s


def _segments(raw, protected):
    out = []
    pos = 0
    for s, e, kind in protected:
        if s > pos:
            out.append((raw[pos:s], False, "text", pos, s))
        out.append((raw[s:e], True, kind, s, e))
        pos = e
    if pos < len(raw):
        out.append((raw[pos:], False, "text", pos, len(raw)))
    return out


def normalize_text(text, glossary=()):
    """规范化一段文本；返回 raw/normalized/segments 与双向 span 映射。

    glossary 可为字符串列表；术语命中段 protected=True，原样保留。
    映射为段级：每段 raw_span ↔ norm_span；变换段内按段偏移线性映射。
    """
    raw = text if isinstance(text, str) else ("" if text is None else str(text))
    protected = _find_spans(raw, glossary)
    segs = []
    norm_pos = 0
    for raw_s, is_prot, kind, rs, re_ in _segments(raw, protected):
        ns = norm_pos
        norm_s = raw_s if is_prot else _transform(raw_s)
        ne = ns + len(norm_s)
        segs.append({
            "raw": raw_s, "normalized": norm_s,
            "raw_span": [rs, re_], "norm_span": [ns, ne],
            "protected": bool(is_prot), "kind": kind,
        })
        norm_pos = ne

    def raw_to_norm(i):
        if not isinstance(i, int) or i < 0 or i > len(raw):
            return None
        for seg in segs:
            a, b = seg["raw_span"]
            if a <= i <= b:
                n0, n1 = seg["norm_span"]
                rlen, nlen = b - a, n1 - n0
                if i == b:
                    return n1
                return n0 + (0 if rlen == 0 else int(round((i - a) * nlen / rlen)))
        return len("".join(s["normalized"] for s in segs))

    def norm_to_raw(j):
        total = sum(len(s["normalized"]) for s in segs)
        if not isinstance(j, int) or j < 0 or j > total:
            return None
        for seg in segs:
            n0, n1 = seg["norm_span"]
            if n0 <= j <= n1:
                a, b = seg["raw_span"]
                rlen, nlen = b - a, n1 - n0
                if j == n1:
                    return b
                return a + (0 if nlen == 0 else int(round((j - n0) * rlen / nlen)))
        return len(raw)

    return {
        "raw": raw,
        "normalized": "".join(s["normalized"] for s in segs),
        "segments": segs,
        "map": [{"raw_span": s["raw_span"], "norm_span": s["norm_span"],
                 "protected": s["protected"], "kind": s["kind"]} for s in segs],
        "raw_to_norm": raw_to_norm,
        "norm_to_raw": norm_to_raw,
    }


def normalize_value(value, glossary=()):
    """递归规范化 str / list / dict；返回同结构，dict 只改 str 值。"""
    if isinstance(value, str):
        return normalize_text(value, glossary)["normalized"]
    if isinstance(value, list):
        return [normalize_value(v, glossary) for v in value]
    if isinstance(value, dict):
        return {k: normalize_value(v, glossary) for k, v in value.items()}
    return value


def _selftest():
    n = 0
    r = normalize_text("ＡＢＣ１２３ ｶﾀｶﾅ")
    assert r["normalized"] == "ABC123 カタカナ", r["normalized"]
    n += 1
    r = normalize_text("舊靑敎國圖")
    assert r["normalized"] == "旧青教国図", r["normalized"]
    n += 1
    r = normalize_text("行なう 表わす 現われ")
    assert r["normalized"] == "行う 表す 現れ", r["normalized"]
    n += 1
    r = normalize_text("DOI:10.1234/AbC_Def と JP21K12345 と ABC用語", glossary=["ABC用語"])
    assert "10.1234/AbC_Def" in r["normalized"], r["normalized"]
    assert "JP21K12345" in r["normalized"], r["normalized"]
    assert "ABC用語" in r["normalized"], r["normalized"]
    assert any(s["protected"] and s["kind"] == "doi" for s in r["segments"])
    assert any(s["protected"] and s["kind"] == "kakenhi" for s in r["segments"])
    assert any(s["protected"] and s["kind"] == "glossary" for s in r["segments"])
    n += 1
    # 双向映射：保护段精确；普通段端点对齐
    r = normalize_text("Ａ舊")
    assert r["raw_to_norm"](0) == 0 and r["raw_to_norm"](2) == 2, r["segments"]
    assert r["norm_to_raw"](0) == 0 and r["norm_to_raw"](2) == 2, r["segments"]
    n += 1
    r = normalize_text("行なう")
    assert r["raw_to_norm"](0) == 0 and r["raw_to_norm"](3) == 2, r["segments"]
    n += 1
    assert normalize_text("")["normalized"] == "", "empty"
    n += 1
    assert normalize_text("ABC")["normalized"] == "ABC"
    n += 1
    assert normalize_value({"a": ["Ａ", 1], "b": None}) == {"a": ["A", 1], "b": None}
    n += 1
    print("normalize selftest: %d/%d PASS" % (n, n))
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
