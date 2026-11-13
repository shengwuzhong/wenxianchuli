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


def _column_boundary_ja(unified_list, W, H=None, is_first_page=False, in_ref=False):
    """投票法为主；投票无结果时，在连续正文带内做左右分离的几何兜底。"""
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
    best = None
    start, stop = int(0.30 * W), int(0.70 * W)
    if len(body) >= 4:
        for x in range(start, stop + 1, 4):
            left = sum(1 for x0, x1 in body if x1 <= x)
            right = sum(1 for x0, x1 in body if x0 >= x)
            if left < 2 or right < 2:
                continue
            score = (min(left, right), left + right, -abs(x - W / 2.0))
            if best is None or score > best[0]:
                best = (score, x)
        if best:
            return best[1]

    # 几何兜底只使用正文带。首页前区以明确的正文节头为准，无节头时沿用前区底界。
    front_bottom = 0.0
    if is_first_page and H:
        front_bottom = _front_zone_bottom(unified_list, W, H, 1)
        for u in sorted(unified_list, key=lambda b: b["box"][1]):
            text = (u.get("main_text") or "").strip()
            if u["type"] == "Section-header" and re.match(
                    r"^(?:(?:[0-9０-９]+|[IVX]+)[.．、]?\s*)?(?:はじめに|緒言|序論|対象と方法|方法)",
                    re.sub(r"\s+", "", text)):
                # 明确节头只能把前区底界前移，避免固定比例排除起始正文块。
                front_bottom = min(front_bottom, u["box"][1])
                break

    candidates = []
    for u in unified_list:
        if u["type"] not in ("Text", "Footnote"):
            continue
        x0, y0, x1, y1 = u["box"]
        width = x1 - x0
        if width <= 0 or width > 0.60 * W:
            continue
        if x1 <= 0.08 * W or x0 >= 0.92 * W:
            continue
        if y0 < front_bottom:
            continue
        # OCR 有时把图/表下缩略语标成 Text；短且贴近所属图/表的块不进入正文带。
        picture_note = False
        if H and u["type"] == "Text":
            for pic in unified_list:
                if pic["type"] not in ("Picture", "Table"):
                    continue
                px0, py0, px1, py1 = pic["box"]
                height, pic_height = y1 - y0, py1 - py0
                if (py1 <= y0 and y0 - py1 <= max(2 * height, 0.05 * H)
                        and x0 >= px0 - 8 and x1 <= px1 + 8
                        and height <= 0.25 * pic_height):
                    picture_note = True
                    break
        if not picture_note:
            candidates.append(u)

    fallback = None
    for x in range(start, stop + 1, 4):
        left = [u for u in candidates if u["box"][2] <= x]
        right = [u for u in candidates if u["box"][0] >= x]
        if not any(u["type"] == "Text" for u in left) \
                or not any(u["type"] == "Text" for u in right):
            continue
        gap = min(u["box"][0] for u in right) - max(u["box"][2] for u in left)
        if gap < 20:
            continue
        # 左右块的 y 包络形成连续正文带；前区及跨线图表块不参与，也不要求全页划分。
        band_top = max(min(u["box"][1] for u in left), min(u["box"][1] for u in right))
        band_bottom = min(max(u["box"][3] for u in left), max(u["box"][3] for u in right))
        if band_bottom <= band_top:
            continue
        score = (gap, -abs(x - W / 2.0))
        if fallback is None or score > fallback[0]:
            fallback = (score, x)
    if fallback:
        return fallback[1]

    def pair_boundary(items, visual=False, align=False):
        """成员子块或图/表混排的保守判定：必须存在真实重叠的左右块对。"""
        best_pair = None
        for x in range(start, stop + 1, 4):
            left = [u for u in items if u["box"][2] <= x]
            right = [u for u in items if u["box"][0] >= x]
            if not left or not right:
                continue
            pairs = []
            for l in left:
                for r in right:
                    if min(l["box"][3], r["box"][3]) <= max(l["box"][1], r["box"][1]):
                        continue
                    types = {l["type"], r["type"]}
                    if visual:
                        if "Text" not in types or not types.intersection(("Picture", "Table")):
                            continue
                    elif l["type"] != "Text" or r["type"] != "Text":
                        continue
                    pairs.append((l, r))
            if not pairs:
                continue
            if align and not any(abs(l["box"][1] - r["box"][1]) <= 0.05 * H
                                 for l, r in pairs):
                continue
            gap = min(u["box"][0] for u in right) - max(u["box"][2] for u in left)
            if gap < 20:
                continue
            if visual:
                wrapped = False
                for l, r in pairs:
                    pic = l if l["type"] in ("Picture", "Table") else r
                    for w in unified_list:
                        if w["type"] not in ("Text", "Footnote"):
                            continue
                        wx0, wy0, wx1, wy1 = w["box"]
                        if (wx1 - wx0 > 0.60 * W and wy0 >= pic["box"][1]
                                and wy0 <= pic["box"][3] + 0.05 * H):
                            wrapped = True
                            break
                    if wrapped:
                        break
                if wrapped:
                    continue
            score = (gap, -abs(x - W / 2.0))
            if best_pair is None or score > best_pair[0]:
                best_pair = (score, x)
        return best_pair[1] if best_pair else None

    # OCR 合并的跨线 Text：优先使用各渠道 members 中保留的子块坐标恢复左右栏。
    recovered = list(candidates)
    for u in unified_list:
        if u["type"] not in ("Text", "Footnote"):
            continue
        ux0, uy0, ux1, uy1 = u["box"]
        if ux1 - ux0 <= 0.60 * W:
            continue
        for blocks in (u.get("members") or {}).values():
            for b in blocks:
                if b.get("cat") not in ("Text", "Footnote"):
                    continue
                box = b.get("box") or []
                if len(box) != 4:
                    continue
                x0, y0, x1, y1 = box
                if not (0 < x1 - x0 <= 0.60 * W):
                    continue
                if x1 <= 0.08 * W or x0 >= 0.92 * W or y0 < front_bottom:
                    continue
                recovered.append({"uid": u["uid"] + ":member", "type": b["cat"],
                                  "box": box, "main_text": b.get("text") or ""})
    boundary = pair_boundary(recovered, align=not in_ref)
    if boundary is not None:
        return boundary

    # 一栏正文、另一栏图/表：排除两侧均非 Text，以及浮图后的单栏绕排。
    visuals = list(candidates)
    for u in unified_list:
        if u["type"] not in ("Picture", "Table"):
            continue
        x0, y0, x1, y1 = u["box"]
        if (0 < x1 - x0 <= 0.60 * W and x1 > 0.08 * W and x0 < 0.92 * W
                and y0 >= front_bottom):
            visuals.append(u)
    boundary = pair_boundary(visuals, visual=True)
    if boundary is not None:
        return boundary

    # 无子块时只在文献页使用中线，且必须有多个行首编号或作者—年份证据。
    if in_ref:
        for u in unified_list:
            if u["type"] != "Text" or u["box"][2] - u["box"][0] <= 0.60 * W:
                continue
            text = u.get("main_text") or ""
            heads = re.findall(r"(?:^|\n)\s*(?:\d+\s*[)）]|[A-Z][A-Za-zÀ-ž'-]+,\s+[A-Z]\.)", text)
            years = re.findall(r"[，,]\s*(?:19|20)\d{2}[，,]", text)
            if len(heads) >= 2 or len(years) >= 2:
                return W / 2.0
    return None


