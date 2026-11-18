# -*- coding: utf-8 -*-
"""字段审计: 16 个字段的"有 / 无 / 未查 / 失败 / 不适用"状态。

核心原则(用户 2026-11-18 定):
- 空值不等于缺失; 没有逐页/逐渠道负证据时，只能标 ``not_checked``。
- ``absent_confirmed`` 必须带证据: 检查了什么、查了什么、用什么方法、结果、置信度。
- 元数据字段的缺值默认 ``not_checked``; 实体字段可由 ner_lite_audit 的零错误审计
  支撑 ``absent_confirmed``。
- 本模块不依赖 tkinter，GUI 和 CLI 共用同一口径。
"""
from __future__ import annotations

import json
import os

import qc
import workbench_state as wb

# (id, 中文名, 组): core=核心, conditional=条件, optional=可选, entity=实体
FIELD_SPECS = (
    ("title", "标题", "core"),
    ("authors", "作者", "core"),
    ("journal", "期刊", "core"),
    ("year", "出版年", "core"),
    ("body", "正文", "core"),
    ("volume", "卷", "conditional"),
    ("issue", "期", "conditional"),
    ("pages", "页码", "conditional"),
    ("references", "参考文献", "conditional"),
    ("keywords", "关键词", "optional"),
    ("abstract", "摘要", "optional"),
    ("affiliations", "机构", "optional"),
    ("citations", "引文句/脚注", "optional"),
    ("datasets", "数据集", "entity"),
    ("funding", "基金", "entity"),
    ("software", "软件", "entity"),
)

STATUS_LABEL = {
    "present": "有",
    "absent_confirmed": "确认无",
    "not_applicable": "不适用",
    "extraction_failed": "抽取失败",
    "not_checked": "未查",
    "uncertain": "待确认",
}
STATUS_ORDER = ("present", "uncertain", "not_checked", "extraction_failed",
                "absent_confirmed", "not_applicable")
GROUP_LABEL = {"core": "核心", "conditional": "条件", "optional": "可选", "entity": "实体"}
ENTITY_FIELD = {"dataset": "datasets", "funding": "funding", "software": "software"}


def metadata_path(doc, zone):
    return os.path.join(zone.out, doc, "metadata.json")


def audit_path(doc, zone):
    return os.path.join(zone.out, doc, "metadata_audit.json")


def _load_json(fp):
    try:
        with open(fp, encoding="utf-8") as fh:
            return json.load(fh), None
    except Exception as e:
        return None, str(e)[:120]


def _val(v):
    """取单值字段的 value; 列表/标量原样返回。"""
    if isinstance(v, dict):
        return v.get("value")
    return v


