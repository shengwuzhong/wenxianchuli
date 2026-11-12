# -*- coding: utf-8 -*-
import os, re, io, json, datetime
import regress
from .common import *


# 作者行信号(英题下 front-matter 里需跳过的行): 罗马拼音锚「名 (Roman)」或上标 marker '^{*}'
_AUTHOR_ROW = re.compile(
    r"[（(][A-Za-z .\-']+[)）]|\^\{[\*\d,，]+\}|\*\s*\{[^}]*\}|<sup>")


def _is_en_abstract_start(s, u):
    """英题下无 Abstract 头的英文摘要开头判定(2026-11-11 扩展日文, 52_230302 实证):
    纯英文长句(≥40 折叠字符, 拉丁为主)、非作者行(无罗马锚/上标)、非关键词/标题/节头行,
    且块为 Text 型(非 Footnote/Section-header)。用于摘要不以 This study/In this 引导的形态。"""
    s = (s or "").strip()
    if not s or u["type"] != "Text":
        return False
    if KW_LINE.match(s) or ABS_HEAD_EN.match(s) or regress.REF_HEAD.search(s):
        return False
    if _AUTHOR_ROW.search(s):
        return False
    if _hangul_ratio(s) > 0.2 or _japanese_ratio(s) > 0.15:
        return False   # 非英文(含韩/日文)不出
    return len(_fold(s)) >= 40 and bool(re.search(r"[A-Za-z]{4,}", s))


def _collect_abstract(pdata, pages, head_u, max_pages=3, skip_fold=None):
    """从头块之下收集摘要正文(跨页续接, 遇 Keywords 行/新节头/文献区 即止)。
    跨栏块按行取: 若块首在头上方, 只取 ABSTRACT_START 之后的行(13625974 作者行同块形态)。
    skip_fold: 折叠全等的节头视为英文题名的尾页复写(1892171/1632041 形态), 跳过不停。"""
    out_lines = []
    uids = []
    start_p = head_u["page"] - 1
    H = pdata[start_p]["h"]
    limit_bottom = head_u["box"][3] + 0.62 * H
    for p in range(start_p, min(len(pages), start_p + max_pages)):
        j = pdata[p]
        for u in j["unified"]:
            if u.get("cross_page", {}).get("role") == "head":
                continue
            if u["type"] in ("Page-header", "Page-footer", "Page-number", "Footnote"):
                continue
            if u["type"] == "Section-header" and u["uid"] != head_u["uid"] \
                    and u["box"][1] >= head_u["box"][3] - 2 \
                    and not (skip_fold and _fold((u["main_text"] or "").split("\n")[0]) == skip_fold):
                return "\n".join(out_lines).strip(), uids   # 区内新节头=界(先判停, 其行不入摘要)
            if u["type"] == "Section-header" and regress.REF_HEAD.search(u["main_text"] or ""):
                return "\n".join(out_lines).strip(), uids
            y1, y3 = u["box"][1], u["box"][3]
            lines = (u["main_text"] or "").split("\n")
            take = []
            if p == start_p and y1 < head_u["box"][3] - 2 and y3 > head_u["box"][3]:
                started = False
                for ln in lines:
                    if ABSTRACT_START.match(ln.strip()):
                        started = True
                    if started:
                        take.append(ln)
            elif y1 >= head_u["box"][3] - 2 or p > start_p:
                if p == start_p and y1 >= limit_bottom:
                    continue
                take = list(lines)
            stop = False
            for ln in take:
                s = ln.strip()
                if not s:
                    continue
                if re.match(r"(?i)^abstract\s*[:：]", s):
                    s = re.split(r"[:：]", s, maxsplit=1)[1].strip()   # 'Abstract: …' 标签剥离
                    if not s:
                        continue
                if skip_fold and _fold(s) == skip_fold:
                    continue   # 块内首行的题名复写
                if re.match(r"^-\s*[A-Z][A-Za-z .\-']{3,40}\s*-$", s):
                    continue   # 尾页罗马拼音作者行(如 '- Yoo Jae Choon -')
                if len(s) < 70 and re.match(r"^[A-Z]", s):
                    _parts = re.split(r"\s*·\s*|\s*,\s*|\s+and\s+", s)
                    if len(_parts) >= 2 and all(re.match(r"^[A-Z][A-Za-z .\-']+$", p.strip())
                                                for p in _parts if p.strip()):
                        continue   # 罗马化作者行('Kim, Jin-Kyoung · Cho, Young-Il')
                if KW_LINE.match(s):
                    stop = True
                    break
                if re.match(r"(?i)^abstract$", s):
                    stop = True   # 独行 Abstract 小标签(13625974 尾)
                    break
                if re.match(r"^\s*(참고\s*문헌|인용\s*문헌|参考文献|References|REFERENCES|Bibliography|参\s*考\s*文\s*献|引\s*用\s*文\s*献)\s*$",
                            s, re.I):
                    stop = True   # 文献区头(行级全等; 摘要内 '선행문헌' 类词不误触; 2026-11-11 增日文)
                    break
                out_lines.append(s)
            if take and u["uid"] not in uids:
                uids.append(u["uid"])
            if stop:
                return "\n".join(out_lines).strip(), uids
    return "\n".join(out_lines).strip(), uids

