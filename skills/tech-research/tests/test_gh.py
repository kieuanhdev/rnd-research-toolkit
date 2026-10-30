import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import gh_collect  # noqa: E402


class ParseIssuesTest(unittest.TestCase):
    def test_excludes_pull_requests(self):
        data = {"items": [
            {"number": 1, "title": "bug", "html_url": "u1", "state": "open", "created_at": "2026-01-02T00:00:00Z",
             "comments": 5, "reactions": {"total_count": 3}, "labels": [{"name": "bug"}]},
            {"number": 2, "title": "pr", "pull_request": {}, "comments": 9},
        ]}
        results = gh_collect.parse_issues(data)
        self.assertEqual([r["number"] for r in results], [1])
        self.assertEqual(results[0]["date"], "2026-01-02")
        self.assertEqual(results[0]["labels"], ["bug"])


class MarkdownTest(unittest.TestCase):
    def test_issue_marks_maintainers(self):
        issue = {"html_url": "https://github.com/o/r/issues/1", "title": "T", "state": "open",
                 "user": {"login": "u"}, "body": "body"}
        comments = [{"user": {"login": "m"}, "author_association": "MEMBER", "body": "fix"},
                    {"user": {"login": "x"}, "author_association": "NONE", "body": "+1"}]
        md = gh_collect.issue_markdown(issue, comments)
        self.assertTrue(md.startswith("Nguồn: GitHub Issue — https://github.com/o/r/issues/1"))
        self.assertIn("- m (maintainer): fix", md)
        self.assertIn("- x: +1", md)

    def test_releases_skip_drafts(self):
        rels = [{"tag_name": "v2", "draft": True, "body": "secret"},
                {"tag_name": "v1", "prerelease": True, "published_at": "2026-05-01T00:00:00Z", "body": "notes"}]
        md = gh_collect.releases_markdown("o/r", rels)
        self.assertNotIn("secret", md)
        self.assertIn("## v1 (pre-release) · 2026-05-01", md)


if __name__ == "__main__":
    unittest.main()
