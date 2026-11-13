# -*- coding: utf-8 -*-
r"""M6 实体补全层 (--stage entity): 正文(body) + 基金/软件/数据集(规则词典降级, 可空)。

职责(与 ner_lite.py 分工):
  - ner_lite.py = LLM 提名 + 程序定位(开放词表, 需 KCI_LLM_KEY; 产物落 out_llm_trial/ 侧目录)。
  - 本模块 = 纯规则 + 闭合词典降级, **不依赖 LLM**, 回灌 metadata.json 的 funding/software/datasets 三键;
    与 ner_lite 的 LLM 结果互补: LLM 有钥匙时优先, 无钥匙时本模块兜底高置信部分。

契约:
  ① body: unified 层非 in_ref 页 Text 块按阅读序拼接(剔跨页头/栏外竖条/页眉页脚/页码), 干净纯文本。
  ② funding: 资助声明句 → 机构 + 课题号(括号内编号/JSPS 科研費/교내연구비/本研究は…支援等)。
     证据闸门同 ner_lite: 每条 entity 带 evidence_span(原文切片), 折叠核对在源块内才收。
  ③ software: 闭合词典(SPSS/R/Stata/Python/AMOS/SAS/MATLAB 等) + 版本号右向外延。
  ④ datasets: 闭合词典(GenBank/PDB/UniProt/NCBI/TCGA/GBIF/Protein Data Bank 等) + 链接外延。
  ⑤ 三键均可能为空列表; 不碰 unify/m3; 只读 unified, 只写 metadata.json + metadata_audit.json 的 entity 段。

用法: python metadata.py <doc> --stage entity
"""
import os, re, io, json, datetime, collections, unicodedata

from .common import (_fold, _foldv, load_audit, save_audit, CONTENT_TYPES, STRUCT_TYPES,
                     _is_margin, _content_blocks, _col_of, _col_blocks, _line_h,
                     ROOT, YEAR_RE, YEAR_OK)

# ================= 闭合词典(追加制) =================

