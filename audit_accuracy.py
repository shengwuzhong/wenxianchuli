# -*- coding: utf-8 -*-
r"""准确性自检脚本：扫描 out/ 下所有 metadata.json + metadata_audit.json，
输出每个字段的置信度分布、low/mid 需复核清单、audit 里的 _bad 标记，一次看清全局准确率。

用法:
  python audit_accuracy.py                 # 全局汇总(所有有 metadata.json 的文档)
  python audit_accuracy.py 52_230302       # 只查某几篇(可多个文档名)
  python audit_accuracy.py --full          # 全局 + 每篇逐字段明细(含 low/mid 值)

字段口径(与用户定义的 14 类实体对齐):
  题录: title/title_en/authors/affiliations
  来源: journal/journal_en/year/volume/issue/pages
  摘要: abstract/abstract_en
  关键词: keywords/keywords_en
  正文: body
  文献: references/footnote_refs
  引文句: citation_spans
  可选实体: funding/software/datasets(可空)

置信度三段: high=可信 / mid=需复核 / low=高风险。标量字段缺失值(NULL/空)记为"缺省"。
"""
import os, io, json, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")

# 标量字段(值为 dict, 含 value + confidence.level)
SCALAR_FIELDS = ["title", "title_en", "journal", "journal_en",
                 "year", "volume", "issue", "pages", "abstract", "abstract_en"]
# 列表字段(值为 list)
LIST_FIELDS = ["authors", "affiliations", "references", "footnote_refs",
               "citation_spans", "keywords", "keywords_en"]
# 可选可空字段(list)
OPTIONAL_FIELDS = ["funding", "software", "datasets"]
# 正文(字符串)
BODY_FIELD = "body"

FIELD_LABEL = {
    "title": u"标题", "title_en": u"标题(英)", "authors": u"作者",
    "affiliations": u"机构", "journal": u"期刊", "journal_en": u"期刊(英)",
    "year": u"出版年", "volume": u"卷", "issue": u"期", "pages": u"页码",
    "abstract": u"摘要", "abstract_en": u"摘要(英)", "keywords": u"关键词",
    "keywords_en": u"关键词(英)", "body": u"正文", "references": u"参考文献",
    "footnote_refs": u"脚注文献", "citation_spans": u"引文句",
    "funding": u"基金", "software": u"研究软件", "datasets": u"科学数据集",
}


def _val(field):
    """标量字段取值: 返回 (value, level, uid, page)。"""
    if not isinstance(field, dict):
        return (None, None, None, None)
    v = field.get("value")
    conf = field.get("confidence") or {}
    lv = conf.get("level")
    return (v, lv, field.get("uid"), field.get("page"))


def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, (str, list, dict)):
        return len(v) == 0
    return False


def _load(doc):
    ddir = os.path.join(OUT, doc)
    meta = None
    audit = None
    mfp = os.path.join(ddir, "metadata.json")
    afp = os.path.join(ddir, "metadata_audit.json")
    if os.path.exists(mfp):
        try:
            meta = json.load(io.open(mfp, encoding="utf-8"))
        except Exception:
            meta = None
    if os.path.exists(afp):
        try:
            audit = json.load(io.open(afp, encoding="utf-8"))
        except Exception:
            audit = None
    return meta, audit


def _audit_bad_flags(audit):
    """从 audit 侧车提取 _bad 类标记(校验层拦截), 汇总成可读字符串。"""
    flags = []
    if not audit:
        return flags
    rv = audit.get("ref_validation") or {}
    if rv.get("year_bad"):
        flags.append(u"参考文献年份疑错 %d 处" % len(rv["year_bad"]))
    if rv.get("pages_bad"):
        flags.append(u"参考文献页码疑错 %d 处" % len(rv["pages_bad"]))
    fv = audit.get("footnote_ref_validation") or {}
    if fv.get("year_bad"):
        flags.append(u"脚注年份疑错 %d 处" % len(fv["year_bad"]))
    if fv.get("pages_bad"):
        flags.append(u"脚注页码疑错 %d 处" % len(fv["pages_bad"]))
    return flags


