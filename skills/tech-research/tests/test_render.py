import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "render_infographic.py")

try:
    import playwright  # noqa: F401
    from PIL import Image
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False


@unittest.skipUnless(HAVE_DEPS, "playwright or Pillow not installed")
class RenderTest(unittest.TestCase):
    def test_render_produces_png(self):
        with tempfile.TemporaryDirectory() as d:
            html = os.path.join(d, "in.html")
            png = os.path.join(d, "out.png")
            with open(html, "w", encoding="utf-8") as f:
                f.write('<!doctype html><meta charset="utf-8">'
                        '<body style="font-family:\'Noto Sans\';margin:0;padding:40px">'
                        "<h1>Kiểm thử tự động — Khoảng trống</h1></body>")
            out = subprocess.run([sys.executable, SCRIPT, html, png], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(os.path.exists(png))
            w, h = Image.open(png).size
            self.assertEqual(w, 2400)
            self.assertGreater(h, 0)
            self.assertEqual(out.stdout.strip(), f"{w}x{h}")


if __name__ == "__main__":
    unittest.main()
