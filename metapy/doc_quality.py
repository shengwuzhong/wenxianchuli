# -*- coding: utf-8 -*-
"""Post-normalization document quality repair/audit.

This module deliberately works *after* front/abs/issue/refs/vertical:
it only performs conservative, deterministic repairs that are supported by
visible evidence (MinerU H1, title_en, existing author lines, page text).

It does not invent bibliographic facts.  When a field cannot be repaired it
is left as-is and a quality flag is emitted for manual review.
"""
import copy
import io
import json
import os
import re
import unicodedata

from .ja_names import enrich_author, name_key, normalize_person_name

JP = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_WS = re.compile(r"[\s\u3000]+")
_MD_HEAD = re.compile(r"^#+\s*")
_MD_MARKS = re.compile(r"(?:\*\*|__|`|~~)")
_PAGE_PREFIX = re.compile(r"^\s*\d{3,4}\s+")
_PAGE_INLINE = re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])1\d{2}(?=[\u3040-\u30ff\u3400-\u9fff])")
_BAD_TITLE = re.compile(
    r"^(?:CONTENTS|Journal of\b|Vol\.?\s*\d|No\.?\s*\d|Abstract\b|Keywords?\b|"
    r"References?\b|NII-Electronic\b|Copyright\b|©|ISSN\b|DOI\b|https?://|"
    r"第\s*\d+\s*回.*(?:講演|予稿)|EDITORIAL\b)",
    re.I)
_FIG_TITLE = re.compile(r"^(?:図|表|Fig\.?|Table)\s*\d", re.I)
_SUBTITLE = re.compile(r"^[―—–-].*[―—–-]$")
_BODY_TITLE = re.compile(
    r"(?:本稿では|本研究では|本研究は|本研究室では|本稿は|ここでは|以下では|"
    r"本発表では|本報告では)")
_MAGAZINE = re.compile(r"(?:コ_ヒ_ブレ_ク|コヒブレク|コーヒーブレイク|ちょっとしたエッセイ|"
                       r"私のすすめるこの一冊|エッセイ)")
_AFFIL = re.compile(
    r"(?:大学|大学院|研究科|学部|学科|専攻|研究所|研究室|センター|機構|学会|"
    r"協会|財団|会社|株式会社|病院|学校|部門|分野|グループ|プロジェクト|"
    r"委員会|部会|教授会|学府|検査技師|医療職|阪大|東大|名大|九大|北大|院工|大理|物性研|"
    r"産総研|産技研|理研|物材機構|フォトバイオ|法政|JST|NEDO)")
_NON_NAME = re.compile(
    r"(?:研究|目的|方法|結果|考察|背景|概要|要旨|論文|本稿|本文|データ|支援|"
    r"学生|今日|在り方|海水|濃度|試料|汚れ|細胞骨格|アクチン|法律|法的|課題|"
    r"現状|編集|出版|応募|募集|公募|プログラム|抄録|発表会|講演|会場|日時|主催|"
    r"連絡先|氏名|年齢|所属|締め切り|期間|対象|応募方法|電話|番号|機関名|審査|"
    r"抗ウイルス|抗腫瘍|細胞増殖|増殖|など|等|我々|近未来|医学系|人間環境|"
    r"食形態|患者|形態)")
_ELEMENTS = {"鉄", "アルミニウム", "亜鉛", "マンガン", "カドミウム", "銅",
             "鉛", "水銀", "カルシウム", "ナトリウム", "カリウム"}
_DEGREES = {"MD", "PhD", "M.D.", "Ph.D.", "Dr", "Prof", "Dr.", "Prof."}
_EN_ROLE = re.compile(r"\b(?:Student|Non-member|Member|Fellow|Professor|Doctor)\b", re.I)
_EN_AFFIL = re.compile(
    r"\b(?:Univ|University|Institute|Research|Technology|Metropolitan|Industrial|"
    r"Kinki|Sch|Fac|Agric|Natl|Resour|Center|Centre|Department|College|School|"
    r"Laboratory|Acad|Sci|Eng|Dept|Division|Faculty)\b", re.I)
