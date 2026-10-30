#!/usr/bin/env python3
"""Search arXiv for recent papers on a topic.

    arxiv_collect.py '"GUI testing" LLM mobile' [--months 24] [--limit 10] --json

Each word or "quoted phrase" must appear (they are joined with AND), limited to computer-science
categories and the last --months, ranked by arXiv relevance. Homonyms cross-listed in cs.* (e.g.
aeroelastic "flutter") can still appear, so judge relevance before using a paper.
Errors never raise: prints {"results": [], "error": "..."} and exits 0.
"""
import argparse
import datetime
import json
import shlex
import sys
import urllib.parse
import xml.etree.ElementTree as ET

from common import get_text

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


def build_query(query, date_from, date_to):
    """Dates are arXiv's YYYYMMDDHHMM. Filtering inside the query (not afterwards) keeps
    relevance ranking from filling the page with old papers; cat:cs.* drops homonyms
    such as aeroelastic "flutter"."""
    try:
        words = shlex.split(query)
    except ValueError:  # unbalanced quote, e.g. an apostrophe
        words = query.replace('"', " ").split()
    terms = [f'all:"{t}"' if " " in t else f"all:{t}" for t in words]
    terms += [f"submittedDate:[{date_from} TO {date_to}]", "cat:cs.*"]
    return " AND ".join(terms) + " ANDNOT cat:physics.*"


def parse_feed(xml_text, cutoff_iso):
    root = ET.fromstring(xml_text)
    results = []
    for e in root.findall("a:entry", NS):
        date = (e.findtext("a:published", "", NS) or e.findtext("a:updated", "", NS))[:10]
        if date < cutoff_iso:
            continue
        abs_url = e.findtext("a:id", "", NS).replace("http://", "https://")
        pdf_url = next((l.get("href") for l in e.findall("a:link", NS) if l.get("title") == "pdf"),
                       abs_url.replace("/abs/", "/pdf/"))
        results.append({
            "id": abs_url.rsplit("/", 1)[-1],
            "title": " ".join(e.findtext("a:title", "", NS).split()),
            "authors": [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)],
            "date": date,
            "abs_url": abs_url,
            "pdf_url": pdf_url,
            "summary": " ".join(e.findtext("a:summary", "", NS).split()),
        })
    return results


def search(query, months, limit):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=months * 30)
    cutoff = start.isoformat()
    params = urllib.parse.urlencode({
        "search_query": build_query(query, start.strftime("%Y%m%d0000"), today.strftime("%Y%m%d2359")),
        "max_results": limit, "sortBy": "relevance",
    }, safe=':*[]"')  # arXiv ignores cat:cs.* when "*" is percent-encoded
    text, err = get_text(f"{API}?{params}", timeout=40)
    if err:
        return {"query": query, "results": [], "error": err}
    try:
        return {"query": query, "results": parse_feed(text, cutoff)[:limit], "error": None}
    except ET.ParseError as e:
        return {"query": query, "results": [], "error": f"invalid XML: {e}"}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("query")
    p.add_argument("--months", type=int, default=24)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true", help="print JSON (the only output format)")
    args = p.parse_args()
    print(json.dumps(search(args.query, args.months, args.limit), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
