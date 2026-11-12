# -*- coding: utf-8 -*-
import os, re, io, json, datetime
from .common import *



def _pick_title(j, want_hangul, want_japanese=False):
    """打分制选标题(禁单取 max 字号): Section-header 权重最高 + 垂直位置 + 宽度占比 + 排除词典
    (차례/요약/Keywords…) + running 头(顶部带且命中 doc_heads 者)排除。
    want_hangul=True 选韩文题; want_japanese=True 选日文题(仮名+汉字); 两者皆假则选英文题。
    (2026-11-11 扩展日文: 日文标题含仮名, 原 _hangul_ratio 会把其归到英文题名, 现按脚本分流。)"""
    H = float(j["h"])
    best, bs = None, -1.0
    for u in j["unified"]:
        if u.get("cross_page", {}).get("role"):
            continue
        if u["type"] in ("Page-header", "Page-footer", "Page-number"):
            continue
        t = (u["main_text"] or "").strip()
        if not t:
            continue
        if t.startswith("<") and "<table" in t:
            continue   # 目录表格(1892171 TOC) 不参与题名
        t = t.split("\n")[0].strip()   # 多行块取首行(英题名+韩作者行同块的 1892171 形态)
        f = _fold(t)
        if not (10 <= len(f) <= 220):
            continue
        y1 = u["box"][1] / H
        if not (TITLE_ZONE[0] <= y1 <= (TITLE_ZONE[1] if (want_hangul or want_japanese) else TITLE_EN_ZONE[1])):
            continue
        hr = _hangul_ratio(t)
        jr = _japanese_ratio(t)
        if want_japanese:
            # 日文题: 须含仮名且非韩文
            if jr < 0.1 or hr >= 0.3:
                continue
        elif want_hangul:
            if hr < 0.3:
                continue
        else:
            # 英文题: 排除韩文、日文仮名与 CJK 汉字(纯汉字日文名如'古市真木雄'既非谚文也非仮名,
            # 误归英文题会导致 title_en 被作者行污染 — 5_55 实证)
            if hr > 0.35 or jr > 0.1 or re.search(u"[一-鿿々〆]", t):
                continue
        first = t.strip()[:12]
        if HEAD_EXCLUDE.match(t.strip()) or HEAD_EXCLUDE.match(first):
            continue
        if u["type"] == "Section-header" and t in (u2["main_text"] or "" for u2 in j["unified"]
                                                   if u2["type"] == "Page-header"):
            continue   # 与页眉完全同文的 '标题' 是 running 头复写(防 1892171 误判)
        score = 0.0
        score += 3.0 if u["type"] == "Section-header" else 1.0
        score += min(2.0, (u["box"][2] - u["box"][0]) / j["w"] * 3)
        score += 2.0 - abs(y1 - 0.20) * 4     # 垂直位置因子(页 10%-45% 最佳)
        score += min(1.5, len(f) / 80.0)
        if score > bs:
            best, bs = u, score
    return best

