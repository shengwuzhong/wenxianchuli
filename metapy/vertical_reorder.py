# -*- coding: utf-8 -*-
"""把竖排统一层按正确阅读序重排。

在 unify 之后运行，直接重写 unified/page_N.json 的 `unified` 列表；
不改 unify.py，只改生成物顺序，并写 vertical_layout 审计字段。
"""
import io
import json
import os
import re

from .vertical_layout import detect_page, order_units


def reorder_doc(doc, out_root):
    udir = os.path.join(out_root, doc, "unified")
    if not os.path.isdir(udir):
        return {"pages": 0, "reversed": 0}
    files = [f for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f)]
    files.sort(key=lambda f: int(re.search(r"\d+", f).group(0)))
    pages = 0
    reversed_pages = 0
    for fn in files:
        fp = os.path.join(udir, fn)
        try:
            page = json.load(io.open(fp, encoding="utf-8-sig"))
        except Exception:
            continue
        units = page.get("unified") or []
        if not units:
            continue
        info = detect_page(units, page.get("w"), page.get("h"))
        if not info.get("vertical"):
            continue
        ordered, info = order_units(units, page.get("w"), page.get("h"))
        page["unified"] = ordered
        page["vertical_layout"] = {
            "vertical": True,
            "confidence": info.get("confidence"),
            "columns": info.get("columns"),
            "reordered": True,
        }
        tmp = fp + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(page, ensure_ascii=False, indent=1))
        os.replace(tmp, fp)
        pages += 1
        reversed_pages += 1
    return {"pages": pages, "reordered": reversed_pages}


def _selftest():
    import tempfile
    import shutil
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "d", "unified")
        os.makedirs(d)
        page = {"w": 793, "h": 1192, "unified": [
            {"uid": "body", "type": "Text", "box": [303, 154, 454, 1097], "main_text": "b"},
            {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702], "main_text": "t"},
            {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053], "main_text": "a"},
        ]}
        io.open(os.path.join(d, "page_0.json"), "w", encoding="utf-8").write(
            json.dumps(page, ensure_ascii=False))
        r = reorder_doc("d", root)
        assert r["reordered"] == 1, r
        out = json.load(io.open(os.path.join(d, "page_0.json"), encoding="utf-8"))
        assert [u["uid"] for u in out["unified"]][:2] == ["title", "author"], out
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("vertical_reorder selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
