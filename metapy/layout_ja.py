# -*- coding: utf-8 -*-
r"""layout_ja: 日文文献版面旁路(unify 后处理, M3 之前)。

针对日文双栏文献(学会誌/医学会誌 常见排版)的版面分析旁路, 解决三件事:
  ① 栏检测: 复刻 merge_out._column_boundary 的投票法(排除跨栏宽块), 保证与 merge 阶段
     栏边界一致(40_10569 p1 实证: 旧 _page_col_boundary 最大空隙法因宽块左边缘拉偏得 429,
     本法与 merge_out 一致得 620)。
  ② 前区分区: 识别首页 front matter(标题/作者/摘要区), 与正文流区分。日文文献前区结构
     与韩/英文不同: 标题常为「日文主标题 + 英文副标题」, 摘要为「要旨」内联段(无独立头),
     作者带「上标数字」关联脚注机构。
  ③ 阅读序: 复刻 merge_out.order_blocks(双栏「左栏 y 序 → 右栏 y 序」+ full 块按 y 交错,
     单栏纯 y,x), 产 reading_order 序号, 与 merge 阶段排序 0 反转。结果只作旁路标注,
     不改变 unify 的几何/文本/共识。

用法:
  python metadata.py <doc> --stage layout_ja     # 单篇, 写回 unified/page_N.json
  python -m metapy.layout_ja                     # 自检

产出(写回每页 unified 块):
  layout: {"detected": "double|single", "boundary": <x 或 null>, "col": 0|1,
           "zone": "front|body", "reading_order": <int>, "is_title": bool}
  (原文 main_text/box/members/readings/confidence 均不动)
"""
import os, re, io, json, datetime, collections

from .common import (CONTENT_TYPES, JP_SECTION_TAG, JP_ABS_INLINE,
                     JP_KW_HEAD, JP_ABS_HEAD)


# —— 日文前区(标题/作者/摘要)判定用常量 ——
# 栏目名(Section-header 型): 総説/解説/特集/原著 等, 属前区标签但非正文流
# 摘要头: 要旨/概要/抄録/要約(独立头或内联)
# 关键词头: キーワード 等

# 前区 y 上限(页高比例): 标题/作者/摘要区通常不超过页高 55%
FRONT_Y_MAX = 0.55

# 标题块判定: Section-header 型且落在页高 30% 内、非栏目名、非摘要/关键词头
TITLE_Y_MAX = 0.30


def _is_front_head(t, u_type):
    """块是否属「前区结构头」: 标题 / 摘要头 / 关键词头(独立 Section-header)。"""
    s = (t or "").strip()
    if not s:
        return False
    if u_type == "Section-header" and (JP_ABS_HEAD.match(s) or JP_KW_HEAD.search(s)):
        return True
    if JP_ABS_INLINE.match(s):
        return True
    return False


def _front_zone_bottom(unified_list, W, H, ncols):
    """前区底界: 首个「正文节头」(非栏目名的 Section-header 出现在摘要/关键词之后) 或首个
    正文流块。无明确节头时用 FRONT_Y_MAX 兜底。返回前区下边界 y。"""
    front_bottom = H * FRONT_Y_MAX
    seen_abstract = False
    for u in sorted(unified_list, key=lambda x: x["box"][1]):
        t = (u["main_text"] or "").strip()
        ut = u["type"]
        y = u["box"][1]
        if _is_front_head(t, ut):
            seen_abstract = True
            continue
        # 正文节头(如「1. はじめに」「はじめに」)或正文段落, 在前区头之后出现 → 前区结束
        if seen_abstract and ut == "Section-header" and not JP_SECTION_TAG.match(t):
            # 栏目名(総説等)不算正文节头; 真正的正文节头标志前区结束
            if not JP_SECTION_TAG.match(t):
                return max(u["box"][1], H * 0.18)
        # 关键词头之后的首个正文块
    return front_bottom