def _iou(a, b):
    """两个 [x0,y0,x1,y1] 框的交并比。"""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _merge_sort_units(unified_list):
    """阅读序的排序单元: 优先取 mineru 子块, 无子块时退回块自身。

    layout 复刻的是 merge 阶段的排序, 而 merge 只对 mineru 块排序; unified 块常由多块
    合并而来, 直接用合并框排序会和 merge 差一截。子块选择先按与块框的 IoU>=0.5 过滤
    (排除同页重复/越界子块), 再取 IoU 最大者, 近似该块在 merge 里的起始单元。"""
    units = []
    for u in unified_list:
        members = [b for b in (u.get("members") or {}).get("mineru") or [] if b.get("box")]
        cat, box = u["type"], list(u["box"])
        if members:
            ub = [float(x) for x in u["box"][:4]]
            near = [b for b in members
                    if _iou(ub, [float(x) for x in b["box"][:4]]) >= 0.5] or members
            best = max(near, key=lambda b: (_iou(ub, [float(x) for x in b["box"][:4]]),
                                            -b["box"][1], -b["box"][0]))
            cat, box = best.get("cat") or cat, list(best["box"])
        units.append({"uid": u["uid"], "cat": cat, "box": box})
    return units


def _merge_boundary_ja(unified_list, W):
    """用各块的 mineru 子块复算 merge_out._column_boundary 的投票结果。

    阅读序必须与 merge 阶段同栏: merge 在 mineru 块上分不出栏的页面(单块占满一栏、
    图表为主的页面), 本函数的返回值为 None, 阅读序随之退回 y 序, 避免出现
    「左栏下段先于右栏上段」的块级反转。"""
    blocks = [{"cat": b.get("cat"), "box": b["box"]}
              for u in unified_list
              for b in (u.get("members") or {}).get("mineru") or [] if b.get("box")]
    if not blocks:
        return None
    body = []
    for b in blocks:
        if b["cat"] not in CONTENT_TYPES:
            continue
        x0, x1 = b["box"][0], b["box"][2]
        width = x1 - x0
        if width <= 0 or width > 0.60 * W:
            continue
        if x1 <= 0.08 * W or x0 >= 0.92 * W:
            continue
        body.append((x0, x1))
    if len(body) < 4:
        return None
    best = None
    for x in range(int(0.30 * W), int(0.70 * W) + 1, 4):
        left = sum(1 for x0, x1 in body if x1 <= x)
        right = sum(1 for x0, x1 in body if x0 >= x)
        if left < 2 or right < 2:
            continue
        score = (min(left, right), left + right, -abs(x - W / 2.0))
        if best is None or score > best[0]:
            best = (score, x)
    return best[1] if best else None


