# -*- coding: utf-8 -*-
"""Non-article page classification tests (cover/toc/abstract/notice)."""
import json
import os
import tempfile
import unittest

from metapy import doc_quality


def _doc(tmp, text, name="d"):
    dd = os.path.join(tmp, name)
    os.makedirs(os.path.join(dd, "unified"), exist_ok=True)
    page = {"unified": [{"main_text": text, "type": "Text"}]}
    with open(os.path.join(dd, "unified", "page_0.json"), "w", encoding="utf-8") as fh:
        json.dump(page, fh, ensure_ascii=False)
    return dd


class DocTypeTest(unittest.TestCase):
    def test_toc_page(self):
        text = ("2011 Vol. 47, No. 1\n"
                "仰臥位搬送時の加減速による血圧変動の解析 1\n"
                "視線入力システムによるポイント操作 10\n"
                "把持動作の手指プリシェイピング 31")
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, text)
            self.assertEqual(doc_quality.detect_document_type(dd, {}), "toc")
            meta, _ = doc_quality.repair_metadata({"title": {"value": None}}, dd)
            self.assertIn("title_not_applicable", meta["quality"]["flags"])
            self.assertNotIn("title_missing", meta["quality"]["flags"])

    def test_award_abstract_page(self):
        text = ("研究奨励\n(1) モバイルオーディションの研究\n"
                "研究奨励\n(2) 脳動脈瘤の研究\n1981 年生")
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, text)
            self.assertEqual(doc_quality.detect_document_type(dd, {}), "multi_abstract")

    def test_society_notice_page(self):
        text = "研究部会\n研究部会名 部会長名\n複写される方へ\nNotice about photocopying"
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, text)
            self.assertEqual(doc_quality.detect_document_type(dd, {}), "announcement")

    def test_cover_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, "")
            self.assertEqual(doc_quality.detect_document_type(dd, {}), "cover")

    def test_toc_page_with_article_not_downgraded(self):
        text = ("2011 Vol. 47, No. 1\n"
                "仰臥位搬送時の加減速による血圧変動の解析 1\n"
                "視線入力システムによるポイント操作 10\n"
                "把持動作の手指プリシェイピング 31")
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, text)
            meta, _ = doc_quality.repair_metadata(
                {"title": {"value": "症例報告"}, "authors": [{"name": "著者"}]}, dd)
            self.assertEqual(meta["document_type"], "article")
            self.assertTrue(meta["is_single_article"])


class FilenameFallbackTest(unittest.TestCase):
    def test_journal_and_year_from_import_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, "本文", "01_文藝言語研究_1984_犬井善壽")
            meta, _ = doc_quality.repair_metadata(
                {"journal": {"value": "月詣和歌集"}, "year": {"value": None}}, dd)
            self.assertEqual(meta["journal"]["value"], "文藝言語研究")
            self.assertEqual(meta["journal"]["confidence"]["source"], "filename_fallback")
            self.assertEqual(meta["year"]["value"], 1984)
            self.assertIn("journal_from_filename", meta["quality"]["flags"])
            self.assertIn("year_from_filename", meta["quality"]["flags"])

    def test_real_journal_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            dd = _doc(tmp, "本文", "01_文藝言語研究_1984_犬井善壽")
            meta, _ = doc_quality.repair_metadata(
                {"journal": {"value": "文藝言語研究"}}, dd)
            self.assertEqual(meta["journal"]["value"], "文藝言語研究")
            self.assertNotIn("journal_from_filename", meta["quality"]["flags"])


if __name__ == "__main__":
    unittest.main()
