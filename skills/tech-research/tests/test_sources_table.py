import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "sources_table.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import sources_table  # noqa: E402

ALL_HEADER = "| # | Loại | Nhãn | Nguồn | Đơn vị / tác giả | NotebookLM |"


def src(n, kind, label="Cộng đồng"):
    return {"n": n, "kind": kind, "label": label, "title": f"T{n}", "url": f"https://x/{n}",
            "publisher": "P", "nlm_status": "ready"}


class RenderAllTest(unittest.TestCase):
    def test_render_all_columns(self):
        lines = sources_table.render_all([src(1, "youtube", "Nhà cung cấp")]).splitlines()
        self.assertEqual(lines[0], ALL_HEADER)
        self.assertEqual(lines[2], "| 1 | youtube | Nhà cung cấp | [T1](https://x/1) | P | ready |")

    def test_render_all_without_nlm(self):
        out = sources_table.render_all([src(1, "so", "Cộng đồng")], nlm=False)
        self.assertNotIn("NotebookLM", out)
        self.assertEqual(out.splitlines()[0].count("|"), 6)

    def test_render_all_counts(self):
        md = sources_table.render_all([src(1, "youtube"), src(2, "youtube"), src(3, "hn")])
        self.assertIn("youtube: 2", md)
        self.assertIn("hn: 1", md)
        self.assertIn("Cộng đồng: 3", md)

    def test_render_all_rejects_bad_label(self):
        with self.assertRaises(SystemExit) as cm:
            sources_table.render_all([src(1, "web", "Vendor")])
        self.assertEqual(cm.exception.code, 2)


class RobustnessTest(unittest.TestCase):
    def test_missing_fields_and_odd_urls(self):
        md = sources_table.render_all([{"n": 1, "kind": "web", "label": "Cộng đồng ",
                                        "url": "https://x/a (b)", "nlm_status": "partial"}])
        self.assertIn("[N/A](https://x/a%20%28b%29)", md)
        self.assertIn("NotebookLM nạp thành công:** 1/1", md)

    def test_citation_key_maps_files_and_urls(self):
        sources = [dict(src(1, "hn"), nlm_input="/w/sources/hn-1.md"),
                   dict(src(2, "youtube"), nlm_input="https://x/2")]
        manifest = {"sources": [{"id": "s1", "input": "/w/sources/hn-1.md"},
                                {"id": "s2", "input": "https://x/2"}, {"id": "s3", "input": "zz"}]}
        self.assertEqual(sources_table.citation_key(sources, [manifest]),
                         ["s1 -> [1] P — T1", "s2 -> [2] P — T2", "s3 -> zz"])


class YoutubeModeTest(unittest.TestCase):
    def test_youtube_mode_vietnamese_headers_and_failed_count(self):
        search = {"results": [{"title": "V", "url": "https://y/1", "channel": "C", "subscribers": 1000,
                               "views": 500, "views_to_subscribers": 0.5, "duration_seconds": 600,
                               "upload_date": "2026-01-01"}],
                  "scanned": 15, "failed": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(search, f)
        out = subprocess.run([sys.executable, SCRIPT, f.name], capture_output=True, text=True).stdout
        os.unlink(f.name)
        self.assertTrue(out.startswith("| # | Video | Kênh | Người đăng ký | Lượt xem | Xem/Đăng ký | Thời lượng | Ngày đăng |"))
        self.assertIn("15 ứng viên, 0 không đọc được", out)


if __name__ == "__main__":
    unittest.main()