_EN_NON_NAME = re.compile(
    r"^(?:First|Second|Third|Fourth|Atomic|Energy|Damage|Compensation|Law|"
    r"Article|Figure|Table|Introduction|Conclusion|References?)$", re.I)
_AUTHOR_MARK = re.compile(r"^[\s○◎●◦○※■□◆◇▪▫♣♠*＊\-\u2013\u2014]+")
_AUTHOR_SUP = re.compile(r"(?:\^\{[^}]*\}|\$[^$]*\$|<sup>.*?</sup>)", re.I)
_AUTHOR_TAIL = re.compile(r"\s*[（(][^（()）]{0,80}[）)]\s*$")
_AUTHOR_MARKER_TAIL = re.compile(r"\s+[A-C]\s*$")


def _read_json(fp):
    with io.open(fp, encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(fp, obj):
    tmp = fp + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, fp)


def _value(x):
    return x.get("value") if isinstance(x, dict) else x


def unified_pages(doc_dir):
    udir = os.path.join(doc_dir, "unified")
    if not os.path.isdir(udir):
        return []
    files = [f for f in os.listdir(udir)
             if re.match(r"page_\d+\.json$", f)]
    files.sort(key=lambda s: int(re.search(r"(\d+)", s).group(1)))
    out = []
    for f in files:
        out.append(_read_json(os.path.join(udir, f)))
    return out


def page_texts(doc_dir):
    out = []
    for p in unified_pages(doc_dir):
        out.append("\n".join(str(u.get("main_text") or u.get("text") or "")
                             for u in (p.get("unified") or p.get("units") or [])))
    return out


def raw_h1(doc_dir):
    """MinerU full.md first H1.  Returns "" when absent/unusable."""
    fp = os.path.join(doc_dir, "raw", "mineru_api", "full.md")
    if not os.path.isfile(fp):
        return ""
    try:
        with io.open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("# "):
                    return line[2:].strip()
    except OSError:
        return ""
    return ""


def raw_author_names(doc_dir):
    """Best-effort author line(s) immediately after MinerU H1.

    Only returns names that pass is_person_name(); it is a fallback for documents
    whose front stage produced no authors (English papers are common).
    """
    fp = os.path.join(doc_dir, "raw", "mineru_api", "full.md")
    if not os.path.isfile(fp):
        return []
    try:
        with io.open(fp, encoding="utf-8", errors="replace") as f:
            lines = [x.strip() for x in f if x.strip()]
    except OSError:
        return []
    start = None
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            start = i + 1
            break
    if start is None:
        return []
    picked = []
    for line in lines[start:start + 6]:
        if line.startswith("# "):
            break
        if line.startswith("## "):
            line = line[3:].strip()   # 69_3 author line is emitted as H2
        if re.match(r"^(?:\d+\s*[.．]|はじめに|序|背景|目的|方法|結果|考察|参考文献)", line):
            break   # section heading, not author line (29_0 实证)
        if line.startswith("<sup>") or re.match(
                r"^(?:Abstract|Received|Key\s*words?|Keywords?|DOI|Vol\.|No\.|CONTENTS)",
                line, re.I):
            break
        picked.append(line)
        if len(picked) >= 4:
            break

    out = []
    seen = set()
    for line in picked:
        line = re.sub(r"<sup>.*?</sup>", "", line, flags=re.I)
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\$[^$]*\$", "", line)
        line = line.replace("\\", "")
        line = re.sub(r"[*＊]\s*\d*$", "", line)
        line = re.sub(r"\([^()]{0,80}\)", "", line)
        line = _EN_ROLE.sub("", line)
        line = re.sub(r"[○◎●]\s*", "", line)
        for part in re.split(r"[,，;；]|\band\b|\s{2,}", line):
            part = part.strip(" .")
            if not part:
                continue
            part = re.sub(r"\b(?:MD|PhD|M\.D\.|Ph\.D\.|Dr\.?|Prof\.?)\b", "",
                          part, flags=re.I)
            # 名前の後ろに読み(こばやし かずと)が続く形を落とす
            part = re.sub(r"^([\u3400-\u9fff々〆]{1,6}\s+[\u3400-\u9fff々〆]{1,6})[\u3040-\u30ff].*$",
                          r"\1", part)
            # 所属+○名前/所属+名前の行から、末尾の日本人名だけを拾う
            m = re.search(r"([\u3400-\u9fff々〆]{1,6}(?:[ 　][\u3400-\u9fff々〆]{1,6})?)$", part)
            if m and len(m.group(1).replace(" ", "")) >= 2:
                cand = m.group(1)
            else:
                cand = part
            cand = _WS.sub(" ", cand).strip(" .")
            toks = cand.split(" ")
            if len(toks) >= 2 and all(len(t) >= 3 and JP.search(t) for t in toks) \
                    and all(is_person_name(t) for t in toks):
                for t in toks:
                    k = name_key(t)
                    if k not in seen:
                        seen.add(k)
                        out.append(t)
                continue
            if is_person_name(cand):
                k = name_key(cand)
                if k not in seen:
                    seen.add(k)
                    out.append(cand)
                continue
            # "鈴木悠矢 西川康博" (space-separated full names) — only split when
            # both sides are >=3 chars, so "村田 知也" stays one name.
            toks = cand.split(" ")
            if len(toks) >= 2 and all(len(t) >= 3 for t in toks) \
                    and all(is_person_name(t) for t in toks):
                for t in toks:
                    k = name_key(t)
                    if k not in seen:
                        seen.add(k)
                        out.append(t)
    return out


