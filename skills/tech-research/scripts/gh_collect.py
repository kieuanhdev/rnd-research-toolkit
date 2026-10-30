#!/usr/bin/env python3
"""Collect a tool's own GitHub signals: the most discussed issues, one issue as Markdown, or releases.

    gh_collect.py issues <owner/repo> ["<query>"] [--months 12] [--limit 10] --json
    gh_collect.py issue <owner/repo> <number> --out issue.md
    gh_collect.py releases <owner/repo> [--limit 10] --out releases.md

Issues show the problems real users hit; releases are the changelog. Uses the GitHub REST API with
the same token lookup as metrics.py (GH_TOKEN or a logged-in gh); without one, search allows
10 requests/minute, which is enough for a few tools. Pull requests are excluded.
Errors never raise: issues prints {"results": [], "error": "..."} and exits 0.
"""
import argparse
import json
import sys
import time
import urllib.parse

from common import get_json
from metrics import github_token

API = "https://api.github.com"
TRUNCATED = "[…cắt bớt]"


def headers():
    h = {"Accept": "application/vnd.github+json"}
    token = github_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def parse_issues(data, limit=None):
    results = []
    for i in data.get("items", []):
        if "pull_request" in i:
            continue
        results.append({
            "number": i["number"],
            "title": i.get("title") or "",
            "url": i.get("html_url"),
            "state": i.get("state"),
            "date": (i.get("created_at") or "")[:10],
            "comments": i.get("comments") or 0,
            "reactions": (i.get("reactions") or {}).get("total_count", 0),
            "labels": [lb.get("name") for lb in i.get("labels") or []],
        })
    return results[:limit] if limit else results


def issue_markdown(issue, comments, max_chars=40000):
    lines = [f"Nguồn: GitHub Issue — {issue.get('html_url')}", "",
             f"# {issue.get('title') or ''}",
             f"Trạng thái: {issue.get('state')} · Người mở: {(issue.get('user') or {}).get('login')}", "",
             (issue.get("body") or "").strip(), "", "## Bình luận"]
    for c in comments:
        assoc = c.get("author_association")
        role = " (maintainer)" if assoc in ("OWNER", "MEMBER", "COLLABORATOR") else ""
        lines += ["", f"- {(c.get('user') or {}).get('login')}{role}: " + (c.get("body") or "").strip()]
    md = "\n".join(lines)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n" + TRUNCATED
    return md


def releases_markdown(repo, releases, max_chars=40000):
    lines = [f"Nguồn: GitHub Releases — https://github.com/{repo}/releases", "", f"# Changelog {repo}"]
    for r in releases:
        if r.get("draft"):
            continue
        tag = r.get("tag_name") or r.get("name")
        pre = " (pre-release)" if r.get("prerelease") else ""
        lines += ["", f"## {tag}{pre} · {(r.get('published_at') or '')[:10]}", (r.get("body") or "").strip()]
    md = "\n".join(lines)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n" + TRUNCATED
    return md


def search_issues(repo, query, months, limit):
    since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - months * 30 * 86400))
    q = f"repo:{repo} is:issue created:>{since} {query or ''}".strip()
    params = urllib.parse.urlencode({"q": q, "sort": "comments", "order": "desc", "per_page": 30})
    data, err = get_json(f"{API}/search/issues?{params}", headers=headers())
    if err:
        return {"repo": repo, "query": query, "results": [], "error": err}
    return {"repo": repo, "query": query, "results": parse_issues(data, limit), "error": None}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("issues")
    s.add_argument("repo")
    s.add_argument("query", nargs="?")
    s.add_argument("--months", type=int, default=12)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true", help="print JSON (the only output format)")
    s = sub.add_parser("issue")
    s.add_argument("repo")
    s.add_argument("number")
    s.add_argument("--out", required=True)
    s = sub.add_parser("releases")
    s.add_argument("repo")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--out", required=True)
    args = p.parse_args()

    if args.cmd == "issues":
        print(json.dumps(search_issues(args.repo, args.query, args.months, args.limit), ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "issue":
        issue, err = get_json(f"{API}/repos/{args.repo}/issues/{args.number}", headers=headers())
        comments, err2 = get_json(f"{API}/repos/{args.repo}/issues/{args.number}/comments?per_page=30",
                                  headers=headers())
        if err:
            print(f"error: {err}", file=sys.stderr)
            return 1
        md = issue_markdown(issue, [] if err2 else comments)
    else:
        releases, err = get_json(f"{API}/repos/{args.repo}/releases?per_page={args.limit}", headers=headers())
        if err:
            print(f"error: {err}", file=sys.stderr)
            return 1
        md = releases_markdown(args.repo, releases)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
