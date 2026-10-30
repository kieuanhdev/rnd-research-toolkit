#!/usr/bin/env python3
"""Check the tools the research plugin needs and print how to fix what is missing.

    python3 doctor.py          # kiểm tra, in lệnh sửa
    python3 doctor.py --fix    # in danh sách lệnh cài, hỏi xác nhận, cài rồi kiểm tra lại
    python3 doctor.py --fix --yes   # như trên nhưng không hỏi (dùng khi người dùng đã đồng ý)

Login steps (notebooklm login, gh auth login) are never run for the user.

Exit code 0 when every required check passes, 1 otherwise.
"""
import argparse
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


def install_plan():
    """Commands that can install what is missing. Logins are excluded on purpose."""
    pip = [sys.executable, "-m", "pip", "install", "--user"]
    pipx = shutil.which("pipx")

    def py_tool(pkg):
        return [pipx, "install", pkg] if pipx else pip + [pkg]

    plan = []
    if not shutil.which("yt-dlp"):
        plan.append(py_tool("yt-dlp"))
    if not shutil.which("notebooklm"):
        plan.append(py_tool("notebooklm-py"))
    if importlib.util.find_spec("playwright") is None:
        plan.append(pip + ["playwright"])
    if not find_chrome():
        plan.append([sys.executable, "-m", "playwright", "install", "chromium"])
    return plan


def apply_fix(assume_yes):
    plan = install_plan()
    if not plan:
        print("Không có gì để cài tự động.")
        return
    print("Sẽ chạy các lệnh sau:")
    for c in plan:
        print("  " + " ".join(c))
    if not assume_yes:
        if not sys.stdin.isatty() or input("Tiếp tục? [y/N] ").strip().lower() != "y":
            print("Đã huỷ. Chạy lại với --yes nếu bạn đồng ý cài.")
            return
    for c in plan:
        print("\n$ " + " ".join(c))
        if subprocess.run(c).returncode != 0:
            print("Lệnh trên lỗi, bỏ qua và chạy tiếp.")
    print("\nĐăng nhập (cần bạn tự làm): `notebooklm login`, và tuỳ chọn `gh auth login`.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    if args.fix:
        apply_fix(args.yes)
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
