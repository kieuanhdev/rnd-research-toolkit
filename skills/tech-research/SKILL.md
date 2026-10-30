---
name: tech-research
description: Multi-source research on a technology or programming topic. Collects recent sources from YouTube, Hacker News, Reddit (via web search), official docs and tech blogs, and arXiv; pulls adoption metrics from GitHub and package registries (pub.dev, npm, PyPI, crates.io); loads the sources into a new Google NotebookLM notebook for cited analysis aimed at the user's question; fact-checks key capability claims against official docs; and writes a Vietnamese decision report with source labels, confidence levels, a metrics table, a "Thử nhanh" quick-start section and an HTML infographic, saved in the current working directory and shown in chat. Use it whenever the user wants to research, compare, evaluate or get a briefing on tools, frameworks, libraries or technical approaches ("research X", "tìm hiểu X", "so sánh A và B", "nên dùng gì cho X"), even if they don't name the sources. If they say "chỉ YouTube" (YouTube only), run the YouTube-only path described inside.
compatibility: Needs the youtube-search skill (yt-dlp) and the notebooklm-studio skill (notebooklm-py CLI, logged in), both in this plugin's skills/ folder. Python 3 stdlib for the collectors; Playwright + Chrome/Chromium (auto-detected, or CHROME_PATH) for the infographic; WebSearch/WebFetch for docs, blogs and Reddit.
---

# Tech Research (multi-source)

```
topic + angle → collect in parallel (YouTube · HN · Reddit/web · docs & blogs · arXiv)
  → select + label → NotebookLM (one notebook) → cited analysis → fact-check against official docs
  → adoption metrics (GitHub + registries) → Vietnamese report + HTML infographic → file + chat
```

The point of using several source types is to separate **what vendors say** from **what independent
users report** and **what the official docs confirm**. Every design choice below serves that.

Read `youtube-search/SKILL.md` and `notebooklm-studio/SKILL.md` (same skills folder) when something
breaks or you need a flag not covered here; they own the details (bot checks, auth, quotas, recovery).

Paths:

- `SK=${CLAUDE_PLUGIN_ROOT}/skills/tech-research/scripts`
- `YTS=${CLAUDE_PLUGIN_ROOT}/skills/youtube-search/scripts/yt_search.py`
- `NLM=${CLAUDE_PLUGIN_ROOT}/skills/notebooklm-studio/scripts/pipeline.py`
- `TEMPLATE=${CLAUDE_PLUGIN_ROOT}/skills/tech-research/assets/infographic_template.html`
- `CONFIG` = `research.config.json` in the current working directory, if it exists. Optional keys:
  `team_name` (default "Ban Research", used in the byline), `reviewer` (omit the review part of the byline
  and the `reviewer` key when absent), `output_dir` (default: the current directory).
- `OUT` = `output_dir` from CONFIG, else the current working directory, unless the user names another place.
  `WORK=$OUT/assets/<kebab-topic>` (no date in the folder name); snapshots go in `$WORK/sources/`.

Run the collector scripts as `cd $SK && python3 <script>` (they import `common.py` from that folder).

**Output language: Vietnamese.** The report, chat messages, `--ask` questions and deliverables
(`--language vi`) are in Vietnamese. Keep the original for search queries (English), titles, channel
and tool names, code, commands and direct quotes (add a Vietnamese gloss after a quote).
Frontmatter keys stay English. The user can override this per request.

## 1. Understand the request; ask at most once

Extract the **topic** (turned into short English search queries, one per main tool or idea) and the
**angle** (what they want to decide or learn; it drives the analysis questions and the report). Also
note every tool the user names: each one must appear in the report, even if no source covers it.

The HTML infographic is always made. Ask **one** question only if they didn't say: whether they also
want a NotebookLM deliverable (flashcards, mind map, audio overview; NotebookLM's own infographic only
if they ask). Empty answer, "không", "skip" → none. Audio is limited to ~3/day and takes 5–15 min.

**"Chỉ YouTube":** collect YouTube only (step 3). Select with step 4's rules: ≤ 10 videos, skip Shorts
and clips under 2 minutes, ≤ 2–3 per channel, label each video. Then run steps 5–6 with `--youtube` only,
and drop the "source types contradict" question. Skip the fact-check (7) and metrics (8). In the report,
drop **Bảng hỗ trợ**, **Số liệu áp dụng** and **Thử nhanh**, mark confidence from YouTube evidence only,
and list the skipped steps in the method notes. In the infographic, use `.unk` for any platform badge
the videos don't state explicitly, or leave the badges out.

