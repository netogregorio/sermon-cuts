#!/usr/bin/env python3
"""Ingest a source video — from YouTube URL or local file path.

The source MP4 lands in a user-visible, Finder-navigable folder:
``<repo>/sources/<slug>/source.mp4``. Pipeline state (meta.json,
transcript, vad, etc.) goes to the hidden ``<skill>/memory/messages/<slug>/``.

Usage:
    01_ingest.py <url-or-path> [--slug SLUG]

If --slug is omitted, derives from YouTube title or filename.

Output:
    <repo>/sources/<slug>/source.mp4
    <skill>/memory/messages/<slug>/meta.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import resolve_messages_dir, resolve_sources_dir

MESSAGES = resolve_messages_dir()
SOURCES = resolve_sources_dir()


def slugify(text: str) -> str:
    """ASCII snake_case slug."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text[:60] or "untitled"


def _slug_dirs(slug: str) -> tuple[Path, Path]:
    """Return (source_dir, state_dir) for a slug. Source dir is user-visible
    under <repo>/sources/<slug>/; state dir is hidden under
    <skill>/memory/messages/<slug>/. Both created if missing."""
    source_dir = SOURCES / slug
    state_dir = MESSAGES / slug
    source_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return source_dir, state_dir


def ingest_youtube(url: str, slug: str | None) -> tuple[Path, dict]:
    # Probe metadata first to derive slug
    probe = subprocess.run(
        ["yt-dlp", "-J", "--no-warnings", url],
        capture_output=True,
        text=True,
        check=True,
    )
    meta = json.loads(probe.stdout)
    title = meta.get("title", "video")
    duration = meta.get("duration", 0)
    slug = slug or slugify(title)
    source_dir, state_dir = _slug_dirs(slug)
    out = source_dir / "source.mp4"
    if out.exists():
        print(f"[skip] {out} already exists", file=sys.stderr)
    else:
        # Download the highest-quality video+audio available.
        #
        # The old format string was:
        #   bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]
        # which was leaking source quality two ways:
        #   (a) [height<=1080] capped at 1080p — threw away the 1440p/2160p
        #       masters that more sermon channels now upload, leaving the
        #       render with a softer starting point than the source offered.
        #   (b) [ext=mp4] forced H.264 and excluded the VP9/AV1 webm streams
        #       YouTube serves at the same resolution. VP9/AV1 1080p
        #       typically encodes 3-4× more efficiently than H.264 1080p
        #       at the bitrates YouTube uses, so the H.264 stream visibly
        #       loses detail in busy frames.
        #
        # The new format prefers ≥1080p in any codec, falling back to the
        # absolute best if no ≥1080p stream exists. ``--merge-output-format
        # mp4`` remuxes the result (lossless container swap) so downstream
        # ffmpeg/cv2 keep working unchanged.
        #
        # Cap the upper bound with the SERMON_CUTS_MAX_HEIGHT env var if you
        # want to throttle disk usage (e.g. =1080 mimics the old default).
        #
        # Route yt-dlp's progress lines to stderr so downstream consumers
        # parsing our stdout (the final JSON receipt) don't choke on
        # download chatter mixed into the output stream.
        max_height = os.environ.get("SERMON_CUTS_MAX_HEIGHT", "").strip()
        if max_height.isdigit():
            fmt = (
                f"bestvideo[height>=1080][height<={max_height}]+bestaudio/"
                f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]"
            )
        else:
            fmt = "bestvideo[height>=1080]+bestaudio/bestvideo+bestaudio/best"
        subprocess.run(
            [
                "yt-dlp",
                "-f",
                fmt,
                "--merge-output-format",
                "mp4",
                "-o",
                str(out),
                url,
            ],
            check=True,
            stdout=sys.stderr,
        )
    meta_out = {
        "source_type": "youtube",
        "url": url,
        "title": title,
        "duration_s": duration,
        "slug": slug,
    }
    (state_dir / "meta.json").write_text(json.dumps(meta_out, indent=2, ensure_ascii=False))
    return out, meta_out


def ingest_local(path: Path, slug: str | None) -> tuple[Path, dict]:
    slug = slug or slugify(path.stem)
    source_dir, state_dir = _slug_dirs(slug)
    out = source_dir / "source.mp4"
    if out.exists():
        print(f"[skip] {out} already exists", file=sys.stderr)
    else:
        # Symlink to save disk (sources can be huge). Copy as fallback.
        try:
            out.symlink_to(path.resolve())
        except OSError:
            shutil.copy2(path, out)
    # Probe duration via ffprobe
    dur = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    duration = float(dur.stdout.strip() or 0)
    meta_out = {
        "source_type": "local",
        "path": str(path),
        "title": path.stem,
        "duration_s": duration,
        "slug": slug,
    }
    (state_dir / "meta.json").write_text(json.dumps(meta_out, indent=2, ensure_ascii=False))
    return out, meta_out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()

    s = args.source
    is_url = s.startswith(("http://", "https://"))
    if is_url:
        out, meta = ingest_youtube(s, args.slug)
    else:
        out, meta = ingest_local(Path(s), args.slug)

    print(
        json.dumps(
            {
                "ok": True,
                "slug": meta["slug"],
                "source_path": str(out),
                "duration_s": meta["duration_s"],
                "source_dir": str(out.parent),
                "state_dir": str(MESSAGES / meta["slug"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
