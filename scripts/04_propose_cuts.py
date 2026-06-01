#!/usr/bin/env python3
"""Stub: emit the inputs Claude needs to propose cuts.

This script does NOT call an LLM — that's deferred to Claude (the agent
loop running this skill). It just packages transcript + VAD into a single
file the agent can read, plus prints the prompt path.

Usage:
    04_propose_cuts.py <slug>

Reads:
    memory/messages/<slug>/transcript.json
    memory/messages/<slug>/vad.json
Writes:
    memory/messages/<slug>/propose_input.json   (combined input)
Prints:
    JSON with paths the agent should read + the prompt to use.

The agent then writes the proposed cuts to:
    memory/messages/<slug>/cuts_proposed.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import SCHEMA_VERSION, config_dir, prompts_dir, resolve_messages_dir

MESSAGES = resolve_messages_dir()


def words_to_text_with_timestamps(words: list[dict]) -> str:
    """Compact textual representation for the LLM, with periodic timestamps."""
    lines: list[str] = []
    cur: list[str] = []
    cur_start = 0.0
    last_ts = -1.0
    for w in words:
        if w.get("type") != "word":
            continue
        t = float(w.get("start") or 0)
        text = (w.get("text") or "").strip()
        if not cur:
            cur_start = t
        cur.append(text)
        # Flush every ~10s OR on sentence-ending punctuation
        last_char = text[-1] if text else ""
        if (t - last_ts > 10 and len(cur) > 1) or last_char in ".!?":
            lines.append(f"[{cur_start:7.2f}] {' '.join(cur)}")
            cur = []
            last_ts = t
    if cur:
        lines.append(f"[{cur_start:7.2f}] {' '.join(cur)}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument(
        "--target",
        choices=["all", "shorts", "reels", "tiktok"],
        default="all",
        help=(
            "delivery target. 'all' (default) uses the 60-90s window from "
            "render_defaults.yaml. 'shorts' caps at shorts_max_duration_s "
            "(60s) for YouTube Shorts compatibility. 'reels'/'tiktok' are "
            "currently aliases for 'all' — the same window fits both."
        ),
    )
    args = ap.parse_args()
    msg_dir = MESSAGES / args.slug
    transcript = json.loads((msg_dir / "transcript.json").read_text())
    vad = json.loads((msg_dir / "vad.json").read_text())

    import yaml as _yaml

    cfg = _yaml.safe_load((config_dir() / "render_defaults.yaml").read_text())
    cut_cfg = cfg.get("cut_validation", {})
    min_s = cut_cfg.get("min_duration_s", 60)
    max_s = cut_cfg.get("max_duration_s", 90)
    if args.target == "shorts":
        max_s = cut_cfg.get("shorts_max_duration_s", 60)

    compact_transcript = words_to_text_with_timestamps(transcript["words"])
    combined = {
        "_schema_version": SCHEMA_VERSION,
        "slug": args.slug,
        "duration_s": vad.get("total_duration_s", 0),
        "transcript_compact": compact_transcript,
        "candidate_cut_points": vad["candidate_cut_points"],
        "n_words": sum(1 for w in transcript["words"] if w.get("type") == "word"),
        # The LLM reads `target` + duration window directly so a single
        # prompt template covers all delivery targets without per-target
        # forks. shorts → 60-60s; everything else → 60-90s.
        "target": args.target,
        "duration_min_s": min_s,
        "duration_max_s": max_s,
    }
    out = msg_dir / "propose_input.json"
    out.write_text(json.dumps(combined, indent=2, ensure_ascii=False))

    print(
        json.dumps(
            {
                "ok": True,
                "input_path": str(out),
                "prompt_path": str(prompts_dir() / "propose_cuts.md"),
                "expected_output_path": str(msg_dir / "cuts_proposed.json"),
                "instructions": (
                    "Now read the prompt at prompt_path and the input at "
                    "input_path, then write JSON array of cut proposals to "
                    "expected_output_path."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
