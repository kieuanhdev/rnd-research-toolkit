---
name: youtube-search
description: Search YouTube with yt-dlp and return structured video results (title, channel, subscriber count, views, duration, upload date, URL, views-to-subscribers engagement ratio), filtered to recent uploads. Use this whenever the user wants to find, search, research, or compare YouTube videos, look for popular or trending videos on a topic, spot outlier videos from small channels, or analyze competitors' content on YouTube, even if they don't mention yt-dlp.
compatibility: Requires yt-dlp on PATH and Python 3.8+. No API key needed.
---

# YouTube Search

Run the bundled script rather than calling yt-dlp by hand. A flat yt-dlp search returns neither upload date nor subscriber count, so the script finds candidates first, then fetches full metadata for each in parallel (with retries). Candidates come from YouTube's own upload-date filter, because plain relevance ranking is full of old videos and a short window would otherwise match nothing.

## Usage

```bash
python3 <skill-dir>/scripts/yt_search.py "<query>" [--limit 20] [--months 6] [--json]
```

- `--limit N`: maximum results (default 20).
- `--months N`: only videos uploaded in the last N months (default 6; decimals like 0.5 work).
- `--json`: raw JSON with `results`, `closest_older`, `scanned`, `failed` and `total` keys, useful when you need to sort, filter, or feed the data into something else.

Expect roughly 10–40 seconds: each candidate costs a couple of seconds, and the script fetches about 3x the limit to survive the date filter. Run it in the foreground and tell the user it may take a moment.

## Output

One block per result separated by dividers: title, channel with subscriber count, views, views-to-subscribers ratio, duration, upload date, URL. Numbers are humanized (1.2K, 3.4M); durations are `H:MM:SS`.

The ratio (`views / subscribers`) measures how far a video travelled beyond a channel's audience. Above 1x means it reached more people than subscribe. Large values from small channels are the interesting outliers. When mentioning it, say it is a rough signal, since old subscribers may be inactive and a few viral videos skew it.

## Things to know

- **Fewer results than the limit** is normal for niche queries or short windows. The script says so and lists the most recent matches just outside the window; pass those on and suggest a larger `--months`.
- **A "could not be read" warning** means some videos failed after retries (throttling or removed videos). Re-run once to fill the gap rather than reporting a short list as final.
- **Hidden subscriber counts** show as `N/A` for both count and ratio; this is a channel setting, not a bug.
- **Live streams are skipped**, since they have no final view count or duration.
- **Results follow YouTube's relevance order**, not ratio order. If the user wants the top by engagement, use `--json` and sort `results` on `views_to_subscribers`.
- **Bot check ("Sign in to confirm you're not a bot")** comes from YouTube, not the script, and is triggered by many requests in a short time (each search reads dozens of videos). The script stops immediately with a message. Report it to the user, suggest waiting, or re-running with `--cookies-from-browser <browser>`, which uses their logged-in browser session. Only add that flag if the user agrees, since it reads their browser cookies.
