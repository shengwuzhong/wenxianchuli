# -*- coding: utf-8 -*-
"""工作台只读接口的单元测试（不启动 HTTP 服务）。"""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

import webapp


class WorkbenchDataTest(unittest.TestCase):
    def test_safe_doc_rejects_traversal(self):
        self.assertEqual(webapp._safe_doc("01_文藝言語研究_1984_犬井善壽"),
                         "01_文藝言語研究_1984_犬井善壽")
        for bad in ("", ".", "..", "../x", "a/b", "a\\b", "a b"):
            self.assertEqual(webapp._safe_doc(bad), "", bad)

    def test_channels_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = "01_test"
            os.makedirs(os.path.join(tmp, doc, "raw", "mineru_api"))
            os.makedirs(os.path.join(tmp, doc, "raw", "dots"))
            with mock.patch.object(webapp, "OUT", tmp):
                self.assertEqual(webapp._channel_presence(doc),
                                 {"mineru": True, "dots": True, "paddle": False})
                self.assertEqual(webapp._missing_channels(doc), ["paddle"])

    def test_meta_fields_and_quality(self):
        meta = {
            "title": {"value": "原题", "normalized": "正题", "confidence": {"level": "high", "source": "v"}},
            "authors": [{"name": "犬井善壽", "normalized": "犬井善壽"}],
            "journal": {"value": "文藝言語研究", "confidence": {"level": "mid", "source": "r"}},
            "year": {"value": 1984},
            "quality": {"flags": ["year_missing", "needs_manual_review"],
                        "document_type": "article", "is_single_article": True},
        }
        fields, raw, conf = webapp._meta_fields(meta)
        self.assertEqual(fields["title"], "正题")
        self.assertEqual(fields["authors"], ["犬井善壽"])
        self.assertEqual(fields["year"], "1984")
        self.assertEqual(raw["title"], "原题")
        self.assertEqual(conf["title"]["level"], "high")
        q = webapp._quality_of(meta)
        self.assertEqual(q["document_type"], "article")
        self.assertTrue(q["is_single_article"])
        self.assertIn("year_missing", q["flags"])

    def test_rescue_alerts_for_terminal_missing_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = "02_test"
            os.makedirs(os.path.join(tmp, doc, "raw", "mineru"))
            os.makedirs(os.path.join(tmp, doc, "raw", "dots"))
            now = time.time()
            job = {"doc": doc, "state": "degraded", "created_at": now - 20,
                   "updated_at": now - 1, "channel_err": {}}
            with mock.patch.object(webapp, "OUT", tmp):
                alerts = webapp._job_alerts(job, now)
            self.assertTrue(any(a["kind"] == "missing_channel" for a in alerts))

    def test_public_job_marks_stalled(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = "03_test"
            os.makedirs(os.path.join(tmp, doc, "raw", "mineru"))
            os.makedirs(os.path.join(tmp, doc, "raw", "dots"))
            os.makedirs(os.path.join(tmp, doc, "raw", "paddle"))
            now = time.time()
            job = {"doc": doc, "state": "运行中", "stage": "渠道解析",
                   "created_at": now - 300, "started_at": now - 200,
                   "updated_at": now - 120, "channel_err": {}}
            with mock.patch.object(webapp, "OUT", tmp):
                pub = webapp._public_job("j1", job)
            self.assertTrue(pub["stalled"])
            self.assertEqual(pub["heartbeat_age"], 120)

    def test_split_authors(self):
        self.assertEqual(webapp._split_authors("犬井善壽\n千草聡、小野のぞみ"),
                         ["犬井善壽", "千草聡", "小野のぞみ"])
        self.assertEqual(webapp._split_authors(["A", "A", " B "]), ["A", "B"])

    def test_review_fields_are_whitelisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = "04_test"
            ddir = os.path.join(tmp, doc)
            os.makedirs(ddir)
            with open(os.path.join(ddir, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump({"title": {"value": "旧题"}}, f, ensure_ascii=False)
            with mock.patch.object(webapp, "OUT", tmp):
                payload = webapp._save_override(doc, {"title": "新题", "evil": "x"}, "人工")
                self.assertEqual(payload["fields"]["title"], "新题")
                self.assertNotIn("evil", payload["override"])
                saved = json.load(open(os.path.join(ddir, "metadata_override.json"), encoding="utf-8"))
                self.assertEqual(saved["fields"]["title"], "新题")
                self.assertTrue(os.path.isfile(os.path.join(ddir, "_review_audit.jsonl")))


if __name__ == "__main__":
    unittest.main()
