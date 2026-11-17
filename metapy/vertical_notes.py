# -*- coding: utf-8 -*-
"""竖排脚注/尾注候选。

只收集有明确注记标记的块：
  Footnote 类型、注N、※、＊、〔注〕、（注）、註
不强行生成 references；古典文学论文常无标准参考文献表。
"""
import io
import json
import os
import re

NOTE = re.compile(r"^\s*(?:注\s*[0-9一二三四五六七八九十百]+|註\s*[0-9一二三四五六七八九十百]+|"
                  r"※|＊|\*|〔注〕|（注）|\(注\))")
NOTE_TYPES = {"Footnote"}


def _text(u):
    return str(u.get("main_text") or u.get("text") or "").strip()


def _box(u):
    b = u.get("box") or [0, 0, 0, 0]
    return float(b[0]), float(b[1]), float(b[2]), float(b[3])


def collect(doc, out_root, max_pages=None):
    udir = os.path.join(out_root, doc, "unified")
    if not os.path.isdir(udir):
        return []
    files = sorted((f for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f)),
                   key=lambda f: int(re.search(r"\d+", f).group(0)))
    out = []
    for fn in files[:max_pages] if max_pages else files:
        pno = int(re.search(r"\d+", fn).group(0)) + 1
        try:
            page = json.load(io.open(os.path.join(udir, fn), encoding="utf-8-sig"))
        except Exception:
            continue
        H = float(page.get("h") or 1)
        for u in page.get("unified") or []:
            t = _text(u)
            if not t:
                continue
            typ = u.get("type")
            marked = bool(NOTE.search(t))
            if typ not in NOTE_TYPES and not marked:
                continue
            x0, y0, x1, y1 = _box(u)
            # 页脚/低位置优先；明确注记不限位置
            score = 2.0 if marked else 1.0
            if y0 >= 0.75 * H:
                score += 1.0
            if typ == "Footnote":
                score += 1.0
            out.append({"page": pno, "uid": u.get("uid"), "type": typ,
                        "text": t[:500], "score": score})
    # 去重（跨渠道合并后 uid 已唯一，此处防重复扫描）
    seen = set()
    uniq = []
    for r in sorted(out, key=lambda x: (-x["score"], x["page"], x["uid"] or "")):
        k = (r["page"], r["uid"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def _selftest():
    pages = {"unified": [
        {"uid": "n1", "type": "Text", "box": [100, 900, 500, 980],
         "main_text": "注1 これは注記である。"},
        {"uid": "b1", "type": "Text", "box": [100, 200, 500, 300],
         "main_text": "本文。"},
    ], "w": 1000, "h": 1200}
    # 用临时文件验证收集逻辑
    import tempfile, shutil
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "d", "unified")
        os.makedirs(d)
        io.open(os.path.join(d, "page_0.json"), "w", encoding="utf-8").write(
            json.dumps(pages, ensure_ascii=False))
        rows = collect("d", root)
        assert len(rows) == 1 and rows[0]["uid"] == "n1", rows
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("vertical_notes selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
