# -*- coding: utf-8 -*-
import json
import os
import pathlib
import tempfile
import time
import unittest
from unittest import mock

import merge_out
import pipeline
import unify
import viewer


class UnifiedSafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.out_root = self.root / "out"
        self.doc_dir = self.out_root / "paper"
        self.udir = self.doc_dir / "unified"
        self.udir.mkdir(parents=True)
        self.page = self.udir / "page_0.json"
        self.page.write_text(json.dumps({"unified": [{"uid": "u0"}]}), encoding="utf-8")
        self.cfg = self.root / "channels.json"
        self.cfg.write_text("{}", encoding="utf-8")
        self.sources = {}
        for ch in ("mineru", "dots", "paddle"):
            src = self.root / "inbox" / ch
            src.mkdir(parents=True)
            self.sources[ch] = str(src)
        self.saved_cfg = (pipeline.CFG, pipeline.CFG_FP, pipeline._io.CFG, pipeline._io.CFG_FP)

    def tearDown(self):
        pipeline.CFG, pipeline.CFG_FP, pipeline._io.CFG, pipeline._io.CFG_FP = self.saved_cfg
        self.tmp.cleanup()

    def test_stale_unified_is_preserved_but_not_loaded(self):
        pages, driven = pipeline._load_fresh_unified(str(self.udir), time.time())
        self.assertIsNone(pages)
        self.assertFalse(driven)
        self.assertTrue(self.page.is_file())

    def test_fresh_unified_is_loaded(self):
        summary = self.udir / "_unified_summary.json"
        summary.write_text("{}", encoding="utf-8")
        now = time.time()
        os.utime(summary, (now + 1, now + 1))
        pages, driven = pipeline._load_fresh_unified(str(self.udir), now)
        self.assertTrue(driven)
        self.assertEqual(pages, {0: [{"uid": "u0"}]})

    def _run_main(self, extra=()):
        with mock.patch.object(pipeline, "log"), \
                mock.patch.object(pipeline, "render_pages", return_value=[(100, 100)]), \
                mock.patch.object(pipeline, "scan_inbox", return_value=self.sources), \
                mock.patch.object(pipeline, "preserve_raw", return_value=0), \
                mock.patch.object(pipeline, "write_calib_marker"), \
                mock.patch.object(pipeline, "adapt_mineru", return_value={0: []}), \
                mock.patch.object(pipeline, "adapt_dots", return_value={0: []}), \
                mock.patch.object(pipeline, "adapt_paddle", return_value={0: []}), \
                mock.patch.object(pipeline, "build_viewer"), \
                mock.patch.object(pipeline, "build_compare_viewer") as compare, \
                mock.patch.object(merge_out, "merge_doc", return_value={"pages": 1, "blocks": 0}):
            pipeline.main([str(self.root / "paper.pdf"), "--out", str(self.doc_dir),
                           "--channels", str(self.cfg), *extra])
        return compare

    def test_no_unify_preserves_existing_directory(self):
        compare = self._run_main(("--no-unify",))
        self.assertTrue(self.page.is_file())
        self.assertIsNone(compare.call_args.kwargs["unified_pages"])
        self.assertFalse(compare.call_args.kwargs["unified_driven"])

    def test_unify_failure_preserves_directory_and_uses_out_root(self):
        with mock.patch.object(unify, "unify_doc", side_effect=RuntimeError("mock failure")) as call:
            self._run_main()
        self.assertTrue(self.page.is_file())
        call.assert_called_once_with("paper", os.path.dirname(os.path.abspath(self.doc_dir)))

    def test_citation_hover_target_covers_nonreview_block(self):
        block = {"cat": "Text", "box": [10, 10, 90, 40], "text": "原文[1]"}
        unified = [
            {"uid": "u0_1", "page": 1, "type": "Text", "box": [10, 10, 90, 40],
             "cross_page": {"spans": False}, "members": {"mineru": [block]},
             "readings": [{"ch": "mineru", "text": "原文[1]", "dice": 1.0, "flags": []}],
             "main_text": "原文[1]", "divergence": {"kind": "none", "detail": ""},
             "confidence": {"level": "high", "basis": ""}, "review": False},
            {"uid": "u0_2", "page": 1, "type": "Text", "box": [10, 50, 90, 80],
             "cross_page": {"spans": False}, "members": {"mineru": [block]},
             "readings": [{"ch": "mineru", "text": "原文[1]", "dice": 1.0, "flags": []}],
             "main_text": "原文[1]", "divergence": {"kind": "none", "detail": ""},
             "confidence": {"level": "high", "basis": ""}, "review": False},
            {"uid": "u0_3", "page": 1, "type": "Text", "box": [10, 90, 90, 120],
             "cross_page": {"spans": False}, "members": {"mineru": [block]},
             "readings": [{"ch": "mineru", "text": "原文[1]", "dice": 1.0, "flags": []}],
             "main_text": "原文[1]", "divergence": {"kind": "none", "detail": ""},
             "confidence": {"level": "high", "basis": ""}, "review": False},
        ]
        meta = {"citation_spans": [{"page": 1, "uid": "u0_1", "kind": "numeric",
                                    "sentence": "原文[1]", "raw": "原文[1]",
                                    "citation_text": "[1]", "offset": [2, 5],
                                    "linked_refs": [], "confidence": "exact"}],
                "footnote_refs": [{"page": 1, "uid": "u0_2", "num": "1",
                                   "confidence": {"level": "high"}}],
                "references": [{"page": 1, "uid": "u0_3", "num": 1,
                                "confidence": {"level": "high"}}]}
        out = self.root / "cite_viewer.html"
        viewer.build_compare_viewer(
            str(out), "cite test", [(100, 100)],
            {"mineru": {0: [block]}, "dots": None, "paddle": None},
            unified_pages={0: unified}, unified_driven=True, meta=meta)
        html = out.read_text(encoding="utf-8")
        self.assertEqual(html.count('<rect class="r cite-target"'), 3)
        for uid in ("u0_1", "u0_2", "u0_3"):
            self.assertIn('<rect class="r cite-target" data-u="%s"' % uid, html)
        self.assertIn(".refs .mf[data-u]", html)
        self.assertIn("citeHover(mf,true)", html)
        self.assertIn("citeHover(mf,false)", html)
        self.assertIn(".r.cite-target.cite-on", html)
        self.assertIn("r.classList.add('cite-on')", html)
        self.assertIn('id="citepop"', html)
        self.assertIn('id="citesvg"', html)
        self.assertIn("cs.setAttribute('viewBox'", html)
        self.assertIn('class="cpbox"', html)
        self.assertIn(".pane:not(.meta) > .pmask", html)

    def test_citation_sentences_are_grouped_without_losing_citations(self):
        sentence = "原文[1]与[2]"
        meta = {
            "references": [
                {"page": 2, "num": 1, "title": "First"},
                {"page": 2, "num": 2, "title": "Second"},
            ],
            "citation_spans": [
                {"page": 1, "uid": "u0_1", "kind": "numeric", "sentence": sentence,
                 "offset": [2, 5], "linked_refs": [{"index": 0}], "confidence": "exact"},
                {"page": 1, "uid": "u0_1", "kind": "numeric", "sentence": sentence,
                 "offset": [6, 9], "linked_refs": [{"index": 1}], "confidence": "partial"},
                {"page": 1, "uid": "u0_2", "kind": "numeric", "sentence": sentence,
                 "offset": [2, 5], "linked_refs": [{"index": 0}], "confidence": "exact"},
            ],
        }
        panel = viewer._meta_cell(meta, 1)
        self.assertIn("本页引文句 2 条(cspan)", panel)
        self.assertIn("3 处引文", panel)
        self.assertEqual(panel.count('<tr class="mf '), 2)
        self.assertEqual(panel.count("<mark>"), 3)
        self.assertIn('<tr class="mf mid" data-u="u0_1"', panel)
        self.assertIn("→ #1 First", panel)
        self.assertIn("→ #2 Second", panel)
        overview = viewer._meta_overview(meta)
        self.assertIn("引文句 2 条</b>(cspan) · 3 处引文", overview)

    def test_explanatory_footnote_shows_raw_text_not_missing_title(self):
        meta = {"footnote_refs": [{"page": 1, "uid": "u0_1", "num": "36",
                                   "raw": "산성의 위치와 복원 경위를 설명한다.", "title": None,
                                   "confidence": {"level": "low"}}]}
        panel = viewer._meta_cell(meta, 1)
        self.assertIn("本页脚注 1 条(frefs)", panel)
        self.assertIn("脚注原文", panel)
        self.assertIn("산성의 위치와 복원 경위를 설명한다.", panel)
        self.assertNotIn("未抽出", panel)

    def test_reference_hover_uses_matching_member_box(self):
        wrong = {"cat": "Text", "box": [10, 80, 90, 100], "text": "Hounslow, Water quality data."}
        right = {"cat": "Text", "box": [10, 10, 90, 40],
                 "text": "Filipek, Interaction of acid mine drainage."}
        unified = [{"uid": "u0_1", "page": 1, "type": "Text", "box": wrong["box"],
                    "cross_page": {"spans": False}, "members": {"mineru": [wrong, right]},
                    "readings": [{"ch": "mineru", "text": wrong["text"] + "\n" + right["text"],
                                  "dice": 1.0, "flags": []}],
                    "main_text": wrong["text"] + "\n" + right["text"],
                    "divergence": {"kind": "none", "detail": ""},
                    "confidence": {"level": "high", "basis": ""}, "review": False}]
        meta = {"references": [{"page": 1, "uid": "u0_1", "num": 14,
                                "raw": right["text"], "title": "Interaction of acid mine drainage",
                                "confidence": {"level": "high"}}]}
        out = self.root / "member_cite.html"
        viewer.build_compare_viewer(
            str(out), "member cite", [(100, 100)],
            {"mineru": {0: [wrong, right]}, "dots": None, "paddle": None},
            unified_pages={0: unified}, unified_driven=True, meta=meta)
        html = out.read_text(encoding="utf-8")
        self.assertIn('data-e="', html)
        self.assertIn('x="10" y="10" width="80" height="30"', html)
        self.assertNotIn('cite-target" data-u="u0_1" data-e=""', html)
        self.assertIn("mf.dataset.e", html)
        self.assertIn('rect.cite-target[data-e="', html)

    def test_overview_click_jumps_to_source_block(self):
        # 总览条目(含跨页关键词行)点击 → JS 跳转到原文块位置: scrollIntoView + 原图栏内定位 + 橙框闪烁
        block = {"cat": "Text", "box": [10, 10, 90, 40], "text": "原文"}
        def _u(p, uid, y):
            return {"uid": uid, "page": p + 1, "type": "Text", "box": [10, y, 90, y + 40],
                    "cross_page": {"spans": False}, "members": {"mineru": [block]},
                    "readings": [{"ch": "mineru", "text": "原文", "dice": 1.0, "flags": []}],
                    "main_text": "原文", "divergence": {"kind": "none", "detail": ""},
                    "confidence": {"level": "high", "basis": ""}, "review": False}
        unified_pages = {0: [_u(0, "u0_1", 10)], 1: [_u(1, "u1_1", 700)]}
        meta = {"keywords": [u"가나다"], "keywords_en": ["alpha"]}
        audit = {"issue": {"keywords": {"source": {"uid": "u1_1"},
                                        "source_en": {"uid": "u0_1"}}}}
        out = self.root / "jump_viewer.html"
        viewer.build_compare_viewer(
            str(out), "jump test", [(100, 100), (100, 100)],
            {"mineru": {0: [block], 1: [block]}, "dots": None, "paddle": None},
            unified_pages=unified_pages, unified_driven=True, meta=meta, audit=audit)
        html = out.read_text(encoding="utf-8")
        self.assertIn("function jumpToUid", html)
        self.assertIn("function flashAt", html)
        self.assertIn(".r.flash", html)
        self.assertIn("var UBOX=", html)
        self.assertIn("UBOX[uid]", html)
        self.assertIn("createElementNS", html)
        self.assertIn("imgw.scrollTop", html)
        self.assertIn('class="mf mid" data-u="u1_1"', html)   # 关键词行(跨页)带证据 uid
        self.assertIn('class="mf mid" data-u="u0_1"', html)   # 关键词(英)行带证据 uid

    def test_metadata_band_renders_inline_math(self):
        # cspan 句/文献题名/摘要此前只 HTML 转义, OCR 读出的行内公式($\approx/\frac/H_2O 式)
        # 以 LaTeX 源码裸露; _texesc=texlite+转义+白名单标签放行, 与正文块同一转换口径。
        sentence = u"광산배수(pH 7)는 $\\approx 660\\ mg\\ l^{-1}$ 이다"
        panel = viewer._meta_cell({"citation_spans": [{"page": 1, "uid": "u0_1",
                                                       "kind": "narrative", "sentence": sentence,
                                                       "offset": [0, 4], "confidence": "exact",
                                                       "linked_refs": []}]}, 1)
        self.assertIn(u"≈", panel)
        self.assertIn("<sup>-1</sup>", panel)
        ref_panel = viewer._meta_cell({"references": [{"page": 1, "uid": "u0_1", "num": 1,
                                                       "title": u"$\\frac{1}{2}$ 배수", "source": "",
                                                       "confidence": {"level": "high"}}]}, 1)
        self.assertIn('<i class="fr"><sup>1</sup>&frasl;<sub>2</sub></i>', ref_panel)
        plain = viewer._meta_cell({"citation_spans": [{"page": 1, "uid": "u0_1",
                                                       "kind": "narrative",
                                                       "sentence": u"일반 문장 <tag> 그대로",
                                                       "offset": [0, 4], "confidence": "exact",
                                                       "linked_refs": []}]}, 1)
        self.assertIn("&lt;tag&gt;", plain)   # 无公式特征时与纯转义等价
        self.assertNotIn("<sub>", plain)


