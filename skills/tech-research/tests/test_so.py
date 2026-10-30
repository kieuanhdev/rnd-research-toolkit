import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import so_collect  # noqa: E402

SEARCH = {"items": [
    {"question_id": 1, "title": "No answers", "link": "https://so/q/1", "answer_count": 0, "score": 50,
     "creation_date": 1700000000},
    {"question_id": 2, "title": "Low &amp; answered", "link": "https://so/q/2", "answer_count": 1, "score": 1,
     "creation_date": 1700000000, "tags": ["flutter"]},
    {"question_id": 3, "title": "High", "link": "https://so/q/3", "answer_count": 2, "score": 9,
     "creation_date": 1700000000, "accepted_answer_id": 30},
]}


class ParseSearchTest(unittest.TestCase):
    def test_drops_unanswered_and_sorts_by_score(self):
        results = so_collect.parse_search(SEARCH)
        self.assertEqual([r["id"] for r in results], ["3", "2"])
        self.assertTrue(results[0]["accepted"])
        self.assertEqual(results[1]["title"], "Low & answered")
        self.assertEqual(results[0]["date"], "2023-11-14")


class QuestionMarkdownTest(unittest.TestCase):
    def test_accepted_answer_first_and_html_stripped(self):
        q = {"link": "https://so/q/3", "title": "T", "tags": ["a"], "score": 9, "body": "<p>Hi <b>there</b></p>"}
        answers = [
            {"score": 20, "is_accepted": False, "owner": {"display_name": "top"}, "body": "<p>top</p>"},
            {"score": 2, "is_accepted": True, "owner": {"display_name": "acc"}, "body": "<pre><code>x()</code></pre>"},
        ]
        md = so_collect.question_markdown(q, answers)
        self.assertTrue(md.startswith("Nguồn: Stack Overflow — https://so/q/3"))
        self.assertIn("Hi there", md)
        self.assertLess(md.index("acc"), md.index("top"))
        self.assertIn("```\nx()\n```", md)


if __name__ == "__main__":
    unittest.main()
