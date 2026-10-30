#!/usr/bin/env python3
"""Search YouTube with yt-dlp and print structured, human-readable results.

Flat search results lack upload date and subscriber count, so candidates are
found with a flat search and then fully extracted in parallel, in relevance
order, until enough videos pass the date filter. The candidate search uses
YouTube's own upload-date filter (the smallest bucket covering the window),
because plain relevance ranking is dominated by old videos and a short window
would otherwise match nothing.
"""
import argparse
import json
import subprocess
import sys
import time
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

DIVIDER = "─" * 64
OVERFETCH = 3  # candidates per requested result; the date filter discards many
WORKERS = 6


COOKIE_ARGS = []  # filled from --cookies-from-browser


class BotCheck(Exception):
    """YouTube is asking for sign-in; retrying will not help."""


def run_ytdlp(args, timeout=120):
    proc = subprocess.run(
        ["yt-dlp", "--no-warnings", *COOKIE_ARGS, *args],
        capture_output=True, text=True, timeout=timeout,
    )
    return proc


# YouTube search "sp" params: upload date bucket + type=video
DATE_BUCKETS = [  # (max window in days, sp)
    (1.5, "EgQIAhAB"),   # today
    (8, "EgQIAxAB"),     # this week
    (32, "EgQIBBAB"),    # this month
    (367, "EgQIBRAB"),   # this year
]


def search_candidates(query, count, window_days):
    sp = next((sp for days, sp in DATE_BUCKETS if window_days <= days), None)
    if sp:
        target = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={sp}"
        extra = ["--playlist-end", str(count)]
    else:
        target, extra = f"ytsearch{count}:{query}", []
    proc = run_ytdlp([target, "--flat-playlist", "-j", *extra])
    if proc.returncode != 0 and not proc.stdout.strip():
        sys.exit(f"yt-dlp search failed:\n{proc.stderr.strip()[:500]}")
    ids = []
    for line in proc.stdout.splitlines():
        try:
            ids.append(json.loads(line)["id"])
        except (ValueError, KeyError):
            continue
    return list(dict.fromkeys(ids))


def fetch_metadata(video_id, attempts=3):
    """Full metadata for one video; retries because YouTube throttles bursts."""
    for attempt in range(attempts):
        try:
            proc = run_ytdlp(
                [f"https://www.youtube.com/watch?v={video_id}", "-j", "--skip-download"]
            )
            if proc.stdout.strip():
                return json.loads(proc.stdout)
            if "not a bot" in proc.stderr:
                raise BotCheck()
        except BotCheck:
            raise
        except (subprocess.TimeoutExpired, ValueError):
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def parse_date(upload_date):
    try:
        return datetime.strptime(upload_date, "%Y%m%d")
    except (TypeError, ValueError):
        return None


def human_number(n):
    if n is None:
        return "N/A"
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= limit:
            return f"{n / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return str(int(n))


def human_duration(seconds):
    if not seconds:
        return "N/A"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def to_result(meta, upload):
    views = meta.get("view_count")
    subs = meta.get("channel_follower_count")
    ratio = round(views / subs, 2) if views is not None and subs else None
    return {
        "title": meta.get("title"),
        "channel": meta.get("channel") or meta.get("uploader"),
        "subscribers": subs,
        "views": views,
        "duration_seconds": meta.get("duration"),
        "upload_date": upload.strftime("%Y-%m-%d"),
        "url": meta.get("webpage_url"),
        "views_to_subscribers": ratio,
    }


def collect(query, limit, months):
    window_days = months * 30.44
    cutoff = datetime.now() - timedelta(days=round(window_days))
    ids = search_candidates(query, max(limit * OVERFETCH, 30), window_days)
    if not ids:  # nothing at all in the bucket: widen the search so we can still show the nearest videos
        ids = search_candidates(query, 15, max(window_days, 366))
    results, older, scanned, failed = [], [], 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for start in range(0, len(ids), WORKERS):
            try:
                batch = list(pool.map(fetch_metadata, ids[start:start + WORKERS]))
            except BotCheck:
                sys.exit(
                    "YouTube is asking this machine to sign in to confirm it is not a bot, so "
                    "video details cannot be read right now.\nOptions: wait and retry later, or "
                    "re-run with --cookies-from-browser <firefox|chrome|...> to use a logged-in "
                    "browser session.")
            for meta in batch:
                scanned += 1
                if not meta:
                    failed += 1
                    continue
                if meta.get("is_live"):
                    continue
                upload = parse_date(meta.get("upload_date"))
                if not upload:
                    continue
                (results if upload >= cutoff else older).append(to_result(meta, upload))
            if len(results) >= limit:
                break
    older.sort(key=lambda r: r["upload_date"], reverse=True)
    return {"results": results[:limit], "closest_older": older[:3],
            "scanned": scanned, "failed": failed, "total": len(ids)}


def render_result(r, i):
    ratio = r["views_to_subscribers"]
    return [
        f"#{i}  {r['title']}",
        f"    Channel:      {r['channel']} ({human_number(r['subscribers'])} subscribers)",
        f"    Views:        {human_number(r['views'])}",
        f"    Engagement:   {f'{ratio:.2f}x views/subs' if ratio is not None else 'N/A'}",
        f"    Duration:     {human_duration(r['duration_seconds'])}",
        f"    Uploaded:     {r['upload_date']}",
        f"    URL:          {r['url']}",
        DIVIDER,
    ]


def render(out, query, months, limit):
    results = out["results"]
    lines = [DIVIDER, f'YouTube results for "{query}" — last {months:g} month(s)', DIVIDER]
    for i, r in enumerate(results, 1):
        lines += render_result(r, i)
    lines.append(f"{len(results)} result(s); checked {out['scanned']} of {out['total']} candidates.")
    if out["failed"]:
        lines.append(f"Warning: {out['failed']} video(s) could not be read (YouTube throttling or "
                     "removed videos) and were skipped; re-run to fill the gap.")
    if len(results) < limit:
        lines.append(f"Note: only {len(results)} of the requested {limit} fell inside the date "
                     "window; try a larger --months for more.")
    if out["closest_older"] and len(results) < limit:
        lines += ["", "Most recent matches just outside the window:", DIVIDER]
        for i, r in enumerate(out["closest_older"], 1):
            lines += render_result(r, i)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20, help="max results (default 20)")
    p.add_argument("--months", type=float, default=6, help="only videos from the last N months (default 6)")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="pass a logged-in browser's cookies to yt-dlp (use if YouTube shows a bot check)")
    p.add_argument("--json", action="store_true", help="emit raw JSON instead of formatted text")
    a = p.parse_args()
    if a.cookies_from_browser:
        COOKIE_ARGS[:] = ["--cookies-from-browser", a.cookies_from_browser]

    out = collect(a.query, a.limit, a.months)
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    if not out["results"]:
        print(f'No videos for "{a.query}" in the last {a.months:g} month(s) '
              f"(checked {out['scanned']} candidates, {out['failed']} unreadable).")
        if out["closest_older"]:
            print("\nMost recent matches just outside the window:\n" + DIVIDER)
            print("\n".join(l for i, r in enumerate(out["closest_older"], 1)
                            for l in render_result(r, i)))
        else:
            print("Try a larger --months.")
        return
    print(render(out, a.query, a.months, a.limit))


if __name__ == "__main__":
    main()