Tell the user up front that a full run takes roughly 10–20 minutes. Don't come back with more
questions mid-run unless something breaks.

## 2. Preflight

```bash
notebooklm auth check --test --json        # need status "ok"; otherwise stop: ask the user to run `notebooklm login`
mkdir -p $WORK/sources                     # every later step writes here
date +%s > $WORK/start                     # for the run time in the method notes
```

Shell variables don't survive between Bash calls, so spell out `$WORK` and `$SK` as full paths in every
command. `metrics.py` picks up a GitHub token on its own (from `GH_TOKEN` or a logged-in `gh`).
A source that isn't available is skipped and noted, never a reason to stop.

## 3. Collect in parallel

Run the scripts in the background in one go, and do the web searches while they run.

| Source | How | Candidates |
|---|---|---|
| YouTube | `python3 $YTS "<query>" --limit 15 --months 12 --json > $WORK/yt-<q>.json` (one or more queries) | 15+ |
| Hacker News | `cd $SK && python3 hn_collect.py "<query>" --months 24 --limit 10 --json > $WORK/hn-<q>.json` (short queries: a tool name or 2–3 words; HN matches titles and URLs only) | 10+ |
| arXiv | `cd $SK && python3 arxiv_collect.py '"<phrase>" <word>' --months 24 --limit 10 --json > $WORK/arxiv.json` | 10 |
| Reddit | WebSearch `site:reddit.com <topic>` and `site:reddit.com/r/<sub> <tool>` for the relevant subreddits (e.g. r/FlutterDev, r/programming, r/QualityAssurance) | 8+ |
| Docs & blogs | WebSearch `<tool> documentation`, `<tool> vs <tool>`, `<topic> 2026 blog`, `<topic> experience migration` | 10+ |