class JapaneseTokenizerTest(unittest.TestCase):
    def test_tokenize_offsets_and_sentences(self):
        from metapy.ja_tokenize import tokenize, split_sentences
        s = "日本語の文献を処理する。次に引用を確認する。"
        toks = tokenize(s)
        self.assertTrue(toks)
        self.assertEqual("".join(t["surface"] for t in toks), s)
        self.assertEqual(split_sentences(s),
                         ["日本語の文献を処理する。", "次に引用を確認する。"])

    def test_content_words(self):
        from metapy.ja_tokenize import content_words
        words = content_words("日本語の文献を処理する。文献を確認する。")
        self.assertTrue(words)
        self.assertTrue(any("文献" in w["word"] for w in words))


class JapaneseDateTest(unittest.TestCase):
    def test_era_to_gregorian(self):
        from metapy.ja_date import normalize_year, normalize_date
        self.assertEqual(normalize_year("令和6年"), "2024")
        self.assertEqual(normalize_year("平成30年"), "2018")
        self.assertEqual(normalize_year("昭和55年"), "1980")
        self.assertEqual(normalize_year("R6"), "2024")
        d = normalize_date("令和6年3月1日")
        self.assertEqual(d["normalized"], "2024-03-01")


class JapaneseMetadataTest(unittest.TestCase):
    def test_name_and_affiliation_keys(self):
        from metapy.ja_names import name_key, affiliation_key, normalize_affiliation
        self.assertEqual(name_key("山田 太郎"), name_key("山田　太郎"))
        self.assertEqual(normalize_affiliation("東京大学：113-8654 本郷"), "東京大学")
        self.assertEqual(affiliation_key("東京大学：113-8654 本郷"), "東京大学")

    def test_auto_keywords_only_when_empty(self):
        from metapy.ja_keywords import ensure_keywords
        m = {"title": {"value": "アプタマー技術による疾患プロテオミクス"},
             "abstract": {"value": "アプタマーで血液中の蛋白質を解析する。"},
             "keywords": []}
        self.assertTrue(ensure_keywords(m))
        self.assertEqual(m["keywords_source"], "auto")
        m2 = {"keywords": ["既存"]}
        self.assertFalse(ensure_keywords(m2))
        self.assertEqual(m2["keywords"], ["既存"])

    def test_reference_split(self):
        from metapy.ref_split import normalize_ref
        r = {"raw": "2) Yoshimura S, Toyoda K, Ohara T, et al: Takotsubo cardiomyopathy in acute ischemic stroke. Ann Neurol 64: 547-554, 2008",
             "title": "Toyoda K", "authors_raw": "Yoshimura S", "source": "Ohara T"}
        self.assertTrue(normalize_ref(r))
        self.assertEqual(r["title"], "Takotsubo cardiomyopathy in acute ischemic stroke")
        self.assertEqual(r["year"], "2008")
        self.assertEqual(r["pages"], "547-554")


