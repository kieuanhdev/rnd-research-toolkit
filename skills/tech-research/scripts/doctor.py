#!/usr/bin/env python3
"""Check the tools the research plugin needs and print how to fix what is missing.

    python3 doctor.py

Exit code 0 when every required check passes, 1 otherwise.
"""
import importlib.util
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_infographic import find_chrome  # noqa: E402


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def main():
    rows = []  # (label, ok, required, fix)
    rows.append(("Python >= 3.9", sys.version_info >= (3, 9), True, "Cài Python 3.9 trở lên"))
    rows.append(("yt-dlp", bool(shutil.which("yt-dlp")), True, "pipx install yt-dlp"))
    has_nlm = bool(shutil.which("notebooklm"))
    rows.append(("notebooklm-py", has_nlm, True, "pipx install notebooklm-py"))
    if has_nlm:
        ok, _ = run(["notebooklm", "auth", "check", "--test"])
        rows.append(("NotebookLM đã đăng nhập", ok, True, "notebooklm login"))
    has_pw = importlib.util.find_spec("playwright") is not None
    rows.append(("Playwright (xuất ảnh infographic)", has_pw, False, "pip install --user playwright"))
    rows.append(("Chrome/Chromium (xuất ảnh infographic)", bool(find_chrome()), False,
                 "Cài Chrome, hoặc đặt CHROME_PATH, hoặc: playwright install chromium"))
    gh = bool(shutil.which("gh")) and run(["gh", "auth", "status"])[0]
    rows.append(("gh đã đăng nhập (tăng giới hạn số liệu GitHub)", gh, False, "gh auth login"))

    failed_required = False
    for label, ok, required, fix in rows:
        mark = "OK  " if ok else ("THIẾU" if required else "tuỳ chọn")
        print(f"[{mark}] {label}" + ("" if ok else f"  ->  {fix}"))
        failed_required |= (not ok and required)
    print("\nSẵn sàng." if not failed_required else "\nCòn thiếu mục bắt buộc, hãy sửa rồi chạy lại.")
    return 1 if failed_required else 0


if __name__ == "__main__":
    sys.exit(main())
