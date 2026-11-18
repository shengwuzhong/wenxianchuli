import os
import unittest

import stages


class OptionalNerTest(unittest.TestCase):
    def setUp(self):
        self._old = (os.environ.pop("KCI_LLM_KEY", None),
                     os.environ.pop("KCI_ZJLAB_KEY", None))

    def tearDown(self):
        for k, v in zip(("KCI_LLM_KEY", "KCI_ZJLAB_KEY"), self._old):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_missing_key_is_skip_not_fatal(self):
        ctx = {"doc": "no_such_doc", "log": lambda m: None}
        msg = stages._st_ner(ctx)
        self.assertIn("跳过", msg)
        self.assertEqual(ctx.get("ner_status"), "extraction_failed")
        self.assertIn("KCI_LLM_KEY", ctx.get("warn", ""))

    def test_ner_is_not_required_for_order(self):
        # viewer/index 的依赖只有 merged/pages，NER 不是硬前置。
        self.assertEqual(stages.BY_ID["viewer"][4], ("merged",))
        self.assertEqual(stages.BY_ID["index"][4], ("pages",))


if __name__ == "__main__":
    unittest.main()
