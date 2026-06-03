#!/usr/bin/env python3
"""Cross-platform orchestrator for the sermon-cuts pipeline.

This is the Python port of the original ``pipeline.sh``. Same CLI surface,
runs on macOS, Linux, and Windows without any shell or POSIX tooling.

Why the port: pipeline.sh required bash, which Windows doesn't ship with.
Users on Windows would either set up WSL or Git Bash, which is friction.
Python is already a hard dependency (the per-stage scripts are all Python),
so the orchestrator runs in Python too — one less environment to bootstrap.

The original ``pipeline.sh`` is kept as a thin wrapper that exec's into
this script, so any muscle memory / cron jobs / docs that reference
``pipeline.sh`` keep working unchanged on Unix.

Modes:
  pipeline.py doctor                         # health-check the environment
  pipeline.py <source>                       # ingest + transcribe + vad + propose
  pipeline.py --propose-only <source>        # same as above (just clarity)
  pipeline.py --render-cut N --slug S        # render cut N for slug S
  pipeline.py --render-cuts N,M,P --slug S   # batch render
  pipeline.py --reburn-srt N --slug S        # only re-burn subtitles (no retracking)

Render flags:
  --skip-scrub        skip the 06b SRT lint pass (CI / batch runs where
                      no human is around to review suspects)
  --target T          delivery target: all (default, 60-90s), shorts
                      (re-caps at 60s), reels, tiktok. Forwarded to
                      04_propose_cuts and 05_validate_cut.
  --quality Q         encoder quality: auto (default — hardware encoder
                      on Apple Silicon) or max (forces libx264/libx265 +
                      filter chain). Forwarded to 07_render_track and
                      09_trim_silences.
  --codec C           video codec: h264 (default) or hevc (~40% smaller
                      files, accepted by all major platforms since 2022).
                      Forwarded to 07_render_track and 09_trim_silences.

Source can be a YouTube URL or a local .mp4/.mov path.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# The scripts directory is wherever this file lives — works whether you
# invoke pipeline.py via the symlinked skill install, the cloned repo
# directly, or a CI checkout. PYTHON resolves the interpreter the user
# launched us with, so virtualenvs / pyenv shims are honored automatically.
SCRIPTS = Path(__file__).resolve().parent
PYTHON = sys.executable


def run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a sub-script and let it talk to our stdout/stderr directly.

    When ``capture`` is True the stdout is collected and returned in the
    CompletedProcess (used for the ingest step where we need the slug
    from the JSON the script prints).
    """
    if capture:
        return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE)
    return subprocess.run(args, check=True)


def script(name: str) -> str:
    """Resolve a sibling script by name, e.g. ``script("01_ingest.py")``."""
    return str(SCRIPTS / name)


def run_ingest_propose(source: str, target: str) -> None:
    """Phase A: download/probe + transcribe + VAD + propose-input.

    Calls 01→04 in sequence. 04 doesn't actually propose cuts (it just
    packages the inputs); the AI agent driving this pipeline is expected
    to read prompts/propose_cuts.md and write cuts_proposed.json next.
    """
    print("→ [1/4] ingest", file=sys.stderr)
    proc = run([PYTHON, script("01_ingest.py"), source], capture=True)
    sys.stdout.write(proc.stdout)
    sys.stdout.flush()
    try:
        meta = json.loads(proc.stdout)
        slug = meta["slug"]
    except (json.JSONDecodeError, KeyError) as e:
        sys.exit(f"could not parse slug from ingest output: {e}")

    print(f"→ [2/4] transcribe (slug={slug})", file=sys.stderr)
    run([PYTHON, script("02_transcribe.py"), slug])

    print("→ [3/4] VAD", file=sys.stderr)
    run([PYTHON, script("03_vad_segments.py"), slug])

    print(f"→ [4/4] propose-cuts input ready (target={target})", file=sys.stderr)
    run([PYTHON, script("04_propose_cuts.py"), slug, "--target", target])

    print(file=sys.stderr)
    print("Next: your AI editor reads propose_input.json + prompts/propose_cuts.md", file=sys.stderr)
    print(f"and writes memory/messages/{slug}/cuts_proposed.json", file=sys.stderr)