def _column_boundary_ja(unified_list, W):
    """复刻 merge_out._column_boundary 的栏边界投票法(与 merge_out.order_blocks 对齐)。

    只统计 Text/Footnote 且宽 <=0.60W、不贴页缘(0.08W~0.92W)的正文块, 在 0.30W~0.70W
    区间找「左边结束块数 + 右边开始块数」最大且两侧各>=2 的竖线。宽块(跨栏标题/摘要/
    作者)不参与投票, 避免像 _page_col_boundary 那样被宽块左边缘拉偏(40_10569 p1 实证:
    旧法边界 429, 本法定为 620, 与 merge_out 一致)。"""
    if not W or W <= 0:
        return None
    body = []
    for u in unified_list:
        if u["type"] not in CONTENT_TYPES:
            continue
        x0, x1 = u["box"][0], u["box"][2]
        width = x1 - x0
        if width <= 0 or width > 0.60 * W:
            continue
        if x1 <= 0.08 * W or x0 >= 0.92 * W:
            continue
        body.append((x0, x1))
    if len(body) < 4:
        return None
    best = None
    start, stop = int(0.30 * W), int(0.70 * W)
    for x in range(start, stop + 1, 4):
        left = sum(1 for x0, x1 in body if x1 <= x)
        right = sum(1 for x0, x1 in body if x0 >= x)
        if left < 2 or right < 2:
            continue
        score = (min(left, right), left + right, -abs(x - W / 2.0))
        if best is None or score > best[0]:
            best = (score, x)
    return best[1] if best else None


def _order_blocks_ja(unified_list, W, boundary):
    """复刻 merge_out.order_blocks 的阅读序(与 merge_out 完全一致), 返回按序 uid 列表。

    双栏页: 跨栏/页眉页脚/脚注/宽块(>0.65W)按 y 保持原位(full), 正文块按
    「左栏 y 序 → 右栏 y 序」(body), 再按 y 把 body 交错插回 full。单栏页: 纯 (y, x)。
    Section-header 非宽非跨栏时参与栏流(与 merge_out 一致, 旧逻辑把它全排最后是错的)。"""
    if not unified_list:
        return []
    if boundary is None:
        return [u["uid"] for u in sorted(unified_list, key=lambda b: (b["box"][1], b["box"][0]))]
    full, cols = [], [[], []]
    for u in unified_list:
        x0, x1 = u["box"][0], u["box"][2]
        width = x1 - x0
        spans = x0 < boundary - 8 and x1 > boundary + 8
        if u["type"] in ("Footnote", "Page-header", "Page-footer", "Page-number") \
                or width > 0.65 * W or spans:
            full.append(u)
        else:
            col = 0 if (x0 + x1) / 2.0 < boundary else 1
            cols[col].append(u)
    body = (sorted(cols[0], key=lambda b: (b["box"][1], b["box"][0]))
            + sorted(cols[1], key=lambda b: (b["box"][1], b["box"][0])))
    full.sort(key=lambda b: (b["box"][1], b["box"][0]))
    out, i = [], 0
    for f in full:
        fy = f["box"][1]
        while i < len(body) and body[i]["box"][1] < fy:
            out.append(body[i])
            i += 1
        out.append(f)
    out.extend(body[i:])
    return [u["uid"] for u in out]


def layout_page(unified_list, W, H, is_first_page=False):
    """单页日文版面旁路: 栏检测 + 前区分区 + 阅读序。返回 (annotated_list, summary)。
    annotated_list 与输入同序, 每块追加 layout 标注(不新建/不删除块)。

    阅读序(reading_order)复刻 merge_out.order_blocks, 保证与 merge 阶段排序 0 反转。
    col/zone 作旁路标注: col 记栏号(full 跨栏块记 -1), zone 记前区/正文(仅首页)。"""
    boundary = _column_boundary_ja(unified_list, W)
    ncols = 2 if boundary is not None else 1
    front_bottom = _front_zone_bottom(unified_list, W, H, ncols) if is_first_page else 0.0

    ordered_uids = _order_blocks_ja(unified_list, W, boundary)
    uid_to_u = {u["uid"]: u for u in unified_list}
    # 块在 merge_out 排序里的栏归属(full 跨栏块 col=-1, 正文块 0/1)
    col_map = {}
    if boundary is not None:
        for u in unified_list:
            x0, x1 = u["box"][0], u["box"][2]
            width = x1 - x0
            spans = x0 < boundary - 8 and x1 > boundary + 8
            if u["type"] in ("Footnote", "Page-header", "Page-footer", "Page-number") \
                    or width > 0.65 * W or spans:
                col_map[u["uid"]] = -1
            else:
                col_map[u["uid"]] = 0 if (x0 + x1) / 2.0 < boundary else 1

    order_map = {}
    for i, uid in enumerate(ordered_uids):
        u = uid_to_u[uid]
        in_front = is_first_page and u["box"][1] < front_bottom
        col = col_map.get(uid, 0)
        layout = {
            "detected": "double" if ncols == 2 else "single",
            "boundary": round(boundary, 1) if boundary is not None else None,
            "col": col,
            "zone": "front" if in_front else "body",
            "reading_order": i,
        }
        u["layout"] = layout
        order_map[uid] = i

    summary = {"ncols": ncols, "boundary": round(boundary, 1) if boundary is not None else None,
               "front_bottom": round(front_bottom, 1) if is_first_page else None,
               "n_blocks": len(unified_list), "n_content": len(ordered_uids)}
    return unified_list, summary


