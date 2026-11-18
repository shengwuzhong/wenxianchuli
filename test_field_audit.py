# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest

import field_audit as fa
import workbench_state as wb


class FieldAuditTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="field_audit_")
        self.z = wb.Zone(
            "T", "测试区", self.root,
            os.path.join(self.root, "uploads"),
            os.path.join(self.root, "out"),
            os.path.join(self.root, "archive"),
            os.path.join(self.root, "gui_runs.jsonl"),
            os.path.join(self.root, "prefs.json"),
            os.path.join(self.root, ".workbench", "state.db"),
            os.path.join(self.root, "out_llm_trial"),
        ).ensure()
        self.doc = "d1"
        self.dd = os.path.join(self.z.out, self.doc)
        os.makedirs(self.dd)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, obj):
        fp = os.path.join(self.dd, name)
        with open(fp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)

    def _meta(self):
        return {
            "title": {"value": "题名", "confidence": {"level": "high", "source": "vertical"}},
            "authors": [{"name": "作者甲"}, {"name": "作者乙"}],
            "journal": {"value": "某刊", "confidence": {"level": "high"}},
            "year": {"value": None, "confidence": {"level": "low"}},
            "volume": {"value": "12"},
            "issue": {"value": None, "confidence": {"source": "volume_only"}},
            "pages": {"value": "1-10"},
            "keywords": ["关键词"],
            "abstract": {"value": None},
            "affiliations": [],
            "references": [],
            "reference_candidates": [{"title": "候选"}],
            "citation_spans": [],
            "footnote_refs": [],
            "citation_resolve": {"total": 0, "unresolved": 0},
            "footnote_ref_validation": {"applicability": {"status": "none", "reason": "无脚注"}},
        }

    def test_sixteen_fields_and_statuses(self):
        self._write("metadata.json", self._meta())
        rows = fa.field_statuses(self.doc, self.z)
        self.assertEqual(16, len(rows))
        by = {r["id"]: r for r in rows}
        self.assertEqual("present", by["title"]["status"])
        self.assertEqual("present", by["authors"]["status"])
        self.assertEqual("not_checked", by["year"]["status"])
        self.assertEqual("not_applicable", by["issue"]["status"])
        self.assertEqual("uncertain", by["references"]["status"])
        self.assertEqual("not_checked", by["body"]["status"])
        self.assertEqual("not_checked", by["abstract"]["status"])
        # 空列表不是缺失证据；没有元数据审计时仍为未查
        self.assertEqual("not_checked", by["datasets"]["status"])
        self.assertEqual(16, len({r["id"] for r in rows}))

    def test_missing_metadata(self):
        rows = fa.field_statuses(self.doc, self.z)
        self.assertEqual(16, len(rows))
        by = {r["id"]: r for r in rows}
        self.assertEqual("extraction_failed", by["title"]["status"])
        self.assertEqual("not_checked", by["body"]["status"])
        self.assertEqual("not_checked", by["funding"]["status"])

    def test_entities_absent_confirmed_and_failed(self):
        self._write("metadata.json", self._meta())
        nd = os.path.join(self.z.ner, "fds_extract", "ner_lite", self.doc)
        os.makedirs(nd)
        with open(os.path.join(nd, "ner_lite.json"), "w", encoding="utf-8") as fh:
            json.dump({"records": [{"kind": "dataset", "name": "数据集A"}]}, fh,
                      ensure_ascii=False)
        with open(os.path.join(nd, "ner_lite_audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"counts": {"errors_network": 0, "dropped_parse_fail": 0}}, fh)
        by = {r["id"]: r for r in fa.field_statuses(self.doc, self.z)}
        self.assertEqual("present", by["datasets"]["status"])
        self.assertEqual("数据集A", by["datasets"]["value"])
        self.assertEqual("absent_confirmed", by["funding"]["status"])
        self.assertTrue(by["funding"]["negative"]["method"])

        with open(os.path.join(nd, "ner_lite_audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"counts": {"errors_network": 2, "dropped_parse_fail": 0}}, fh)
        by = {r["id"]: r for r in fa.field_statuses(self.doc, self.z)}
        self.assertEqual("extraction_failed", by["funding"]["status"])

    def test_summary(self):
        self._write("metadata.json", self._meta())
        s = fa.summary(self.doc, self.z)
        self.assertEqual(16, s["total"])
        self.assertEqual(5, s["core_total"])
        self.assertGreaterEqual(s["needs_audit"], 1)


if __name__ == "__main__":
    unittest.main()
