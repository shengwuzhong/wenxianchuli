# -*- coding: utf-8 -*-
"""NER 产物落点回归：区根 / 叶子 / 尾斜杠 / fds_extract 父目录。"""
import os
import tempfile
import unittest
from unittest import mock

import ner_lite
import pipeline
import stages


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

    def test_stage_uses_ctx_ner_root(self):
        old = os.environ.get("KCI_ZJLAB_KEY")
        os.environ["KCI_ZJLAB_KEY"] = "test-only"
        seen = {}

        def _write(*args, **kwargs):
            seen.update(kwargs)
            return kwargs.get("dst")

        audit = {"counts": {"nominations": 0, "admitted": 0, "records": 0,
                            "dropped_anchor_miss": 0}}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ctx = {
                    "doc": "doc_a",
                    "log": lambda m: None,
                    "out_root": os.path.join(tmp, "out"),
                    "ner_root": os.path.join(tmp, "out_llm_trial"),
                }
                with mock.patch("pipeline.load_cfg", return_value={"llm": {}}), \
                        mock.patch("ner_lite.make_model", return_value=object()), \
                        mock.patch("ner_lite.run_doc", return_value=({}, audit)), \
                        mock.patch("ner_lite.write_outputs", side_effect=_write):
                    stages._st_ner(ctx)
                self.assertEqual(seen.get("dst"), ctx["ner_root"])
        finally:
            if old is None:
                os.environ.pop("KCI_ZJLAB_KEY", None)
            else:
                os.environ["KCI_ZJLAB_KEY"] = old


if __name__ == "__main__":
    unittest.main()