def _latex_text(s):
    # Nested braces make a single regex unreliable (74.2: \mathbf { S m _{1-x} R }).
    s = re.sub(r"\\[A-Za-z]+\s*", "", s)
    s = s.replace("$", "")
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"[_^]\s*", "", s)
    return s


def clean_title_text(t):
    """Return (clean_title, embedded_author, embedded_affiliation)."""
    s = str(t or "")
    s = _MD_HEAD.sub("", s)
    s = _MD_MARKS.sub("", s)
    s = _latex_text(s)
    s = re.sub(r"\s*##+\s*", " ", s)
    s = _WS.sub(" ", s).strip()
    s = _PAGE_PREFIX.sub("", s)
    s = _PAGE_INLINE.sub("", s)
    s = s.strip(" .．。")
    author = None
    affil = None
    m = re.search(r"\s+([\u3040-\u30ff\u3400-\u9fff]{2,8})\s*[（(]([^）)]{2,60})[）)]\s*$", s)
    if m:
        author, affil = m.group(1).strip(), m.group(2).strip()
        s = s[:m.start()].strip()
    else:
        # remove a trailing affiliation-only parenthetical
        m = _AUTHOR_TAIL.search(s)
        if m and _AFFIL.search(m.group(0)):
            s = s[:m.start()].strip()
    return s.strip(), author, affil


def title_is_bad(t):
    t = str(t or "").strip()
    if not t or len(t) < 5:
        return True
    if _PAGE_PREFIX.match(t):
        return True
    if _BAD_TITLE.search(t) or _FIG_TITLE.search(t) or _SUBTITLE.match(t):
        return True
    if _BODY_TITLE.search(t):
        return True
    if _MAGAZINE.search(t):
        return True
    if t.startswith("【") or "##" in t:
        return True
    if len(t) > 80 and ("。" in t or t.count("、") >= 2):
        return True
    if len(t) > 30 and re.search(r"[。！？!?]\s*$", t):
        return True
    return False


def title_is_valid(t):
    t = str(t or "").strip()
    if title_is_bad(t):
        return False
    if _looks_author_list(t):
        return False
    if re.fullmatch(r"[\d\s.,，-]+", t):
        return False
    return True