`<q>` is just a query index. Merge the YouTube files into `$WORK/search.json` keeping the shape
`{"results": [...], "closest_older": [...], "scanned": <sum>, "failed": <sum of counts>}`, de-duplicated
by URL. Skip empty files: on a bot check, yt_search prints nothing. Follow youtube-search's guidance
there (wait, or cookies only with the user's consent).
HN is thin on niche topics; that's a finding, not a failure. Note it.

## 4. Select and label

Targets, with a hard cap of 50 in the notebook: **YouTube ≤ 10 · docs & blogs 6–8 · community threads
(HN + Reddit) 5–8 · arXiv 0–3 · total ≈ 20–30.** Never pad with off-topic sources; report a shortfall.

Priority: relevance to the angle → substance (skip Shorts and clips under 2 minutes, thin listicles,
SEO spam) → **independence** (when two sources are equally relevant, prefer the one without a commercial
stake) → variety (≤ 2–3 per channel, author or organization).

Give each source exactly one label (exact strings; the table script rejects others):

- `Nhà cung cấp`: made or sells the tool, or the content is sponsored by someone with a stake.
- `Cộng đồng`: users discussing it (HN, Reddit, independent personal blogs).
- `Tài liệu chính thức`: docs, changelogs, READMEs.
- `Nghiên cứu`: academic papers.
- `Báo chí / tổng hợp`: third-party articles that fit none of the above.

Judge from the channel, author, domain, sponsor disclosures and content. When unsure between vendor
and something else, choose `Nhà cung cấp` and say why in the method notes.

Write `$WORK/sources.json`, one row per selected source in report order. `n` is the source's number
everywhere: in the report's [n] citations and in its snapshot file name.
`{"n", "kind": "youtube|web|reddit|hn|arxiv", "label", "title", "url", "publisher", "nlm_input", "nlm_status"}`

- `nlm_input`: the exact value you pass to NotebookLM. That is the video URL, the arXiv `pdf_url`, or
  the snapshot's absolute path `$WORK/sources/<kind>-<n>.md`. The citation map joins on it.
- `nlm_status`: `ready`, `partial` (loaded, but the content is incomplete, e.g. a Reddit snippet),
  `error` or `skipped`.

## 5. Snapshots, then load NotebookLM

NotebookLM often can't read Reddit, HN or JS-heavy pages from a URL, so give it text files:

- HN: `cd $SK && python3 hn_collect.py --thread <id> --out $WORK/sources/hn-<n>.md`
- Reddit, docs and blogs: WebFetch the page and save the substance (post plus comments with usernames
  where available; for docs, the relevant sections) to `$WORK/sources/<kind>-<n>.md`. The first line
  must be `Nguồn: <kind> — <url>`. If WebFetch fails on Reddit, save the title and search snippet, mark
  that row `partial`, and write "Reddit chỉ lấy được một phần" in the method notes.
- arXiv: pass the `pdf_url` with `--url`, so NotebookLM reads the full paper, not just the abstract.

Before Phase A, check that every `--file` path exists (`ls`). pipeline.py creates the notebook *before*
adding sources, so a missing file leaves an empty notebook and a non-zero exit. If that happens anyway,
fix the file and retry with `--notebook <id>`. Never use `--title` again, which would create a second notebook.

**Phase A**, which creates the notebook and adds the sources:

```bash
python3 $NLM --title "<Chủ đề> — research <YYYY-MM-DD>" \
  --youtube <url> ... --file $WORK/sources/<kind>-<n>.md ... --url <arxiv pdf_url> ... --out $WORK/load-1
```

Read `$WORK/load-1/manifest.json`. For Google-side errors (500/502, `UNCONFIRMED_WRITE`), check
`notebooklm source list -n <id> --json` for silent successes, then re-add. For a source that can't be
processed, swap in the next spare of the same kind. Do **one** top-up round (`--notebook <id> ...
--out $WORK/load-2`), then accept any shortfall. Update `nlm_status` in `sources.json`.

## 6. Cited analysis (NotebookLM)

```bash
python3 $NLM --notebook <id> --summary --ask "<q1>" ... --ask "<q6>" --language vi \
  [--deliverables flashcards,mindmap,audio ...] --out $WORK
```

Write 4–6 **Vietnamese** questions as one conversation: the landscape (each tool: what it is, how it
works, platforms), then the user's actual decision, then what drives opinions and who has a stake,
then disagreements and evidence. **One question must ask where the source types contradict each other**
(community vs vendor vs docs vs research). End with outliers and gaps, naming the tools the user asked
about that the sources don't cover.

Then build the citation map. Pass the top-up manifest too, if there was one:

```bash
python3 $SK/sources_table.py --all $WORK/sources.json --citation-key \
  --manifest $WORK/load-1/manifest.json [--manifest $WORK/load-2/manifest.json]
```

It prints `source_id -> [n] Publisher — Title` for every source. Use those `[n]` in the report. Strip NotebookLM's canned "Would you like me to…" upsell lines
from `$WORK/analysis.md`. Spot-check headline numbers and quotes against the citation snippets. Mark
claims whose citations don't resolve as "chưa xác minh". Drop model names or facts NotebookLM adds
that no snippet contains.

Then write `$WORK/analysis-mapped.md`: a copy of the cleaned `analysis.md` with NotebookLM's citation numbers
renumbered to the report's `[n]` using the citation key. This is the file the report links to, so a reader who
clicks `[3]` lands on source 3. Do not link the raw `analysis.md`.

## 7. Fact-check against official docs

List the **yes/no facts the angle depends on** for every recommended or compared tool, including tools
the user named that no source covered: platform support (Android / iOS / Web), licence, pricing or
free tier, self-hostable, and whatever else decides the user's question. WebFetch the official docs or
README for each one. Record `{tool, fact, value, doc_url, checked_on}`.

- Official docs are **trusted for capability facts**: if the docs say it, it's `đã xác nhận`.
- **Quality or performance claims** ("ổn định hơn", "nhanh nhất", "tự sửa mọi lỗi"), whether from
  docs or any vendor, are `Thấp` confidence unless an independent source backs them.
- Couldn't confirm → `chưa xác nhận`. Never guess. Never leave a bare "❓".
- These checks happen outside NotebookLM. Cite them as "docs chính thức" plus the link, never with a
  NotebookLM-style [n].

## 8. Adoption metrics

Write `$WORK/tools.json` with the repo and packages for each tool (look them up from the docs):
`[{"name", "github": "owner/repo", "pubdev": [], "npm": [], "pypi": [], "crates": []}]`, then:

```bash
cd $SK && python3 metrics.py $WORK/tools.json --json > $WORK/metrics.json
python3 metrics.py --markdown $WORK/metrics.json > $WORK/metrics.md
```

The numbers come only from the APIs. Other ecosystems (Maven, Go, NuGet…) show `không có dữ liệu`,
which is expected. Metrics never go into NotebookLM.

## 9. Write the report

`python3 $SK/sources_table.py --all $WORK/sources.json > $WORK/sources.md`, plus the YouTube stats via
`sources_table.py $WORK/search.json --manifest $WORK/load-1/manifest.json [--manifest $WORK/load-2/manifest.json]
--urls <youtube urls in order>`.

Write `$OUT/<Chủ đề>.md` (no date in the file name; the date lives in the `date` property). If that name is taken, add a short distinguishing suffix in parentheses, e.g. `<Chủ đề> (đa nguồn).md`, never a date:

```markdown
---
type: tech-research
topic: "<chủ đề>"
queries: {youtube: [...], hn: [...], reddit: [...], web: [...], arxiv: [...]}
date: <YYYY-MM-DD>
notebook_id: <id>
sources: {total: <n ready>, youtube: <n>, community: <n>, docs: <n>, research: <n>}
deliverables: [infographic, ...]
language: vi
author: "<tên model đang chạy, vd Opus 5.5>"
tags: [research, tech]
---

# <Chủ đề>

**Người thực hiện:** <tên model đang chạy, vd Opus 5.5> (<team_name>)

> **Câu hỏi nghiên cứu:** <the user's angle, in their words>

## Tóm tắt để ra quyết định
3–5 bullets: what to choose and why. Give each conclusion a confidence level:
**Cao** (several independent sources agree) · **Trung bình** (evidence exists but is thin or mixed
with interests) · **Thấp** (one source, or vendor only).

## Phân tích
Organized around the user's question, not one section per --ask. Cite as "<publisher> ([n], <label>)",
e.g. "cộng đồng HN [14] phản bác…", "nhà cung cấp tự nhận [3]…". Show where the source types
disagree. Say which claims rest on a single source.

## Bảng hỗ trợ
One row per tool (including those outside the sources) × the facts from step 7. Each cell holds the value
plus the doc link and the check date, or `chưa xác nhận`.

## Số liệu áp dụng
<metrics.md> plus 1–2 sentences reading it (stars measure attention, not quality).

## Thử nhanh
For the 1–2 recommended tools: minimal install + first-run steps from the official docs, with links.
Start with: "Tổng hợp từ tài liệu chính thức, chưa chạy thử."

## Kết luận & khuyến nghị
Actionable points for the user and their team.

## Nguồn
<sources.md> then the YouTube stats block, plus one or two sentences on engagement (views/subs is rough).

## Sản phẩm
![Infographic](assets/<SLUG>/infographic.png) and any NotebookLM deliverables (audio embed, flashcards link,
mind map as an indented outline).

## Phương pháp & ghi chú
- Queries per source; candidates scanned; sources skipped and why (bot check, Reddit partial, HN thin…)
- NotebookLM: sources loaded/failed, top-ups, notebook ID
- Verification: what was checked against snippets, what is "chưa xác minh", corrections made
- Run time (start → end)
- Full Q&A: [analysis-mapped.md](assets/<SLUG>/analysis-mapped.md)
```

## 10. Infographic, then show it

Copy `$TEMPLATE` to `$WORK/infographic.html`. Fill it **from the finished, verified report**, following
the comments in the template: group the tools, set support badges only from the Bảng hỗ trợ, and add
the recommendation, disagreements, gaps and a source-mix footer. Then render it:

```bash
cd $SK && python3 render_infographic.py $WORK/infographic.html $WORK/infographic.png
```

Look at the PNG (Read it) and fix any overflow or wrong text before finishing. NotebookLM's own
infographic is made only if the user asked for it (`--deliverables infographic --language vi`).

Print the full report in chat (minus the frontmatter), then its file path and the notebook ID. If a
source type or deliverable failed, say so plainly. Deliverables can be resumed with
`pipeline.py --notebook <id> --deliverables <kind> --language vi --out $WORK`.
