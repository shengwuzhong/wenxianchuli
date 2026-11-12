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
import os, re, io, json, datetime, collections

from .common import (_fold, _foldv, load_audit, save_audit, CONTENT_TYPES, STRUCT_TYPES,
                     _is_margin, _content_blocks, _col_of, _col_blocks, _line_h,
                     ROOT, YEAR_RE, YEAR_OK)

# ================= 闭合词典(追加制) =================

# 软件: 名称 -> 别名/大小写无关匹配键(全部小写)
_SOFTWARE_DICT = {
    "SPSS": ["spss"],
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
}

# 数据集/资料库: 名称 -> 别名
_DATASET_DICT = {
    "GenBank": ["genbank"],
    "PDB": ["pdb", "protein data bank"],
    "UniProt": ["uniprot"],
    "NCBI": ["ncbi", "pubmed", "geo", "sra", "refseq"],
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
    "CiNii": ["cinii"],
    "NDL Search": ["ndl search", "ndlサーチ"],
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

# 基金编号模式: 括号内课题号 / JSPS 编号 / NRF 编号
_FUNDING_NO = re.compile(
    r"\((?:NRF|JSPS|KAKENHI|Grant|No\.?|과제번호|사업번호|課題番号)?\s*[A-Z0-9][A-Z0-9\-\./]{2,}\s*\)"
    r"|(?:NRF|JSPS|KAKENHI|KAKEN)[\s\-]*[0-9][A-Z0-9\-]{3,}"
    r"|(?:No\.?|No\.?)\s*[0-9][A-Z0-9\-]{3,}", re.I)

# 基金机构词典(闭合)
_FUNDING_AGENCY = re.compile(
    u"한국연구재단|교육부|과학기술정보통신부|미래창조과학부|농림축산식품부|보건복지부|"
    u"National\\s+Research\\s+Foundation|Korea\\s+Research\\s+Foundation|"
    u"日本学術振興会|文部科学省|科学技術振興機構|JST|JSPS|科研費|科学研究費|"
    u"National\\s+Science\\s+Foundation|NSF|National\\s+Institutes\\s+of\\s+Health|NIH|"
    u"European\\s+Research\\s+Council|ERC|Wellcome\\s+Trust|"
    u"교내연구비|교내\\s*연구비|校内\\s*研究費", re.I)


# ================= 块加载(口径同 ner_lite.load_blocks) =================

def load_body_blocks(doc, out_root):
    """正文块: unified 取 Text/Footnote, 剔文献页/跨页头/栏外竖条。返回 [(page, uid, text, box)]。"""
    udir = os.path.join(out_root, doc, "unified")
    blocks = []
    for f in sorted(os.listdir(udir)):
        m = re.match(r"page_(\d+)\.json$", f)
        if not m:
            continue
        j = json.load(io.open(os.path.join(udir, f), encoding="utf-8"))
        if j.get("in_ref"):
            continue
        W = j.get("w") or 0
        for u in j.get("unified") or []:
            if u.get("type") not in CONTENT_TYPES:
                continue
            if u.get("cross_page", {}).get("role"):
                continue
            if _is_margin(u, W):
                continue
            t = (u.get("main_text") or "").strip()
            if not t:
                continue
            blocks.append({"page": u.get("page"), "uid": u.get("uid"),
                           "type": u.get("type"), "text": t, "box": u.get("box")})
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

def _extract_funding(blocks):
    """基金: 触发词句 → 机构 + 编号。返回 [{name, evidence_span, uid, page, kind}]。"""
    out = []
    for b in blocks:
        t = b["text"]
        for sent in _split_sents(t):
            if not _FUNDING_TRIGGER.search(sent):
                continue
            agency = None
            no = None
            m = _FUNDING_AGENCY.search(sent)
            if m:
                agency = m.group(0)
            m2 = _FUNDING_NO.search(sent)
            if m2:
                no = m2.group(0)
            if not agency and not no:
                continue
            name = agency or ""
            if no:
                name = ("%s %s" % (name, no)).strip()
            if not name:
                continue
            out.append({"kind": "funding", "name": name.strip(),
                        "evidence_span": sent.strip(), "uid": b["uid"],
                        "page": b["page"], "agency": agency, "grant_no": no})
    return out


def _extract_software(blocks):
    """软件: 词典匹配(词边界) + 版本号右向外延。"""
    out = []
    ver_re = re.compile(r"(?:v(?:er(?:sion)?)?\.?\s*|version\s+)?(\d+(?:\.\d+)+)")
    for b in blocks:
        t = b["text"]
        for name, aliases in _SOFTWARE_DICT.items():
            for al in aliases:
                # 词边界(避免 'spss' 命中 'spssx' 之外的假阳性; 单字母 R 特判)
                if al == "r":
                    rx = re.compile(r"(?<![A-Za-z])R(?![A-Za-z])")
                else:
                    rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(al) + r"(?![A-Za-z0-9])", re.I)
                for m in rx.finditer(t):
                    # 版本号外延: 紧邻的版本号
                    span_end = m.end()
                    vm = ver_re.match(t[m.end():m.end() + 20].lstrip())
                    ver = None
                    if vm:
                        ver = vm.group(0)
                        span_end = m.end() + len(t[m.end():m.end() + 20]) - len(t[m.end():m.end() + 20].lstrip()) + vm.end()
                    slice_txt = t[m.start():span_end]
                    out.append({"kind": "software", "name": name,
                                "version": ver, "evidence_span": slice_txt.strip(),
                                "uid": b["uid"], "page": b["page"]})
                break  # 一个软件只取第一个别名命中
    return out