def _parse_author_line(line, u, foot_affil):
    """作者行解析: 上标集合化(*/**/***/†/‡/¹²/LaTeX $^{1)}$ 全归一) + 机构剥离 + 职称/角色词剥离
    + 括号内罗马拼音硬锚 + OCR 粘连名(홍영식서울교육대학교)按机构词表切开。
    返回 [(name, markers, affiliation, role, roman)]。
    (2026-11-11 扩展日文: 全角/半角括号内罗马拼音锚「森 悠一郎(Yuichiro MORI)」;
     日文名=汉字+仮名, 不再要求纯谚文音节。)"""
    line = (line or "").strip()
    if not line:
        return []
    # (2026-11-11 修复) 英文行判定: 含 CJK 汉字(日文纯汉字名如'古市真木雄'无仮名)也应走非英文分支,
    # 否则全角逗号'，'分隔失效。韩文谚文/日文仮名/中日韩汉字任一存在即非英文行。
    en_line = (_hangul_ratio(line) < 0.2 and _japanese_ratio(line) < 0.1
               and not re.search(u"[一-鿿々〆]", line))
    line = DEGREE.sub("", line)
    line = line.strip(" ·•,․")
    if not line:
        return []
    out = []
    # (2026-11-11 修复日文) LaTeX 上标 '$ ^{1,2} $' 内逗号会干扰切分: 先用占位符包裹上标,
    # 切分后再从占位符恢复 markers, 兼顾「名'，'名」的全角逗号分层与 marker 保留。
    _sup_ph = []
    def _hide_sup(m):
        _sup_ph.append(m.group(1))
        return u"\ue000%d\ue001" % (len(_sup_ph) - 1)
    line = SUP_LATEX.sub(_hide_sup, line)
    # 英文行逗号分层; 韩/日文行 ·•․、全角逗号'，' 与'逗号+名'分层(英文逗号多为机构内分隔)
    if en_line:
        toks = re.split(r"\s*,\s*|\s+and\s+", line)
    else:
        # (2026-11-12 修复日文) 日文作者行以「空格+上标 marker」分隔多位作者(40_10569 实证:
        # '本田 省二 $ ^{1)} $ 徳永 誠 …'), 上标占位符\ue000N\ue001 即作者间分隔点。
        # 先按占位符+其它分隔符切分(占位符用捕获组保留), 再配对「作者名→marker」, 不再把整行合并成一个 name。
        # (5_55 实证: '古市真木雄 $^{1,2}$，和賀巌 $^{*1,2,3}$，…' 全角逗号+上标; 去掉 ',\\s+' 重叠分支避免 re.split 产 None)
        toks = re.split(u"(\ue000\\d+\ue001)|[·•․，]|\\s+,\\s+", line)
    pending_mk = None   # (2026-11-12) 上标占位符 split 成独立 token 时, 后置挂接到上一个作者的 markers
    for tk in toks:
        if not tk:
            continue   # re.split 相邻分隔会产生 None/空串
        tk = tk.strip()
        if not tk:
            continue
        # 占位符 token(作者名后的上标): 挂到上一个作者名(日文语义: '本田 省二 $^{1)} $ 徳永 誠…')
        if re.fullmatch(u"\ue000\\d+\ue001", tk):
            if pending_mk is not None:
                pending_mk.append(_sup_ph[int(re.match(u"\ue000(\\d+)\ue001", tk).group(1))])
            continue
        tk = re.sub(r"^(?:and|&)\s+", "", tk)
        # 从占位符恢复 markers 并剥离上标
        mk = [m for m in re.findall(u"\ue000(\\d+)\ue001", tk)]
        mk = [_sup_ph[int(i)] for i in mk]
        tk = re.sub(u"\ue000\\d+\ue001", "", tk)
        pending_mk = mk   # 记录本作者的 markers 列表引用, 供后置占位符追加
        mk += re.findall(r"<sup>(.*?)</sup>", tk, flags=re.I)
        tk = SUP_LATEX.sub("", tk)
        tk = re.sub(r"<sup>.*?</sup>", "", tk, flags=re.I)
        tk = re.sub(r"</?sup>", "", tk, flags=re.I)
        # (2026-11-11 修复) 裸上标 marker '^{*}' / '^{*1,2}' / '^{1,2}'(非 $ 包裹, unify 层
        # 已把 LaTeX $^{...}$ 折成 '^{*}' 形态, 52_230302 实证): 先提取再剥, 否则 marker 丢失、
        # 作者无法关联机构。
        mk += re.findall(r"[\^]?\{([\*\d,，]+)\}", tk)
        tk = re.sub(r"[\^]?\{[\*\d,，]+\}", "", tk)
        tk = re.sub(r"(\*{1,4}|†|‡|§)+(?=$|[\s·•,.])", "", tk).strip(" ·•,․")
        role = None
        mrole = ROLE_WORDS.search(tk)
        if mrole:
            role = mrole.group(1)
            tk = ROLE_WORDS.sub("", tk).strip(" ,·•")
        affil = None
        roman = None
        # 括号罗马拼音锚: 韩文名[가-힣] 或 日文名[一-鿿々〆ぁ-ゖァ-ヶ]+ 前接全角/半角括号
        mrom = re.match(u"^([가-힣一-鿿々〆ぁ-ゖァ-ヶ\\s]{2,12})[（(]([A-Za-z .\\-']+)[)）](.*)$", tk)
        if mrom:
            nm = mrom.group(1).strip()
            roman = mrom.group(2).strip()
            rest = mrom.group(3).strip()
        else:
            # OCR 粘连: 人名后直接跟机构(홍영식서울교육대학교 / 森悠一郎東京大学) — 取最长 2-4 音节
            # 人名前缀, 余部前 4 字内出现机构词即切开
            split_at = None
            for i0 in range(2, min(9, len(tk))):
                if re.fullmatch(u"[가-힣]{2,4}|[一-鿿々〆ぁ-ゖァ-ヶ]{2,8}", tk[:i0]):
                    mm = (AFFIL_HEAD if _japanese_ratio(tk) < 0.1 else JP_AFFIL_HEAD).search(tk[i0:])
                    if mm and mm.start() <= 4:
                        split_at = i0
                        break
            if split_at:
                nm, affil = tk[:split_at], tk[split_at:].strip()
                rest = ""
            else:
                nm, rest = tk, ""
        if rest:
            maff2 = AFFIL_HEAD.search(rest) or JP_AFFIL_HEAD.search(rest)
            if maff2 is None and rest.strip("() ,·•"):
                pass
        nm = _norm_ws(nm)
        nm = HONORIFIC.sub("", nm).strip(" ,·•")
        if not nm or len(_fold(nm)) < 2:
            continue
        if ROLE_WORDS.fullmatch(nm):
            continue
        if JP_SECTION_TAG.match(nm):
            continue   # 栏目名(総説/解説/特集等)不作作者(42_185 实证)
        if affil is None and nm:
            maff3 = AFFIL_HEAD.search(nm) or JP_AFFIL_HEAD.search(nm)
            if maff3 and not re.fullmatch(u"[가-힣]{2,4}|[一-鿿々〆ぁ-ゖァ-ヶ]{2,8}", nm):
                if maff3.start() >= 2 and re.fullmatch(u"[가-힣]{2,4}|[一-鿿々〆ぁ-ゖァ-ヶ]{2,8}", nm[:maff3.start()]):
                    affil = nm[maff3.start():].strip()
                    nm = nm[:maff3.start()]
        out.append({"name": nm, "markers": mk, "affiliation": affil,
                    "role": role, "roman": roman})
    return out