def _looks_author_list(t):
    t = str(t or "").strip()
    if re.match(r"^(?:[A-Z]\.\s*){2,}", t):
        return True
    if len(re.findall(r"\b[A-Z][a-z]+\s+[A-Z]{1,3}\b", t)) >= 2:
        return True
    return False


def _strip_trailing_parens(s):
    """Remove nested trailing parentheses, e.g. '栗栖清浩 (TOA (株))'."""
    s = s.strip()
    while s and s[-1] in "）)":
        depth = 0
        cut = -1
        for i in range(len(s) - 1, -1, -1):
            if s[i] in "）)":
                depth += 1
            elif s[i] in "（(":
                depth -= 1
                if depth == 0:
                    cut = i
                    break
        if cut <= 0:
            break
        s = s[:cut].strip()
    return s


def is_person_name(name):
    s = normalize_person_name(str(name or ""))
    if not s:
        return False
    s = _AUTHOR_SUP.sub("", s)
    s = _AUTHOR_MARK.sub("", s)
    s = _strip_trailing_parens(s)
    s = _AUTHOR_MARKER_TAIL.sub("", s).strip(" ,，、;；:：")
    if not s or len(s) > 20:
        return False
    if s.strip(" .") in _DEGREES:
        return False
    if re.search(r"[。！？!?：:0-9]", s):
        return False
    if s in _ELEMENTS or any(e in s for e in _ELEMENTS if len(e) >= 2):
        return False
    if _AFFIL.search(s) or _NON_NAME.search(s):
        return False
    if re.match(r"^(?:第|図|表|Fig\.?|Table|http|##|\d)", s):
        return False
    if re.match(r"^[A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']*){0,3}$", s):
        if _EN_NON_NAME.match(s):
            return False
        if _EN_AFFIL.search(s) or re.search(r"\b(?:et|al|Journal|Proc|Vol|No)\b", s, re.I):
            return False
        return True
    plain = _WS.sub("", s)
    if re.fullmatch(r"[\u3400-\u9fff々〆]{1,6}", plain):
        return True
    if re.fullmatch(r"[\u3400-\u9fff々〆]{1,4}[\u3040-\u30ff]{1,6}", plain):
        return True
    if re.fullmatch(r"[\u30a0-\u30ffー]{2,10}", plain):
        return True
    if re.fullmatch(r"[\u3400-\u9fff々〆]{1,6}\s+[\u3400-\u9fff々〆]{1,6}", s):
        return True
    return False


def _expand_author(name):
    s = str(name or "").strip()
    if not s:
        return []
    parts = [s]
    if len(s) > 20 or re.search(r"[,，、;；]", s):
        parts = [x for x in re.split(r"[,，、;；]", s) if x.strip()]
    out = []
    for p in parts:
        p = _AUTHOR_MARK.sub("", p)
        p = _AUTHOR_SUP.sub("", p)
        p = _AUTHOR_MARKER_TAIL.sub("", p)
        p = _strip_trailing_parens(p)
        p = p.strip(" ,，、;；:：")
        if is_person_name(p):
            out.append(p)
    return out


def repair_authors(authors, extra=()):
    out = []
    seen = set()
    for a in list(authors or []) + list(extra or []):
        if isinstance(a, dict):
            nm = a.get("name")
            base = dict(a)
        else:
            nm = a
            base = {"name": nm, "markers": [], "affiliation": None,
                    "role": None, "roman": None}
        for n in _expand_author(nm):
            k = name_key(n)
            if not k or k in seen:
                continue
            seen.add(k)
            d = dict(base)
            d["name"] = n
            d.setdefault("markers", [])
            d.setdefault("affiliation", None)
            d.setdefault("role", None)
            d.setdefault("roman", None)
            out.append(enrich_author(d))
    # Remove split fragments when a longer full name exists
    # (2021.2: "ナンダル ビカス" also produced "ナンダル"/"ビカス").
    keys = [name_key(a.get("name")) for a in out]
    kept = []
    for a, k in zip(out, keys):
        if any(k != other and k and k in other for other in keys):
            continue
        kept.append(a)
    return kept