def scrub_srt(slug: str, idx: int, skip_scrub: bool, llm_scrub: bool) -> None:
    """Run the SRT scrub pass with context-aware output mode.

    --llm-scrub → calls 06b with --full-llm-review (sends entire SRT
       + per-cue transcript snippet to the LLM; applies all returned
       fixes). Catches errors the rule-based heuristics miss; needs
       ANTHROPIC_API_KEY (preferred) or GROQ_API_KEY. ~$0.01 per cut.
    TTY → interactive y/n/edit prompts (stdout suppressed; user sees
    prompts on stderr).
    Non-TTY → emit the --agent-review JSON to stdout so the orchestrating
    agent can read it and apply file-edit fixes before render continues.
    """
    if skip_scrub:
        print(f"→ cut #{idx}: scrub SRT [skipped — --skip-scrub]", file=sys.stderr)
        return
    if llm_scrub:
        print(f"→ cut #{idx}: scrub SRT [LLM full-review]", file=sys.stderr)
        run([PYTHON, script("06b_scrub_srt.py"), slug, str(idx), "--full-llm-review"])
        return
    print(f"→ cut #{idx}: scrub SRT (review suspects)", file=sys.stderr)
    # Stdin is a TTY → interactive review. Otherwise let 06b emit its
    # agent-review JSON to the caller's stdout (the agent reads it).
    if sys.stdin.isatty():
        subprocess.run(
            [PYTHON, script("06b_scrub_srt.py"), slug, str(idx)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    else:
        run([PYTHON, script("06b_scrub_srt.py"), slug, str(idx)])


def run_render(slug: str, cuts: list[int], *, target: str, quality: str,
               codec: str, skip_scrub: bool, llm_scrub: bool) -> None:
    """Phase C: per-cut render. Validate → build SRT → scrub → render →
    normalize → trim silences (opt-in)."""
    if not slug:
        sys.exit("--slug required for --render-cut/--render-cuts")
    if not cuts:
        sys.exit("cut index required for --render-cut/--render-cuts")
    for idx in cuts:
        print(f"→ cut #{idx}: validate (target={target})", file=sys.stderr)
        run([PYTHON, script("05_validate_cut.py"), slug, str(idx),
             "--target", target, "--write-back"])
        print(f"→ cut #{idx}: build SRT", file=sys.stderr)
        run([PYTHON, script("06_build_srt.py"), slug, str(idx)])
        scrub_srt(slug, idx, skip_scrub, llm_scrub)
        print(f"→ cut #{idx}: render with tracking + burn legenda "
              f"(quality={quality} codec={codec})", file=sys.stderr)
        run([PYTHON, script("07_render_track.py"), slug, str(idx),
             "--quality", quality, "--codec", codec])
        print(f"→ cut #{idx}: normalize audio", file=sys.stderr)
        run([PYTHON, script("08_audio_normalize.py"), slug, str(idx), "--in-place"])
        print(f"→ cut #{idx}: trim long silences (opt-in)", file=sys.stderr)
        run([PYTHON, script("09_trim_silences.py"), slug, str(idx),
             "--quality", quality, "--codec", codec, "--in-place"])


def run_reburn(slug: str, cuts: list[int], *, quality: str, codec: str,
               skip_scrub: bool, llm_scrub: bool) -> None:
    """Re-burn subtitles + re-render without redoing tracking. Useful
    after editing the SRT (e.g. caption corrections) when the face
    trajectory hasn't changed."""
    if not slug:
        sys.exit("--slug required for --reburn-srt")
    for idx in cuts:
        print(f"→ cut #{idx}: rebuild SRT + reburn "
              f"(quality={quality} codec={codec})", file=sys.stderr)
        run([PYTHON, script("06_build_srt.py"), slug, str(idx)])
        scrub_srt(slug, idx, skip_scrub, llm_scrub)
        run([PYTHON, script("07_render_track.py"), slug, str(idx),
             "--quality", quality, "--codec", codec])
        run([PYTHON, script("08_audio_normalize.py"), slug, str(idx), "--in-place"])
        run([PYTHON, script("09_trim_silences.py"), slug, str(idx),
             "--quality", quality, "--codec", codec, "--in-place"])


def parse_cuts(s: str) -> list[int]:
    """Parse the CUTS argument from "1,2,3" / "5" into [int].

    Whitespace tolerated. Empty entries dropped. Bad ints raise SystemExit
    with a clear message rather than the cryptic ValueError default.
    """
    try:
        return [int(x.strip()) for x in s.split(",") if x.strip()]
    except ValueError:
        sys.exit(f"cut indices must be comma-separated integers, got: {s!r}")


def main() -> None:
    # The leading subcommand parser is separate because doctor/ui/nightly/
    # migrate/review don't share the rest of the flag surface — they just
    # delegate straight through to their own script with whatever extra
    # args the user passed. Mirrors how the .sh version short-circuited
    # subcommands at the top of the case statement.
    if len(sys.argv) >= 2 and sys.argv[1] in {"doctor", "ui", "nightly", "migrate"}:
        sub = sys.argv[1]
        script_name = {
            "doctor": "doctor.py",
            "ui": "ui.py",
            "nightly": "nightly.py",
            "migrate": "migrate_paths.py",
        }[sub]
        sys.exit(subprocess.run(
            [PYTHON, script(script_name), *sys.argv[2:]]
        ).returncode)
    if len(sys.argv) >= 2 and sys.argv[1] == "review":
        # review.py prints the render command on stdout for the user to
        # execute. Capture, echo, exec.
        if len(sys.argv) < 3:
            sys.exit("usage: pipeline.py review <slug>")
        proc = subprocess.run(
            [PYTHON, script("review.py"), sys.argv[2]],
            check=False, text=True, stdout=subprocess.PIPE,
        )
        if proc.returncode != 0:
            sys.exit(proc.returncode)
        cmd = proc.stdout.strip()
        print(f"→ executando: {cmd}", file=sys.stderr)
        # Use the shell so the user's render command runs with quoting
        # exactly as review.py emitted it.
        sys.exit(subprocess.run(cmd, shell=True).returncode)

    ap = argparse.ArgumentParser(
        prog="pipeline.py",
        description=(
            "Cross-platform orchestrator for the sermon-cuts pipeline. "
            "Phase A: ingest + transcribe + VAD + propose-input. "
            "Phase C: per-cut render (validate → SRT → scrub → render → "
            "normalize → trim)."
        ),
    )
    ap.add_argument("source", nargs="?", default=None,
                    help="YouTube URL or local .mp4/.mov path. Required for "
                    "Phase A; ignored for render/reburn modes.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--propose-only", action="store_true",
                      help="run Phase A only (same as default — kept for clarity)")
    mode.add_argument("--render-cut", metavar="N",
                      help="render a single cut (1-based index)")
    mode.add_argument("--render-cuts", metavar="N,M,P",
                      help="batch-render multiple cuts")
    mode.add_argument("--reburn-srt", metavar="N",
                      help="re-burn subtitles on an existing render without "
                      "redoing face tracking")
    ap.add_argument("--slug", default="",
                    help="message slug (required for render/reburn modes)")
    ap.add_argument("--skip-scrub", action="store_true",
                    help="skip the SRT scrub pass (CI / batch without an agent)")
    ap.add_argument("--llm-scrub", action="store_true",
                    help=(
                        "route the SRT scrub through 06b_scrub_srt "
                        "--full-llm-review — sends every cue + per-cue "
                        "transcript context to the LLM and applies all "
                        "returned fixes. Catches errors the rule-based "
                        "heuristics miss. Needs ANTHROPIC_API_KEY or "
                        "GROQ_API_KEY. ~$0.01 per cut on Claude Haiku 4.5."
                    ))
    ap.add_argument("--target", default="all",
                    choices=["all", "shorts", "reels", "tiktok"],
                    help="delivery target — shorts caps at 60s")
    ap.add_argument("--quality", default="auto",
                    choices=["auto", "max"],
                    help="encoder quality preset")
    ap.add_argument("--codec", default="h264",
                    choices=["h264", "hevc"],
                    help="video codec for delivery")

    args = ap.parse_args()

    if args.render_cut or args.render_cuts:
        cuts = parse_cuts(args.render_cut or args.render_cuts)
        run_render(args.slug, cuts, target=args.target, quality=args.quality,
                   codec=args.codec, skip_scrub=args.skip_scrub,
                   llm_scrub=args.llm_scrub)
        return

    if args.reburn_srt:
        cuts = parse_cuts(args.reburn_srt)
        run_reburn(args.slug, cuts, quality=args.quality, codec=args.codec,
                   skip_scrub=args.skip_scrub, llm_scrub=args.llm_scrub)
        return

    # Default mode: Phase A.
    if not args.source:
        ap.error("source required for ingest/propose mode (or pass "
                 "--render-cut N --slug S)")
    run_ingest_propose(args.source, args.target)


if __name__ == "__main__":
    main()
