#!/usr/bin/env python3
"""Compress long pauses inside an already-rendered cut.

Reads the VAD silences computed by ``03_vad_segments.py`` and, for each
silence inside the cut's window longer than ``threshold_s`` (default 2.5s),
keeps only ``keep_silence_s`` of breathing room and drops the rest.

Effect: a 60s cut with two 4s dramatic pauses becomes ~54s with the
*timing* of the pauses preserved (~1s each instead of 4s). The speaker's
rhythm stays intact, the dragging silences go away.

This step is OPT-IN per cut via ``cuts_proposed.json``::

    {
      "n": 3,
      "slug": "perdao_no_varejo",
      "start": 412.5,
      "end": 478.1,
      "trim_silences": true,            // ← turn it on
      "trim_threshold_s": 2.5,          // ← optional override
      "trim_keep_silence_s": 1.0        // ← optional override
    }

Without those keys, this script is a no-op (`pipeline.sh` only calls it
when the cut requests it).

Usage:
    09_trim_silences.py <slug> <cut_index> [--in-place]

Re-encodes once (`pick_video_encoder` from _common picks the hardware
encoder when available). The re-encode cost is the trade-off for the
feature; expect ~3-5s overhead on Apple Silicon.

Reads:
    memory/messages/<slug>/cuts_proposed.json
    memory/messages/<slug>/vad.json
    memory/messages/<slug>/renders/NN-slug.mp4
Writes:
    memory/messages/<slug>/renders/NN-slug.trimmed.mp4
    (or overwrites NN-slug.mp4 if --in-place)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    config_dir,
    fail,
    pick_video_encoder,
    resolve_ffmpeg,
    resolve_messages_dir,
    resolve_renders_dir,
)

MESSAGES = resolve_messages_dir()
RENDERS = resolve_renders_dir()
CFG = yaml.safe_load((config_dir() / "render_defaults.yaml").read_text())
FFMPEG = resolve_ffmpeg(CFG.get("ffmpeg_bin"))
VID = CFG["video"]

DEFAULT_THRESHOLD_S = 2.5
DEFAULT_KEEP_SILENCE_S = 1.0


def compute_keep_intervals(
    silences: list[dict],
    cut_start: float,
    cut_end: float,
    threshold_s: float,
    keep_silence_s: float,
) -> list[tuple[float, float]]:
    """Return list of [start, end] intervals (relative to cut start) we want
    to keep. Silences longer than ``threshold_s`` collapse to
    ``keep_silence_s`` worth of audio centered on the pause's natural start.

    Why center on the start? Speakers usually let a thought land BEFORE the
    pause, so the first ~1s of silence reads as "intentional weight". The
    tail of a long pause reads as "dragging" — that's what we trim.
    """
    cut_dur = cut_end - cut_start
    # Filter silences that overlap the cut window AND exceed the threshold.
    long_silences: list[tuple[float, float]] = []
    for sil in silences:
        sil_start = max(0.0, float(sil["start"]) - cut_start)
        sil_end = min(cut_dur, float(sil["end"]) - cut_start)
        if sil_end <= sil_start:
            continue
        if (sil_end - sil_start) <= threshold_s:
            continue
        long_silences.append((sil_start, sil_end))
    long_silences.sort()

    if not long_silences:
        # Nothing to trim — return the whole cut as a single interval.
        return [(0.0, cut_dur)]

    # Build keep-intervals by walking the timeline and "skipping" the
    # excess of each long silence past keep_silence_s.
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for sil_start, sil_end in long_silences:
        keep_until = min(cut_dur, sil_start + keep_silence_s)
        if keep_until > cursor:
            keep.append((cursor, keep_until))
        cursor = sil_end
    if cursor < cut_dur:
        keep.append((cursor, cut_dur))
    return keep


def build_concat_filter(intervals: list[tuple[float, float]]) -> str:
    """Build an ffmpeg ``filter_complex`` expression that trims the input
    into the given intervals and concatenates them with PTS reset.

    Output streams are ``[vout]`` and ``[aout]``.
    """
    parts: list[str] = []
    for i, (a, b) in enumerate(intervals):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    n = len(intervals)
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vout][aout]")
    return ";".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("cut_index", type=int)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument(
        "--quality",
        choices=["auto", "max"],
        default="auto",
        help=(
            "encoder quality for the re-encode pass — should match what 07 "
            "used, otherwise the trimmed output silently downgrades."
        ),
    )
    args = ap.parse_args()

    msg_dir = MESSAGES / args.slug
    cuts = json.loads((msg_dir / "cuts_proposed.json").read_text())
    cut = cuts[args.cut_index - 1]
    n = cut.get("n", args.cut_index)
    slug = cut["slug"]
    src = RENDERS / args.slug / f"{n:02d}-{slug}.mp4"
    if not src.exists():
        fail(
            f"render não encontrado: {src}",
            hint=f"rode primeiro: ./scripts/07_render_track.py {args.slug} {args.cut_index}",
        )

    if not cut.get("trim_silences"):
        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "cut.trim_silences not set; nothing to do",
                    "path": str(src),
                }
            )
        )
        return

    vad = json.loads((msg_dir / "vad.json").read_text())
    silences = vad.get("silences", [])
    threshold_s = float(cut.get("trim_threshold_s", DEFAULT_THRESHOLD_S))
    keep_silence_s = float(cut.get("trim_keep_silence_s", DEFAULT_KEEP_SILENCE_S))
    cut_start = float(cut["start"])
    cut_end = float(cut["end"])

    intervals = compute_keep_intervals(silences, cut_start, cut_end, threshold_s, keep_silence_s)

    cut_dur = cut_end - cut_start
    trimmed_dur = sum(b - a for a, b in intervals)
    saved_s = round(cut_dur - trimmed_dur, 2)

    if len(intervals) == 1 and saved_s < 0.1:
        # No useful trim found — keep the original.
        print(
            json.dumps(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "no silences exceeded threshold",
                    "path": str(src),
                    "threshold_s": threshold_s,
                }
            )
        )
        return

    out = src.with_name(f"{n:02d}-{slug}.trimmed.mp4")
    filter_complex = build_concat_filter(intervals)

    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(src),
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        *pick_video_encoder(VID, quality=args.quality),
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    if args.in_place:
        out.replace(src)
        out = src

    print(
        json.dumps(
            {
                "ok": True,
                "path": str(out),
                "intervals_kept": len(intervals),
                "duration_before_s": round(cut_dur, 2),
                "duration_after_s": round(trimmed_dur, 2),
                "saved_s": saved_s,
                "threshold_s": threshold_s,
                "keep_silence_s": keep_silence_s,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
