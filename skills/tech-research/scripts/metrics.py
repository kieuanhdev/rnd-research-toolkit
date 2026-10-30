#!/usr/bin/env python3
"""Fetch adoption metrics (GitHub + package registries) for the tools a report compares.

    metrics.py tools.json --json > metrics.json      # fetch
    metrics.py --markdown metrics.json > metrics.md  # render the Vietnamese table

tools.json: [{"name": "Patrol", "github": "leancodepl/patrol", "pubdev": ["patrol"],
              "npm": [], "pypi": [], "crates": []}]   (every key but "name" is optional)

Numbers come only from the APIs, never estimated; a missing value renders "không có dữ liệu".
GitHub's limit is 60 requests/hour unauthenticated; the token comes from GH_TOKEN or, if unset,
from `gh auth token` when the gh CLI is logged in. "Issue + PR mở" is GitHub's open_issues_count,
which includes open pull requests.
crates.io only publishes a 90-day figure, so those cells are labelled "(90 ngày)".
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

from common import get_json, today
from sources_table import human_number

NO_DATA = "không có dữ liệu"
HEADER = "| Công cụ | Sao GitHub | Push gần nhất | Issue + PR mở | Lượt tải 30 ngày | Ngày lấy |"

# registry key in tools.json -> (display name, URL template, path to the count in the JSON)
REGISTRIES = {
    "pubdev": ("pub.dev", "https://pub.dev/api/packages/{}/score", ("downloadCount30Days",)),
    "npm": ("npm", "https://api.npmjs.org/downloads/point/last-month/{}", ("downloads",)),
    "pypi": ("PyPI", "https://pypistats.org/api/packages/{}/recent", ("data", "last_month")),
    "crates": ("crates.io", "https://crates.io/api/v1/crates/{}", ("crate", "recent_downloads")),
}


def dig(data, path):
    for key in path:
        if not isinstance(data, dict) or data.get(key) is None:
            return None
        data = data[key]
    return data


def github_token():
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def normalize_tool(t):
    """Tolerate hand-written tools.json: a bare string instead of a list (which would otherwise be
    iterated letter by letter into real counts for one-letter packages), a full GitHub URL, and
    PyPI names that pypistats only accepts in PEP 503 form."""
    t = dict(t)
    for key in REGISTRIES:
        value = t.get(key) or []
        t[key] = [value] if isinstance(value, str) else list(value)
    t["pypi"] = [re.sub(r"[-_.]+", "-", p).lower() for p in t["pypi"]]
    if t.get("github"):
        repo = re.sub(r"^(https?://)?(www\.)?github\.com/", "", t["github"].strip()).strip("/")
        t["github"] = "/".join(repo.removesuffix(".git").split("/")[:2])
    return t


def fetch_github(repo, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data, err = get_json(f"https://api.github.com/repos/{repo}", headers=headers)
    if err:
        return {"error": err}
    return {"stars": data.get("stargazers_count"), "pushed_at": data.get("pushed_at"),
            "open_issues": data.get("open_issues_count")}


def fetch_downloads(key, package):
    name, url, path = REGISTRIES[key]
    data, err = get_json(url.format(urllib.parse.quote(package, safe="@")))
    count = None if err else dig(data, path)
    if count is None:
        return {"registry": name, "package": package, "error": err or "no download count"}
    return {"registry": name, "package": package, "downloads_30d": count}


def fetch_all(tools):
    token = github_token()
    rows = []
    for t in map(normalize_tool, tools):
        row = {"name": t["name"], "fetched_at": today(),
               "github": fetch_github(t["github"], token) if t.get("github") else {"error": "no repo"},
               "downloads": []}
        for key in REGISTRIES:
            for package in t[key]:
                row["downloads"].append(fetch_downloads(key, package))
        rows.append(row)
    return rows


def render_markdown(rows):
    lines = [HEADER, "|---|---|---|---|---|---|"]
    for r in rows:
        gh = r.get("github") or {}
        if "error" in gh:
            missing = NO_DATA + (" (rate limit)" if "rate limit" in gh["error"].lower() else "")
            stars = pushed = issues = missing
        else:
            stars = human_number(gh.get("stars"))
            pushed = (gh.get("pushed_at") or NO_DATA)[:10]
            issues = NO_DATA if gh.get("open_issues") is None else str(gh["open_issues"])
        parts = []
        for d in r.get("downloads", []):
            if "error" in d:
                parts.append(f"{d['package']} ({d['registry']}): {NO_DATA}")
            else:
                suffix = " (90 ngày)" if d["registry"] == "crates.io" else ""
                parts.append(f"{d['package']} ({d['registry']}): {human_number(d['downloads_30d'])}{suffix}")
        downloads = "; ".join(parts) or NO_DATA
        lines.append(f"| {r['name']} | {stars} | {pushed} | {issues} | {downloads} | {r['fetched_at']} |")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("tools_json", nargs="?")
    p.add_argument("--json", action="store_true", help="fetch and print metrics JSON")
    p.add_argument("--markdown", metavar="METRICS_JSON", help="render a metrics.json as Markdown")
    args = p.parse_args()
    if args.markdown:
        with open(args.markdown, encoding="utf-8") as f:
            print(render_markdown(json.load(f)))
        return 0
    if not args.tools_json:
        p.error("give tools.json or --markdown metrics.json")
    with open(args.tools_json, encoding="utf-8") as f:
        print(json.dumps(fetch_all(json.load(f)), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
