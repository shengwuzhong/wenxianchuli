# -*- coding: utf-8 -*-
r"""layout_ja: 日文文献版面旁路(unify 后处理, M3 之前)。

针对日文双栏文献(学会誌/医学会誌 常见排版)的版面分析旁路, 解决三件事:
  ① 栏检测: 复用 _page_col_boundary 的页栏判定, 并针对日文「左栏窄右栏宽」「标题横跨双栏」
     等形态增强(栏边界取内容块左边缘最大空隙, 而非固定页宽中点)。
  ② 前区分区: 识别首页 front matter(标题/作者/摘要区), 与正文流区分。日文文献前区结构
     与韩/英文不同: 标题常为「日文主标题 + 英文副标题」, 摘要为「要旨」内联段(无独立头),
     作者带「上标数字」关联脚注机构。
  ③ 阅读序: 双栏页按「左栏自上而下 → 右栏自上而下」重排块序列, 产 reading_order 序号;
     单栏页按 y 递增。结果只作旁路标注, 不改变 unify 的几何/文本/共识。

用法:
  python metadata.py <doc> --stage layout_ja     # 单篇, 写回 unified/page_N.json
  python -m metapy.layout_ja                     # 自检

产出(写回每页 unified 块):
  layout: {"detected": "double|single", "boundary": <x 或 null>, "col": 0|1,
           "zone": "front|body", "reading_order": <int>, "is_title": bool}
  (原文 main_text/box/members/readings/confidence 均不动)
"""
import os, re, io, json, datetime, collections

from .common import (ROOT, CONTENT_TYPES, STRUCT_TYPES, TERM,
                     _fold, _content_blocks, _is_margin, _page_col_boundary,
                     _col_of_b, _japanese_ratio, JP_SECTION_TAG, JP_ABS_INLINE,
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


def _detect_cols(unified_list, W):
    """页栏判定(增强): 优先用 _page_col_boundary(左边缘最大空隙法), 失败时退回页宽中点双栏试探。
    返回 (boundary_x, ncols)。boundary_x=None 表示单栏。"""
    b = _page_col_boundary({"w": W, "unified": unified_list})
    if b is not None:
        return b, 2
    # 退回: 若内容块中心明显分居页宽两侧(且两侧各有块), 判双栏, 边界取中点
    cxs = [(u["box"][0] + u["box"][2]) / 2.0 for u in _content_blocks(unified_list, W)]
    if len(cxs) >= 4:
        mid = W / 2.0
        n_left = sum(1 for x in cxs if x < mid)
        n_right = len(cxs) - n_left
        if n_left >= 2 and n_right >= 2 and (max(cxs) - min(cxs)) > 0.40 * W:
            return mid, 2
    return None, 1


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


def layout_page(unified_list, W, H, is_first_page=False):
    """单页日文版面旁路: 栏检测 + 前区分区 + 阅读序。返回 (annotated_list, summary)。
    annotated_list 与输入同序, 每块追加 layout 标注(不新建/不删除块)。"""
    boundary, ncols = _detect_cols(unified_list, W)
    front_bottom = _front_zone_bottom(unified_list, W, H, ncols) if is_first_page else 0.0

    # 内容块(参与阅读序)与结构块(页眉/页脚/页码)分离
    content = _content_blocks(unified_list, W)
    content_ids = {u["uid"] for u in content}

    # 阅读序: 三段式。
    # ① 前区块(front matter, 仅首页): 标题/作者/摘要, 按 y 自然序, 恒排最前。
    # ② 正文流块(Text/Footnote): 双栏按「左栏自上而下 → 右栏自上而下」, 单栏按 y。
    # ③ 其余块(Section-header/Picture/Page-header/Page-footer/Page-number 等):
    #    不参与栏切分(标题/图表常横跨双栏), 按 y 排序附在正文流之后。
    def _rank(u):
        uid = u["uid"]
        y0, y1, x0, x2 = u["box"][1], u["box"][3], u["box"][0], u["box"][2]
        in_front = is_first_page and y0 < front_bottom and uid in content_ids
        if in_front:
            return (0, round(y0), round(x0))
        if uid in content_ids:
            if ncols == 2 and boundary is not None:
                col = _col_of_b(u, boundary, W)
                return (1, col, round(y0), round(x0))
            return (1, 0, round(y0), round(x0))
        return (2, round(y0), round(x0))

    ordered = sorted(unified_list, key=_rank)

    # 回写 layout 标注
    order_map = {}
    for i, u in enumerate(ordered):
        in_front = is_first_page and u["box"][1] < front_bottom and u["uid"] in content_ids
        col = _col_of_b(u, boundary, W) if (ncols == 2 and boundary is not None
                                            and u["uid"] in content_ids and not in_front) else 0
        layout = {
            "detected": "double" if ncols == 2 else "single",
            "boundary": round(boundary, 1) if boundary is not None else None,
            "col": col,
            "zone": "front" if in_front else "body",
            "reading_order": i,
        }
        u["layout"] = layout
        order_map[u["uid"]] = i

    summary = {"ncols": ncols, "boundary": round(boundary, 1) if boundary is not None else None,
               "front_bottom": round(front_bottom, 1) if is_first_page else None,
               "n_blocks": len(unified_list), "n_content": len(content)}
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