def _collect_jp_inline(pdata, pages, blk, li):
    """日文内联摘要头「要旨：…」收集(2026-11-12 T-20261112-WB-ABS): 从定位到的
    「要旨：」行起收集摘要正文, 至 Keywords/新节头/文献区/跨页续接外止。返回 (txt, uids)。

    与 _collect_abstract 的差异: 内联头可出现在块内非首行(43_10814 作者行后空行接「要旨：…」),
    也可能带「【目的】/【方法】/【結果】/【結論】」结构词(40_10569/43_10814 实证)。值来自原文切片。
    """
    lines = []
    uids = [blk["uid"]]
    # 头行本身: 「要旨：【目的】…」→ 取冒号后内容(含【目的】标签, 不剥离)
    first = (blk["main_text"] or "").split("\n")[li]
    first_rest = re.split(r"[:：]", first, maxsplit=1)
    if len(first_rest) > 1 and first_rest[1].strip():
        lines.append(first_rest[1].strip())
    # 同块后续行: 至 Keywords/另一个摘要头/HTML 表格标签 止
    for ln in (blk["main_text"] or "").split("\n")[li + 1:]:
        s = ln.strip()
        if not s:
            continue
        if KW_LINE.match(s) or JP_ABS_INLINE.match(s):
            break
        if s.startswith("<table") or s.startswith("<"):
            break   # 表格 HTML 标签(OCR 把图表并入摘要块, 40_10569/42_93 实证), 不属摘要正文
        lines.append(s)
    # 日文「要旨」摘要恒在首页完整块内结束(结构词【結論】即末), 不做跨页续接——
    # 跨页会把正文/表格卷进来(43_10814/40_10569 实证)。
    return "\n".join(x for x in lines if x).strip(), uids