def _doc_summary(doc):
    """单篇汇总: 返回 dict, 含各字段状态与需复核项。"""
    meta, audit = _load(doc)
    out = {"doc": doc, "meta": meta, "audit": audit}
    if not meta:
        out["missing"] = True
        return out
    out["missing"] = False
    scalar = {}
    for f in SCALAR_FIELDS:
        v, lv, uid, page = _val(meta.get(f))
        scalar[f] = {"value": v, "level": lv, "uid": uid, "page": page}
    lists = {}
    for f in LIST_FIELDS:
        lists[f] = meta.get(f) or []
    opt = {}
    for f in OPTIONAL_FIELDS:
        opt[f] = meta.get(f) or []
    body = meta.get(BODY_FIELD) or ""
    out["scalar"] = scalar
    out["lists"] = lists
    out["optional"] = opt
    out["body"] = body
    # 需复核项: low/mid 的标量字段 + 空值标量字段。
    # 空值分两类: ① value=None 但有 confidence(level 非空)=「抽取失败」(规则跑了但没命中);
    #           ② value=None 且 confidence 为空/缺整个字段=「未抽取/原文无」。
    review = []
    for f in SCALAR_FIELDS:
        s = scalar[f]
        if s["level"] in ("low", "mid"):
            # 有 level 但 value 空 → 抽取失败(比 mid 更严重)
            tag = ("fail_%s" % s["level"]) if _is_empty(s["value"]) else s["level"]
            review.append((f, tag, s["value"]))
        elif _is_empty(s["value"]) and s["level"] is None:
            review.append((f, "empty", None))
    out["review"] = review
    out["bad_flags"] = _audit_bad_flags(audit)
    return out


def _fmt_val(v, maxlen=50):
    if v is None:
        return u"—"
    s = str(v).replace("\n", " ")
    if len(s) > maxlen:
        s = s[:maxlen] + u"…"
    return s


