# -*- coding: utf-8 -*-
"""竖排引文候选 -> 参考文献/前掲链接。

只处理 citation_spans 中 source=vertical_cspan 的候选：
  - 注N：按注记编号匹配 references
  - 前掲/同書/ibid：继承上一条已链接引文
不伪造未匹配的链接。
"""
import copy
import re

_NUM = re.compile(r"注\s*([0-9〇一二三四五六七八九十百千]+)")
_KAN = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNIT = {"十": 10, "百": 100, "千": 1000}


def jpnum(s):
    """'二七'/'二十七'/'一〇' -> int；纯数字直接转。"""
    s = str(s or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if all(ch in _KAN for ch in s):
        return int("".join(str(_KAN[ch]) for ch in s))
    total = 0
    section = 0
    for ch in s:
        if ch in _KAN:
            section = _KAN[ch]
        elif ch in _UNIT:
            if section == 0:
                section = 1
            total += section * _UNIT[ch]
            section = 0
        else:
            return None
    return total + section


def _ref_num(r):
    n = r.get("num")
    if n is None:
        m = _NUM.search(str(r.get("raw") or ""))
        return jpnum(m.group(1)) if m else None
    if isinstance(n, int):
        return n
    return jpnum(str(n)) if not str(n).isdigit() else int(n)


def link_doc(meta):
    out = copy.deepcopy(meta)
    refs = out.get("references") or []
    by_num = {}
    for i, r in enumerate(refs):
        n = _ref_num(r)
        if n is not None:
            by_num.setdefault(n, i)
    spans = out.get("citation_spans") or []
    linked = 0
    prev = None
    for s in spans:
        if s.get("linked_refs"):
            prev = s
            continue
        ct = str(s.get("citation_text") or "")
        if re.search(r"(?:前掲|同書|ibid|op\.?\s*cit)", ct, re.I) and prev:
            s["linked_refs"] = copy.deepcopy(prev.get("linked_refs") or [])
            s["resolve_method"] = "ibid"
            s["resolve_confidence"] = "partial"
            linked += 1
            prev = s
            continue
        m = _NUM.search(ct)
        if m:
            n = jpnum(m.group(1))
            if n in by_num:
                i = by_num[n]
                r = refs[i]
                s["linked_refs"] = [{"index": i, "num": r.get("num"), "uid": r.get("uid")}]
                s["resolve_method"] = "note_number"
                s["resolve_confidence"] = "exact"
                linked += 1
                prev = s
                continue
        s["resolve_note"] = "no_matching_ref"
    out["citation_spans"] = spans
    out["citation_link"] = {"total": len(spans), "linked": linked,
                            "by_note": len(by_num)}
    return out, linked


def _selftest():
    meta = {"references": [{"num": 1, "title": "A", "uid": "r1"},
                           {"num": 27, "title": "B", "uid": "r2"}],
            "citation_spans": [
                {"citation_text": "注一", "linked_refs": []},
                {"citation_text": "前掲", "linked_refs": []},
                {"citation_text": "注二七", "linked_refs": []},
            ]}
    out, n = link_doc(meta)
    assert n == 3, out
    assert out["citation_spans"][0]["linked_refs"][0]["uid"] == "r1"
    assert out["citation_spans"][1]["resolve_method"] == "ibid"
    assert out["citation_spans"][2]["linked_refs"][0]["uid"] == "r2"
    assert jpnum("二十七") == 27 and jpnum("一〇") == 10
    print("vertical_cite_link selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
