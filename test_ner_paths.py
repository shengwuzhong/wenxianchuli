# -*- coding: utf-8 -*-
"""NER 产物落点回归：区根 / 叶子 / 尾斜杠 / fds_extract 父目录。"""
import os
import tempfile
import unittest

import ner_lite
import pipeline


class NerPathTest(unittest.TestCase):
    def test_leaf_root_and_leaf_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "out_llm_trial")
            leaf = os.path.join(root, "fds_extract", "ner_lite")
            self.assertEqual(ner_lite._leaf(root), leaf)
            self.assertEqual(ner_lite._leaf(leaf), leaf)
            self.assertEqual(ner_lite._leaf(leaf + os.sep), leaf)

    def test_leaf_accepts_fds_extract_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            fds = os.path.join(tmp, "out_llm_trial", "fds_extract")
            self.assertEqual(
                ner_lite._leaf(fds),
                os.path.join(fds, "ner_lite"),
            )

    def test_pipeline_ner_root_is_sibling_of_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_doc = os.path.join(tmp, "out", "doc_a")
            self.assertEqual(
                pipeline.ner_root_for_out(out_doc),
                os.path.join(tmp, "out_llm_trial"),
            )
            self.assertEqual(
                pipeline.ner_root_for_out(os.path.join(tmp, "zones", "zone_b", "out", "doc_b")),
                os.path.join(tmp, "zones", "zone_b", "out_llm_trial"),
            )

    def test_pipeline_root_matches_write_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_doc = os.path.join(tmp, "out", "doc_a")
            ner_root = pipeline.ner_root_for_out(out_doc)
            self.assertEqual(
                ner_lite._leaf(ner_root),
                os.path.join(ner_root, "fds_extract", "ner_lite"),
            )
            self.assertFalse(
                ner_lite._leaf(ner_root).startswith(os.path.join(tmp, "out", "fds_extract"))
            )


if __name__ == "__main__":
    unittest.main()
