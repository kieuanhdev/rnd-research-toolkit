#!/usr/bin/env python3
"""Render an infographic HTML page to PNG with headless Chrome.

    python3 render_infographic.py infographic.html infographic.png [--width 2400]

Uses Chrome/Chromium found on this machine (override with CHROME_PATH), else Playwright's own
Chromium (`playwright install chromium`). Takes a full-page screenshot at the given width and prints "WxH". Run it with plain
`python3` (not `python3 -I`): Playwright is installed in user site-packages.
"""
import argparse
import os
import shutil
import sys

CHROME_CANDIDATES = [
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    """CHROME_PATH env var, then common install paths, then PATH. None means use Playwright's own Chromium."""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("html")
    p.add_argument("png")
    p.add_argument("--width", type=int, default=2400)
    args = p.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Thiếu Playwright: cài bằng `pip install --user playwright`.", file=sys.stderr)
        return 3
    if not os.path.exists(args.html):
        print(f"Không tìm thấy file HTML: {args.html}", file=sys.stderr)
        return 3
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=find_chrome())
            page = browser.new_page(viewport={"width": args.width, "height": 1350})
            page.goto("file://" + os.path.abspath(args.html))
            page.wait_for_load_state("networkidle")
            page.screenshot(path=args.png, full_page=True)
            size = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.scrollHeight]")
            browser.close()
    except Exception as e:  # Chrome launch, navigation or screenshot failure
        print(f"Không xuất được ảnh: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    print(f"{size[0]}x{size[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