# 软件: 名称 -> 别名/大小写无关匹配键(全部小写)
_SOFTWARE_DICT = {
    "SPSS": ["spss", "pasw"],
    "R": ["r", "r-project", "rstudio"],
    "Stata": ["stata"],
    "SAS": ["sas"],
    "Python": ["python", "numpy", "scipy", "pandas", "scikit-learn", "matplotlib"],
    "MATLAB": ["matlab"],
    "AMOS": ["amos"],
    "Mplus": ["mplus"],
    "GraphPad Prism": ["graphpad", "prism"],
    "ImageJ": ["imagej", "fiji"],
    "OpenCV": ["opencv"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "EndNote": ["endnote"],
    "Excel": ["excel"],
    "ArcGIS": ["arcgis"],
    "ANSYS": ["ansys"],
    "COMSOL": ["comsol"],
    "ChemDraw": ["chemdraw"],
    "BLAST": ["blast"],
    "MEGA": ["mega"],
    "VASP": ["vasp"],
    "Gaussian": ["gaussian"],
    "LAMMPS": ["lammps"],
    # 日文文献/国内学会常用(软件名 + 日文写法/厂商写法)
    "JMP": ["jmp"],
    "EZR": ["ezr"],
    "4 Steps エクセル統計": ["エクセル統計", "4 steps"],
    "GSAS": ["gsas"],
    "Z-Rietveld": ["z-rietveld"],
    "LabSolutions": ["labsolutions"],
    "SPW": ["spw"],
    "Origin": ["originpro", "originlab"],
    "KaleidaGraph": ["kaleidagraph"],
    "Photoshop": ["photoshop"],
    "Illustrator": ["illustrator"],
    "QGIS": ["qgis"],
    "Metashape": ["metashape", "photoscan"],
    "SfM": ["agisoft"],
}

# 短名/易假阳性词: 需在附近出现软件语句境才收(避免 'PLA2R' / 'R2019-073' 类误命中)
_SOFTWARE_CTX = {
    "R": re.compile(u"ソフト|統計|解析|パッケージ|version|ver\\.|を用い|使用|cran|rstudio", re.I),
}

# 数据集/资料库: 名称 -> 别名
_DATASET_DICT = {
    "GenBank": ["genbank", "ddbj/embl/genbank"],
    "PDB": ["pdb", "protein data bank", "pdbj"],
    "UniProt": ["uniprot", "uniprotkb", "swiss-prot"],
    "NCBI": ["ncbi"],
    "DDBJ": ["ddbj"],
    "EMBL-EBI": ["embl", "ebi", "ena"],
    "TCGA": ["tcga", "the cancer genome atlas"],
    "GEO": ["gene expression omnibus"],
    "KEGG": ["kegg"],
    "GO": ["gene ontology"],
    "dbSNP": ["dbsnp"],
    "ClinVar": ["clinvar"],
    "HGMD": ["hgmd"],
    "ICD": ["icd-10", "icd10"],
    "DSM": ["dsm-5", "dsm5", "dsm-iv", "dsm4"],
    "GBIF": ["gbif"],
    "Kaggle": ["kaggle"],
    "ImageNet": ["imagenet"],
    "COCO": ["ms-coco", "coco dataset"],
    "JPND": ["jpnd"],
    "CiNii": ["cinii", "cinii research"],
    "NDL Search": ["ndl search", "ndlサーチ", "国立国会図書館サーチ"],
}

# 基金: 资助声明触发词(命中后取整句或就近提取机构/编号)
_FUNDING_TRIGGER = re.compile(
    u"(本\\s*研\\s*究|이\\s*논\\s*문|이\\s*연\\s*구|본\\s*연\\s*구|本\\s*研\\s*究)\\s*"
    u"(?:는|은|은\\s*|이\\s*|は)?"
    u"(?:.*?)(?:의\\s*|의\\s*지원|지원을\\s*받아|의\\s*연구비|연구비|"
    u"지원\\s*에\\s*의해|지원\\s*받|지원\\s*을|の\\s*支援|の\\s*助成|助成|"
    u"JSPS|科研費|科学研究費|文部科学省|日本学術振興会|National\\s+Research\\s+Foundation|"
    u"한국연구재단|NRF|National\\s+Science\\s+Foundation|NSF|"
    u"Grant\\s+Number|grant\\s+number|Grant\\s+No|이\\s*연구는)", re.I)

# 日文致谢动词: 必须与机构/项目/编号共现(单独出现只当作普通正文, 不入库)
_ACK = re.compile(u"助成|研究助成|支援|研究費|補助金|交付|grant|funded|supported", re.I)

# 基金项目名(日文常见写法; 无机构名时作实体主干)
_FUNDING_PROGRAM = re.compile(
    u"科学研究費助成事業|科学研究費補助金|科学研究費|科研費|KAKENHI|学術研究助成基金|"
    u"特別研究員奨励費|科学技術振興機構|国立研究開発法人|GteX|GX\\s*技術創出事業|"
    u"基盤研究\\s*\\(?[SABC]\\)?|若手研究|挑戦的研究|厚生労働科学研究", re.I)

# 基金编号模式(强约束优先: 科研費 JP / JST JPMJ / 奨励費 22J / 課題番号 / NRF)
_FUNDING_NO_STRICT = re.compile(
    r"JP\d{2}[A-Z]{1,2}\d{4,}"
    r"|JPMJ[A-Z0-9]{4,}"
    r"|(?<![0-9A-Za-z])\d{2}[A-Z]\d{4,}(?![0-9A-Za-z])"
    r"|(?:課題番号|課題\s*No\.?)[：:\s]*([0-9]{2,}[A-Z0-9\-]{2,})"
    r"|(?:NRF|JSPS|KAKENHI|KAKEN)[\s\-]*[0-9][A-Z0-9\-]{3,}", re.I)

# 基金编号模式(兜底: 括号内课题号 / No. 编号)
_FUNDING_NO = re.compile(
    r"\((?:NRF|JSPS|KAKENHI|Grant|No\.?|과제번호|사업번호|課題番号)?\s*[A-Z0-9][A-Z0-9\-\./]{2,}\s*\)"
    r"|(?:No\.?)\s*[0-9][A-Z0-9\-]{3,}", re.I)

# 基金机构词典(闭合)
_FUNDING_AGENCY = re.compile(
    u"한국연구재단|교육부|과학기술정보통신부|미래창조과학부|농림축산식품부|보건복지부|"
    u"National\\s+Research\\s+Foundation|Korea\\s+Research\\s+Foundation|"
    u"日本学術振興会|文部科学省|科学技術振興機構|JST|JSPS|科研費|科学研究費|"
    u"厚生労働省|農林水産省|経済産業省|環境省|内閣府|総務省|"
    u"日本医療研究開発機構|AMED|新エネルギー・産業技術総合開発機構|NEDO|"
    u"National\\s+Science\\s+Foundation|NSF|National\\s+Institutes\\s+of\\s+Health|NIH|"
    u"European\\s+Research\\s+Council|ERC|Wellcome\\s+Trust|"
    u"교내연구비|교내\\s*연구비|校内\\s*研究費", re.I)


# ================= 块加载(口径同 ner_lite.load_blocks) =================

def load_body_blocks(doc, out_root, include_ref=False, types=None):
    """正文块: unified 取 Text/Footnote, 剔文献页/跨页头/栏外竖条。返回 [(page, uid, text, box)]。

    include_ref=True 时额外收 in_ref 页的 Text/Footnote(块标记 in_ref), 供基金抽取用:
    日文「謝辞」常与文献表同页而被整页判成 literature, 但 ack 句仍在(不参与 body)。
    types 可放宽块类型(如加 Caption), 仅软件/数据集抽取用; body 另行重建, 不受影响。
    """
    udir = os.path.join(out_root, doc, "unified")
    types = types or CONTENT_TYPES
    blocks = []
    for f in sorted(os.listdir(udir)):
        m = re.match(r"page_(\d+)\.json$", f)
        if not m:
            continue
        j = json.load(io.open(os.path.join(udir, f), encoding="utf-8"))
        in_ref = bool(j.get("in_ref"))
        if in_ref and not include_ref:
            continue
        W = j.get("w") or 0
        for u in j.get("unified") or []:
            if u.get("type") not in types:
                continue
            if u.get("cross_page", {}).get("role"):
                continue
            if _is_margin(u, W):
                continue
            t = (u.get("main_text") or "").strip()
            if not t:
                continue
            blocks.append({"page": u.get("page"), "uid": u.get("uid"),
                           "type": u.get("type"), "text": t, "box": u.get("box"),
                           "in_ref": in_ref})
    return blocks


# 首页 front matter 信号: 作者上标标记/邮箱/机构脚注行(^{N} 起) — 正文应剔除
# 作者区带 '$ ^{1,2} $' LaTeX 上标; 机构区带 '^{1} ' 前缀(作者-机构对应脚注)
_FRONT_NOISE = re.compile(r"^\s*(\\^\\{\\d|\^{2,}\d|E-mail|\\$\\s*\\^\\{|\\*\\s*E-mail)", re.I)
_AUTHOR_ZONE = re.compile(r"\$\s*\^\{")


def _is_front_matter(t):
    """判定整块为首页 front matter(作者区/机构脚注区): 含 LaTeX 上标 '$ ^{..} $' 或机构 '^{N} ' 前缀。"""
    if _AUTHOR_ZONE.search(t):
        return True
    # 机构脚注: 首行以 ^{N} 开头(允许前导空格, 如 '^{1} フォーネスライフ株式会社：...')
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    return bool(lines) and bool(re.match(r"^\^\{\d+\}", lines[0]))


def _build_body(blocks, pdata, doc, out_root):
    """正文拼接: 页内按阅读序(栏→y→x), 页间按页序。仅取 Text 块(剔 Footnote=脚注属参考文献/注释实体),
    剔除页眉页脚/页码/运行头/首页作者机构脚注等 front matter。"""
    doc_dir = os.path.join(out_root, doc)
    pages = sorted(int(re.match(r"page_(\d+)\.json$", f).group(1))
                   for f in os.listdir(doc_dir + "/unified")
                   if re.match(r"page_\d+\.json$", f))
    pdata = {p: json.load(io.open(os.path.join(doc_dir, "unified", "page_%d.json" % p),
                                  encoding="utf-8")) for p in pages}
    from .common import _doc_heads, _clean_lines
    doc_heads = _doc_heads(pdata, pages)
    paras = []
    for p in pages:
        j = pdata[p]
        if j.get("in_ref"):
            continue
        W = j.get("w") or 0
        boundary = _page_col_boundary_local(j, W)
        ordered = []
        for u in j.get("unified") or []:
            if u.get("type") != "Text":      # 正文只取 Text, 脚注/图/表/题注不混入
                continue
            if u.get("cross_page", {}).get("role"):
                continue
            if _is_margin(u, W):
                continue
            t = (u.get("main_text") or "").strip()
            if not t:
                continue
            col = _col_of_b_local(u, boundary, W)
            ordered.append((col, u["box"][1], u["box"][0], t))
        ordered.sort()
        for col, y, x, t in ordered:
            if p == 0 and _is_front_matter(t):   # 首页作者区/机构脚注区不进正文
                continue
            cleaned, _ = _clean_lines(t, set(), doc_heads)
            if cleaned:
                paras.append(cleaned)
    return "\n\n".join(paras).strip()


def _page_col_boundary_local(j, W):
    from .common import _page_col_boundary
    return _page_col_boundary(j)


def _col_of_b_local(u, boundary, W):
    if boundary is None:
        return 0
    return 0 if (u["box"][0] + u["box"][2]) / 2.0 < boundary else 1


# ================= 规则抽取 =================

def _is_funding_sent(sent):
    """基金句判定: 韩/英旧触发词, 或(日文致谢动词 + 机构/项目/编号共现)。

    只有致谢动词(支援/助成/研究費)而没有任何机构/项目/编号, 视为普通正文引用, 不入库。
    """
    if _FUNDING_TRIGGER.search(sent):
        return True
    if not _ACK.search(sent):
        return False
    return bool(_FUNDING_AGENCY.search(sent) or _FUNDING_PROGRAM.search(sent)
                or _FUNDING_NO_STRICT.search(sent) or _FUNDING_NO.search(sent))


def _extract_funding(blocks):
    """基金: 触发词句 → 机构/项目名 + 编号。返回 [{name, evidence_span, uid, page, kind}]。"""
    out = []
    for b in blocks:
        t = b["text"]
        for sent in _split_sents(t):
            if not _is_funding_sent(sent):
                continue
            agency = None
            m = _FUNDING_AGENCY.search(sent) or _FUNDING_PROGRAM.search(sent)
            if m:
                agency = m.group(0)
            no = None
            m2 = _FUNDING_NO_STRICT.search(sent) or _FUNDING_NO.search(sent)
            if m2:
                no = m2.group(1) or m2.group(0)
            if not agency and not no:
                continue
            parts = []
            if agency:
                parts.append(agency.strip())
            if no:
                g = no.strip()
                if not any(g in p for p in parts):
                    parts.append(g)
            name = " ".join(parts).strip()
            span = sent.strip()
            if not name or not span:
                continue
            out.append({"kind": "funding", "name": name,
                        "evidence_span": span, "uid": b["uid"],
                        "page": b["page"], "agency": agency, "grant_no": no})
    return out


def _nrm_idx(t):
    """NFKC 归一(全角英数→半角)并保留归一字符→原串下标映射, 供词典匹配后回切原文。"""
    buf, idx = [], []
    for i, ch in enumerate(t):
        for c in unicodedata.normalize("NFKC", ch):
            buf.append(c)
            idx.append(i)
    return "".join(buf), idx


def _orig_slice(t, idx, s, e):
    """归一化下标区间 → 原串切片(evidence_span 取原文, 不用归一文本)。"""
    if not idx or s >= e or s >= len(idx):
        return ""
    a = idx[s]
    b = idx[min(e, len(idx)) - 1] + 1
    return t[a:b].strip()


def _alias_rx(al, short=False):
    """别名→词边界正则; 短名单字母(如 R)也要求前后非字母数字, 防 'PLA2R'/'R2019-073' 命中。"""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(al) + r"(?![A-Za-z0-9])", re.I)