def _order_blocks_ja(unified_list, W, boundary):
    """复刻 merge_out.order_blocks 的阅读序(与 merge_out 对齐), 返回按序 uid 列表。

    双栏页: 跨栏/页眉页脚/脚注/宽块(>0.65W)按 y 保持原位(full), 正文块按
    「左栏 y 序 → 右栏 y 序」(body)。与 merge_out 的差别只有两处, 都是为了按 merge
    的排序单元对齐: ①用 mineru 子块坐标排序; ②full 块按 y 切成带, 带内先左栏后右栏
    (merge 的单队列法会被左栏靠下的小块堵住, 把右栏靠上的正文挤到图片之后)。
    单栏页: 纯 (y, x)。
    Section-header 非宽非跨栏时参与栏流(与 merge_out 一致, 旧逻辑把它全排最后是错的)。"""
    if not unified_list:
        return []
    units = _merge_sort_units(unified_list)
    has_members = any((u.get("members") or {}).get("mineru") for u in unified_list)
    # 阅读序的栏边界以 merge 阶段为准; 无 mineru 子块时才用本页检测结果。
    order_bnd = _merge_boundary_ja(unified_list, W) if has_members else boundary
    if order_bnd is None:
        return [b["uid"] for b in sorted(units, key=lambda b: (b["box"][1], b["box"][0]))]
    full, cols = [], [[], []]
    for b in units:
        x0, x1 = b["box"][0], b["box"][2]
        width = x1 - x0
        spans = x0 < order_bnd - 8 and x1 > order_bnd + 8
        if b["cat"] in ("Footnote", "Page-header", "Page-footer", "Page-number") \
                or width > 0.65 * W or spans:
            full.append(b)
        else:
            cols[0 if (x0 + x1) / 2.0 < order_bnd else 1].append(b)
    for c in cols:
        c.sort(key=lambda b: (b["box"][1], b["box"][0]))
    full.sort(key=lambda b: (b["box"][1], b["box"][0]))
    out, i0, i1 = [], 0, 0
    for f in full:
        fy = f["box"][1]
        while i0 < len(cols[0]) and cols[0][i0]["box"][1] < fy:
            out.append(cols[0][i0])
            i0 += 1
        while i1 < len(cols[1]) and cols[1][i1]["box"][1] < fy:
            out.append(cols[1][i1])
            i1 += 1
        out.append(f)
    out.extend(cols[0][i0:] + cols[1][i1:])
    return [b["uid"] for b in out]


