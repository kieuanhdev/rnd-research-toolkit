import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import arxiv_collect  # noqa: E402

with open(os.path.join(HERE, "fixtures", "arxiv.xml"), encoding="utf-8") as f:
    FEED = f.read()


class ParseFeedTest(unittest.TestCase):
    def test_parse_feed_fields(self):
        results = arxiv_collect.parse_feed(FEED, "2000-01-01")
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(set(r), {"id", "title", "authors", "date", "abs_url", "pdf_url", "summary"})
            self.assertIn("/pdf/", r["pdf_url"])
            self.assertTrue(r["authors"])

    def test_parse_feed_skips_query_title(self):
        titles = [r["title"] for r in arxiv_collect.parse_feed(FEED, "2000-01-01")]
        self.assertFalse(any(t.startswith("arXiv Query") for t in titles))

    def test_parse_feed_cutoff(self):
        self.assertEqual(arxiv_collect.parse_feed(FEED, "2999-01-01"), [])


class BuildQueryTest(unittest.TestCase):
    def test_date_range_and_cs_category_in_query(self):
        q = arxiv_collect.build_query('"GUI testing" LLM', "202510270000", "202610272359")
        self.assertEqual(q, 'all:"GUI testing" AND all:LLM AND submittedDate:[202510270000 TO 202610272359] AND cat:cs.* ANDNOT cat:physics.*')

    def test_apostrophe_does_not_raise(self):
        q = arxiv_collect.build_query("Flutter's testing", "202510270000", "202610272359")
        self.assertIn("all:testing", q)


if __name__ == "__main__":
    unittest.main()
