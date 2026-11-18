import unittest

from metapy.front import apply_title_fallback


class TitleFallbackTest(unittest.TestCase):
    def test_fills_empty_title_from_english(self):
        meta = {"title": {"value": ""},
                "title_en": {"value": "Editorial Statistics", "page": 1,
                             "confidence": {"score": 0.9}}}
        self.assertTrue(apply_title_fallback(meta))
        self.assertEqual(meta["title"]["value"], "Editorial Statistics")
        self.assertEqual(meta["title"]["confidence"]["source"], "title_en_fallback")
        self.assertTrue(meta["title_fallback_from_en"])

    def test_clears_stale_title_missing_flag(self):
        meta = {"title": {"value": ""},
                "title_en": {"value": "Editorial Statistics"},
                "quality": {"flags": ["title_missing", "needs_manual_review"]},
                "quality_flags": ["title_missing"]}
        self.assertTrue(apply_title_fallback(meta))
        self.assertNotIn("title_missing", meta["quality"]["flags"])
        self.assertIn("needs_manual_review", meta["quality"]["flags"])
        self.assertNotIn("title_missing", meta["quality_flags"])

    def test_does_not_overwrite_title(self):
        meta = {"title": {"value": "日本語題名"},
                "title_en": {"value": "English Title"}}
        self.assertFalse(apply_title_fallback(meta))
        self.assertEqual(meta["title"]["value"], "日本語題名")
        self.assertNotIn("title_fallback_from_en", meta)


if __name__ == "__main__":
    unittest.main()
