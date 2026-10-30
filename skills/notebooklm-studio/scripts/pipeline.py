#!/usr/bin/env python3
"""NotebookLM source-to-deliverables pipeline built on the `notebooklm` CLI.

Creates (or reuses) a notebook, adds typed sources, waits until every source is
ready, optionally runs analysis (summary + questions), generates the requested
Studio deliverables, waits for each, and downloads each by its exact artifact ID.
Every ID is recorded in <out>/manifest.json as soon as it is known, so a partial
failure can be resumed by hand.

Stdlib only. Run with --dry-run to print the command plan without touching the account.

Example:
  pipeline.py --title "Transformers 101" \
      --youtube https://youtu.be/XXXX --file notes.pdf --text "My own notes..." \
      --ask "What are the main arguments?" --summary \
      --deliverables audio,mindmap,flashcards,infographic --out ./transformers-101
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DELIVERABLES = ("audio", "mindmap", "flashcards", "infographic")
# Seconds to wait for each artifact type; audio routinely takes 5-15 minutes.
ARTIFACT_TIMEOUT = {"audio": 1500, "flashcards": 600, "infographic": 900}


class PipelineError(RuntimeError):
    pass


class Runner:
    def __init__(self, dry_run: bool, manifest_path: Path | None):
        self.dry_run = dry_run
        self.manifest_path = manifest_path
        self.manifest: dict = {"sources": [], "analysis": {}, "deliverables": {}}
        self._fake = 0
        self.all_sources = False

    def log(self, msg: str) -> None:
        print(f"[pipeline] {msg}", file=sys.stderr, flush=True)

    def save(self) -> None:
        if self.manifest_path and not self.dry_run:
            self.manifest_path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False))

    def cli(self, *args: str, parse_json: bool = True, ok_codes=(0,)) -> tuple[int, dict | str]:
        cmd = ["notebooklm", "--quiet", *args]
        if self.dry_run:
            print(" ".join(_quote(a) for a in cmd))
            self._fake += 1
            return 0, {"_dry": f"<id-{self._fake}>"}
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = proc.stdout.strip()
        if proc.returncode not in ok_codes:
            raise PipelineError(
                f"`{' '.join(cmd[:4])} ...` exited {proc.returncode}: "
                f"{_error_text(out) or proc.stderr.strip()[-800:]}"
            )
        if not parse_json:
            return proc.returncode, out
        try:
            return proc.returncode, json.loads(out) if out else {}
        except json.JSONDecodeError:
            return proc.returncode, {"_raw": out}


def _quote(a: str) -> str:
    if a and all(c.isalnum() or c in "-_./:=@,%+" for c in a):
        return a
    return "'" + a.replace("'", "'\\''") + "'"


def _error_text(out: str) -> str:
    try:
        d = json.loads(out)
        return f"{d.get('code')}: {d.get('message') or d.get('error')}"
    except Exception:
        return out[-800:]


def _dig(d: dict, *paths: str):
    """Return the first non-empty value among dotted paths (JSON shapes vary by command)."""
    for p in paths:
        cur = d
        for key in p.split("."):
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur:
            return cur
    return d.get("_dry") if isinstance(d, dict) else None


def preflight(r: Runner) -> None:
    if r.dry_run:
        r.cli("auth", "check", "--test", "--json")
        return
    _, d = r.cli("auth", "check", "--test", "--json", ok_codes=(0, 1))
    if not (d.get("status") == "ok" and d.get("checks", {}).get("token_fetch")):
        raise PipelineError(
            "NotebookLM auth is not valid. Ask the user to run `notebooklm login` "
            "(or `notebooklm auth refresh`) and try again."
        )


def add_sources(r: Runner, nb: str, args) -> None:
    specs: list[tuple[str, str, str | None]] = []  # (type, content, title)
    for u in args.youtube:
        specs.append(("youtube", u, None))
    for u in args.url:
        specs.append(("url", u, None))
    for f in args.file:
        p = Path(f).expanduser()
        # A missing path would otherwise be ingested as literal text, so fail loudly instead.
        if not p.is_file():
            if not r.dry_run:
                raise PipelineError(f"File not found: {f}")
            r.log(f"WARNING file not found (dry run continues): {f}")
        specs.append(("file", str(p.resolve()), None))
    for i, t in enumerate(args.text, 1):
        specs.append(("text", t, args.text_title[i - 1] if i <= len(args.text_title) else f"Pasted text {i}"))

    if not specs:
        return
    for kind, content, title in specs:
        cmd = ["source", "add", content, "--type", kind, "-n", nb, "--json"]
        if title:
            cmd += ["--title", title]
        if kind in ("file", "url", "youtube"):
            cmd += ["--timeout", "180"]
        label = content if kind != "text" else title
        # One dead link (private/removed video, paywall) shouldn't sink the other sources.
        try:
            _, d = r.cli(*cmd)
            sid = _dig(d, "source.id", "id")
            if not sid:
                raise PipelineError(f"no source id returned: {d}")
        except PipelineError as e:
            r.manifest["sources"].append({"id": None, "type": kind, "input": label,
                                          "status": "add_failed", "error": str(e)})
            r.save()
            r.log(f"WARNING could not add {kind} {label[:60]!r}: {e}")
            continue
        r.manifest["sources"].append({"id": sid, "type": kind, "input": label, "status": "added"})
        r.save()
        r.log(f"added {kind} source {sid}")

    # Sources process server-side in parallel, so waiting sequentially costs ~max(time).
    for s in r.manifest["sources"]:
        if not s["id"]:
            continue
        code, d = r.cli("source", "wait", s["id"], "-n", nb, "--timeout", str(args.source_timeout),
                        "--json", ok_codes=(0, 1, 2))
        s["status"] = {0: "ready", 2: "timeout"}.get(code, "error")
        r.save()
        r.log(f"source {s['id']}: {s['status']}")
    bad = [s for s in r.manifest["sources"] if s["status"] != "ready"]
    if bad and not r.dry_run:
        detail = ", ".join(f"{s['input']} -> {s['status']}" for s in bad)
        if len(bad) == len(r.manifest["sources"]):
            raise PipelineError(f"No source became ready: {detail}")
        r.log(f"WARNING continuing without: {detail}")


def ready_source_flags(r: Runner) -> list[str]:
    # With no -s flags the CLI uses every source in the notebook.
    if r.all_sources:
        return []
    flags: list[str] = []
    for s in r.manifest["sources"]:
        if s["status"] == "ready" or r.dry_run:
            flags += ["-s", s["id"]]
    return flags


def analyze(r: Runner, nb: str, args, out: Path) -> None:
    lines = [f"# Analysis: {r.manifest.get('title', nb)}", ""]
    if args.summary:
        _, d = r.cli("summary", "-n", nb, "--topics", "--json")
        r.manifest["analysis"]["summary"] = d
        summary = _dig(d, "summary", "description.summary") or json.dumps(d, indent=2)
        lines += ["## Summary", "", str(summary), ""]
        topics = d.get("suggested_topics") or d.get("topics") or []
        if topics:
            lines += ["## Suggested topics", ""]
            for t in topics:
                lines.append(f"- {t.get('question') or t.get('topic') or t if isinstance(t, dict) else t}")
            lines.append("")
    conv = None
    src = ready_source_flags(r)
    for q in args.ask:
        cmd = ["ask", q, "-n", nb, "--json", *src]
        if conv:
            cmd += ["-c", conv]  # never --new: with --json it silently deletes the conversation
        _, d = r.cli(*cmd)
        conv = d.get("conversation_id") or conv
        refs = d.get("references") or []
        r.manifest["analysis"].setdefault("qa", []).append(
            {"question": q, "answer": d.get("answer"), "references": refs})
        r.manifest["analysis"]["conversation_id"] = conv
        # Drop NotebookLM's trailing "🌱 Next step: would you like me to generate…" upsell.
        answer = "\n".join(l for l in str(d.get("answer", "")).splitlines() if not l.lstrip().startswith("🌱"))
        lines += [f"## Q: {q}", "", answer.rstrip(), ""]
        if refs:
            names = {s["id"]: s["input"] for s in r.manifest["sources"]}
            lines += ["Citations:", ""]
            seen = set()
            for ref in refs:
                if not isinstance(ref, dict) or ref.get("citation_number") in seen:
                    continue
                seen.add(ref.get("citation_number"))
                quote = " ".join(str(ref.get("cited_text") or "").split())
                if len(quote) > 400:
                    quote = quote[:400] + "…"
                ref_name = names.get(ref.get("source_id"), ref.get("source_id"))
                lines.append(f"- [{ref.get('citation_number', '?')}] {ref_name}: \"{quote}\"")
            lines.append("")
    r.save()
    if not r.dry_run and (args.summary or args.ask):
        (out / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
        r.log(f"wrote {out / 'analysis.md'}")


def _card_text(side) -> str:
    if isinstance(side, str):
        return side
    if isinstance(side, dict):
        blocks = side.get("flashcardContentBlock") or side.get("blocks") or []
        if blocks:
            return "\n".join(str(b.get("content", "")) if isinstance(b, dict) else str(b) for b in blocks)
        return str(side.get("content") or side.get("text") or side)
    return str(side)


def render_flashcards(deck_path: Path, out: Path) -> str:
    """Write flashcards.md (readable) and flashcards.tsv (Anki/Quizlet import) from the JSON deck."""
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    cards = deck.get("cards", []) if isinstance(deck, dict) else deck
    title = deck.get("title", "Flashcards") if isinstance(deck, dict) else "Flashcards"
    md = [f"# {title}", ""]
    tsv = []
    for i, c in enumerate(cards, 1):
        q, a = _card_text(c.get("front", c.get("question"))), _card_text(c.get("back", c.get("answer")))
        md += [f"**{i}. {q}**", "", a, ""]
        tsv.append(f"{q}\t{a}".replace("\n", "<br>"))
    (out / "flashcards.md").write_text("\n".join(md), encoding="utf-8")
    (out / "flashcards.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    return str(out / "flashcards.md")


def generate(r: Runner, nb: str, args, out: Path, wanted: list[str]) -> None:
    src = ready_source_flags(r)
    lang = ["--language", args.language] if args.language else []
    pending: dict[str, str] = {}

    for kind in wanted:
        if kind == "mindmap":
            cmd = ["generate", "mind-map", "-n", nb, "--json", *src, *lang]
            if args.mindmap_instructions:
                cmd += ["--instructions", args.mindmap_instructions]
            # Interactive mind maps are polled to completion by the CLI and the tree is in the
            # result, so there is no `artifact wait` and no download step.
            _, d = r.cli(*cmd)
            entry = {"id": d.get("note_id") or d.get("_dry"), "status": "completed"}
            if not r.dry_run:
                path = out / "mindmap.json"
                path.write_text(json.dumps(d.get("mind_map"), indent=2, ensure_ascii=False), encoding="utf-8")
                entry["file"] = str(path)
            r.manifest["deliverables"]["mindmap"] = entry
            r.save()
            r.log("mind map done")
            continue

        cmd = ["generate", kind, "-n", nb, "--no-wait", "--json", "--retry", "2", *src]
        if kind == "audio":
            cmd += ["--format", args.audio_format, "--length", args.audio_length, *lang]
            if args.audio_prompt:
                cmd.insert(2, args.audio_prompt)
        elif kind == "infographic":
            cmd += ["--orientation", args.infographic_orientation, "--detail", args.infographic_detail,
                    "--style", args.infographic_style, *lang]
            if args.infographic_prompt:
                cmd.insert(2, args.infographic_prompt)
        elif kind == "flashcards":
            cmd += ["--quantity", args.flashcards_quantity, "--difficulty", args.flashcards_difficulty]
            # `generate flashcards` has no --language flag (0.8.x), so ask for it in the prompt.
            prompt = args.flashcards_prompt or ""
            if args.language:
                prompt = f"{prompt} Write every card (front and back) in language '{args.language}'.".strip()
            if prompt:
                cmd.insert(2, prompt)
        try:
            _, d = r.cli(*cmd)
        except PipelineError as e:
            r.manifest["deliverables"][kind] = {"status": "failed_to_start", "error": str(e)}
            r.save()
            r.log(f"{kind}: failed to start ({e})")
            continue
        aid = _dig(d, "task_id", "artifact_id", "artifact.id", "id")
        r.manifest["deliverables"][kind] = {"id": aid, "status": "in_progress"}
        r.save()
        pending[kind] = aid
        r.log(f"{kind} started: {aid}")

    for kind, aid in pending.items():
        entry = r.manifest["deliverables"][kind]
        try:
            r.cli("artifact", "wait", aid, "-n", nb, "--timeout", str(ARTIFACT_TIMEOUT[kind]), "--json")
        except PipelineError as e:
            entry.update(status="not_completed", error=str(e))
            r.save()
            r.log(f"{kind}: did not complete ({e})")
            continue
        target = {
            "audio": ["download", "audio", str(out / "audio-overview.m4a")],
            "infographic": ["download", "infographic", str(out / "infographic.png")],
            # The CLI's own --format markdown prints raw content-block dicts (0.8.x), so take
            # the JSON deck and render markdown/TSV ourselves.
            "flashcards": ["download", "flashcards", str(out / "flashcards.json")],
        }[kind]
        try:
            r.cli(*target, "-a", aid, "-n", nb, "--force", "--json")
            entry.update(status="completed", file=target[2])
            if kind == "flashcards" and not r.dry_run:
                entry["file"] = render_flashcards(out / "flashcards.json", out)
        except PipelineError as e:
            entry.update(status="download_failed", error=str(e))
        r.save()
        r.log(f"{kind}: {entry['status']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--title", help="Create a new notebook with this title")
    g.add_argument("--notebook", help="Reuse an existing notebook ID")
    ap.add_argument("--youtube", action="append", default=[], help="YouTube URL (repeatable)")
    ap.add_argument("--url", action="append", default=[], help="Web page URL (repeatable)")
    ap.add_argument("--file", action="append", default=[], help="Local file: PDF, txt, md, docx, audio... (repeatable)")
    ap.add_argument("--text", action="append", default=[], help="Inline text source (repeatable)")
    ap.add_argument("--text-title", action="append", default=[], help="Title for the matching --text")
    ap.add_argument("--source-timeout", type=int, default=600)
    ap.add_argument("--all-sources", action="store_true",
                    help="With --notebook: analyze/generate from every source in the notebook, not just "
                         "the ones added in this run (default when no new sources are given)")
    ap.add_argument("--summary", action="store_true", help="Save notebook summary + suggested topics")
    ap.add_argument("--ask", action="append", default=[], help="Analysis question (repeatable, one conversation)")
    ap.add_argument("--deliverables", default="", help=f"Comma list from {','.join(DELIVERABLES)} or 'all'")
    ap.add_argument("--language", help="Output language code, e.g. vi, en, fr (per command, never account-wide)")
    ap.add_argument("--audio-prompt")
    ap.add_argument("--audio-format", default="deep-dive", choices=["deep-dive", "brief", "critique", "debate"])
    ap.add_argument("--audio-length", default="default", choices=["short", "default", "long"])
    ap.add_argument("--mindmap-instructions")
    ap.add_argument("--flashcards-prompt")
    ap.add_argument("--flashcards-quantity", default="standard", choices=["fewer", "standard", "more"])
    ap.add_argument("--flashcards-difficulty", default="medium", choices=["easy", "medium", "hard"])
    ap.add_argument("--infographic-prompt")
    ap.add_argument("--infographic-orientation", default="landscape", choices=["landscape", "portrait", "square"])
    ap.add_argument("--infographic-detail", default="standard", choices=["concise", "standard", "detailed"])
    ap.add_argument("--infographic-style", default="auto",
                    choices=["auto", "sketch-note", "professional", "bento-grid", "editorial", "instructional",
                             "bricks", "clay", "anime", "kawaii", "scientific"])
    ap.add_argument("--out", default=".", help="Output directory for files + manifest.json")
    ap.add_argument("--dry-run", action="store_true", help="Print the command plan only")
    args = ap.parse_args()

    wanted = list(DELIVERABLES) if args.deliverables.strip() == "all" else \
        [d.strip().replace("mind-map", "mindmap") for d in args.deliverables.split(",") if d.strip()]
    unknown = set(wanted) - set(DELIVERABLES)
    if unknown:
        ap.error(f"unknown deliverable(s): {', '.join(sorted(unknown))}")

    out = Path(args.out).expanduser().resolve()
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.json"
    if manifest.exists() and not args.dry_run:
        # Keep the previous run's IDs when resuming into the same directory.
        manifest.rename(out / f"manifest.{time.strftime('%Y%m%d-%H%M%S')}.json")
    r = Runner(args.dry_run, manifest)
    r.all_sources = args.all_sources or (args.notebook and not (args.youtube or args.url or args.file or args.text))
    started = time.time()
    try:
        preflight(r)
        if args.notebook:
            nb = args.notebook
        else:
            _, d = r.cli("create", args.title, "--json")
            nb = _dig(d, "notebook.id", "id")
            if not nb:
                raise PipelineError(f"No notebook id returned: {d}")
            r.manifest["title"] = args.title
        r.manifest["notebook_id"] = nb
        r.save()
        r.log(f"notebook {nb}")
        add_sources(r, nb, args)
        if args.summary or args.ask:
            analyze(r, nb, args, out)
        if wanted:
            generate(r, nb, args, out, wanted)
    except PipelineError as e:
        r.manifest["error"] = str(e)
        r.save()
        r.log(f"FAILED: {e}")
        return 1
    finally:
        r.manifest["elapsed_seconds"] = round(time.time() - started)
        r.save()
    if not args.dry_run:
        print(json.dumps(r.manifest, indent=2, ensure_ascii=False))
    failed = [k for k, v in r.manifest["deliverables"].items() if v.get("status") != "completed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
