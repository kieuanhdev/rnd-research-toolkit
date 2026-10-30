---
name: notebooklm-studio
description: Turn YouTube videos, web pages, PDFs/docs and pasted text into Google NotebookLM (a.k.a. Gemini Notebook) deliverables via the notebooklm-py CLI — create a notebook, add sources, analyze them with grounded, cited Q&A and summaries, and generate an Audio Overview (podcast), mind map, flashcards, and infographic, downloaded as files. Use this whenever the user wants a podcast/audio overview, mind map, flashcards, study deck, or infographic made from videos, links, documents or notes, wants to "put these in NotebookLM", or wants source-grounded analysis of a set of materials — even if they don't name NotebookLM. For other NotebookLM chores (sharing, labels, deep research, slide decks, video) fall back to `notebooklm --help` or the upstream `notebooklm` skill.
---

# NotebookLM Studio

Drive Google NotebookLM through the `notebooklm` CLI (package `notebooklm-py`, an unofficial
client) to go from raw sources to finished study/communication material:

```
create notebook → add sources (YouTube / URL / file / text) → wait until ready
   → analysis (summary, cited Q&A) → generate deliverables → wait → download by exact ID
```

`scripts/pipeline.py` does this whole chain in one command and records every ID in
`manifest.json`. Prefer it over hand-running the steps; drop to individual CLI commands
when the user wants something the script doesn't cover or a step needs repair.

## 0. Preflight (always)

```bash
notebooklm --version                          # this skill was written against 0.8.x
notebooklm auth check --test --json           # need .status=="ok" and .checks.token_fetch==true
```