class JapaneseCitationResolveTest(unittest.TestCase):
    def test_ibid_and_author_year(self):
        from metapy.cite_resolve import resolve_citations
        refs = [
            {"num": 1, "authors_raw": "山田 太郎", "year": "2020", "title": "地震探査", "uid": "u1"},
            {"num": 2, "authors_raw": "佐藤 花子", "year": "2021", "title": "断層", "uid": "u2"},
        ]
        spans = [
            {"page": 1, "uid": "a", "sentence": "山田 (2020)", "citation_text": "山田 (2020)",
             "authors": ["山田"], "year": "2020", "linked_refs": []},
            {"page": 1, "uid": "b", "sentence": "前掲の手法", "citation_text": "前掲",
             "authors": [], "year": None, "linked_refs": []},
        ]
        out = resolve_citations({"references": refs, "citation_spans": spans})
        self.assertEqual(out["citation_spans"][0]["linked_refs"][0]["index"], 0)
        self.assertEqual(out["citation_spans"][1]["resolve_method"], "ibid")


class VerticalFrontTest(unittest.TestCase):
    def test_title_and_author(self):
        from metapy.front_vertical import extract_page
        units = [
            {"uid": "body", "type": "Text", "box": [303, 154, 454, 1097],
             "main_text": "西行は、元永元年に生れ、数多くの歌を詠んだ。"},
            {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702],
             "main_text": "『月詣和歌集』所載西行歌本文小考"},
            {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053],
             "main_text": "犬 井 善 壽"},
        ]
        out = extract_page(units, 793, 1192)
        self.assertEqual(out["title"]["text"], "『月詣和歌集』所載西行歌本文小考")
        self.assertEqual(out["author_candidates"][0]["name"], "犬井善壽")

    def test_page_header_title_beats_author(self):
        from metapy.front_vertical import title_candidates
        units = [
            {"uid": "author", "type": "Section-header", "box": [625, 896, 655, 1060],
             "main_text": "清 登 典 子"},
            {"uid": "title", "type": "Page-header", "box": [711, 186, 746, 446],
             "main_text": "「恋の詞」と蕉風俳諧"},
        ]
        rows = title_candidates(units, 875, 1241)
        self.assertEqual(rows[0]["text"], "「恋の詞」と蕉風俳諧")


