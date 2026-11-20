# -*- coding: utf-8 -*-
"""无关键词行时的日文关键词抽取。

规则：
  - 只从 title / abstract / body 抽内容词；
  - 用 ja_tokenize 的日文分词（SudachiPy，缺失时降级）；
  - 名词/专名优先，标题词加权；
  - 过滤通用学术词、数字、单字；
  - 只写入空 keywords，不覆盖已有作者/编辑关键词；
  - 仅对日文文献生效: 题名/摘要无假名即跳过(2026-11-20 修)。

2026-11-20 缺陷说明(法/俄文献误判为日文):
  SudachiPy 会把 France/Goes/history/of 等高频外来词返回片假名规范形
  (フランス/ゲース/ヒストリー/オブ), 这些假名一旦写入 keywords,
  viewer._meta_is_ja 数到 >=3 个假名就判为日文文献, 元数据面板整体切成
  「日文标题 · 標題 / 日文摘要 · 要旨」。故此处必须先确认文档确为日文。
"""
import re

from .ja_tokenize import content_words

# 平假名 + 片假名(不含汉字): 非日文文献(拉丁/西里尔)原文不会出现
_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_KANA_MIN = 1          # 题名/摘要出现 1 个假名即视为日文, 避免纯汉字日文题名被漏

_STOP = {
    "研究", "報告", "技術", "結果", "方法", "目的", "対象", "考察", "文献",
    "本稿", "今回", "近年", "以上", "以下", "場合", "必要", "可能", "重要",
    "検討", "解析", "分析", "評価", "調査", "実験", "論文", "雑誌", "日本",
    "もの", "こと", "ため", "よう", "など", "この", "その", "これ", "それ",
}


def _text(obj):
    if isinstance(obj, dict):
        return str(obj.get("value") or "")
    return str(obj or "")


def _is_japanese_word(w):
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", w))


def extract_keywords(meta, limit=8):
    """返回日文关键词列表（按标题/摘要/正文加权排序）。"""
    scores = {}
    sources = [
        (_text(meta.get("title")), 3.0),
        (_text(meta.get("abstract")), 1.5),
        (_text(meta.get("body")), 1.0),
    ]
    for text, weight in sources:
        if not text:
            continue
        for row in content_words(text):
            w = row.get("word") or ""
            if len(w) < 2 or w in _STOP or not _is_japanese_word(w):
                continue
            if row.get("pos") not in ("名詞", "固有名詞"):
                continue
            if re.fullmatch(r"[\d\W_]+", w):
                continue
            scores[w] = scores.get(w, 0.0) + float(row.get("count") or 1) * weight
    rows = sorted(scores.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [w for w, _ in rows[:limit]]


def looks_japanese(meta):
    """文档是否日文: 题名/摘要原文里出现假名即视为日文。

    只看原文(未经日文分词), 因此拉丁/西里尔文本不会被 Sudachi 的片假名
    规范形污染误判。纯汉字题名(无假名)的日文文献会被判否——这类文献
    本就抽不出假名词, 跳过自动补词无损失。
    """
    for k in ("title", "abstract"):
        txt = _text(meta.get(k))
        if len(_KANA_RE.findall(txt)) >= _KANA_MIN:
            return True
    return False


def ensure_keywords(meta, limit=8):
    """原地补齐 keywords；返回是否写入。已有非空 keywords 不改。"""
    if meta.get("keywords"):
        return False
    if not looks_japanese(meta):
        return False
    kws = extract_keywords(meta, limit=limit)
    if not kws:
        return False
    meta["keywords"] = kws
    meta["keywords_auto"] = list(kws)
    meta["keywords_source"] = "auto"
    return True


def _selftest():
    meta = {"title": {"value": "アプタマー技術による大規模疾患プロテオミクス"},
            "abstract": {"value": "血液中のタンパク質をアプタマーで解析する。"
                                   "大規模プロテオーム研究とアプタマー技術。"},
            "keywords": []}
    kws = extract_keywords(meta)
    assert kws, kws
    assert all(_is_japanese_word(w) for w in kws), kws
    assert "アプタマー" in kws or "プロテオーム" in kws, kws
    assert ensure_keywords(meta) and meta["keywords_source"] == "auto"
    existed = {"keywords": ["既存"]}
    assert not ensure_keywords(existed) and existed["keywords"] == ["既存"]
    print("ja_keywords selftest: PASS -> %s" % kws)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