def _extract_software(blocks):
    """软件: 词典匹配(全角归一 + 词边界) + 版本号右向外延。"""
    out = []
    ver_re = re.compile(r"\s*(?:v(?:er(?:sion)?)?\.?\s*)?(\d+(?:\.\d+)+)")
    for b in blocks:
        if b.get("in_ref"):        # 文献表里的软件名多为他人引用, 不入库
            continue
        t = b["text"]
        nt, idx = _nrm_idx(t)
        for name, aliases in _SOFTWARE_DICT.items():
            ctx = _SOFTWARE_CTX.get(name)
            for al in aliases:
                hit = False
                rx = _alias_rx(al, short=(name == "R"))
                for m in rx.finditer(nt):
                    if ctx and not ctx.search(nt[max(0, m.start() - 24):m.end() + 24]):
                        continue
                    span_end = m.end()
                    vm = ver_re.match(nt[m.end():m.end() + 24])
                    ver = None
                    if vm:
                        ver = vm.group(1)
                        span_end = m.end() + vm.end()
                    span = _orig_slice(t, idx, m.start(), span_end)
                    if not span:
                        continue
                    out.append({"kind": "software", "name": name,
                                "version": ver, "evidence_span": span,
                                "uid": b["uid"], "page": b["page"]})
                    hit = True
                if hit:
                    break          # 同一软件只取首个命中的别名
    return out