def _collect_jp_headingless(pdata, pages, title_block):
    """日文无头摘要(2026-11-12 T-20261112-WB-ABS): 无独立「要旨」头、无内联「要旨：」时,
    在标题/作者/机构区之后取首页首个「日文正文长段」作为摘要(5_55 序言式摘要形态)。

    判定信号: 块为 Text 型、日文比例高、折叠长度达标、位于标题块下方、且未到 Keywords/正文节头。
    返回 (txt, uids, head_u)。无法判定返回 (None, [], None)。值来自原文切片, 不改写。
    """
    j0 = pdata[0]
    H = j0["h"]
    W = j0["w"]
    title_bottom = title_block["box"][3] if title_block is not None else 0.0
    # 下界: 首页 Keywords 行 / 英文摘要头 的位置。摘要恒在 Keywords 之前;
    # 若首页已有英文摘要头(ABS_HEAD_EN)或 Keywords, 则该文为英文摘要文献, 无头日文摘要
    # 候选块必须位于 keywords_y 上方(52_230725 实证: 英文摘要+Keywords 之后才是日文正文, 不应误判)。
    kw_y = None
    en_abs_present = False
    for u in sorted(j0["unified"], key=lambda x: x["box"][1]):
        t = (u["main_text"] or "").strip()
        if u["type"] == "Section-header" and ABS_HEAD_EN.match(t):
            en_abs_present = True
        for ln in (u["main_text"] or "").split("\n"):
            if KW_LINE.match(ln.strip()):
                if kw_y is None or u["box"][1] < kw_y:
                    kw_y = u["box"][1]
    # 首页已有英文摘要头 → 该文以英文摘要为主, 不强行造日文无头摘要
    if en_abs_present:
        return None, [], None
    # 首页正文流块候选(按 y 升序): Text 型, 位于标题区下方、Keywords 行上方
    cands = []
    for u in sorted(j0["unified"], key=lambda x: x["box"][1]):
        if u.get("cross_page", {}).get("role"):
            continue
        if u["type"] != "Text":
            continue
        if u["box"][1] < title_bottom - 4:
            continue
        if kw_y is not None and u["box"][1] >= kw_y:
            continue
        cands.append(u)
    # 逐块找首个「日文长段」: 跳过作者行(含上标 marker)、机构行、关键词行
    for u in cands:
        t = (u["main_text"] or "").strip()
        if not t:
            continue
        first = t.split("\n")[0].strip()
        # 跳过关键词/节头/文献区头
        if KW_LINE.match(first) or JP_ABS_INLINE.match(first) or JP_KW_HEAD.match(first):
            continue
        if regress.REF_HEAD.search(first):
            continue
        # 跳过作者行(罗马锚/上标 marker/纯人名)与机构行
        if _AUTHOR_ROW.search(first):
            continue
        if re.match(r"^\$\s*\^", first) or MARKER_LINE.match(first):
            continue
        # 日文比例高且长度达标 → 判为摘要首段
        if _japanese_ratio(first) > 0.15 and len(_fold(first)) >= 40:
            # 从该行起收集, 至该块末尾(同块后续行), 停于 Keywords
            lines = []
            for ln in t.split("\n"):
                s = ln.strip()
                if not s:
                    continue
                if KW_LINE.match(s) or JP_ABS_INLINE.match(s):
                    break
                lines.append(s)
            txt = "\n".join(lines).strip()
            if txt:
                return txt, [u["uid"]], u
    return None, [], None


