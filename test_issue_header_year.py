# -*- coding: utf-8 -*-
import unittest

from metapy import issue


class HeaderYearTest(unittest.TestCase):
    def test_header_year_is_used_when_regex_has_no_guard_signal(self):
        res = issue.extract(
            [(0, "u1", "「比較民俗研究」 23. 2009/3", "header")],
            1, set())
        self.assertEqual(res["year"]["value"], 2009)
        self.assertEqual(res["year"]["confidence"]["source"], "header")

    def test_body_citation_year_is_not_used(self):
        res = issue.extract(
            [(0, "u1", "この研究は1983年に発表された。", "text")],
            1, set())
        self.assertIsNone(res["year"]["value"])

    def test_top_bare_year_needs_publication_signal(self):
        res = issue.extract(
            [(0, "u1", "1983", "top")],
            1, set())
        self.assertIsNone(res["year"]["value"])

    def test_header_year_beats_received_year(self):
        res = issue.extract(
            [(0, "h", "J. Test Vol. 62 No. 2, Feb. 2013", "header"),
             (0, "t", "Received June 11, 2012", "text")],
            1, set())
        self.assertEqual(res["year"]["value"], 2013)
        self.assertEqual(res["year"]["confidence"]["source"], "header")

    def test_first_page_text_masthead_year_used(self):
        res = issue.extract(
            [(0, "t", "Vol. 53 No. 6 2003", "text")],
            1, set())
        self.assertEqual(res["year"]["value"], 2003)
        self.assertEqual(res["year"]["confidence"]["source"], "text_pub")

    def test_text_citation_with_pages_not_used_as_masthead(self):
        res = issue.extract(
            [(0, "t", "Vol. 53 No. 6, pp. 1-10, 2003", "text")],
            1, set())
        self.assertNotEqual(res["year"]["confidence"]["source"], "text_pub")


if __name__ == "__main__":
    unittest.main()