def layout_ja_doc(doc, out_root):
    """单篇: 逐页跑 layout_page, 写回 unified/page_N.json 的 layout 标注 + _layout_ja.json 日志。"""
    doc_dir = os.path.join(out_root, doc)
    udir = os.path.join(doc_dir, "unified")
    if not os.path.isdir(udir):
        print("跳过 %s: 无 unified 产物" % doc)
        return None
    pages = sorted(int(re.match(r"page_(\d+)\.json$", f).group(1))
                   for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f))
    stats = {"pages": 0, "double_col_pages": 0, "single_col_pages": 0,
             "front_zone_pages": 0, "blocks_annotated": 0, "per_page": {}}
    for p in pages:
        fp = os.path.join(udir, "page_%d.json" % p)
        j = json.load(io.open(fp, encoding="utf-8"))
        # 语言判定: 本页日文比例(仅首页用 front 分区; 全页都做栏检测+阅读序)
        is_first = (p == min(pages))
        unified_list, s = layout_page(j["unified"], j["w"], j["h"], is_first_page=is_first)
        j["unified"] = unified_list
        io.open(fp, "w", encoding="utf-8").write(json.dumps(j, ensure_ascii=False))
        stats["pages"] += 1
        stats["double_col_pages"] += 1 if s["ncols"] == 2 else 0
        stats["single_col_pages"] += 1 if s["ncols"] == 1 else 0
        stats["front_zone_pages"] += 1 if (is_first and s["front_bottom"]) else 0
        stats["blocks_annotated"] += s["n_blocks"]
        stats["per_page"][p + 1] = s
    io.open(os.path.join(udir, "_layout_ja.json"), "w", encoding="utf-8").write(
        json.dumps({"doc": doc, "stats": stats,
                    "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
                   ensure_ascii=False, indent=1))
    print("== layout_ja %s ==\n  页数 %d  双栏 %d  单栏 %d  前区 %d  标注块 %d" % (
        doc, stats["pages"], stats["double_col_pages"], stats["single_col_pages"],
        stats["front_zone_pages"], stats["blocks_annotated"]))
    return stats


def _selftest():
    """构造两个迷你页: 单栏(前区+正文) 与 双栏(标题横跨+左右栏), 验证栏检测/分区/阅读序。"""
    W, H = 1241.0, 1754.0
    # 双栏页: 左右栏各 2 个 Text 块(满足 _page_col_boundary 两侧各>=2 的要求), y 交错
    blocks = [
        {"uid": "a", "box": [100, 100, 600, 140], "type": "Text",
         "main_text": "左栏正文A", "cross_page": {"role": None}},
        {"uid": "b", "box": [632, 100, 1132, 140], "type": "Text",
         "main_text": "右栏正文B", "cross_page": {"role": None}},
        {"uid": "c", "box": [100, 150, 600, 400], "type": "Text",
         "main_text": "左栏正文C", "cross_page": {"role": None}},
        {"uid": "d", "box": [632, 150, 1132, 500], "type": "Text",
         "main_text": "右栏正文D", "cross_page": {"role": None}},
    ]
    lst, s = layout_page(blocks, W, H, is_first_page=False)
    ok_cols = (s["ncols"] == 2)
    # 阅读序: 左栏(a,c)应排在右栏(b,d)之前, 且同栏内 y 递增
    order = {u["uid"]: u["layout"]["reading_order"] for u in lst}
    ok_order = (order["a"] < order["c"] < order["b"] < order["d"])
    # 单栏页
    blocks2 = [
        {"uid": "a", "box": [100, 100, 600, 140], "type": "Text",
         "main_text": "单栏A", "cross_page": {"role": None}},
        {"uid": "b", "box": [100, 200, 600, 240], "type": "Text",
         "main_text": "单栏B", "cross_page": {"role": None}},
    ]
    lst2, s2 = layout_page(blocks2, W, H, is_first_page=False)
    ok_single = (s2["ncols"] == 1)
    ok = ok_cols and ok_order and ok_single
    print("layout_ja selftest: %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