def _report_all(docs, full=False):
    print(u"=" * 78)
    print(u"metadata 抽取准确性自检")
    print(u"扫描目录: out/  |  文档数: %d" % len(docs))
    print(u"=" * 78)
    # 全局置信度统计
    lv_stat = {"high": 0, "mid": 0, "low": 0, "fail": 0, "empty": 0}
    summaries = []
    for d in docs:
        s = _doc_summary(d)
        summaries.append(s)
        if s.get("missing"):
            continue
        for f in SCALAR_FIELDS:
            st = s["scalar"][f]
            if _is_empty(st["value"]):
                # 空值: 有 level 但空=抽取失败; 无 level=未抽/原文无
                if st["level"] in ("low", "mid", "high"):
                    lv_stat["fail"] += 1
                else:
                    lv_stat["empty"] += 1
            elif st["level"] in lv_stat:
                lv_stat[st["level"]] += 1
    total = sum(lv_stat.values())
    print()
    print(u"—— 标量字段置信度分布（全部文档合计）——")
    print(u"  high(可信)     : %d  (%.0f%%)" % (lv_stat["high"], 100.0 * lv_stat["high"] / total if total else 0))
    print(u"  mid(需复核)    : %d  (%.0f%%)" % (lv_stat["mid"], 100.0 * lv_stat["mid"] / total if total else 0))
    print(u"  low(高风险)    : %d  (%.0f%%)" % (lv_stat["low"], 100.0 * lv_stat["low"] / total if total else 0))
    print(u"  fail(抽取失败) : %d  (%.0f%%)  ← 值空但有置信度, 规则未命中, 重点修" % (lv_stat["fail"], 100.0 * lv_stat["fail"] / total if total else 0))
    print(u"  empty(未抽/原文无): %d  (%.0f%%)" % (lv_stat["empty"], 100.0 * lv_stat["empty"] / total if total else 0))
    print(u"  —— 合计 %d 个标量字段" % total)
    print()
    # 每篇汇总表
    print(u"—— 每篇汇总 ——")
    print(u"%-12s %-28s %s" % (u"文档", u"需复核字段(级别)", u"校验拦截"))
    for s in summaries:
        if s.get("missing"):
            print(u"%-12s %s" % (s["doc"], u"[无 metadata.json]"))
            continue
        rev = u", ".join(u"%s(%s)" % (FIELD_LABEL.get(f, f), lv)
                          for f, lv, v in s["review"]) or u"无"
        bad = u", ".join(s["bad_flags"]) or u"无"
        print(u"%-12s %-28s %s" % (s["doc"], rev, bad))
    print()
    # 可选实体统计
    print(u"—— 可选实体(基金/软件/数据集)命中情况 ——")
    print(u"%-12s %-10s %-10s %-10s" % (u"文档", u"基金", u"软件", u"数据集"))
    for s in summaries:
        if s.get("missing"):
            print(u"%-12s %-10s %-10s %-10s" % (s["doc"], u"—", u"—", u"—"))
            continue
        opt = s["optional"]
        print(u"%-12s %-10d %-10d %-10d" % (s["doc"], len(opt["funding"]),
                                            len(opt["software"]), len(opt["datasets"])))
    print()
    if full:
        print(u"=" * 78)
        for s in summaries:
            if s.get("missing"):
                continue
            print()
            print(u"▍文档 %s" % s["doc"])
            print(u"  正文 %d 字" % len(s["body"]))
            for f in SCALAR_FIELDS:
                st = s["scalar"][f]
                lab = FIELD_LABEL.get(f, f)
                mark = st["level"] if st["level"] else ("empty" if _is_empty(st["value"]) else "-")
                print(u"  %-10s [%-5s] %s" % (lab, mark, _fmt_val(st["value"])))
            for f in LIST_FIELDS:
                lab = FIELD_LABEL.get(f, f)
                n = len(s["lists"][f])
                if f == "authors":
                    nm = u", ".join((a.get("name") or "") for a in s["lists"][f])
                    print(u"  %-10s [%-5d] %s" % (lab, n, _fmt_val(nm, 60)))
                else:
                    print(u"  %-10s [%-5d]" % (lab, n))
            if s["bad_flags"]:
                print(u"  ⚠ 校验拦截: %s" % u"; ".join(s["bad_flags"]))
    print()
    print(u"=" * 78)
    print(u"结论：优先人工复核所有 mid/low/empty 字段，对照 viewer 里对应 uid 的原文证据。")
    print(u"=" * 78)


