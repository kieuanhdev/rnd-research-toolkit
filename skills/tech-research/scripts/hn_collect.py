#!/usr/bin/env python3
"""Find Hacker News discussions on a topic, or save one thread as a Markdown snapshot.

    hn_collect.py "<query>" [--months 12] [--limit 15] --json      # search stories
    hn_collect.py --thread <id> --out thread.md                     # snapshot one thread

Uses the free Algolia HN API (no account). Stories without comments are dropped, since the
point is to hear the community, and results are sorted by comment count.
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

API = "https://hn.algolia.com/api/v1"
TRUNCATED = "[…cắt bớt]"


def hn_url(item_id):
    return f"https://news.ycombinator.com/item?id={item_id}"


def parse_search(data, limit=None):
    """Keep Algolia's relevance order to pick the top `limit` discussed stories, then sort them by comments."""
    results = []
    for h in data.get("hits", []):
        comments = h.get("num_comments") or 0
        if not comments:
            continue
        results.append({
            "id": h["objectID"],
            "title": h.get("title") or "",
            "url": h.get("url"),
            "hn_url": hn_url(h["objectID"]),
            "author": h.get("author"),
            "date": (h.get("created_at") or "")[:10],
            "points": h.get("points") or 0,
            "num_comments": comments,
        })
    results = results[:limit] if limit else results
    results.sort(key=lambda r: r["num_comments"], reverse=True)
    return results


def plain(text):
    if not text:
        return ""
    text = re.sub(r"<p>|<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def subtree_size(c):
    return 1 + sum(subtree_size(k) for k in c.get("children") or [])


def thread_markdown(item, max_chars=60000, rank=None, max_depth=2, max_replies=3):
    """Snapshot a thread so big threads stay representative.

    Algolia lists comments oldest first, so a plain depth-first dump would fill the budget with
    the first few comments. Instead top-level comments follow HN's ranking (`rank`, the story's
    `kids` order; else biggest subtree first), and each gets an equal share of the budget with
    at most `max_replies` replies per comment down to `max_depth`.
    """
    lines = [f"Nguồn: Hacker News — {hn_url(item['id'])}", "", f"# {item.get('title') or ''}"]
    if item.get("url"):
        lines.append(f"Link: {item['url']}")
    lines.append(f"Người đăng: {item.get('author')}")
    if item.get("text"):
        lines += ["", plain(item["text"])]
    lines += ["", "## Bình luận"]

    top = [c for c in item.get("children") or [] if plain(c.get("text"))]
    position = {cid: i for i, cid in enumerate(rank or [])}
    top.sort(key=lambda c: (position.get(c.get("id"), len(position)), -subtree_size(c)))
    share = max(1200, max_chars // max(len(top), 1))

    def render(c, depth, out, budget):
        body = plain(c.get("text"))
        if not body:
            return budget
        indent = "  " * depth
        line = f"{indent}- {c.get('author')}: " + body[:budget].replace("\n", f"\n{indent}  ")
        if out and len(line) > budget:
            return budget
        out.append(line)
        budget -= len(line)
        if depth < max_depth:
            kids = sorted(c.get("children") or [], key=subtree_size, reverse=True)[:max_replies]
            for k in kids:
                if budget <= 0:
                    break
                budget = render(k, depth + 1, out, budget)
        return budget

    used = len("\n".join(lines))
    for i, c in enumerate(top):
        chunk = []
        render(c, 0, chunk, share)
        text = "\n".join(chunk)
        if used + len(text) > max_chars:
            lines += ["", f"{TRUNCATED} còn {len(top) - i} bình luận cấp đầu không đưa vào"]
            break
        lines.append(text)
        used += len(text) + 1
    md = "\n".join(lines)
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n" + TRUNCATED
    return md


def hn_rank(story_id):
    """Top-level comment ids in HN's own ranking order (Firebase API), or None."""
    data, err = get_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
    return None if err or not isinstance(data, dict) else data.get("kids")


def search(query, months, limit):
    cutoff = int(time.time() - months * 30 * 86400)
    params = urllib.parse.urlencode({
        "query": query, "tags": "story", "hitsPerPage": 50,
        "restrictSearchableAttributes": "title,url", "typoTolerance": "false", "queryType": "prefixNone",
        "numericFilters": f"created_at_i>{cutoff}",
    })
    data, err = get_json(f"{API}/search?{params}")
    if err:
        return {"query": query, "results": [], "error": err}
    return {"query": query, "results": parse_search(data, limit), "error": None}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("query", nargs="?")
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--json", action="store_true", help="print JSON (the only output format)")
    p.add_argument("--thread", help="HN item id to snapshot")
    p.add_argument("--out", help="output Markdown file for --thread")
    args = p.parse_args()

    if args.thread:
        if not args.out:
            p.error("--thread needs --out")
        item, err = get_json(f"{API}/items/{args.thread}")
        if err:
            print(f"error: {err}", file=sys.stderr)
            return 1
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(thread_markdown(item, rank=hn_rank(args.thread)))
        print(args.out)
        return 0
    if not args.query:
        p.error("give a query or --thread")
    print(json.dumps(search(args.query, args.months, args.limit), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