def _extract_datasets(blocks):
    """数据集: 词典匹配(全角归一 + 词边界)。"""
    out = []
    for b in blocks:
        if b.get("in_ref"):        # 文献表里的库名/登录号属引用, 不入库
            continue
        t = b["text"]
        nt, idx = _nrm_idx(t)
        for name, aliases in _DATASET_DICT.items():
            for al in aliases:
                hit = False
                rx = _alias_rx(al)
                for m in rx.finditer(nt):
                    span = _orig_slice(t, idx, m.start(), m.end())
                    if not span:
                        continue
                    out.append({"kind": "dataset", "name": name,
                                "evidence_span": span, "uid": b["uid"],
                                "page": b["page"]})
                    hit = True
                if hit:
                    break
    return out


def _split_sents(t):
    """切句(粗切, 供基金触发词定位用)。"""
    return re.split(r"(?<=[.。])", t or "")


# ================= 去重 =================

def _dedup(entities):
    """按 (kind, name) 去重, 保留首个 evidence_span 与全部定位。"""
    seen = {}
    order = []
    for e in entities:
        key = (e["kind"], e["name"])
        if key in seen:
            seen[key]["locations"].append({"uid": e["uid"], "page": e["page"],
                                           "evidence_span": e["evidence_span"]})
            continue
        seen[key] = {"kind": e["kind"], "name": e["name"],
                     "locations": [{"uid": e["uid"], "page": e["page"],
                                    "evidence_span": e["evidence_span"]}]}
        if e.get("agency") is not None:
            seen[key]["agency"] = e["agency"]
        if e.get("grant_no") is not None:
            seen[key]["grant_no"] = e["grant_no"]
        if e.get("version") is not None:
            seen[key]["version"] = e["version"]
        order.append(key)
    return [seen[k] for k in order]


