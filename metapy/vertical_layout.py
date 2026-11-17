# -*- coding: utf-8 -*-
"""竖排日文页面的检测与阅读序。

只处理页面块（unified units 或 merged blocks），不改 unify 的几何/文本。
判定依据：高而窄的正文块占比 + 多列 x 分布 + 页高比例。

阅读序：
  列从右到左（x1 降序）
  列内从上到下（y0 升序）
  页眉/页脚/页码等 furniture 单独处理
"""
import re

FURNITURE = {"Page-header", "Page-footer", "Page-number"}
BODY = {"Text", "Section-header", "Caption", "Table", "Picture",
        "Footnote", "List", "Formula"}


def _box(u):
    b = u.get("box") or []
    if not isinstance(b, (list, tuple)) or len(b) < 4:
        return 0.0, 0.0, 0.0, 0.0
    try:
        return float(b[0]), float(b[1]), float(b[2]), float(b[3])
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0, 0.0


def _type(u):
    return u.get("type") or u.get("cat") or ""


def _is_tall(u, H):
    x0, y0, x1, y1 = _box(u)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return False
    if h < 0.12 * H:
        return False
    return h >= 1.6 * w


def _content(units):
    return [u for u in units
            if _type(u) not in FURNITURE and _type(u) in BODY]


def _group_columns(units):
    """按 x 区间分组；返回 [[unit...], ...]，组内不排序。"""
    items = []
    for u in units:
        x0, _y0, x1, _y1 = _box(u)
        items.append((x0, x1, u))
    if not items:
        return []
    items.sort(key=lambda t: (t[0], t[1]))
    groups = []
    for x0, x1, u in items:
        placed = False
        for g in groups:
            gx0, gx1 = g["x0"], g["x1"]
            overlap = min(x1, gx1) - max(x0, gx0)
            if overlap > 0.4 * min(x1 - x0, gx1 - gx0):
                g["x0"] = min(gx0, x0)
                g["x1"] = max(gx1, x1)
                g["units"].append(u)
                placed = True
                break
        if not placed:
            groups.append({"x0": x0, "x1": x1, "units": [u]})
    return [g["units"] for g in groups]


def detect_page(units, W, H):
    """返回 {vertical, confidence, tall_ratio, columns, body_n}。"""
    body = _content(units)
    if not body or not W or not H:
        return {"vertical": False, "confidence": 0.0,
                "tall_ratio": 0.0, "columns": 0, "body_n": len(body)}
    tall = [u for u in body if _is_tall(u, H)]
    ratio = len(tall) / float(len(body))
    cols = _group_columns(body)
    # 竖排典型：正文多数为高窄列，且不少于 2 列；横排页通常 tall 比例低。
    vertical = (ratio >= 0.45 and len(tall) >= 3 and len(cols) >= 2)
    # 单列竖排兜底：极窄页面/题名页，正文块很高
    if not vertical and len(body) <= 2 and len(tall) == len(body) \
            and any((_box(u)[3] - _box(u)[1]) > 0.5 * H for u in tall):
        vertical = True
    conf = 0.0
    if vertical:
        conf = min(0.98, 0.55 + 0.35 * ratio + 0.02 * min(len(cols), 6))
    return {"vertical": vertical, "confidence": round(conf, 2),
            "tall_ratio": round(ratio, 2), "columns": len(cols),
            "body_n": len(body)}


def order_units(units, W, H):
    """返回 (ordered_units, info)。

    横向：保持 (y0, x0) 排序。
    竖排：正文列从右到左；列内 y0；furniture 放末尾。
    """
    info = detect_page(units, W, H)
    if not units:
        return [], info
    if not info["vertical"]:
        ordered = sorted(units, key=lambda u: (_box(u)[1], _box(u)[0]))
        return ordered, info

    body = _content(units)
    furniture = [u for u in units if u not in body]
    cols = _group_columns(body)
    cols.sort(key=lambda c: -max(_box(u)[2] for u in c))
    ordered = []
    for col in cols:
        ordered.extend(sorted(col, key=lambda u: (_box(u)[1], _box(u)[0])))
    # 页眉/页脚/页码放末尾，避免被当成题名/正文
    furniture.sort(key=lambda u: (_box(u)[1], _box(u)[0]))
    ordered.extend(furniture)
    info["order"] = [u.get("uid") for u in ordered]
    return ordered, info


def first_content(ordered):
    for u in ordered:
        if _type(u) not in FURNITURE:
            return u
    return None


def _selftest():
    # 01 第 1 页真实块的简化 fixture
    units = [
        {"uid": "p", "type": "Page-number", "box": [95, 116, 126, 136], "main_text": "226"},
        {"uid": "body1", "type": "Text", "box": [303, 154, 454, 1097], "main_text": "本文"},
        {"uid": "body2", "type": "Text", "box": [246, 191, 298, 993], "main_text": "本文2"},
        {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702],
         "main_text": "『月詣和歌集』所載西行歌本文小考"},
        {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053],
         "main_text": "犬井善壽"},
        {"uid": "page2", "type": "Page-number", "box": [90, 1108, 102, 1125], "main_text": "1"},
    ]
    info = detect_page(units, 793, 1192)
    assert info["vertical"] and info["confidence"] > 0.5, info
    ordered, info = order_units(units, 793, 1192)
    assert first_content(ordered)["uid"] == "title", [u["uid"] for u in ordered]
    assert [u["uid"] for u in ordered][:3] == ["title", "author", "body1"]
    # 横向页：宽块，不应判竖排
    wide = [{"uid": "w%d" % i, "type": "Text",
             "box": [80, 150 + i * 120, 1100, 210 + i * 120], "main_text": "x"}
            for i in range(4)]
    assert not detect_page(wide, 1200, 1600)["vertical"]
    print("vertical_layout selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