class VerticalLayoutTest(unittest.TestCase):
    @staticmethod
    def _units():
        return [
            {"uid": "p", "type": "Page-number", "box": [95, 116, 126, 136]},
            {"uid": "body1", "type": "Text", "box": [303, 154, 454, 1097]},
            {"uid": "body2", "type": "Text", "box": [246, 191, 298, 993]},
            {"uid": "title", "type": "Section-header", "box": [655, 255, 695, 702]},
            {"uid": "author", "type": "Section-header", "box": [572, 900, 602, 1053]},
            {"uid": "page2", "type": "Page-number", "box": [90, 1108, 102, 1125]},
        ]

    def test_vertical_order(self):
        from metapy.vertical_layout import detect_page, order_units, first_content
        units = self._units()
        self.assertTrue(detect_page(units, 793, 1192)["vertical"])
        ordered, _ = order_units(units, 793, 1192)
        self.assertEqual([u["uid"] for u in ordered][:3], ["title", "author", "body1"])
        self.assertEqual(first_content(ordered)["uid"], "title")

    def test_horizontal_not_vertical(self):
        from metapy.vertical_layout import detect_page
        wide = [{"uid": "w%d" % i, "type": "Text",
                 "box": [80, 150 + i * 120, 1100, 210 + i * 120]} for i in range(4)]
        self.assertFalse(detect_page(wide, 1200, 1600)["vertical"])


