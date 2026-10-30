#!/usr/bin/env python3
"""Render the sources section of a research report as Markdown (Vietnamese headings).

    python3 sources_table.py --all sources.json
    python3 sources_table.py search.json [--manifest manifest.json ...] [--urls URL ...]

--all renders one table of every source sent to NotebookLM, whatever its kind, with its label
(Nhà cung cấp / Cộng đồng / Tài liệu chính thức / Nghiên cứu / Báo chí / tổng hợp), plus counts.
sources.json: [{"n", "kind", "label", "title", "url", "publisher", "nlm_status", "nlm_input"}];
nlm_status is ready | partial (loaded, content incomplete) | error | skipped, and nlm_input is the
exact --youtube/--url/--file value sent to NotebookLM.
--all --no-nlm drops the NotebookLM column, for quick-mode reports.
--all with --citation-key and --manifest prints "source_id -> [n] Publisher — Title" for every source.

The YouTube mode joins youtube-search's --json output with notebooklm-studio's manifest.json so
every selected video shows its search metadata and whether NotebookLM actually ingested it.

--urls picks and orders the videos that were sent to NotebookLM (default: all results).
With --manifest, the table lists every video sent but the summary stats count only the ones
NotebookLM ingested, so they describe the evidence the analysis actually rests on.
--citation-key prints "source_id -> Channel — Title" lines instead, for naming citations.
"""
import argparse
import collections
import json
import statistics
import sys
import urllib.parse


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


def ratio(r):
    return "N/A" if r is None else f"{r:.2f}x"


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


LABELS = ("Nhà cung cấp", "Cộng đồng", "Tài liệu chính thức", "Nghiên cứu", "Báo chí / tổng hợp")


LOADED = ("ready", "partial")


def link_url(url):
    return urllib.parse.quote(url or "", safe=":/?#&=%@+~,;!*'")


def render_all(sources, nlm=True):
    """nlm=False (quick mode, no NotebookLM) drops the NotebookLM column and load count."""
    for s in sources:
        s["label"] = (s.get("label") or "").strip()
    bad = [s for s in sources if s["label"] not in LABELS]
    if bad:
        print(f"invalid label in row {bad[0].get('n')}: {bad[0].get('label')!r}; "
              f"use one of: {', '.join(LABELS)}", file=sys.stderr)
        sys.exit(2)
    lines = ["| # | Loại | Nhãn | Nguồn | Đơn vị / tác giả |" + (" NotebookLM |" if nlm else ""),
             "|---|---|---|---|---|" + ("---|" if nlm else "")]
    for s in sources:
        lines.append(f"| {s.get('n', '?')} | {s.get('kind', 'N/A')} | {s['label']} "
                     f"| [{cell(s.get('title') or 'N/A')}]({link_url(s.get('url'))}) "
                     f"| {cell(s.get('publisher') or 'N/A')} |" + (f" {s.get('nlm_status', 'N/A')} |" if nlm else ""))
    kinds = collections.Counter(s.get("kind", "N/A") for s in sources)
    labels = collections.Counter(s["label"] for s in sources)
    ready = sum(1 for s in sources if s.get("nlm_status") in LOADED)
    lines += ["",
              f"- **Theo loại:** " + ", ".join(f"{k}: {v}" for k, v in kinds.most_common()),
              f"- **Theo nhãn:** " + ", ".join(f"{k}: {v}" for k, v in labels.most_common())]
    if nlm:
        lines.append(f"- **NotebookLM nạp thành công:** {ready}/{len(sources)}")
    return "\n".join(lines)