def layout_page(unified_list, W, H, is_first_page=False, in_ref=False):
    """单页日文版面旁路: 栏检测 + 前区分区 + 阅读序。返回 (annotated_list, summary)。
    annotated_list 与输入同序, 每块追加 layout 标注(不新建/不删除块)。

    阅读序(reading_order)复刻 merge_out.order_blocks, 保证与 merge 阶段排序 0 反转。
    col/zone 作旁路标注: col 记栏号(full 跨栏块记 -1), zone 记前区/正文(仅首页)。"""
    boundary = _column_boundary_ja(unified_list, W, H, is_first_page=is_first_page, in_ref=in_ref)
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
        unified_list, s = layout_page(j["unified"], j["w"], j["h"], is_first_page=is_first,
                                      in_ref=bool(j.get("in_ref")))
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
    # 几何兜底：每栏仅 1 个 Text，x 分离、gap>=20 且 y 重叠。
    blocks3 = [
        {"uid": "left", "box": [100, 300, 600, 700], "type": "Text",
         "main_text": "左栏单块", "cross_page": {"role": None}},
        {"uid": "right", "box": [632, 320, 1132, 720], "type": "Text",
         "main_text": "右栏单块", "cross_page": {"role": None}},
    ]
    lst3, s3 = layout_page(blocks3, W, H, is_first_page=False)
    order3 = {u["uid"]: u["layout"]["reading_order"] for u in lst3}
    ok_fallback = s3["ncols"] == 2 and order3["left"] < order3["right"]
    # 跨栏图片把页面切成上下两带: 带内先左后右, 右栏上部块不得被压到图片之后。
    blocks4 = [
        {"uid": "l1", "box": [100, 100, 600, 300], "type": "Text",
         "main_text": "左栏上段", "cross_page": {"role": None}},
        {"uid": "r1", "box": [632, 100, 1132, 200], "type": "Text",
         "main_text": "右栏上段", "cross_page": {"role": None}},
        {"uid": "f", "box": [100, 400, 1132, 700], "type": "Picture",
         "main_text": "跨栏图", "cross_page": {"role": None}},
        {"uid": "l2", "box": [100, 720, 600, 900], "type": "Text",
         "main_text": "左栏下段", "cross_page": {"role": None}},
        {"uid": "r2", "box": [632, 720, 1132, 900], "type": "Text",
         "main_text": "右栏下段", "cross_page": {"role": None}},
    ]
    lst4, s4 = layout_page(blocks4, W, H, is_first_page=False)
    order4 = {u["uid"]: u["layout"]["reading_order"] for u in lst4}
    ok_band = (s4["ncols"] == 2 and order4["l1"] < order4["r1"] < order4["f"]
               < order4["l2"] < order4["r2"])
    ok = ok_cols and ok_order and ok_single and ok_fallback and ok_band
    print("layout_ja selftest: %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