def _report_single(doc):
    """单篇复核清单(markdown 格式), 输出到 out/<doc>/_accuracy_checklist.md。"""
    s = _doc_summary(doc)
    if s.get("missing"):
        print(u"[%s] 无 metadata.json，跳过。" % doc)
        return None
    meta = s["meta"]
    lines = []
    lines.append(u"# %s — 抽取准确性复核清单" % doc)
    lines.append(u"")
    lines.append(u"> 生成时间: %s ｜ 对照原文时用 viewer_compare.html 里点击字段锚点(uid)定位证据。" % (meta.get("generated") or ""))
    lines.append(u"> 判定记号: ✅ 正确 / ⚠️ 部分错(漏/多) / ❌ 错误 / ➖ 原文无此字段")
    lines.append(u"")
    lines.append(u"## 一、题录")
    lines.append(u"")
    lines.append(u"| 字段 | 值 | 置信度 | 证据锚点 | 判定 |")
    lines.append(u"|---|---|---|---|---|")
    for f in ("title", "title_en", "authors", "affiliations"):
        if f in ("title", "title_en"):
            st = s["scalar"][f]
            anchor = u"p%d %s" % (st["page"], st["uid"]) if st["uid"] else u"—"
            lines.append(u"| %s | %s | %s | %s | ☐ |" % (FIELD_LABEL[f], _fmt_val(st["value"], 60), st["level"] or u"缺省", anchor))
        else:
            lst = s["lists"][f]
            if f == "authors":
                val = u"; ".join((a.get("name") or "") + (u"(%s)" % a["roman"] if a.get("roman") else u"")
                                 for a in lst) or u"—"
            else:
                val = u"；".join(lst) or u"—"
            lines.append(u"| %s | %s | — | — | ☐ |" % (FIELD_LABEL[f], _fmt_val(val, 60)))
    lines.append(u"")
    lines.append(u"## 二、来源（期刊/年/卷/期/页）")
    lines.append(u"")
    lines.append(u"| 字段 | 值 | 置信度 | 证据锚点 | 判定 |")
    lines.append(u"|---|---|---|---|---|")
    for f in ("journal", "journal_en", "year", "volume", "issue", "pages"):
        st = s["scalar"][f]
        anchor = u"p%d %s" % (st["page"], st["uid"]) if st["uid"] else u"—"
        lines.append(u"| %s | %s | %s | %s | ☐ |" % (FIELD_LABEL[f], _fmt_val(st["value"], 60), st["level"] or u"缺省", anchor))
    lines.append(u"")
    lines.append(u"## 三、摘要与关键词")
    lines.append(u"")
    lines.append(u"| 字段 | 值(截断) | 置信度 | 判定 |")
    lines.append(u"|---|---|---|---|")
    for f in ("abstract", "abstract_en"):
        st = s["scalar"][f]
        lines.append(u"| %s | %s | %s | ☐ |" % (FIELD_LABEL[f], _fmt_val(st["value"], 60), st["level"] or u"缺省"))
    for f in ("keywords", "keywords_en"):
        lst = s["lists"][f]
        val = u"；".join(lst) if lst else u"—"
        lines.append(u"| %s | %s | — | ☐ |" % (FIELD_LABEL[f], _fmt_val(val, 60)))
    lines.append(u"")
    lines.append(u"## 四、正文与文献")
    lines.append(u"")
    lines.append(u"- **正文**: %d 字" % len(s["body"]))
    lines.append(u"- **参考文献**: %d 条" % len(s["lists"]["references"]))
    lines.append(u"- **脚注文献**: %d 条" % len(s["lists"]["footnote_refs"]))
    lines.append(u"- **引文句**: %d 条" % len(s["lists"]["citation_spans"]))
    if s["bad_flags"]:
        lines.append(u"- ⚠️ **校验拦截**: %s" % u"；".join(s["bad_flags"]))
    lines.append(u"")
    lines.append(u"## 五、可选实体（可能为空）")
    lines.append(u"")
    lines.append(u"| 字段 | 条数 | 值 | 判定 |")
    lines.append(u"|---|---|---|---|")
    for f in ("funding", "software", "datasets"):
        lst = s["optional"][f]
        val = u"；".join((x.get("name") or str(x)) if isinstance(x, dict) else str(x) for x in lst) if lst else u"—"
        lines.append(u"| %s | %d | %s | ☐ |" % (FIELD_LABEL[f], len(lst), _fmt_val(val, 60)))
    lines.append(u"")
    lines.append(u"## 六、需重点复核（low/mid/empty）")
    lines.append(u"")
    if s["review"]:
        for f, lv, v in s["review"]:
            lines.append(u"- [ ] **%s**（%s）: %s" % (FIELD_LABEL.get(f, f), lv, _fmt_val(v, 60)))
    else:
        lines.append(u"- 无（全部 high 或非空）")
    lines.append(u"")
    fp = os.path.join(OUT, doc, "_accuracy_checklist.md")
    with io.open(fp, "w", encoding="utf-8") as fh:
        fh.write(u"\n".join(lines))
    return fp


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    docs = sorted(d for d in os.listdir(OUT)
                  if os.path.isdir(os.path.join(OUT, d))
                  and os.path.exists(os.path.join(OUT, d, "metadata.json")))
    if args:
        docs = [d for d in args if d in docs]
    if not docs:
        print(u"out/ 下没有含 metadata.json 的文档。")
        return
    if len(args) == 1:
        # 单篇 → 生成复核清单 markdown
        fp = _report_single(args[0])
        if fp:
            print(u"已生成复核清单: %s" % fp)
        return
    _report_all(docs, full=full)


if __name__ == "__main__":
    main()