def citation_key(sources, manifests):
    by_input = {s.get("nlm_input"): s for s in sources if s.get("nlm_input")}
    out = []
    for m in manifests:
        for entry in m.get("sources", []):
            if not entry.get("id"):
                continue
            s = by_input.get(entry.get("input"))
            out.append(f"{entry['id']} -> [{s.get('n')}] {s.get('publisher') or 'N/A'} — {s.get('title') or 'N/A'}"
                       if s else f"{entry['id']} -> {entry.get('input')}")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("search_json", nargs="?")
    p.add_argument("--all", metavar="SOURCES_JSON", help="render the unified table of all sources")
    p.add_argument("--manifest", action="append", default=[],
                   help="notebooklm-studio manifest.json, for per-source status (repeatable; later wins)")
    p.add_argument("--urls", nargs="*", help="selected video URLs, in report order")
    p.add_argument("--no-nlm", action="store_true", help="--all without the NotebookLM column (quick mode)")
    p.add_argument("--citation-key", action="store_true",
                   help="print NotebookLM source_id -> video name mapping and exit")
    args = p.parse_args()

    if args.all:
        with open(args.all, encoding="utf-8") as f:
            sources = json.load(f)
        if args.citation_key:
            manifests = []
            for path in args.manifest:
                with open(path, encoding="utf-8") as f:
                    manifests.append(json.load(f))
            print("\n".join(citation_key(sources, manifests)))
        else:
            print(render_all(sources, nlm=not args.no_nlm))
        return
    if not args.search_json:
        p.error("give search.json or --all sources.json")
    with open(args.search_json, encoding="utf-8") as f:
        search = json.load(f)
    by_url = {v["url"]: v for v in search.get("results", []) + search.get("closest_older", [])}
    if args.urls:
        missing = [u for u in args.urls if u not in by_url]
        if missing:
            sys.exit(f"not in search results: {', '.join(missing)}")
        videos = [by_url[u] for u in args.urls]
    else:
        videos = search.get("results", [])

    status, source_ids = {}, {}
    for path in args.manifest:
        with open(path, encoding="utf-8") as f:
            for s in json.load(f).get("sources", []):
                status[s.get("input")] = s.get("status")
                if s.get("id"):
                    source_ids[s["id"]] = s.get("input")

    if args.citation_key:
        for sid, url in source_ids.items():
            v = by_url.get(url)
            print(f"{sid} -> {v['channel']} — {v['title']}" if v else f"{sid} -> {url}")
        return

    has_status = bool(status)
    head = "| # | Video | Kênh | Người đăng ký | Lượt xem | Xem/Đăng ký | Thời lượng | Ngày đăng |"
    rule = "|---|---|---|---|---|---|---|---|"
    if has_status:
        head += " NotebookLM |"
        rule += "---|"
    lines = [head, rule]
    for i, v in enumerate(videos, 1):
        row = (f"| {i} | [{cell(v['title'])}]({v['url']}) | {cell(v['channel'])} "
               f"| {human_number(v.get('subscribers'))} | {human_number(v.get('views'))} "
               f"| {ratio(v.get('views_to_subscribers'))} | {human_duration(v.get('duration_seconds'))} "
               f"| {v.get('upload_date', 'N/A')} |")
        if has_status:
            row += f" {status.get(v['url'], 'chưa gửi')} |"
        lines.append(row)

    used = [v for v in videos if status.get(v["url"]) == "ready"] if has_status else videos
    views = [v["views"] for v in used if v.get("views") is not None]
    ratios = [v["views_to_subscribers"] for v in used if v.get("views_to_subscribers") is not None]
    label = "Video được phân tích" if has_status else "Video"
    lines += ["", f"- **{label}:** {len(used)}, từ {len({v['channel'] for v in used})} kênh"]
    if views:
        lines.append(f"- **Tổng lượt xem:** {human_number(sum(views))} (trung vị {human_number(statistics.median(views))})")
    if ratios:
        top = max((v for v in used if v.get("views_to_subscribers") is not None),
                  key=lambda v: v["views_to_subscribers"])
        lines.append(f"- **Trung vị xem/đăng ký:** {ratio(statistics.median(ratios))}; "
                     f"nổi bật nhất: {cell(top['title'])} ({cell(top['channel'])}, {ratio(top['views_to_subscribers'])})")
    if has_status:
        lines.append(f"- **NotebookLM nạp thành công:** {len(used)}/{len(videos)} video đã gửi")
    failed = search.get("failed", 0)
    failed = len(failed) if isinstance(failed, list) else failed
    lines.append(f"- **Quét tìm kiếm:** {search.get('scanned', 'N/A')} ứng viên, {failed} không đọc được")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
