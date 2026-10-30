import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import metrics  # noqa: E402

HEADER = "| Công cụ | Sao GitHub | Push gần nhất | Issue + PR mở | Lượt tải 30 ngày | Ngày lấy |"


def row(**kw):
    base = {"name": "Patrol", "fetched_at": "2026-10-27",
            "github": {"stars": 1453, "pushed_at": "2026-10-27T15:40:26Z", "open_issues": 120},
            "downloads": [{"registry": "pub.dev", "package": "patrol", "downloads_30d": 640619}]}
    base.update(kw)
    return base


class RenderMarkdownTest(unittest.TestCase):
    def test_table_header(self):
        self.assertEqual(metrics.render_markdown([row()]).splitlines()[0], HEADER)

    def test_full_row(self):
        line = metrics.render_markdown([row()]).splitlines()[2]
        self.assertIn("| Patrol | 1.5K | 2026-10-27 | 120 | patrol (pub.dev): 640.6K | 2026-10-27 |", line)

    def test_table_marks_missing_as_no_data(self):
        line = metrics.render_markdown([row(github={"error": "no repo"}, downloads=[])]).splitlines()[2]
        self.assertEqual(line.count("không có dữ liệu"), 4)

    def test_github_rate_limited_row(self):
        md = metrics.render_markdown([row(github={"error": "HTTP 403 rate limit exceeded"})])
        self.assertIn("không có dữ liệu (rate limit)", md)

    def test_downloads_joined(self):
        md = metrics.render_markdown([row(downloads=[
            {"registry": "pub.dev", "package": "patrol", "downloads_30d": 640619},
            {"registry": "npm", "package": "x", "error": "HTTP 404"},
            {"registry": "crates.io", "package": "serde", "downloads_30d": 386307292},
        ])])
        self.assertIn("patrol (pub.dev): 640.6K; x (npm): không có dữ liệu; serde (crates.io): 386.3M (90 ngày)", md)


class NormalizeToolTest(unittest.TestCase):
    def test_string_becomes_list(self):
        self.assertEqual(metrics.normalize_tool({"name": "P", "pubdev": "patrol"})["pubdev"], ["patrol"])

    def test_github_url_stripped(self):
        t = metrics.normalize_tool({"name": "D", "github": "https://github.com/wix/Detox.git/"})
        self.assertEqual(t["github"], "wix/Detox")

    def test_pypi_name_normalized(self):
        t = metrics.normalize_tool({"name": "F", "pypi": ["Flask_SQLAlchemy", "Django"]})
        self.assertEqual(t["pypi"], ["flask-sqlalchemy", "django"])


if __name__ == "__main__":
    unittest.main()
