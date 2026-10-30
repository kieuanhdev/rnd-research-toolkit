import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import hn_collect  # noqa: E402

KEYS = {"id", "title", "url", "hn_url", "author", "date", "points", "num_comments"}


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


class ParseSearchTest(unittest.TestCase):
    def test_parse_search_fields(self):
        results = hn_collect.parse_search(fixture("hn_search.json"))
        self.assertTrue(results)
        for r in results:
            self.assertEqual(set(r), KEYS)
            self.assertEqual(r["hn_url"], f"https://news.ycombinator.com/item?id={r['id']}")

    def test_parse_search_drops_zero_comment_and_sorts(self):
        results = hn_collect.parse_search(fixture("hn_search.json"))
        counts = [r["num_comments"] for r in results]
        self.assertNotIn(0, counts)
        self.assertEqual(counts, sorted(counts, reverse=True))


class ThreadMarkdownTest(unittest.TestCase):
    def test_thread_header_and_comments(self):
        md = hn_collect.thread_markdown(fixture("hn_item.json"))
        self.assertTrue(md.startswith("Nguồn: Hacker News — https://news.ycombinator.com/item?id=48733008"))
        self.assertIn("- sandcat_:", md)
        self.assertIn("  - iishanto:", md)

    def test_thread_text_strips_html(self):
        item = {"id": 1, "title": "T", "author": "a", "text": None, "url": None,
                "children": [{"author": "x", "text": "a &amp; b <p>c</p><a href='x'>d</a>", "children": []}]}
        md = hn_collect.thread_markdown(item)
        self.assertIn("a & b", md)
        self.assertIn("c", md)
        self.assertIn("d", md)
        self.assertNotIn("<", md)

    def test_big_thread_keeps_many_top_level_comments_in_rank_order(self):
        def reply(i, depth):
            kids = [reply(i * 10 + k, depth + 1) for k in range(5)] if depth < 4 else []
            return {"id": i, "author": f"r{i}", "text": "y" * 400, "children": kids}
        top = [{"id": 1000 + t, "author": f"top{t}", "text": "x" * 300,
                "children": [reply(t * 100 + k, 1) for k in range(5)]} for t in range(100)]
        item = {"id": 1, "title": "Big", "author": "a", "text": None, "url": None, "children": top}
        rank = [1000 + t for t in reversed(range(100))]
        md = hn_collect.thread_markdown(item, max_chars=60000, rank=rank)
        kept = [line for line in md.splitlines() if line.startswith("- top")]
        self.assertGreaterEqual(len(kept), 40)
        self.assertTrue(kept[0].startswith("- top99:"))

    def test_thread_truncates(self):
        item = {"id": 1, "title": "T", "author": "a", "text": "x" * 5000, "url": None,
                "children": [{"author": "y", "text": "z" * 5000, "children": []}]}
        md = hn_collect.thread_markdown(item, max_chars=1000)
        self.assertLessEqual(len(md), 1200)
        self.assertTrue(md.endswith("[…cắt bớt]"))


if __name__ == "__main__":
    unittest.main()