def abstract_doc(doc, out_root):
    """单篇③: 韩英双摘要定位(首页优先, 英文摘要缺则检索尾页文献区后残余区域——regress
    ref_region 遇 Abstract 截断已证明此形态存在)。尾页英文 matter 顺带供给 title_en 兜底与
    罗马化作者名。产出 metadata.json abstract/abstract_en/keywords。"""
    doc_dir = os.path.join(out_root, doc)
    udir = os.path.join(doc_dir, "unified")
    if not os.path.isdir(udir):
        print("跳过 %s: 无 unified 产物" % doc)
        return None
    pages = sorted(int(re.match(r"page_(\d+)\.json$", f).group(1))
                   for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f))
    pdata = {p: json.load(io.open(os.path.join(udir, "page_%d.json" % p), encoding="utf-8"))
             for p in pages}
    umap = {u["uid"]: u for p in pages for u in pdata[p]["unified"]}

    def _find_head(pat, page_list):
        for p in page_list:
            for u in pdata[p]["unified"]:
                if u.get("cross_page", {}).get("role"):
                    continue
                t = (u["main_text"] or "").strip()
                if "\n" in t:
                    t = t.split("\n")[0].strip()
                if pat.match(t):
                    return u
        return None

    def _conf(u, uids):
        lv = "high"
        basis = []
        us = [umap[x] for x in (uids or []) if x in umap]
        if u is not None and u["review"]:
            lv = "mid" if u["confidence"]["level"] != "low" else "low"
            basis.append("头块级%s" % u["confidence"]["level"])
        rev = sum(1 for x in us if x["review"])
        if us and rev > len(us) / 2:
            lv = "mid" if lv == "high" else lv
            basis.append("正文块过半复检")
        # (2026-11-12) 未定位到摘要头且无正文块时, 值为空属「原文无/未抽」, 不标 high(否则审计误判为可靠)
        if u is None and not us:
            lv = "empty"
            basis = basis or ["未定位摘要头"]
        return {"level": lv, "basis": "; ".join(basis) or "界限干净",
                "source": "regex", "uid_head": u and u["uid"]}

    res = {}
    # —— 摘要(2026-11-11 扩展日文; 2026-11-12 T-20261112-WB-ABS 补内联/无头): ——
    # 日文「要旨/概要/抄録/要約」与韩文 요약 同归 abstract 字段。三级查找:
    #   ① 独立头(要旨 独行) ② 内联头(要旨：…) ③ 无头首段(序言式摘要)。
    #   韩文路径(独立头 ABS_HEAD_KO / 内联 ABS_INLINE_KO)保持原语义不变。
    h_ko = _find_head(ABS_HEAD_KO, [0])
    h_jp = _find_head(JP_ABS_HEAD, [0]) if h_ko is None else None
    if h_ko is not None or h_jp is not None:
        head = h_ko or h_jp
        # 韩/日摘限首页(首页摘要不跨页; 跨页续接会把正文卷进来——1892171 实况)
        txt, uids = _collect_abstract(pdata, [0], head, max_pages=1)
        res["abstract"] = {"value": txt or None, "page": 1, "box": head["box"],
                           "confidence": _conf(head, uids)}
    else:
        # ② 内联头: 韩文(요약：) 或 日文(要旨：/【目的】), 遍历首页各块各行(含块内非首行)
        found = None
        jp_found = None
        for u in pdata[0]["unified"]:
            if u.get("cross_page", {}).get("role"):
                continue
            if u["type"] in ("Page-header", "Page-footer", "Page-number"):
                continue
            lns = (u["main_text"] or "").split("\n")
            for i, ln in enumerate(lns):
                if JP_ABS_INLINE.match(ln.strip()):
                    jp_found = (u, i)
                    break
                if found is None and ABS_INLINE_KO.match(ln.strip()):
                    found = (u, i)
            if jp_found or found:
                break
        if jp_found:
            # 日文内联「要旨：…」(40_10569/43_10814/42_93 形态)
            blk, li = jp_found
            txt, uids = _collect_jp_inline(pdata, pages, blk, li)
            res["abstract"] = {"value": txt or None, "page": 1, "box": blk["box"],
                               "confidence": _conf(blk, uids)}
        elif found:
            # 韩文内联「요약：…」(895567 形态, 原逻辑)
            blk, li = found
            first_rest = re.split(r"[:：]", (blk["main_text"] or "").split("\n")[li], maxsplit=1)
            lines = [first_rest[1].strip()] if len(first_rest) > 1 and first_rest[1].strip() else []
            stop = False
            for ln in (blk["main_text"] or "").split("\n")[li + 1:]:
                s = ln.strip()
                if not s:
                    continue
                if KW_LINE.match(s) or ABS_INLINE_KO.match(s):
                    stop = True
                    break
                lines.append(s)
            stop = False
            for p in range(1, min(3, len(pages))):
                for u in pdata[p]["unified"]:
                    if u.get("cross_page", {}).get("role"):
                        continue
                    if u["type"] in ("Page-header", "Page-footer", "Page-number", "Footnote"):
                        continue
                    if u["type"] == "Section-header":
                        stop = True
                        break
                    for ln in (u["main_text"] or "").split("\n"):
                        if KW_LINE.match(ln.strip()) or ABS_INLINE_KO.match(ln.strip()):
                            stop = True
                            break
                        lines.append(ln.strip())
                    if stop:
                        break
                if stop:
                    break
            res["abstract"] = {"value": "\n".join(l for l in lines if l).strip() or None,
                               "page": 1, "box": blk["box"],
                               "confidence": {"level": "mid", "basis": "内联 요약 头(与Key words同块)",
                                              "source": "regex", "uid_head": blk["uid"]}}
        else:
            # ③ 无头首段: 日文文献序言式摘要(5_55 形态, 无「要旨」头), 仅当首页确为日文时尝试
            j0 = pdata[0]
            jp_full = "".join((u["main_text"] or "") for u in j0["unified"])
            title_block = _find_head(ABS_HEAD_EN, [0]) or _find_head(JP_ABS_HEAD, [0])
            if _japanese_ratio(jp_full) > 0.05 and _hangul_ratio(jp_full) < 0.1:
                # 用 layout_ja 的 front zone 或标题块定位: 优先取标题块(日文主标题 Section-header)
                if title_block is None:
                    # 日文主标题: 首页首个非栏目名的 Section-header
                    for u in sorted(j0["unified"], key=lambda x: x["box"][1]):
                        if u["type"] == "Section-header" and not JP_SECTION_TAG.match(
                                (u["main_text"] or "").strip()) and not JP_ABS_HEAD.match(
                                (u["main_text"] or "").strip()):
                            title_block = u
                            break
                txt, uids, head_u = _collect_jp_headingless(pdata, pages, title_block)
                if txt:
                    res["abstract"] = {"value": txt, "page": 1, "box": head_u["box"],
                                       "confidence": {"level": "mid",
                                                      "basis": "无头首段(序言式摘要, 标题/作者后取至Keywords)",
                                                      "source": "regex", "uid_head": head_u["uid"]}}
                else:
                    res["abstract"] = {"value": None, "confidence": _conf(None, [])}
            else:
                res["abstract"] = {"value": None, "confidence": _conf(None, [])}
    # —— 英摘要: 首页 → 全文档倒序检索(英文摘要可能位于文末参考文献区之后/之内——
    #    regress ref_region 遇 Abstract 截断已证明此形态; 1892171 '< ABSTRACT >' 在文献区尾) ——
    h_en = _find_head(ABS_HEAD_EN, [0])
    tail = None
    if h_en is None:
        h_en = _find_head(ABS_HEAD_EN, list(reversed(pages[1:])))
        if h_en is not None:
            tail = h_en["page"]
    # —— 英摘要取值: 首页 Abstract 头 → 英题下无头形态(作者行下取至 Keywords) ——
    meta0 = json.load(io.open(os.path.join(doc_dir, "metadata.json"), encoding="utf-8"))         if os.path.exists(os.path.join(doc_dir, "metadata.json")) else {}
    ten_fold = _fold(((meta0.get("title_en") or {}).get("value") or ""))
    # 尾页英文题名预探(h_en 之下的首个英文节头/长英文行): 其折叠值供收集时跳过题名复写
    if h_en is not None and h_en["page"] - 1 > 0:
        hp = h_en["page"] - 1
        for u in sorted(pdata[hp]["unified"], key=lambda x: x["box"][1]):
            if u.get("cross_page", {}).get("role"):
                continue
            if u["box"][1] <= h_en["box"][3]:
                continue
            if u["type"] not in ("Section-header", "Text"):
                continue
            first = (u["main_text"] or "").split("\n")[0].strip()
            if len(_fold(first)) >= 15 and _hangul_ratio(first) < 0.2 \
               and not KW_LINE.match(first) and not ABS_HEAD_EN.match(first):
                ten_fold = ten_fold or _fold(first)
                break
    if h_en is not None:
        txt, uids = _collect_abstract(pdata, pages, h_en, skip_fold=ten_fold or None)
        res["abstract_en"] = {"value": txt or None, "page": h_en["page"], "box": h_en["box"],
                              "from_tail": bool(tail),
                              "confidence": _conf(h_en, uids)}
    else:
        ten = (meta0.get("title_en") or {})
        if (ten.get("page") or 1) == 1 and ten.get("uid") in umap:
            blk = umap[ten["uid"]]
            lines = []
            started = False
            stop = False
            for p in range(0, min(3, len(pages))):
                for u in pdata[p]["unified"]:
                    if u.get("cross_page", {}).get("role"):
                        continue
                    if u["type"] in ("Page-header", "Page-footer", "Page-number"):
                        continue
                    if p == 0 and u["box"][1] < blk["box"][3] - 4 and u["uid"] != blk["uid"]:
                        continue
                    seg = (u["main_text"] or "").split(chr(10))
                    for ln in seg:
                        s = ln.strip()
                        # (2026-11-11) 跳过英题块内的标题行与作者行: 标题行折叠等于 title_en,
                        # 作者行含罗马拼音锚「名(Roman)」或上标 marker '^{*}'。
                        if _fold(s) == ten_fold or _AUTHOR_ROW.search(s):
                            continue
                        if not started:
                            if ABSTRACT_START.match(s):
                                started = True
                                if re.match(r"(?i)^abstract\s*[:：]", s):
                                    s = re.split(r"[:：]", s, maxsplit=1)[1].strip()
                                    if not s:
                                        continue
                            # (2026-11-11 扩展) 日文/国际期刊英文摘要无引导词('The identification
                            # of light elements…' 不以 This study/In this 开头, 52_230302 实证):
                            # 英题块之后, 跳过作者行(罗马拼音锚/上标 marker), 首个纯英文长句起即摘要。
                            elif _is_en_abstract_start(s, u):
                                started = True
                            else:
                                continue
                        if KW_LINE.match(s):
                            stop = True
                            break
                        if re.match(r"(?i)^abstract$", s):
                            stop = True
                            break
                        if u["type"] != "Footnote":
                            lines.append(s)
                    if stop:
                        break
                if stop:
                    break
            txt = chr(10).join(l for l in lines if l).strip()
            if txt:
                res["abstract_en"] = {"value": txt, "page": 1, "box": blk["box"],
                                      "from_tail": False,
                                      "confidence": {"level": "mid",
                                                     "basis": "英题下无 Abstract 头, 作者行下取至 Keywords",
                                                     "source": "regex", "uid_head": blk["uid"]}}
    if "abstract_en" not in res:
        res["abstract_en"] = {"value": None, "from_tail": False, "confidence": _conf(None, [])}
    # —— 尾页英文 matter 顺带: title_en 兜底 + 罗马化作者 ——
    meta_fp = os.path.join(doc_dir, "metadata.json")
    meta = json.load(io.open(meta_fp, encoding="utf-8")) if os.path.exists(meta_fp) else {}
    tail_title_en = None
    tail_roman = []
    # (2026-11-11 扩展日文) 无 Abstract 头的尾页英文 front-matter(5_55 形态: 英文标题/作者/摘要/关键词
    # 整体后置到文末, 无 Abstract 标签): 倒序检索尾页英文 Section-header 作为 title_en, 并顺带提取
    # 其下方英文作者行(罗马拼音)。
    if h_en is None and not (meta.get("title_en") or {}).get("value"):
        for p in reversed(pages[1:]):
            jp = pdata[p]
            secs = [u for u in jp["unified"]
                    if u.get("type") == "Section-header"
                    and not u.get("cross_page", {}).get("role")]
            for u in secs:
                first = (u["main_text"] or "").split("\n")[0].strip()
                if len(_fold(first)) >= 15 and _hangul_ratio(first) < 0.2 \
                   and _japanese_ratio(first) < 0.1 and not KW_LINE.match(first) \
                   and not ABS_HEAD_EN.match(first) and not regress.REF_HEAD.search(first):
                    tail_title_en = {"value": first, "page": p + 1, "box": u["box"], "uid": u["uid"]}
                    # 英文标题下方首个英文作者行(罗马拼音, 逗号分隔)
                    below = sorted([x for x in jp["unified"]
                                    if not x.get("cross_page", {}).get("role")
                                    and x["box"][1] > u["box"][3]
                                    and x["type"] in ("Text",)],
                                   key=lambda x: x["box"][1])
                    _abstract_lines = []
                    _saw_author = False
                    for x in below:
                        t = (x["main_text"] or "").strip()
                        if not t:
                            continue
                        if KW_LINE.match(t.split("\n")[0].strip()):
                            break
                        seg = t.split("\n")[0]
                        if not _saw_author and _hangul_ratio(seg) < 0.2 and _japanese_ratio(seg) < 0.1 \
                           and re.search(r"[A-Z][a-z]+", seg) and "$" in seg:
                            # 剥离 LaTeX 上标, 取英文名
                            seg_clean = re.sub(r"\$\s*\^\{[^}]*\}\s*\$", "", seg)
                            parts = re.split(r"\s*,\s*|\s+and\s+", seg_clean)
                            rn = [q.strip() for q in parts
                                  if re.match(r"^[A-Z][A-Za-z .\-']+$", q.strip())]
                            if len(rn) >= 2:
                                tail_roman = rn
                                _saw_author = True
                            continue
                        # 机构行(以 '$ ^{n} $' 上标开头或纯机构词)跳过; 其余英文长段即摘要正文
                        if re.match(r"^\$\s*\^", seg):
                            continue
                        if _hangul_ratio(seg) < 0.2 and _japanese_ratio(seg) < 0.1 \
                           and len(_fold(seg)) >= 40:
                            _abstract_lines.append(seg)
                    if _abstract_lines:
                        res["abstract_en"] = {"value": "\n".join(_abstract_lines),
                                              "page": p + 1, "box": u["box"], "from_tail": True,
                                              "confidence": {"level": "mid",
                                                             "basis": "尾页英文 matter 无 Abstract 头, 作者/机构行下取至 Keywords",
                                                             "source": "regex", "uid_head": u["uid"]}}
                    break
            if tail_title_en is not None:
                break
    if h_en is not None and h_en["page"] - 1 > 0:
        hp = h_en["page"] - 1
        below = [u for u in pdata[hp]["unified"]
                 if not u.get("cross_page", {}).get("role")
                 and u["box"][1] > h_en["box"][3]
                 and u["type"] in ("Section-header", "Text")]
        below.sort(key=lambda u: u["box"][1])
        for u in below[:3]:
            t = (u["main_text"] or "").strip()
            if not t:
                continue
            first = t.split("\n")[0].strip()
            if tail_title_en is None and (u["type"] == "Section-header" or _hangul_ratio(first) < 0.2) \
               and len(_fold(first)) >= 15 and not KW_LINE.match(first) \
               and not ABS_HEAD_EN.match(first):
                tail_title_en = {"value": first, "page": hp + 1, "box": u["box"], "uid": u["uid"]}
            for ln in t.split("\n"):
                m = re.match(r"^-\s*([A-Z][A-Za-z .\-']{3,40})\s*-$", ln.strip())
                if m:
                    tail_roman.append(m.group(1).strip())
    # keywords 行(顺带)
    kws = []
    for p in pages:
        if p > 2 and not res["abstract_en"].get("from_tail"):
            break
        for u in pdata[p]["unified"]:
            for ln in (u["main_text"] or "").split("\n"):
                if KW_LINE.match(ln.strip()):
                    kws.append(ln.strip())
    res["keywords_lines"] = kws[:4]
    # 成品清洗: 剥粘入的 running 脚/URL 行(1892171 韩摘尾 'www.kci.go.kr' 实证)
    doc_heads = _doc_heads(pdata, pages)
    for k in ("abstract", "abstract_en"):
        v = (res[k] or {}).get("value")
        if v:
            cleaned, _ = _clean_lines(v, (), doc_heads)
            res[k]["value"] = cleaned.strip() or v
    # §38 分层: confidence.basis → audit; 产品 confidence 只留 {level, source, uid_head}
    abs_audit = {}
    for k in ("abstract", "abstract_en"):
        c = (res[k] or {}).get("confidence") or {}
        abs_audit[k] = {"basis": c.get("basis")}
        res[k]["confidence"] = {"level": c.get("level"), "source": c.get("source"),
                                "uid_head": c.get("uid_head")}
    meta.pop("tail_english_matter", None)   # 遗留诊断键清理(§38 已迁 audit)
    meta.update({"doc": doc,
                 "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "abstract": res["abstract"], "abstract_en": res["abstract_en"],
                 "keywords_lines": res["keywords_lines"]})
    if tail_title_en is not None and not (meta.get("title_en") or {}).get("value"):
        meta.setdefault("title_en", {})
        meta["title_en"].update({"value": tail_title_en["value"], "page": tail_title_en["page"],
                                 "box": tail_title_en["box"], "uid": tail_title_en["uid"],
                                 "confidence": {"level": "mid", "source": "tail_matter"}})
        if tail_roman and meta.get("authors"):
            ko_authors = [a for a in meta["authors"] if a.get("name")]
            if len(tail_roman) == len(ko_authors):
                for a, r in zip(ko_authors, tail_roman):
                    a["roman"] = a.get("roman") or r
        abs_audit["title_en"] = {"basis": "尾页英文 matter 供给"}
        abs_audit["tail_english_matter"] = {"title_en": tail_title_en, "roman_authors": tail_roman}
    io.open(meta_fp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    audit = load_audit(doc_dir)
    audit.update(dict({"doc": doc}, **abs_audit))
    save_audit(doc_dir, audit)
    print("== ③ %s ==" % doc)
    for k in ("abstract", "abstract_en"):
        v = res[k]["value"]
        print("  %-11s: p%-3s from_tail=%s len=%-5s %s" % (
            k, res[k].get("page", "-"), res[k].get("from_tail", "-"),
            len(v or ""), (v or "(无)")[:60].replace("\n", " ")))
    if tail_title_en:
        print("  tail title_en: %s" % tail_title_en["value"][:64])
    if tail_roman:
        print("  tail roman   : %s" % "; ".join(tail_roman))
    return meta


def _selftest():
    """离线冒烟: 摘要边界与英题下无头路径; 只写临时目录。"""
    import hashlib
    import shutil
    import tempfile

    head = {"uid": "h", "page": 1, "type": "Section-header", "box": [0, 10, 100, 20],
            "main_text": "Abstract", "cross_page": {}}
    body = {"uid": "b", "page": 1, "type": "Text", "box": [0, 30, 100, 50],
            "main_text": "This study is complete.", "cross_page": {}}
    kw = {"uid": "k", "page": 1, "type": "Text", "box": [0, 60, 100, 80],
          "main_text": "Keywords: alpha, beta", "cross_page": {}}
    text, uids = _collect_abstract({0: {"h": 1000, "unified": [head, body, kw]}}, [0], head,
                                   max_pages=1)
    ok1 = text == "This study is complete." and uids == ["b", "k"]

    tmp = tempfile.mkdtemp()
    try:
        doc_dir = os.path.join(tmp, "d")
        udir = os.path.join(doc_dir, "unified")
        os.makedirs(udir)
        title = {"uid": "t", "page": 1, "type": "Section-header", "box": [0, 100, 500, 140],
                 "main_text": "English Title", "cross_page": {}}
        block = {"uid": "b", "page": 1, "type": "Text", "box": [0, 160, 500, 220],
                 "main_text": "Abstract: This study answers.\nKeywords: alpha, beta",
                 "cross_page": {}}
        page = {"w": 1000, "h": 1000, "unified": [title, block]}
        page_fp = os.path.join(udir, "page_0.json")
        io.open(page_fp, "w", encoding="utf-8").write(json.dumps(page, ensure_ascii=False))
        before = hashlib.sha256(io.open(page_fp, "rb").read()).hexdigest()
        io.open(os.path.join(doc_dir, "metadata.json"), "w", encoding="utf-8").write(json.dumps(
            {"doc": "d", "title_en": {"value": "English Title", "page": 1, "uid": "t"}},
            ensure_ascii=False))
        meta = abstract_doc("d", tmp)
        audit = load_audit(doc_dir)
        ok2 = (meta["abstract_en"]["value"] == "This study answers."
               and meta["abstract_en"]["confidence"]["uid_head"] == "t"
               and meta["keywords_lines"] == ["Keywords: alpha, beta"]
               and audit["abstract_en"]["basis"] == "英题下无 Abstract 头, 作者行下取至 Keywords"
               and hashlib.sha256(io.open(page_fp, "rb").read()).hexdigest() == before)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # 3) 日文/国际期刊无引导词英文摘要(52_230302 形态): 英题块内混标题+作者行(罗马锚/上标),
    #    摘要以 'The identification of light elements…' 开头(非 This study/In this), 需跳过标题+作者行
    tmp = tempfile.mkdtemp()
    try:
        doc_dir = os.path.join(tmp, "d")
        udir = os.path.join(doc_dir, "unified")
        os.makedirs(udir)
        ten_block = {"uid": "t", "page": 1, "type": "Text", "box": [0, 100, 500, 180],
                     "main_text": "Neutron diffraction experiments of iron hydride\n"
                                  "森 悠一郎(Yuichiro MORI)  ^{*}\n鍵 裕之(Hiroyuki KAGI)  ^{*}",
                     "cross_page": {}}
        abs_block = {"uid": "b", "page": 1, "type": "Text", "box": [0, 190, 500, 260],
                     "main_text": "The identification of light elements in the Earth's core has been "
                                  "an open question for more than 50 years.",
                     "cross_page": {}}
        kw_block = {"uid": "k", "page": 1, "type": "Text", "box": [0, 270, 500, 300],
                    "main_text": "Keywords: Neutron diffraction, High pressure", "cross_page": {}}
        page = {"w": 1000, "h": 1000, "unified": [ten_block, abs_block, kw_block]}
        io.open(os.path.join(udir, "page_0.json"), "w", encoding="utf-8").write(
            json.dumps(page, ensure_ascii=False))
        io.open(os.path.join(doc_dir, "metadata.json"), "w", encoding="utf-8").write(json.dumps(
            {"doc": "d", "title_en": {"value": "Neutron diffraction experiments of iron hydride",
                                      "page": 1, "uid": "t"}}, ensure_ascii=False))
        meta = abstract_doc("d", tmp)
        v = meta["abstract_en"]["value"] or ""
        ok3 = v.startswith("The identification of light elements") \
            and "森 悠一郎" not in v and "Neutron diffraction experiments" not in v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for i, ok in enumerate((ok1, ok2, ok3), 1):
        if not ok:
            print("FAIL [abs case %d]" % i)
    print("abs selftest: %d/3 PASS" % (ok1 + ok2 + ok3))
    return ok1 and ok2 and ok3


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