def front_doc(doc, out_root):
    """单篇②: 首页 front-matter 的 标题(韩/英双字段分离) + 作者(上标集合+机构脚注配对) + 机构。
    作者区=标题下至 摘要/차례/Keywords 头之间; 机构脚注=首页 Footnote 型块内的 '标记) 机构' 行。"""
    doc_dir = os.path.join(out_root, doc)
    udir = os.path.join(doc_dir, "unified")
    if not os.path.isdir(udir):
        print("跳过 %s: 无 unified 产物" % doc)
        return None
    j0 = json.load(io.open(os.path.join(udir, "page_0.json"), encoding="utf-8"))
    # 标题(2026-11-11 扩展日文: 先按脚本判定首页主导脚本, 日文题归 title 字段)
    jp_lead = _japanese_ratio(_fold("".join((u["main_text"] or "") for u in j0["unified"]))) >= 0.05
    t_ko = _pick_title(j0, True, want_japanese=jp_lead)
    t_en = _pick_title(j0, False)
    H = float(j0["h"])
    # 作者区: 标题(韩/英)之下, 摘要/차례/키워드头 之上; 区块行级扫描(两个区: 韩题下 + 英题下)
    stops = []
    for u in j0["unified"]:
        t = (u["main_text"] or "").strip()
        if t_ko and u["uid"] == t_ko["uid"] or t_en and u["uid"] == t_en["uid"]:
            continue
        if HEAD_EXCLUDE.match(t.split("\n")[0].strip()) or \
           re.match(u"^(요\\s*약|·국문요약|Keywords?|중심어|차\\s*례|要\\s*旨|概\\s*要|抄\\s*録|要\\s*約)", t.strip()):
            stops.append(u["box"][1])

    # 作者区扫描须跳过另一标题块(英文题 t_en 下会扫到日文题 t_ko, 反之亦然)与栏目名 Section-header
    # (如日文「総 説/解説/特集」, 42_185 实证: 総説+日文题被误当作者)。
    _title_uids = {u["uid"] for u in (t_ko, t_en) if u is not None}

    def _zone(top_u):
        if top_u is None:
            return []
        zstop = [y for y in stops if y > top_u["box"][3] + 2]
        limit = min(zstop) if zstop else top_u["box"][3] + 0.32 * H
        out = []
        for u in j0["unified"]:
            if u.get("cross_page", {}).get("role"):
                continue
            if u["type"] in ("Page-header", "Page-footer", "Page-number", "Footnote"):
                continue
            if u["uid"] in _title_uids:
                continue   # 跳过标题块(含另一标题)
            y1 = u["box"][1]
            if y1 < top_u["box"][3] - 4 or y1 >= limit - 2:
                continue
            # 栏目名 Section-header(総説/解説/特集等)整块跳过: 不是作者, 也非正文节头(标题区上沿)
            if u["type"] == "Section-header" and JP_SECTION_TAG.match((u["main_text"] or "").strip()):
                continue
            for ln in (u["main_text"] or "").split("\n"):
                s = ln.strip()
                if not s:
                    continue
                if ABSTRACT_START.match(s) or JP_ABS_INLINE.match(s):
                    # 内联摘要头(英/韩/日「要旨:」)即作者区边界: 作者行与要旨同块时(40_10569 实证
                    # OCR 把作者区+要旨合并进一个 Text 块), 到要旨即止, 后续摘要正文不入作者。
                    limit = min(limit, y1)
                    break
                if JP_SECTION_TAG.match(s):
                    continue   # 栏目名行(如「総 説」)不作作者
                out.append((s, u))
        return out

    zone_lines = _zone(t_ko)
    if t_en is not None:
        zone_lines += [z for z in _zone(t_en) if z not in zone_lines]
    affil_notes = {}      # marker -> affiliation(来自脚注)
    affil_foot_all = []   # (2026-11-11) 机构脚注去重列表(供无上标关联时的日文/机构兜底)

    def _affil_marker_line(s):
        """机构脚注行归一化: LaTeX 上标 '$ ^{1)} $熊本…'(40_10569 实证) 折成 '1) 熊本…' 再匹配 MARKER_LINE。
        返回 (marker, 机构文本) 或 None。"""
        _latex = SUP_LATEX.match(s)
        if _latex:
            s = _latex.group(1).strip().rstrip(")") + ") " + s[_latex.end():].strip()
        m = MARKER_LINE.match(s)
        if not m:
            return None
        return m.group(1).strip(), m.group(2)

    # 机构脚注收集: 保留对「普通 Footnote」的跨页过滤, 但机构标记行('* 東京大学…' / '$ ^{1)} $熊本…')即使在
    # 跨页脚注块(cross_page.role='tail')里也应收录(日文综述机构常在跨页脚注, 52_230302/40_10569 实证)。
    for u in j0["unified"]:
        if u["type"] != "Footnote":
            continue
        if u.get("cross_page", {}).get("role") and not any(
                (AFFIL_HEAD.search(ln) or JP_AFFIL_HEAD.search(ln)) and _affil_marker_line(ln.strip())
                for ln in (u["main_text"] or "").split("\n")):
            continue
        for ln in (u["main_text"] or "").split("\n"):
            s = ln.strip()
            hit = _affil_marker_line(s)
            if hit and (AFFIL_HEAD.search(hit[1]) or JP_AFFIL_HEAD.search(hit[1])
                        or ROLE_WORDS.search(hit[1])):
                val = hit[1].strip()
                # (2026-11-11 精确性) 机构行截断: 'Corresponding author' 之后常粘入正文
                # (unify 把正文误并入 Footnote 块, 52_230302 实证: '...E-mail: xxx, Corresponding
                #  author は，鉄一水素二元系に…'), 机构信息到 Corresponding author 即止。
                cut = re.search(r"Corresponding\s+author|E-mail\s*:", val, re.I)
                if cut:
                    # 保留 'Corresponding author' 前的机构主体; 若含 E-mail 则截到 E-mail
                    val = val[:cut.start()].rstrip(" ,·•")
                affil_notes[hit[0]] = val
                if val not in affil_foot_all:
                    affil_foot_all.append(val)
    # 解析作者行(行内有 2-4 音节韩文名/日文名/罗马锚/上标残留 才算)
    authors = []
    affils_zone = []
    for s, u in zone_lines:
        # (2026-11-11 修复日文) 机构行判定: 命中日文机构头(株式会社/大学/研究科等)即归 affils_zone,
        # 不再要求低仮名比例——片假名公司名(フォーネスライフ株式会社)仮名比例高, 旧条件会漏判,
        # 导致机构行被 _parse_author_line 误当作者(5_55 实证)。英文机构仍要求低 CJK 比例。
        _jp_affil = JP_AFFIL_HEAD.search(s) and not AFFIL_HEAD.search(s)
        if (re.fullmatch(u"[\\(（].+[\\)）]", s) and (AFFIL_HEAD.search(s) or JP_AFFIL_HEAD.search(s))) or \
           _jp_affil or \
           ((_hangul_ratio(s) < 0.2 and _japanese_ratio(s) < 0.1) and (AFFIL_HEAD.search(s) or JP_AFFIL_HEAD.search(s)) and "," not in s):
            affils_zone.append(re.sub(ROLE_WORDS, "", s).strip("() ").strip())
            continue
        if len(_fold(s)) > 80 and not re.search(u"[·•]", s):
            # 长行无作者分隔符 → 更像正文/摘要, 仅取首段尝试。
            # (2026-11-12 修复日文) 日文作者行常以「空格 + 上标 marker」分隔多位作者(40_10569 实证:
            # '本田 省二 $ ^{1)} $ 徳永 誠 …' 13 位作者 >80 折叠字符, 无 '·'), 含上标 marker 即作者行, 放行。
            _has_sup = bool(re.search(u"\\^\\{?[\\*\\d]", s))
            if not _has_sup and not re.match(u"^[가-힣]{2,4}[一-鿿々〆ぁ-ゖァ-ヶ]{2,8}?[\\(（ ]", s):
                continue
        # (2026-11-11 扩展日文) 排除投稿/接收日期行(如 '(受付 2020 年 9 月 30 日…受理…)'),
        # 含'年/月/日'日期且被全角括号包裹, 非作者(5_55 实证)
        if re.search(u"[年月日]", s) and re.search(u"受付|改訂|受理|Received|Accepted|Revised|投稿", s):
            continue
        parsed = _parse_author_line(s, u, affil_notes)
        # (2026-11-11 修复) en_side 判定须与 _parse_author_line 的 en_line 一致: 含 CJK 汉字即非英文侧,
        # 否则纯汉字日文名(古市真木雄)被误标 roman_source, 在第 281 行被全部过滤(5_55 实证)
        en_side = _hangul_ratio(s) < 0.2 and _japanese_ratio(s) < 0.1 \
            and not re.search(u"[一-鿿々〆]", s)
        for p in parsed:
            p["uid"] = u["uid"]
            p["page"] = 1
            p["box"] = u["box"]
            if en_side:
                p["roman_source"] = True   # 英题下作者区=罗马拼音来源, 事后链接到韩文作者
        authors.extend(parsed)
        if not parsed and (AFFIL_HEAD.search(s) or JP_AFFIL_HEAD.search(s)):
            affils_zone.append(re.sub(ROLE_WORDS, "", s).strip("() ").strip())
    # 机构脚注配对(上标集合→机构) + 罗马拼音锚/序链接
    def _norm_roman(s):
        return re.sub(r"[^a-z]", "", (s or "").lower())

    for a in authors:
        _marker_nums = []
        for mk in a["markers"]:
            key = mk.strip().rstrip(")")
            _marker_nums += [int(x) for x in re.findall(r"\d+", key)]
            for nk, nv in affil_notes.items():
                nk0 = nk.rstrip(")")
                if nk0 == key or (key.isdigit() and nk0 == key) or (nk0 == "*" and key == "*"):
                    mrole = ROLE_WORDS.search(nv)
                    a["affiliation"] = a["affiliation"] or ROLE_WORDS.sub("", nv).strip(" ,·•")
                    a["role"] = a["role"] or (mrole.group(1) if mrole else None)
        if a["affiliation"] is None and affils_zone:
            # (2026-11-11 扩展日文) 机构在正文而非脚注时(5_55 实证), 从 affils_zone 按上标前缀匹配:
            # 作者 marker '1'/'1,2'/'*1,2,3' 的每个数字 → 机构行 '^{n} ' 前缀。
            _hits = []
            for v in affils_zone:
                msup = re.match(u"\\^\\{?(\\d+)", v)
                if msup and int(msup.group(1)) in _marker_nums:
                    _hits.append(re.sub(u"^\\^\\{?\\d+\\}?\\s*", "", v).strip())
            if _hits:
                a["affiliation"] = _hits[0]
            else:
                a["affiliation"] = affils_zone[0]
    roman_pool = [a for a in authors if a.get("roman_source")]
    ko_authors = [a for a in authors if not a.get("roman_source")]
    if roman_pool and ko_authors:
        if len(roman_pool) == len(ko_authors):          # 顺序链接(895567 同序实证)
            for ka, ra in zip(ko_authors, roman_pool):
                ka["roman"] = ka["roman"] or ra["name"]
        else:                                            # 锚链接(括号罗马拼音)
            for ka in ko_authors:
                if ka.get("roman"):
                    continue
                tgt = _norm_roman(ka.get("roman_hint") or "")
                for ra in roman_pool:
                    if tgt and tgt in _norm_roman(ra["name"]):
                        ka["roman"] = ra["name"]
                        break
    authors = [a for a in authors if not a.get("roman_source")]
    # (2026-11-11 扩展日文) 兜底: 首页无作者区时, 从全文档页眉 running head 识别
    # 「姓名・姓名」形态作者(日文综述「解説・資料」栏目: 作者在奇数页页眉, 如 '森 悠一郎・鍵 裕之')。
    # 保守约束: 仅当 authors 为空; 行由「・」分隔的 2-4 段 CJK 名组成; 且与标题/期刊名折叠值不同。
    if not authors:
        head_auth = []
        for p in sorted({int(re.match(r"page_(\d+)\.json$", f).group(1))
                         for f in os.listdir(udir) if re.match(r"page_\d+\.json$", f)}):
            try:
                pj = json.load(io.open(os.path.join(udir, "page_%d.json" % p), encoding="utf-8"))
            except Exception:
                continue
            for u in pj.get("unified", []):
                if u.get("type") != "Page-header":
                    continue
                s = (u.get("main_text") or "").strip()
                if u"・" not in s and u"·" not in s:
                    continue
                parts = re.split(u"[・·]", s)
                parts = [p.strip() for p in parts if p.strip()]
                if not (2 <= len(parts) <= 4):
                    continue
                # 每段须是「2-8 字 CJK(汉字/仮名/谚文)名」(允许内含单个空格分隔姓与名)
                if not all(re.fullmatch(u"[一-鿿々〆ぁ-ゖァ-ヶ가-힣]{1,6}(?:\\s[一-鿿々〆ぁ-ゖァ-ヶ가-힣]{1,6})?", x)
                           for x in parts):
                    continue
                # 排除栏目标签(如 '解説・資料' 全段无空格, 无姓名结构): 至少一段含空格(姓 名分隔)
                if not any(u" " in x for x in parts):
                    continue
                fold_s = _fold(s)
                if fold_s in (t_ko and _fold(t_ko["main_text"] or ""), t_en and _fold(t_en["main_text"] or "")):
                    continue   # 排除标题型 running head
                if head_auth and _fold(head_auth[0]["name"]) != fold_s:
                    continue   # 只接受稳定复现的作者 running head
                head_auth = [{"name": x, "markers": [], "affiliation": None,
                              "role": None, "roman": None} for x in parts]
                break
        if head_auth:
            authors = head_auth
    affils = []
    for a in authors:
        if a["affiliation"] and a["affiliation"] not in affils:
            affils.append(a["affiliation"])
    for v in affils_zone:
        # (2026-11-11) 去上标前缀(^{1})再收录, 与作者关联的去前缀机构对齐去重
        v = re.sub(u"^\\^\\{?\\d+\\}?\\s*", "", v).strip()
        if v and v not in affils:
            affils.append(v)
    # (2026-11-11 扩展日文) 机构兜底: 首页脚注里 '标记) 机构' 行(如 '* 東京大学大学院理学系研究科…')
    # 即便作者来自页眉、无上标关联, 也把脚注机构收录进 affiliations(用去重列表, 避免同标记覆盖)。
    for v in affil_foot_all:
        if v and v not in affils:
            affils.append(v)

    def _best_text(u):
        """题名取值: 主读法之外, 若各渠道 dice 与主读法≥0.8, 取断行/空格最多者(dots 断行='\n' 版
        本即带空格的正确形态); 多行块按主读法首行的折叠长度截前缀(英题名+韩作者行同块形态)。"""
        mt = u["main_text"] or ""
        cands = [r["text"] for r in u["readings"]
                 if (r.get("text") or "").strip() and _gdice(r["text"], mt) >= TITLE_READING_DICE] or [mt]
        best = max(cands, key=lambda t: t.count(" ") + t.count("\n") * 2)
        val = re.sub(r"\s*\n\s*", " ", best).strip()
        val = re.sub(r"^#+\s*", "", val)
        if len(mt.split("\n")) > 1:
            # 多行块只留题名首行: 在主读法首行长附近找'第一个词尾空格'截断(rfind 会落到
            # 次行更远的空格上——实证 1892171 题名尾被切进 '김 진 경' 作者行)
            raw_len = len(mt.split("\n")[0])
            if len(val) > raw_len:
                cut = -1
                for mm in re.finditer(r"\s", val):
                    if mm.start() >= raw_len - 2:
                        cut = mm.start()
                        break
                if cut > raw_len * 0.5:
                    val = val[:cut].strip()
        return val

    def _conf(u, extra=""):
        if u is None:
            return {"level": "low", "basis": "未定位" + extra, "source": "regex"}
        lvl = "high"
        basis = []
        if u["review"]:
            lvl = "mid" if u["confidence"]["level"] != "low" else "low"
            basis.append("块级%s" % u["confidence"]["level"])
        rs = [r for r in u["readings"] if (r.get("text") or "").strip()]
        if rs:
            mt = u["main_text"] or ""
            ag = sum(1 for r in rs if _gdice(r["text"], mt) >= TITLE_READING_DICE) / float(len(rs))
            if ag < 0.67:
                lvl = "low"
            basis.append("渠道一致%.0f%%" % (ag * 100))
        return {"level": lvl, "basis": "; ".join(basis) or "三家一致", "source": "regex",
                "page": 1, "box": u["box"], "uid": u["uid"]}

    def _clean_title(t):
        t = SUP_LATEX.sub("", t or "").strip()
        t = re.sub(r"^#+\s*", "", t)
        t = re.sub(r"(\*{1,4}|†|‡|§)+(?=$|\s)", "", t).strip()
        return t

    meta_fp = os.path.join(doc_dir, "metadata.json")
    meta = json.load(io.open(meta_fp, encoding="utf-8")) if os.path.exists(meta_fp) else {}
    meta.pop("front_notes", None)   # 遗留诊断键清理(§38 已迁 audit)
    t_ko_c, t_en_c = _conf(t_ko), _conf(t_en)
    meta.update({
        "doc": doc,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        # 产品: 五元组 + confidence{level, source}; basis 见 metadata_audit.json
        "title": {"value": _clean_title(_best_text(t_ko)) if t_ko else None,
                  "page": t_ko_c.get("page"), "box": t_ko_c.get("box"), "uid": t_ko_c.get("uid"),
                  "confidence": {"level": t_ko_c["level"], "source": t_ko_c["source"]}},
        "title_en": {"value": _clean_title(_best_text(t_en)) if t_en else None,
                     "page": t_en_c.get("page"), "box": t_en_c.get("box"), "uid": t_en_c.get("uid"),
                     "confidence": {"level": t_en_c["level"], "source": t_en_c["source"]}},
        "authors": authors,
        "affiliations": affils,
    })
    io.open(meta_fp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    audit = load_audit(doc_dir)
    audit.update({"doc": doc,
                  "title": {"basis": t_ko_c["basis"]},
                  "title_en": {"basis": t_en_c["basis"]},
                  "front_notes": {"author_zone_lines": [s for s, _ in zone_lines],
                                  "affil_footnotes": affil_notes}})
    save_audit(doc_dir, audit)
    print("== ② %s ==" % doc)
    print("  title    : %s" % ((meta["title"]["value"] or "")[:56]))
    print("  title_en : %s" % ((meta["title_en"]["value"] or "(未定位→③尾页检索)")[:56]))
    for a in authors:
        print("  author   : %-12s sup=%s roman=%s affil=%s role=%s" % (
            a["name"], "/".join(a["markers"]) or "-", a["roman"] or "-",
            (a["affiliation"] or "-")[:30], a["role"] or "-"))
    for v in affils:
        print("  affil    : %s" % v[:60])
    return meta


def _selftest():
    """纯函数自检: 作者标记/罗马拼音/机构粘连与标题评分。"""
    marked = _parse_author_line(r"홍영식$^{1)}$", None, {})
    ok1 = len(marked) == 1 and marked[0]["name"] == "홍영식" and marked[0]["markers"] == ["1)"]
    roman = _parse_author_line("김진경(Kim Jin-Kyoung)", None, {})
    ok2 = len(roman) == 1 and roman[0]["name"] == "김진경" \
        and roman[0]["roman"] == "Kim Jin-Kyoung"
    glued = _parse_author_line("홍영식서울교육대학교", None, {})
    ok3 = len(glued) == 1 and glued[0]["name"] == "홍영식" \
        and glued[0]["affiliation"] == "서울교육대학교"
    header = {"uid": "h", "type": "Section-header", "main_text": "창의정보 문화연구의 방법론",
              "box": [20, 200, 460, 240], "cross_page": {}}
    text = {"uid": "t", "type": "Text", "main_text": "창의정보 문화연구의 방법론",
            "box": [20, 260, 460, 300], "cross_page": {}}
    picked = _pick_title({"h": 1000, "w": 500, "unified": [header, text]}, True)
    ok4 = picked is header
    html_marked = _parse_author_line(u"신성환<sup>●</sup>", None, {})
    ok5 = len(html_marked) == 1 and html_marked[0]["name"] == u"신성환" \
        and html_marked[0]["markers"] == [u"●"]
    # 日文作者行(2026-11-11 扩展): 全角括号罗马拼音锚「森 悠一郎(Yuichiro MORI)」
    jp = _parse_author_line("森 悠一郎(Yuichiro MORI)", None, {})
    ok6 = len(jp) == 1 and jp[0]["name"] == "森 悠一郎" and jp[0]["roman"] == "Yuichiro MORI"
    # 日文标题脚本判定(纯汉字无仮名不影响韩文路径, 含仮名判定为 ja)
    ok7 = _script_kind("中性子回折実験で探る") == "ja" and _script_kind("한글") == "ko"
    oks = (ok1, ok2, ok3, ok4, ok5, ok6, ok7)
    for i, ok in enumerate(oks, 1):
        if not ok:
            print("FAIL [front case %d]" % i)
    print("front selftest: %d/7 PASS" % sum(oks))
    return all(oks)


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