Not installed → `uv tool install "notebooklm-py[browser]"` (or `pipx install`; avoid
`pip --break-system-packages`). Auth not ok → ask the user to run `notebooklm login` themselves
(it opens a browser — you can't complete it for them), or try `notebooklm auth refresh` first.
Never print or copy the contents of `~/.notebooklm/` — those files are full Google-account
credentials.

If anything in this file disagrees with `notebooklm <command> --help`, trust the help: it
matches the installed version.

## 1. Agree on scope before spending quota

Generation is slow and rate-limited by Google, so confirm what the user actually wants before
kicking it off. The things worth settling (ask only what isn't already clear):

- **Which deliverables.** Don't generate all four "just in case". Free accounts get roughly
  **3 audio overviews and ~3 infographics per day**, 10 flashcard decks and 10 mind maps
  (paid tiers are higher). `notebooklm usage --json` shows live remaining compute. If the user
  asks for more audio/infographics than a free tier allows, say so up front.
- **New notebook or existing one.** `notebooklm list --json` to find an existing one.
- **Language** of the outputs. Pass `--language vi` etc. per command, and never run
  `notebooklm language set`, which silently changes the whole account's default. Audio,
  mind map and infographic accept `--language`; **flashcards don't**, so the language request has
  to go in the flashcards prompt (the script does this for you). Spot-check the cards afterwards.
- **Angle / audience** — this goes into the prompts (see §4) and is the biggest quality lever.

A clear request like "make a podcast and flashcards from these 3 videos" already authorizes
creating the notebook, adding sources, waiting, generating those two things, and writing the
files. Don't re-ask for each step. Do ask before anything destructive (deleting notebooks,
sources or artifacts) or anything the user didn't request.

## 2. Run the pipeline

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/notebooklm-studio/scripts/pipeline.py \
  --title "Transformers explained" \
  --youtube "https://www.youtube.com/watch?v=XXXX" \
  --url "https://example.com/article" \
  --file ./paper.pdf \
  --text "$(cat notes.md)" --text-title "My notes" \
  --summary --ask "What are the 3 core ideas and how do they connect?" \
  --deliverables audio,mindmap,flashcards,infographic \
  --audio-prompt "For first-year CS students; concrete analogies, no hype" \
  --infographic-orientation portrait --infographic-style instructional \
  --flashcards-quantity more \
  --language en \
  --out ./transformers-explained
```

- Use `--notebook <id>` instead of `--title` to add to an existing notebook. When you add new
  sources there, analysis and deliverables use **only the newly added sources** by default, which
  suits "make an episode about this article". Add `--all-sources` when the user wants the whole
  notebook covered. If it's unclear, ask: it changes the output a lot.
- `--deliverables` takes any subset of `audio,mindmap,flashcards,infographic` or `all`; omit it
  for analysis only.
- Run `--dry-run` first if you want to show the user the exact commands without touching their
  account.
- It takes a while: sources ~1–5 min (long YouTube videos more), flashcards/mind map ~1–3 min,
  infographic ~2–8 min, audio commonly 5–15 min. Run it in the background if your host supports
  that, and tell the user roughly how long to expect. Don't leave them staring at nothing.
- Exit 0 = everything requested was produced. Exit 1 = read `manifest.json`: it says which step
  failed and holds every ID needed to resume by hand (§5).

Outputs in `--out`:

| File | What it is |
|---|---|
| `manifest.json` | notebook ID, every source ID/status, Q&A with references, every artifact ID/status/file |
| `analysis.md` | summary, suggested topics, each Q&A with its `[n]` citations quoted from the source text |
| `audio-overview.m4a` | the Audio Overview (two-host podcast) |
| `mindmap.json` | mind-map tree (`{name, children:[...]}`) |
| `flashcards.md` / `.tsv` / `.json` | readable deck, Anki/Quizlet import file (front⇥back), raw deck |
| `infographic.png` | the infographic image |

After it finishes, tell the user where the files are, give the notebook ID, and mention they can
open the notebook in the NotebookLM web app (the interactive mind map and audio player live there).
If they'd like to see the mind map without the web app, offer to render `mindmap.json` as an
indented outline or a Mermaid `mindmap` diagram. That's a quick, nice touch.

## 3. Sources: what to know

| Input | Flag | Notes |
|---|---|---|
| YouTube | `--youtube URL` | Needs captions/transcript; private, age-gated or caption-less videos fail to process. |
| Web page | `--url URL` | Paywalled/JS-heavy pages may fail; manual retry with `notebooklm source add URL --type url --fallback-fetch`. |
| Local file | `--file PATH` | PDF, txt, md, docx, audio, images… Script checks the file exists. Without that check the CLI would silently ingest the *path string* as text. Symlinks are rejected unless you add `--follow-symlinks` manually. |
| Text | `--text "..." --text-title T` | For pasted notes/transcripts. For long text, save to a `.md`/`.txt` and pass `--file` instead. |

Decide whether pasted text is *material* or *instructions about the material*. Material (lecture
notes, a transcript) is a source. Commentary *about* the sources (reviewer feedback, "my advisor
wants X", the angle the user cares about) belongs in the `--ask` questions and the deliverable
prompts. If you add it as a source, NotebookLM will cite it back as evidence and blend it into the
mind map and infographic. A critique of a thesis chapter should cite the chapter, not the reviewer.

Always pass the type explicitly (`--type youtube|url|file|text`) when adding by hand. The
auto-detection guesses, and a wrong guess wastes a source slot. Every source must reach
`ready` before chat or generation. `source wait` exits 0 = ready, 1 = failed, 2 = timeout. If a
source can't be added or never becomes ready (dead/private video, paywall), the script records
it in `manifest.json` (`add_failed` / `error` / `timeout`) and continues with the rest. Tell the user which
ones were dropped and why, rather than burying it.

## 4. Analysis and prompts

Analysis is grounded only in the notebook's sources, which is the point. Answers come back with
`references[].source_id` citations.

- `--summary` → NotebookLM's auto summary plus suggested topics. It's a good first look at
  unfamiliar material.
- `--ask` (repeatable) → questions run as one conversation, so later questions can build on
  earlier ones. Good analysis questions are specific: "Where do sources A and B disagree about X,
  and what evidence does each cite?" beats "analyze these".
- By hand: `notebooklm ask "..." -n <nb> --json`, continue with `-c <conversation_id>`, narrow
  with `-s <source_id>`. **Never use `ask --new` with `--json`.** `--json` implies `--yes`, so it
  irreversibly deletes the notebook's existing conversation without prompting.
- `notebooklm suggest-prompts -n <nb>` gives NotebookLM's own question ideas when the user
  doesn't know what to ask.
- Chat answers often end with a canned "🌱 Next step: would you like me to generate…" upsell.
  When you relay an answer, drop that line. It's NotebookLM talking, not the user's content.
- When reporting analysis, synthesize. Tie the answer back to the user's question, keep the
  `[n]` citations meaningful by naming the cited sources, and point out where sources were thin.

Steering the deliverables (all optional, but they make a big difference):

| Deliverable | Knobs | Steering tip |
|---|---|---|
| Audio | `--audio-prompt`, `--audio-format deep-dive\|brief\|critique\|debate`, `--audio-length short\|default\|long` | Name the audience and focus ("for nurses, focus on dosing errors"). `brief` ≈ a few minutes; `debate` makes the two hosts argue sides. |
| Mind map | `--mindmap-instructions` | e.g. "organize by chronology" or "top level = the 5 chapters". Synchronous; no wait step. |
| Flashcards | `--flashcards-prompt`, `--flashcards-quantity fewer\|standard\|more`, `--flashcards-difficulty easy\|medium\|hard` | e.g. "definitions and formulas only". |
| Infographic | `--infographic-prompt`, `--infographic-orientation landscape\|portrait\|square`, `--infographic-detail concise\|standard\|detailed`, `--infographic-style auto\|sketch-note\|professional\|bento-grid\|editorial\|instructional\|scientific\|…` | Portrait suits phones/posters; `detailed` + `scientific` for technical material. |

Deliverables use only the sources that are `ready` (the script passes them with `-s`).

## 5. Doing steps by hand / recovering

The rules that keep manual work safe:

1. Use `--json` and pass `-n <notebook_id>` on **every** command. Don't rely on
   `notebooklm use`, because the "current notebook" is shared global state.
2. Capture IDs: `create` → `.notebook.id`; `source add` → `.source.id`; `generate <type> --no-wait --json` → `.task_id` (this *is* the artifact ID).
3. Wait, then download **by that exact ID**. Without `-a`, `download` grabs the *latest* artifact
   of that type, which may be someone else's or an older one:

```bash
notebooklm generate audio "focus on X" -n $NB -s $SRC --no-wait --json   # → .task_id
notebooklm artifact wait $ID -n $NB --timeout 1500 --json                  # default 300s is too short for audio
notebooklm download audio ./audio-overview.m4a -a $ID -n $NB
notebooklm download flashcards ./cards.json -a $ID -n $NB   # see note below re: --format markdown
notebooklm download infographic ./infographic.png -a $ID -n $NB
notebooklm generate mind-map -n $NB --json > mm.json   # done when it returns; tree is in .mind_map
```

In 0.8.x, `download flashcards --format markdown|html` dumps raw `{'flashcardContentBlock': ...}`
dicts instead of card text. Download JSON (`{title, cards:[{front, back}]}`, each side holding
`flashcardContentBlock[].content`) and render it, or call `render_flashcards()` from
`scripts/pipeline.py`.

Diagnose with read-only commands before changing anything:

```bash
notebooklm auth check --test --passive --json
notebooklm source list -n $NB --json
notebooklm artifact list -n $NB --json
```

- Errors under `--json` look like `{"error": true, "code": "RATE_LIMITED", "message": ...}`.
  `RATE_LIMITED` / daily-limit messages: stop, tell the user which quota they hit and that it
  resets daily, and don't loop on retries. `AUTH_ERROR`: re-run the auth check, then ask the user
  to `notebooklm login`. `UNCONFIRMED_WRITE`: the action may have happened, so list before retrying
  to avoid duplicates.
- Artifact stuck/failed: check `artifact list`; `notebooklm artifact retry <id> -n $NB` retries
  in place (check its `--help` first).
- Resume a half-finished run: `pipeline.py --notebook <id from manifest> --deliverables <the ones
  that failed> --out <same dir>`. Adding no `--youtube/--file/...` flags means no new sources,
  and the script uses all sources already in the notebook. The previous `manifest.json` is kept
  as `manifest.<timestamp>.json`.

## 6. Python API (only if the user wants code)

For an app/script rather than a one-off run, use the async API and keep the same
ready-then-generate-then-wait discipline:

```python
from notebooklm import NotebookLMClient
async with NotebookLMClient.from_storage() as client:      # not awaited
    nb = await client.notebooks.create("Title")
    src = await client.sources.add_url(nb.id, url)
    await client.sources.wait_until_ready(nb.id, src.id, timeout=600)
    task = await client.artifacts.generate_audio(nb.id, source_ids=[src.id], instructions="...")
    final = await client.artifacts.wait_for_completion(nb.id, task.task_id, timeout=1500)
    await client.artifacts.download_audio(nb.id, "out.m4a", artifact_id=task.task_id)
```

Check exact method names with `python -c "import notebooklm, inspect; help(notebooklm.NotebookLMClient)"`
or https://github.com/teng-lin/notebooklm-py/blob/main/docs/python-api.md. Don't guess them.