# ================= 主流程 =================

def entity_doc(doc, out_root):
    """单篇: body + funding/software/datasets(规则词典) 回灌 metadata.json。"""
    doc_dir = os.path.join(out_root, doc)
    meta_fp = os.path.join(doc_dir, "metadata.json")
    udir = os.path.join(doc_dir, "unified")
    if not os.path.exists(meta_fp) or not os.path.isdir(udir):
        print("跳过 entity %s: 缺 metadata/unified" % doc)
        return None
    meta = json.load(io.open(meta_fp, encoding="utf-8"))
    blocks = load_body_blocks(doc, out_root, types=CONTENT_TYPES | {"Caption"})
    fblocks = load_body_blocks(doc, out_root, include_ref=True)   # 基金: 谢辞常与文献同页
    body = _build_body(blocks, None, doc, out_root)
    funding = _dedup(_extract_funding(fblocks))
    software = _dedup(_extract_software(blocks))
    datasets = _dedup(_extract_datasets(blocks))
    meta.update({
        "doc": doc,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "body": body,
        "funding": funding,
        "software": software,
        "datasets": datasets,
    })
    io.open(meta_fp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    audit = load_audit(doc_dir)
    audit["entity"] = {
        "body_chars": len(body),
        "funding": len(funding), "software": len(software), "datasets": len(datasets),
        "source": "regex+dictionary",
    }
    save_audit(doc_dir, audit)
    print("== entity %s == body=%d字 funding=%d software=%d datasets=%d" % (
        doc, len(body), len(funding), len(software), len(datasets)))
    return meta


# ================= 自检 =================

def _selftest():
    n_ok = 0

    def blk(text, uid="u"):
        return {"uid": uid, "page": 1, "type": "Text", "text": text,
                "box": [0, 0, 100, 20]}

    # 1) 软件词典 + 版本外延
    sw = _extract_software([blk(u"자료 분석은 SPSS 21.0 프로그램을 사용하였다.")])
    ok1 = any(s["name"] == "SPSS" and s["version"] == "21.0" for s in sw)
    # 2) 数据集词典
    ds = _extract_datasets([blk(u"配列は GenBank に登録した (accession no. AB123456).")])
    ok2 = any(d["name"] == "GenBank" for d in ds)
    # 3) 基金触发 + 机构 + 编号
    fd = _extract_funding([blk(u"本研究は JSPS 科研費 (KAKENHI 21K00000) の助成を受けた。")])
    ok3 = any(f["kind"] == "funding" and "JSPS" in f["name"] for f in fd)
    # 4) 韩文基金
    fd2 = _extract_funding([blk(u"이 논문은 한국연구재단의 지원을 받아 수행되었음 (NRF-2023R1A2C1000000).")])
    ok4 = any("한국연구재단" in f["name"] for f in fd2)
    # 5) 去重
    ded = _dedup([{"kind": "software", "name": "SPSS", "uid": "a", "page": 1,
                   "evidence_span": "SPSS"},
                  {"kind": "software", "name": "SPSS", "uid": "b", "page": 2,
                   "evidence_span": "SPSS"}])
    ok5 = len(ded) == 1 and len(ded[0]["locations"]) == 2
    # 6) 日文谢辞: JSPS 科研費 + JP 编号
    fd3 = _extract_funding([blk(u"本稿で紹介した研究は, JSPS 科研費 (JP18H05224), "
                               u"特別研究員奨励費(22J21462)の助成を受けたものである。")])
    ok6 = any(f["grant_no"] and f["grant_no"].startswith("JP18H05224") for f in fd3)
    # 7) 日文谢辞: 文部科学省 + 課題番号
    fd4 = _extract_funding([blk(u"本研究は文部科学省科学研究費補助金の支援を受け，"
                               u"課題番号 20K12345 で実施した。")])
    ok7 = any("文部科学省" in f["name"] for f in fd4)
    # 8) 无机构/项目的泛致谢句不入库
    fd5 = _extract_funding([blk(u"本研究の一部は，研究成果の公表のために助成を受けた。")])
    ok8 = len(fd5) == 0
    # 9) 全角写法(ＳＰＳＳ ２６)可匹配, evidence_span 取原文全角
    sw2 = _extract_software([blk(u"統計解析にはＳＰＳＳ ２６を用いた。")])
    ok9 = any(s["name"] == "SPSS" and u"ＳＰＳＳ" in s["evidence_span"] for s in sw2)
    # 10) 日文数据集写法 + 正文引用(报告书目)不入库
    ds2 = _extract_datasets([blk(u"構造はタンパク質立体構造データベース(PDB)に登録され，"
                                 u"国立国会図書館サーチでも公開されている。")])
    cit = _extract_funding([blk(u"文部科学省研究開発局・京都大学防災研究所（2021）により"
                                u"掘削されたコアを解析した。")])
    ok10 = any(d["name"] == "PDB" for d in ds2) and any(d["name"] == "NDL Search" for d in ds2) \
        and len(cit) == 0
    cases = (ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8, ok9, ok10)
    for i, ok in enumerate(cases, 1):
        if ok:
            n_ok += 1
        else:
            print("FAIL [entity case %d]" % i)
    print("entity selftest: %d/%d PASS" % (n_ok, len(cases)))
    return n_ok == len(cases)


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