def _looks_like_toc_page(first):
    """A page of article titles with trailing page numbers (issue contents)."""
    if not re.search(r"(?:Vol\.?|vol\.?)\s*\d", first):
        return False
    lines = [ln.strip() for ln in first.splitlines() if ln.strip()]
    numbered = [ln for ln in lines
                if len(ln) >= 12 and re.search(r"\s+\d{1,3}$", ln)]
    return len(numbered) >= 3


def _looks_like_award_page(first):
    """Award/abstract collection page: several award entries, no single title."""
    heads = first.count("研究奨励") + first.count("研究奖励")
    return heads >= 2 and ("年生" in first or "正員" in first)


def _looks_like_announcement_page(first):
    """Society notice / committee-list page, not an article."""
    return ("研究部会" in first and
            ("複写される方へ" in first or "Notice about" in first))


def detect_document_type(doc_dir, meta):
    pages = page_texts(doc_dir)
    txt = "\n".join(pages)
    first = pages[0] if pages else ""
    title = str(_value((meta or {}).get("title")) or "")
    h1 = raw_h1(doc_dir)
    head = "\n".join([title, h1])

    # TOC: only when the document head/page begins with CONTENTS/目次.
    # (70_2 contains a body word "目次" somewhere; don't classify on that.)
    if re.search(r"(?:^\s*CONTENTS\b|\bCONTENTS\b|^\s*目\s*次\s*$)", head, re.M | re.I):
        return "toc"
    if re.search(r"(?:^\s*CONTENTS\b|^\s*目\s*次\s*$)", first[:1200], re.M | re.I):
        return "toc"

    # Program/abstract collection: require the signal in title/H1, not body prose.
    if re.search(r"(?:学会・研究会抄録|研究発表会|プログラム|Program\b)", head, re.I) \
            and re.search(r"(?:抄録|発表会|^\s*\d+[.．]\s+)", first, re.M):
        return "program"
    if re.search(r"(?:応募|募集|公募|申請要領|申請方法)", head) and \
            re.search(r"(?:締め?切り|応募期間|対象者|連絡先)", first):
        return "announcement"
    if re.search(r"(?:応募|募集|公募)", first[:600]) and \
            re.search(r"(?:締め?切り|応募期間|対象者|連絡先)", first):
        return "announcement"
    if _MAGAZINE.search(head) or _MAGAZINE.search(first[:600]):
        return "magazine"

    # Contents / award-abstract / notice pages have no single article title.
    if _looks_like_toc_page(first):
        return "toc"
    if _looks_like_award_page(first):
        return "multi_abstract"
    if _looks_like_announcement_page(first):
        return "announcement"

    # Cover/only-image page: little text on page 0 and no title at all.
    if len(first.strip()) < 200 and not head.strip():
        return "cover"

    codes = re.findall(r"\b\d{2}[A-Za-z]{2,4}-\d+\b", txt)
    if len(codes) >= 2:
        return "multi_abstract"
    return "article"


def _bad_journal(v):
    s = str(v or "").strip()
    if not s or len(s) < 2:
        return True
    if re.search(r"(?:本文は|東大理|都立大理|名大工|阪大|大学|研究科|研究所)", s):
        return True
    if s in ("本文は",):
        return True
    return False


def _bad_pages(v):
    s = str(v or "").strip()
    if not s:
        return False
    m = re.fullmatch(r"(\d{4})\s*[-–—]\s*(\d{4})", s)
    if m and m.group(1) == m.group(2):
        return True
    if m and int(m.group(2)) - int(m.group(1)) > 300:
        return True
    return False