def _extract_datasets(blocks):
    """数据集: 词典匹配。"""
    out = []
    for b in blocks:
        t = b["text"]
        for name, aliases in _DATASET_DICT.items():
            for al in aliases:
                rx = re.compile(r"(?<![A-Za-z0-9])" + re.escape(al) + r"(?![A-Za-z0-9])", re.I)
                for m in rx.finditer(t):
                    out.append({"kind": "dataset", "name": name,
                                "evidence_span": t[m.start():m.end()],
                                "uid": b["uid"], "page": b["page"]})
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
    blocks = load_body_blocks(doc, out_root)
    body = _build_body(blocks, None, doc, out_root)
    funding = _dedup(_extract_funding(blocks))
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
    # 1) 软件词典 + 版本外延
    sw = _extract_software([{"uid": "u0", "page": 1, "type": "Text",
                             "text": u"자료 분석은 SPSS 21.0 프로그램을 사용하였다.",
                             "box": [0, 0, 100, 20]}])
    ok1 = any(s["name"] == "SPSS" and s["version"] == "21.0" for s in sw)
    # 2) 数据集词典
    ds = _extract_datasets([{"uid": "u1", "page": 1, "type": "Text",
                             "text": u"配列は GenBank に登録した (accession no. AB123456).",
                             "box": [0, 0, 100, 20]}])
    ok2 = any(d["name"] == "GenBank" for d in ds)
    # 3) 基金触发 + 机构 + 编号
    fd = _extract_funding([{"uid": "u2", "page": 1, "type": "Text",
                            "text": u"本研究は JSPS 科研費 (KAKENHI 21K00000) の助成を受けた。",
                            "box": [0, 0, 100, 20]}])
    ok3 = any(f["kind"] == "funding" and "JSPS" in f["name"] for f in fd)
    # 4) 韩文基金
    fd2 = _extract_funding([{"uid": "u3", "page": 1, "type": "Text",
                             "text": u"이 논문은 한국연구재단의 지원을 받아 수행되었음 (NRF-2023R1A2C1000000).",
                             "box": [0, 0, 100, 20]}])
    ok4 = any("한국연구재단" in f["name"] for f in fd2)
    # 5) 去重
    ded = _dedup([{"kind": "software", "name": "SPSS", "uid": "a", "page": 1,
                   "evidence_span": "SPSS"},
                  {"kind": "software", "name": "SPSS", "uid": "b", "page": 2,
                   "evidence_span": "SPSS"}])
    ok5 = len(ded) == 1 and len(ded[0]["locations"]) == 2
    for i, ok in enumerate((ok1, ok2, ok3, ok4, ok5), 1):
        if ok:
            n_ok += 1
        else:
            print("FAIL [entity case %d]" % i)
    print("entity selftest: %d/5 PASS" % n_ok)
    return n_ok == 5


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
