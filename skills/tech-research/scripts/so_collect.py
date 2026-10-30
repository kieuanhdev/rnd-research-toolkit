#!/usr/bin/env python3
"""Find Stack Overflow questions on a topic, or save one question with its top answers as Markdown.

    so_collect.py "<query>" [--months 24] [--limit 10] --json      # search questions
    so_collect.py --question <id> --out question.md                # snapshot one question

Uses the free Stack Exchange API (no key: 300 requests/day per IP). Questions without answers are
dropped, since the point is to see real problems and how people solved them; results are sorted by score.
Errors never raise: search prints {"results": [], "error": "..."} and exits 0.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse

from common import get_json

API = "https://api.stackexchange.com/2.3"
TRUNCATED = "[…cắt bớt]"


def plain(text):
    if not text:
        return ""
    text = re.sub(r"<pre[^>]*><code>", "\n```\n", text)
    text = re.sub(r"</code></pre>", "\n```\n", text)
    text = re.sub(r"<p>|<br\s*/?>|<li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(text)).strip()


def parse_search(data, limit=None):
    """Keep the API's relevance order to pick the top `limit` answered questions, then sort them by score."""
    results = []
    for q in data.get("items", []):
        if not q.get("answer_count"):
            continue
        results.append({
            "id": str(q["question_id"]),
            "title": html.unescape(q.get("title") or ""),
            "url": q.get("link"),
            "tags": q.get("tags") or [],
            "date": time.strftime("%Y-%m-%d", time.gmtime(q.get("creation_date") or 0)),
            "score": q.get("score") or 0,
            "answer_count": q["answer_count"],
            "view_count": q.get("view_count") or 0,
            "accepted": "accepted_answer_id" in q,
        })
    results = results[:limit] if limit else results
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def question_markdown(question, answers, max_chars=40000, max_answers=3):
    lines = [f"Nguồn: Stack Overflow — {question.get('link')}", "",
             f"# {html.unescape(question.get('title') or '')}",
             f"Tags: {', '.join(question.get('tags') or [])} · Điểm: {question.get('score', 0)}", "",
             plain(question.get("body")), "", "## Câu trả lời"]
    answers = sorted(answers, key=lambda a: (not a.get("is_accepted"), -(a.get("score") or 0)))[:max_answers]
    for a in answers:
        mark = " (được chấp nhận)" if a.get("is_accepted") else ""
        lines += ["", f"### {a.get('owner', {}).get('display_name', '?')} · điểm {a.get('score', 0)}{mark}",
                  plain(a.get("body"))]
    md = "\n".join(lines)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n" + TRUNCATED
    return md


def search(query, months, limit):
    params = urllib.parse.urlencode({
        "q": query, "site": "stackoverflow", "order": "desc", "sort": "relevance",
        "fromdate": int(time.time() - months * 30 * 86400), "pagesize": 50,
    })
    data, err = get_json(f"{API}/search/advanced?{params}")
    if err:
        return {"query": query, "results": [], "error": err}
    return {"query": query, "results": parse_search(data, limit), "error": None,
            "quota_remaining": data.get("quota_remaining")}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("query", nargs="?")
    p.add_argument("--months", type=int, default=24)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true", help="print JSON (the only output format)")
    p.add_argument("--question", help="question id to snapshot")
    p.add_argument("--out", help="output Markdown file for --question")
    args = p.parse_args()

    if args.question:
        if not args.out:
            p.error("--question needs --out")
        common = "site=stackoverflow&filter=withbody"
        q, err = get_json(f"{API}/questions/{args.question}?{common}")
        a, err2 = get_json(f"{API}/questions/{args.question}/answers?{common}&sort=votes&pagesize=10")
        if err or not q.get("items"):
            print(f"error: {err or 'question not found'}", file=sys.stderr)
            return 1
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(question_markdown(q["items"][0], [] if err2 else a.get("items", [])))
        print(args.out)
        return 0
    if not args.query:
        p.error("give a query or --question")
    print(json.dumps(search(args.query, args.months, args.limit), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