def _text(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "、".join(_text(x) for x in v if _text(x))
    if isinstance(v, dict):
        return _text(v.get("value") or v.get("name") or v.get("text"))
    return str(v).strip()


def _confidence(m, key):
    v = m.get(key)
    c = v.get("confidence") if isinstance(v, dict) else None
    if not isinstance(c, dict):
        return {"level": "", "source": ""}
    return {"level": c.get("level") or "", "source": c.get("source") or ""}


def _basis(audit, key):
    v = (audit or {}).get(key)
    if isinstance(v, dict):
        return v.get("basis") or ""
    return ""


def _record(fid, label, group, status, value="", reason="", evidence="",
            confidence=None, basis="", negative=None, flag=""):
    return {
        "id": fid,
        "label": label,
        "group": group,
        "group_label": GROUP_LABEL.get(group, group),
        "status": status,
        "status_label": STATUS_LABEL.get(status, status),
        "value": value,
        "reason": reason,
        "evidence": evidence,
        "confidence": confidence or {"level": "", "source": ""},
        "basis": basis,
        "negative": negative or {},
        "flag": flag,
        "needs_audit": status in ("not_checked", "uncertain"),
    }


def _present(fid, label, group, value, reason="", evidence="", confidence=None,
             basis="", flag=""):
    return _record(fid, label, group, "present", value=value, reason=reason,
                   evidence=evidence, confidence=confidence, basis=basis, flag=flag)


def _missing(fid, label, group, evidence, basis="", reason="", status="not_checked"):
    return _record(fid, label, group, status,
                   reason=reason or "metadata 无值；尚无逐页/逐渠道负证据",
                   evidence=evidence, basis=basis)


def _pages_checked(doc, zone):
    """已解析的 unified 页数; 用于负证据，而不是拍脑袋写“全部”。"""
    try:
        d = os.path.join(zone.out, doc, "unified")
        n = len([f for f in os.listdir(d) if f.startswith("page_") and f.endswith(".json")])
        return "%d 页" % n if n else "无 unified 页"
    except OSError:
        return "无 unified 页"


def _meta_fields(m, audit, doc, zone, mfp):
    """元数据 12 字段(不含正文/实体)。"""
    out = []
    ev = mfp
    title = _text(_val(m.get("title"))) or _text(_val(m.get("title_en")))
    out.append(_present("title", "标题", "core", title,
                        "metadata.title" if _text(_val(m.get("title"))) else "metadata.title_en",
                        ev, _confidence(m, "title"), _basis(audit, "title"))
               if title else
               _missing("title", "标题", "core", ev, _basis(audit, "title")))

    authors = [a.get("name") for a in (m.get("authors") or [])
               if isinstance(a, dict) and _text(a.get("name"))]
    out.append(_present("authors", "作者", "core", "；".join(authors),
                        "metadata.authors", ev, {"level": "", "source": "authors"},
                        _basis(audit, "authors")) if authors else
               _missing("authors", "作者", "core", ev))

    kw = m.get("keywords") or []
    kw_lines = m.get("keywords_lines") or []
    kw_text = _text(kw) or _text(kw_lines)
    out.append(_present("keywords", "关键词", "optional", kw_text,
                        "metadata.keywords" if kw else "metadata.keywords_lines",
                        ev, {"level": "", "source": m.get("keywords_source") or ""},
                        _basis(audit, "keywords")) if kw_text else
               _missing("keywords", "关键词", "optional", ev))

    ab = _text(_val(m.get("abstract")))
    ab_src = "metadata.abstract"
    if not ab:
        ab = _text(_val(m.get("abstract_en")))
        ab_src = "metadata.abstract_en"
    out.append(_present("abstract", "摘要", "optional", ab, ab_src, ev,
                        _confidence(m, "abstract" if "abstract." in ab_src and ab_src.endswith("abstract") else "abstract_en"),
                        _basis(audit, "abstract")) if ab else
               _missing("abstract", "摘要", "optional", ev, _basis(audit, "abstract")))

    affs = [a.get("name") if isinstance(a, dict) else _text(a)
            for a in (m.get("affiliations") or [])]
    affs = [a for a in affs if _text(a)]
    if not affs:
        affs = [_text(a.get("affiliation")) for a in (m.get("authors") or [])
                if isinstance(a, dict) and _text(a.get("affiliation"))]
    ner_org = []
    product_fp, _ = wb.entity_paths(doc, zone)
    prod, _err = _load_json(product_fp)
    if prod:
        ner_org = [_text(r.get("name") or r.get("text")) for r in (prod.get("records") or [])
                   if isinstance(r, dict) and r.get("kind") == "org"
                   and _text(r.get("name") or r.get("text"))]
    all_aff = affs + ner_org
    out.append(_present("affiliations", "机构", "optional", "；".join(all_aff),
                        "metadata.affiliations / authors[].affiliation / ner_lite org", ev)
               if all_aff else _missing("affiliations", "机构", "optional", ev))

    jv = _text(_val(m.get("journal")) or _val(m.get("journal_en")))
    out.append(_present("journal", "期刊", "core", jv, "metadata.journal", ev,
                        _confidence(m, "journal"), _basis(audit, "journal")) if jv else
               _missing("journal", "期刊", "core", ev, _basis(audit, "journal")))

    yv = _text(_val(m.get("year")))
    out.append(_present("year", "出版年", "core", yv, "metadata.year", ev,
                        _confidence(m, "year"), _basis(audit, "year")) if yv else
               _missing("year", "出版年", "core", ev, _basis(audit, "year")))

    for fid, label in (("volume", "卷"), ("issue", "期"), ("pages", "页码")):
        val = _text(_val(m.get(fid)))
        conf = _confidence(m, fid)
        if val:
            out.append(_present(fid, label, "conditional", val, "metadata." + fid,
                                ev, conf, _basis(audit, fid)))
        elif fid == "issue" and conf.get("source") == "volume_only":
            out.append(_record("issue", "期", "conditional", "not_applicable",
                               reason="按卷编号，期号在原文结构中不适用",
                               evidence=ev, confidence=conf,
                               basis=_basis(audit, "issue")))
        else:
            out.append(_missing(fid, label, "conditional", ev, _basis(audit, fid)))

    refs = m.get("references") or []
    ref_text = _text(refs)
    cand = m.get("reference_candidates") or []
    if ref_text:
        out.append(_present("references", "参考文献", "conditional",
                            "%d 条：%s" % (len(refs), ref_text[:160]),
                            "metadata.references", ev))
    elif cand:
        out.append(_record("references", "参考文献", "conditional", "uncertain",
                           value="%d 条候选" % len(cand),
                           reason="仅有候选，尚未确认/结构化",
                           evidence=ev))
    else:
        out.append(_missing("references", "参考文献", "conditional", ev))

    cites = m.get("citation_spans") or []
    foot = m.get("footnote_refs") or []
    cr = m.get("citation_resolve") or {}
    if cites or foot:
        n = len(cites) + len(foot)
        extra = ""
        if cr and (cr.get("unresolved") or 0):
            extra = "，未解析 %d" % int(cr.get("unresolved") or 0)
        out.append(_present("citations", "引文句/脚注", "optional",
                            "%d 处%s" % (n, extra), "metadata.citation_spans / footnote_refs",
                            ev, flag=("引文未解析" if extra else "")))
    else:
        app = (m.get("footnote_ref_validation") or {}).get("applicability") or {}
        if app.get("status") == "none":
            out.append(_record("citations", "引文句/脚注", "optional", "not_applicable",
                               reason=app.get("reason") or "原文无编号脚注结构",
                               evidence=ev))
        else:
            out.append(_missing("citations", "引文句/脚注", "optional", ev))
    return out


def field_statuses(doc, zone):
    """返回 16 字段状态列表，顺序固定。"""
    mfp = metadata_path(doc, zone)
    m, err = _load_json(mfp)
    audit, _aerr = _load_json(audit_path(doc, zone))
    if m is None:
        reason = "metadata.json 不存在" if not os.path.isfile(mfp) else "metadata.json 解析失败: %s" % err
        out = [_record(fid, label, group, "extraction_failed", reason=reason, evidence=mfp)
               for fid, label, group in FIELD_SPECS if group != "entity" and fid != "body"]
        out.append(_record("body", "正文", "core", "not_checked",
                           reason="无元数据，无法确认正文", evidence=mfp))
    else:
        out = _meta_fields(m, audit, doc, zone, mfp)
        body_ok = qc.body_ok(doc, os.path.join(zone.out, doc))
        out.append(_present("body", "正文", "core", "unified 正文 ≥500 字符",
                            "unified/_unified_summary.json", os.path.join(zone.out, doc, "unified"))
                   if body_ok else
                   _record("body", "正文", "core", "not_checked",
                           reason="unified 正文 <500 字符或缺失；尚未逐页确认",
                           evidence=os.path.join(zone.out, doc, "unified")))

    st = wb.entity_statuses(doc, zone)
    product_fp, audit_fp = wb.entity_paths(doc, zone)
    prod, _perr = _load_json(product_fp)
    for kind in wb.ENTITY_KINDS:
        s = st.get(kind) or {}
        status = s.get("status") or "not_checked"
        vals = []
        if prod:
            vals = [_text(r.get("name") or r.get("text"))
                    for r in (prod.get("records") or [])
                    if isinstance(r, dict) and r.get("kind") == kind
                    and _text(r.get("name") or r.get("text"))]
        negative = {}
        if status == "absent_confirmed":
            negative = {
                "pages_checked": _pages_checked(doc, zone),
                "queries": "数据集 / 基金 / 软件三类各检索一次",
                "method": "LLM 提名 + 程序定位 + 审计",
                "result": s.get("reason") or "无该类实体",
                "confidence": "audit 零网络/解析错误",
            }
        out.append(_record(ENTITY_FIELD.get(kind, kind), wb.ENTITY_LABEL.get(kind, kind),
                           "entity", status, value="；".join(vals),
                           reason=s.get("reason") or "",
                           evidence=(audit_fp if status == "absent_confirmed" else product_fp),
                           negative=negative,
                           flag=("有记录" if vals else "")))
    # 固定顺序; 防止未来加字段时顺序漂移
    order = {fid: i for i, (fid, _l, _g) in enumerate(FIELD_SPECS)}
    out.sort(key=lambda r: order.get(r["id"], 999))
    return out


def summary(doc, zone):
    rows = field_statuses(doc, zone)
    counts = {k: 0 for k in STATUS_ORDER}
    for r in rows:
        if r["status"] in counts:
            counts[r["status"]] += 1
    core = [r for r in rows if r["group"] == "core"]
    return {
        "total": len(rows),
        "counts": counts,
        "core_total": len(core),
        "core_present": sum(1 for r in core if r["status"] == "present"),
        "needs_audit": sum(1 for r in rows if r["needs_audit"]),
        "entities": {k: (next((r["status"] for r in rows
                               if r["id"] == ENTITY_FIELD.get(k, k)), ""))
                     for k in wb.ENTITY_KINDS},
    }
