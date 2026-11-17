# -*- coding: utf-8 -*-
"""日文分词/形态素分析（可选依赖，带降级）。

用途：
  - 给字段抽取提供可靠的日文词边界；
  - 给关键词候选、作者/机构、全文检索提供 token；
  - 输出 raw surface + normalized form + POS + 原文 offset。

优先 SudachiPy + sudachidict_core；未安装时使用正则降级，不阻断主流程。
"""
import json
import re
import sys

_TOKENIZER = None
_BACKEND = "regex"


def _get_tokenizer():
    global _TOKENIZER, _BACKEND
    if _TOKENIZER is not None:
        return _TOKENIZER
    try:
        from sudachipy import dictionary
        try:
            d = dictionary.Dictionary(dict="core")
        except TypeError:
            d = dictionary.Dictionary(dict_type="core")
        try:
            _TOKENIZER = d.tokenizer()
        except AttributeError:
            _TOKENIZER = d.create()
        _BACKEND = "sudachi"
        return _TOKENIZER
    except Exception:
        pass
    try:
        from janome.tokenizer import Tokenizer as JanomeTokenizer
        _TOKENIZER = JanomeTokenizer()
        _BACKEND = "janome"
        return _TOKENIZER
    except Exception:
        _TOKENIZER = False
        _BACKEND = "regex"
        return _TOKENIZER


def backend():
    _get_tokenizer()
    return _BACKEND


def _sudachi_mode(mode):
    try:
        from sudachipy import tokenizer as st
        return {"A": st.Tokenizer.SplitMode.A,
                "B": st.Tokenizer.SplitMode.B,
                "C": st.Tokenizer.SplitMode.C}.get((mode or "C").upper(), st.Tokenizer.SplitMode.C)
    except Exception:
        return None


def _tokenize_sudachi(text, mode="C"):
    tok = _get_tokenizer()
    out = []
    for m in tok.tokenize(text, _sudachi_mode(mode)):
        pos = m.part_of_speech()
        out.append({
            "surface": m.surface(),
            "normalized": m.normalized_form(),
            "reading": m.reading_form(),
            "pos": list(pos),
            "start": m.begin(),
            "end": m.end(),
        })
    return out


def _tokenize_janome(text):
    tok = _get_tokenizer()
    out = []
    for m in tok.tokenize(text):
        s = m.surface
        base = m.base_form or s
        pos = (m.part_of_speech or "").split(",")
        out.append({
            "surface": s, "normalized": base, "reading": m.reading or "",
            "pos": pos, "start": None, "end": None,
        })
    return out


_RE_FALLBACK = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々〆ヵヶ]+"
    r"|[A-Za-z0-9][A-Za-z0-9_.:/%+\-]*|.", re.S)


def _tokenize_regex(text):
    return [{"surface": m.group(0), "normalized": m.group(0), "reading": "",
             "pos": ["名詞" if re.match(r"[\u3040-\u30ff\u4e00-\u9fff]", m.group(0)) else "*"],
             "start": m.start(), "end": m.end()} for m in _RE_FALLBACK.finditer(text)]


def tokenize(text, mode="C"):
    """返回 token 列表；每个 token 含 surface/normalized/reading/pos/start/end。"""
    text = text or ""
    if not text:
        return []
    b = backend()
    if b == "sudachi":
        return _tokenize_sudachi(text, mode)
    if b == "janome":
        return _tokenize_janome(text)
    return _tokenize_regex(text)


def split_sentences(text):
    """日文句子切分；保留句末标点，不依赖分词器。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"(?<=[。！？!?])\s*|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


_STOP = {
    "する", "為る", "ある", "有る", "いる", "居る", "なる", "成る",
    "こと", "もの", "ため", "よう", "など", "この", "その", "あの",
    "これ", "それ", "あれ", "ここ", "そこ", "また", "および", "及び",
    "について", "による", "より", "から", "まで", "として",
}


def content_words(text, limit=None, min_len=2):
    """抽取内容词（名词/专名/动词/形容词），按频次与长度排序；用于关键词候选。"""
    counts = {}
    for t in tokenize(text, "C"):
        pos = t.get("pos") or []
        if not pos:
            continue
        top = pos[0]
        if top not in ("名詞", "固有名詞", "動詞", "形容詞", "副詞"):
            continue
        w = (t.get("normalized") or t.get("surface") or "").strip()
        if len(w) < min_len or w in _STOP or re.fullmatch(r"[\d\W_]+", w):
            continue
        key = w
        d = counts.setdefault(key, {"word": w, "surface": t.get("surface") or w,
                                    "pos": top, "count": 0})
        d["count"] += 1
    rows = sorted(counts.values(), key=lambda x: (-x["count"], -len(x["word"]), x["word"]))
    return rows[:limit] if limit else rows


def _selftest():
    s = "日本語の文献を処理する。次に引用を確認する。"
    toks = tokenize(s)
    assert toks and "".join(t["surface"] for t in toks) == s, toks
    assert any(t["surface"] == "日本語" for t in toks), toks
    assert split_sentences(s) == ["日本語の文献を処理する。", "次に引用を確認する。"], split_sentences(s)
    words = content_words(s)
    assert any(w["word"] == "文献" for w in words), words
    assert all(len(w["word"]) >= 2 for w in words), words
    print("ja_tokenize selftest: PASS (%s, %d tokens)" % (backend(), len(toks)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selfcheck":
        sys.exit(_selftest())
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "日本語の文献を処理する。"
    print(json.dumps({"backend": backend(), "tokens": tokenize(text),
                      "sentences": split_sentences(text),
                      "content_words": content_words(text, 20)},
                     ensure_ascii=False, indent=1))