class MergeReadingOrderTest(unittest.TestCase):
    @staticmethod
    def _b(x0, y0, x1, y1, cat="Text", text=""):
        return {"ch": "mineru", "cat": cat, "box": [x0, y0, x1, y1], "text": text}

    def test_two_column_reads_left_then_right(self):
        blocks = [
            self._b(100, 600, 550, 700, text="L1"),
            self._b(650, 600, 1100, 700, text="R1"),
            self._b(100, 760, 550, 860, text="L2"),
            self._b(650, 760, 1100, 860, text="R2"),
            self._b(200, 100, 1000, 150, "Section-header", "title"),
            self._b(1000, 50, 1140, 80, "Page-header", "H"),
            self._b(100, 1500, 550, 1560, "Footnote", "F"),
        ]
        ordered = [b["text"] for b in merge_out.order_blocks(blocks, 1200)]
        self.assertEqual(ordered, ["H", "title", "L1", "L2", "R1", "R2", "F"])

    def test_single_column_stays_y_then_x(self):
        blocks = [
            self._b(100, 300, 1000, 350, text="B"),
            self._b(100, 200, 1000, 250, text="A"),
        ]
        ordered = [b["text"] for b in merge_out.order_blocks(blocks, 1200)]
        self.assertEqual(ordered, ["A", "B"])


if __name__ == "__main__":
    unittest.main()