def repair_metadata(meta, doc_dir):
    """Conservative post-normalization repair.  Returns (new_meta, info)."""
    out = copy.deepcopy(meta or {})
    # Recompute from current fields; do not inherit stale flags from a previous run.
    flags = set()
    info = {"changed": False}

    doc_type = detect_document_type(doc_dir, out)
    if out.get("document_type") != doc_type:
        out["document_type"] = doc_type
        info["changed"] = True
    single = (doc_type == "article")
    if out.get("is_single_article") is not single:
        out["is_single_article"] = single
        info["changed"] = True
    if not single:
        flags.add("composite_document")

    h1, h1_author, h1_affil = clean_title_text(raw_h1(doc_dir))
    cur = str(_value(out.get("title")) or "")
    cur_clean, cur_author, cur_affil = clean_title_text(cur)
    ten = str(_value(out.get("title_en")) or "")
    ten_clean, _, _ = clean_title_text(ten)

    chosen = cur
    source = (out.get("title") or {}).get("confidence", {}).get("source") if isinstance(out.get("title"), dict) else None
    embedded_author = None
    embedded_affil = None
    if not cur or title_is_bad(cur):
        if title_is_valid(h1):
            chosen, source, embedded_author, embedded_affil = h1, "mineru_h1", h1_author, h1_affil
        elif title_is_valid(ten_clean):
            chosen, source = ten_clean, "title_en"
        elif cur_clean and cur_clean != cur:
            chosen, source = cur_clean, source or "regex"
            embedded_author, embedded_affil = cur_author, cur_affil
        elif doc_type == "article":
            flags.add("title_suspect")
    else:
        # 当前题名明显是 H1 的前缀（常见：题名被截断），优先用完整 H1。
        if title_is_valid(h1) and cur_clean and h1.startswith(cur_clean) \
                and len(h1) > len(cur_clean) + 3:
            chosen, source, embedded_author, embedded_affil = h1, "mineru_h1", h1_author, h1_affil
        else:
            chosen = cur_clean or cur
            embedded_author, embedded_affil = cur_author, cur_affil
            if chosen != cur:
                source = source or "regex"
    if chosen != cur:
        if isinstance(out.get("title"), dict):
            td = dict(out["title"])
            td["value"] = chosen or None
            td["confidence"] = dict(td.get("confidence") or {"level": "mid"})
            td["confidence"]["source"] = source or "quality"
            out["title"] = td
        else:
            out["title"] = {"value": chosen or None, "confidence":
                            {"level": "mid", "source": source or "quality"}}
        out["title_source"] = source or "quality"
        flags.add("title_repaired")
        info["changed"] = True
    if not str(_value(out.get("title")) or "").strip():
        if doc_type in ("cover", "toc", "announcement", "multi_abstract", "program"):
            flags.add("title_not_applicable")
        else:
            flags.add("title_missing")

    old_authors = out.get("authors") or []
    extra = []
    if embedded_author:
        extra.append({"name": embedded_author, "markers": [],
                      "affiliation": embedded_affil, "role": None, "roman": None})
    if h1_author and not embedded_author:
        extra.append({"name": h1_author, "markers": [],
                      "affiliation": h1_affil, "role": None, "roman": None})
    new_authors = repair_authors(old_authors, extra)
    raw_names = raw_author_names(doc_dir)
    if out.get("title_source") == "vertical":
        raw_names = []   # 竖排页已有 unified 作者候选，尾页英文摘要的作者行不可信
    if raw_names:
        # 72.2 这类日英双语作者行会同时给出“西口 大貴 / Daiki Nishiguchi”；
        # 按题名脚本选一组，避免同名重复。
        want_ja = bool(JP.search(chosen))
        same = [n for n in raw_names if bool(JP.search(n)) == want_ja]
        if same:
            raw_names = same
        elif want_ja:
            raw_names = []   # 日文题名 + 只有英文名：多半是尾页英文摘要，不用
        if not new_authors:
            new_authors = repair_authors(raw_names)
            if new_authors:
                flags.add("authors_from_raw")
        elif single and len(raw_names) > len(new_authors):
            existing = [name_key(a.get("name")) for a in new_authors
                        if isinstance(a, dict) and a.get("name")]
            extra = [rn for rn in raw_names
                     if not any(name_key(rn) in k or k in name_key(rn) for k in existing)]
            if extra:
                merged = repair_authors(new_authors + extra)
                if len(merged) > len(new_authors):
                    new_authors = merged
                    flags.add("authors_from_raw")
    if new_authors != old_authors:
        out["authors"] = new_authors
        info["changed"] = True
    if not new_authors:
        flags.add("authors_missing")
    elif len(new_authors) < len(old_authors):
        flags.add("authors_filtered")

    abstract = str(_value(out.get("abstract")) or "")
    abstract_en = str(_value(out.get("abstract_en")) or "")
    if not abstract:
        if abstract_en and single:
            src = out.get("abstract_en") if isinstance(out.get("abstract_en"), dict) else {}
            out["abstract"] = {
                "value": abstract_en,
                "page": src.get("page"),
                "box": src.get("box"),
                "confidence": {"level": (src.get("confidence") or {}).get("level", "mid")
                               if isinstance(src.get("confidence"), dict) else "mid",
                               "source": "abstract_en"},
                "lang": "en",
                "fallback": True,
            }
            flags.add("abstract_from_en")
            info["changed"] = True
        else:
            flags.add("abstract_missing")
    if isinstance(out.get("abstract"), dict) and out["abstract"].get("fallback"):
        flags.add("abstract_from_en")

    j = _value(out.get("journal"))
    if j and _bad_journal(j):
        out["journal"] = {"value": None, "confidence": {"level": "low", "source": "quality"}}
        flags.add("journal_suspect")
        info["changed"] = True
    p = _value(out.get("pages"))
    if p and _bad_pages(p):
        flags.add("pages_suspect")
    if not _value(out.get("year")):
        flags.add("year_missing")
    if not _value(out.get("journal")):
        flags.add("journal_missing")

    refs = out.get("references") or []
    if refs:
        if any((not r.get("source")) or (not r.get("pages")) for r in refs
               if isinstance(r, dict)):
            flags.add("references_incomplete")
        if not out.get("citation_spans"):
            flags.add("citations_missing")
    cr = out.get("citation_resolve") or {}
    if isinstance(cr, dict) and int(cr.get("unresolved") or 0) > 0:
        flags.add("citations_unresolved")

    if not single:
        flags.add("needs_manual_review")
    if "title_missing" in flags or "authors_missing" in flags:
        flags.add("needs_manual_review")

    out["quality_flags"] = sorted(flags)
    out["quality"] = {
        "version": 1,
        "document_type": doc_type,
        "is_single_article": single,
        "flags": sorted(flags),
        "checked": True,
    }
    info.update({"document_type": doc_type, "is_single_article": single,
                 "flags": sorted(flags)})
    return out, info


def apply_doc(doc, out_root):
    dd = os.path.join(out_root, doc)
    fp = os.path.join(dd, "metadata.json")
    if not os.path.exists(fp):
        return None
    meta = _read_json(fp)
    new, info = repair_metadata(meta, dd)
    if info.get("changed"):
        _write_json(fp, new)
    return info


def _selftest():
    assert clean_title_text("185 嚥下障害患者の栄養選択")[0] == "嚥下障害患者の栄養選択"
    assert clean_title_text("題名 本間芳文 (札幌国際大学)")[0] == "題名"
    assert is_person_name("小野のぞみ")
    assert is_person_name("大石 朋子")
    assert not is_person_name("研究の目的")
    assert not is_person_name("鉄")
    assert not is_person_name("アルミニウム")
    assert not is_person_name("神経系アクチン細胞骨格3")
    assert not is_person_name("阪大理")
    assert not title_is_valid("図 1 気候区分とクロロフィル aの分布")
    assert not title_is_valid("本稿では、筆者の所属する…")
    print("doc_quality selftest: PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
