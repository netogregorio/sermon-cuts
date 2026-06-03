#!/usr/bin/env python3
"""Transcribe source video with word-level timestamps.

Two providers:
  --provider=youtube  (default): yt-dlp downloads auto-captions, parse VTT
                       inline word timestamps. Free, instant, sometimes makes
                       small word-level mistakes you'll want to correct manually.
  --provider=groq:     Extract audio, send to Groq Whisper-large-v3. Slower
                       (~30s per 10min audio) but much higher accuracy. Needs
                       GROQ_API_KEY in env.

For the youtube provider, the source must have been ingested with a stored
`meta.json` containing the URL.

Usage:
    02_transcribe.py <slug> [--provider=youtube|groq] [--language=pt] [--force]

Reads:  memory/messages/<slug>/source.mp4
        memory/messages/<slug>/meta.json
Writes: memory/messages/<slug>/transcript.json

Output schema (same shape for both providers):
{
  "words": [{"text": "Eu", "start": 1.95, "end": 2.12, "type": "word"},
            {"text": " ", "start": 2.12, "end": 2.13, "type": "spacing"}, ...],
  "language": "pt",
  "_provider": "youtube-vtt" | "groq-whisper-large-v3"
}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    SCHEMA_VERSION,
    config_dir,
    fail,
    resolve_ffmpeg,
    resolve_messages_dir,
    resolve_sources_dir,
)

SOURCES = resolve_sources_dir()
MESSAGES = resolve_messages_dir()
CFG = yaml.safe_load((config_dir() / "render_defaults.yaml").read_text())
FFMPEG = resolve_ffmpeg(CFG.get("ffmpeg_bin"))


def load_env() -> None:
    if os.environ.get("GROQ_API_KEY"):
        return
    for env_path in (Path.home() / ".env", Path.cwd() / ".env", Path.cwd() / "edit/.env"):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ─── YouTube VTT provider ──────────────────────────────────────────────────

TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
CUE_HEADER_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})")
INLINE_TS_RE = re.compile(r"<(\d{2}:\d{2}:\d{2}\.\d{3})>")
TAG_RE = re.compile(r"<[^>]+>")


def _ts_to_seconds(s: str) -> float:
    m = TS_RE.match(s)
    if not m:
        return 0.0
    h, mn, sc, ms = m.groups()
    return int(h) * 3600 + int(mn) * 60 + int(sc) + int(ms) / 1000.0


def _parse_vtt_cue(cue_start: float, cue_end: float, text: str) -> list[dict]:
    text = text.replace("\n", " ").strip()
    if not text:
        return []
    chunks: list[tuple[float, str]] = []
    last_pos = 0
    last_ts = cue_start
    for m in INLINE_TS_RE.finditer(text):
        chunks.append((last_ts, text[last_pos : m.start()]))
        last_ts = _ts_to_seconds(m.group(1))
        last_pos = m.end()
    chunks.append((last_ts, text[last_pos:]))
    out: list[dict] = []
    for i, (start, raw) in enumerate(chunks):
        clean = TAG_RE.sub("", raw).strip()
        if not clean:
            continue
        end = chunks[i + 1][0] if i + 1 < len(chunks) else cue_end
        words = clean.split()
        if len(words) == 1:
            out.append({"start": start, "end": end, "text": words[0]})
        else:
            dur = max(0.01, end - start) / len(words)
            for j, w in enumerate(words):
                out.append(
                    {
                        "start": start + j * dur,
                        "end": start + (j + 1) * dur,
                        "text": w,
                    }
                )
    return out


def _parse_vtt_file(vtt_path: Path) -> list[dict]:
    text = vtt_path.read_text()
    blocks = re.split(r"\n\n+", text)
    all_words: list[dict] = []
    for block in blocks:
        raw_lines = block.splitlines()
        timing_idx = None
        for i, line in enumerate(raw_lines):
            if CUE_HEADER_RE.match(line):
                timing_idx = i
                break
        if timing_idx is None:
            continue
        m = CUE_HEADER_RE.match(raw_lines[timing_idx])
        if not m:
            continue
        start = _ts_to_seconds(m.group(1))
        end = _ts_to_seconds(m.group(2))
        body_lines = [ln for ln in raw_lines[timing_idx + 1 :] if INLINE_TS_RE.search(ln)]
        if not body_lines:
            continue
        body = "\n".join(body_lines)
        all_words.extend(_parse_vtt_cue(start, end, body))
    all_words.sort(key=lambda w: w["start"])
    seen: set[tuple[str, int]] = set()
    deduped: list[dict] = []
    for w in all_words:
        key = (w["text"].lower(), int(round(w["start"] * 20)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(w)
    return deduped


def transcribe_youtube(url: str, language: str, work_dir: Path) -> dict:
    """Pull YouTube's own captions (creator-uploaded or auto-generated).

    Previous implementation hit two bugs on the wild:

      1. Asked yt-dlp for ``f"{language}.*,{language}"`` (e.g. ``pt.*,pt``),
         which globbed pt-orig + pt + pt-PT + pt-BR. yt-dlp dutifully
         downloaded each, and on the third request YouTube returned
         HTTP 429 (rate limit). yt-dlp exited non-zero — fatal for the
         caller — *after* two perfectly valid VTT files had already
         landed on disk.

      2. ``check=True`` made any non-zero exit catastrophic. So the
         valid VTTs were thrown away on a transient rate-limit error.

    The new strategy walks a small list of language variants, one at a
    time, and stops at the first one that lands a VTT. yt-dlp's exit
    code is treated as advisory — if a VTT was written, we use it; if
    it wasn't, we move on to the next variant. Net result: we make
    exactly enough calls to find one working transcript.
    """
    out_template = str(work_dir / "subs.%(ext)s")

    # Variants to try, in preference order. ``-orig`` is YouTube's tag for
    # the original-language track (creator-uploaded OR auto-generated in
    # the speaker's language). PT-BR comes before PT-PT because Brazilian
    # Portuguese is the dominant variant in sermons going through this
    # pipeline; if neither's tagged, the unlocalized ``language`` itself
    # catches whatever YouTube has.
    variants = [
        f"{language}-orig",
        f"{language}-BR",
        language,
        f"{language}-PT",
    ]

    errors: list[str] = []
    for variant in variants:
        # Drop any leftover VTTs from a prior variant attempt so glob() can
        # uniquely identify what *this* call produced.
        for stale in work_dir.glob("*.vtt"):
            stale.unlink()

        proc = subprocess.run(
            [
                "yt-dlp",
                "--write-auto-subs",
                "--sub-langs",
                variant,
                "--sub-format",
                "vtt",
                "--skip-download",
                "--no-warnings",
                "-o",
                out_template,
                url,
            ],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        )

        vtts = sorted(work_dir.glob("*.vtt"))
        if vtts:
            # File on disk wins over exit code: a non-zero return from
            # yt-dlp at this point means a *later* sibling download failed
            # (rate-limit, network blip), not the one we asked for here.
            vtt = vtts[0]
            print(
                f"  pulled YouTube caption variant '{variant}' "
                f"({vtt.stat().st_size // 1024} KB)",
                file=sys.stderr,
            )
            raw_words = _parse_vtt_file(vtt)
            if not raw_words:
                # VTT existed but had no parseable cues — keep trying.
                errors.append(f"{variant}: VTT had no parseable cues")
                continue
            return {
                "words": _to_scribe_shape(raw_words),
                "language": language,
                "_provider": "youtube-vtt",
                "_caption_variant": variant,
            }

        # No VTT written. Capture yt-dlp's stderr tail so the eventual
        # error message tells the user *why* nothing came through.
        stderr_tail = (proc.stderr.decode("utf-8", "replace") if proc.stderr else "")[-300:]
        errors.append(f"{variant}: exit={proc.returncode} {stderr_tail.strip()[-200:]}")

    # All variants failed — surface the collected errors so the user can
    # see whether it's a missing-captions issue or a yt-dlp / network one.
    raise RuntimeError(
        "no YouTube captions could be pulled for this video.\n"
        + "tried variants in order:\n"
        + "\n".join(f"  - {e}" for e in errors)
        + "\n\nIf the video genuinely has no captions, re-run with "
        "--provider=local (faster-whisper, offline) or --provider=groq "
        "(needs GROQ_API_KEY)."
    )


# ─── Groq provider ─────────────────────────────────────────────────────────


def _extract_audio(src: Path, out: Path) -> None:
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        check=True,
        stderr=subprocess.DEVNULL,
    )


def transcribe_groq(src: Path, language: str) -> dict:
    load_env()
    if not os.environ.get("GROQ_API_KEY"):
        fail(
            "GROQ_API_KEY não configurada",
            hint="adicione `GROQ_API_KEY=gsk_...` no ~/.env ou exporte no shell. "
            "Alternativa: use --provider=youtube (legendas auto, grátis).",
            url="https://console.groq.com/keys",
        )
    from groq import Groq

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = Path(tmp.name)
    try:
        print("  extracting mono16k audio...", file=sys.stderr)
        _extract_audio(src, wav)
        size_mb = wav.stat().st_size / 1e6
        print(f"  sending to Groq Whisper-large-v3 ({size_mb:.1f} MB)...", file=sys.stderr)
        client = Groq()
        with open(wav, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=(wav.name, f.read()),
                model="whisper-large-v3",
                language=language,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
    finally:
        wav.unlink(missing_ok=True)
    raw = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    raw_words = [
        {
            "start": float(w.get("start") or 0),
            "end": float(w.get("end") or w.get("start") or 0),
            "text": (w.get("word") or w.get("text") or "").strip(),
        }
        for w in raw.get("words", [])
        if (w.get("word") or w.get("text"))
    ]
    return {
        "words": _to_scribe_shape(raw_words),
        "language": raw.get("language", language),
        "_provider": "groq-whisper-large-v3",
    }


# ─── faster-whisper (local) provider ───────────────────────────────────────


def transcribe_local(src: Path, language: str, model_size: str) -> dict:
    """Transcribe via faster-whisper running locally — no API key required.

    Model files are cached in ``~/.cache/sermon-cuts/whisper/<size>``. First
    run downloads ~1.5 GB for large-v3 and ~500 MB for medium; subsequent
    runs reuse the cache.

    On Apple Silicon faster-whisper uses CTranslate2 with Metal acceleration
    when available — large-v3 runs at about 1× realtime, medium at ~3×.
    On Linux/CUDA it goes faster still; on a CPU-only Linux box, drop
    ``--model-size medium`` (or smaller) to keep latency reasonable.

    Output shape is identical to the Groq path, so downstream scripts
    don't care which provider was used.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fail(
            "faster-whisper não está instalado",
            hint="rode `pip install faster-whisper` no venv da skill. "
            "Alternativa: use --provider=youtube (grátis) ou --provider=groq (chave API).",
            url="https://github.com/SYSTRAN/faster-whisper",
        )

    cache_dir = Path.home() / ".cache/sermon-cuts/whisper"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Compute type pick: float16 on Apple Silicon / CUDA-capable; otherwise int8
    # which is the most portable and still respectable quality. faster-whisper
    # falls back automatically when the requested type isn't supported.
    import platform

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        compute_type = "int8_float32"
        device = "auto"
    else:
        compute_type = "int8"
        device = "auto"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = Path(tmp.name)
    try:
        print(
            f"  extracting mono16k audio + loading model={model_size} ({compute_type})...",
            file=sys.stderr,
        )
        _extract_audio(src, wav)
        model = WhisperModel(
            model_size, device=device, compute_type=compute_type, download_root=str(cache_dir)
        )
        print("  transcribing locally (this can take a few minutes)...", file=sys.stderr)
        segments, info = model.transcribe(
            str(wav), language=language, word_timestamps=True, vad_filter=False
        )
        raw_words: list[dict] = []
        for seg in segments:
            if not seg.words:
                continue
            for w in seg.words:
                text = (w.word or "").strip()
                if not text:
                    continue
                raw_words.append({"start": float(w.start), "end": float(w.end), "text": text})
    finally:
        wav.unlink(missing_ok=True)

    return {
        "words": _to_scribe_shape(raw_words),
        "language": info.language or language,
        "_provider": f"faster-whisper-{model_size}",
    }


# ─── shared post-processing ────────────────────────────────────────────────


def _to_scribe_shape(raw_words: list[dict]) -> list[dict]:
    out: list[dict] = []
    prev_end = None
    for w in raw_words:
        s = float(w["start"])
        e = float(w["end"])
        text = (w["text"] or "").strip()
        if not text:
            continue
        if prev_end is not None and s > prev_end + 0.001:
            out.append({"text": " ", "start": prev_end, "end": s, "type": "spacing"})
        out.append({"text": text, "start": s, "end": e, "type": "word"})
        prev_end = e
    return out


# ─── main ──────────────────────────────────────────────────────────────────


def _auto_pick_provider(meta: dict) -> str:
    """Provider selection when --provider isn't passed.

    Updated priority (Jun 2026): when the source is a YouTube URL, prefer
    ``youtube`` over ``groq``. YT's own auto-captions are free, instant,
    and accurate enough for sermon cuts (the scrub step catches the
    dropped-word errors). Sending the audio back through Groq Whisper is
    wasted spend and round-trip latency when YouTube already has a
    transcript right there. Groq stays the preferred provider for local
    files where there's no YT track to pull from.

    Order:
      1. ``youtube`` — source is a YouTube URL. Free, fast, good enough.
                       Even short YT videos prefer this path now.
      2. ``groq``    — GROQ_API_KEY is set AND source isn't YouTube (or
                       --provider=groq was passed explicitly). Best
                       accuracy on local recordings.
      3. ``local``   — faster-whisper imports successfully. Offline,
                       premium quality, but slow for long inputs on CPU.
      4. error       — no providers available.

    Override with --provider= at any time to bypass this heuristic.
    """
    load_env()  # populate from ~/.env so the GROQ key check is honest

    is_youtube = meta.get("source_type") == "youtube" and meta.get("url")
    if is_youtube:
        # YouTube source → always start with its own captions. If they're
        # missing or broken, transcribe_youtube raises with a clear error
        # message telling the user to rerun with --provider=local or
        # --provider=groq, so the fallback path stays explicit.
        return "youtube"

    if os.environ.get("GROQ_API_KEY"):
        return "groq"

    try:
        import faster_whisper  # noqa: F401

        return "local"
    except ImportError:
        pass

    fail(
        "nenhum provider de transcrição disponível",
        hint="opções: (a) `pip install faster-whisper` no venv pra rodar local, "
        "(b) `GROQ_API_KEY=gsk_...` no ~/.env, ou "
        "(c) ingerir o source como URL do YouTube pra usar auto-captions.",
        url="https://console.groq.com/keys",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument(
        "--provider",
        choices=["youtube", "groq", "local", "auto"],
        default="auto",
        help="auto → groq if key set, else local if faster-whisper installed, else youtube",
    )
    ap.add_argument("--language", default="pt")
    ap.add_argument(
        "--model-size",
        default="large-v3",
        help="faster-whisper model name when --provider=local (e.g. medium, large-v3)",
    )
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    msg_dir = MESSAGES / args.slug
    src = SOURCES / args.slug / "source.mp4"
    out = msg_dir / "transcript.json"
    if not src.exists():
        fail(
            f"source não encontrado: {src}",
            hint=f"rode primeiro: ./scripts/pipeline.sh <url-ou-mp4>  (ou: 01_ingest.py <src> --slug {args.slug})",
        )
    if out.exists() and not args.force:
        print(json.dumps({"ok": True, "skipped": True, "path": str(out)}, indent=2))
        return

    meta = json.loads((msg_dir / "meta.json").read_text())

    provider = args.provider
    if provider == "auto":
        provider = _auto_pick_provider(meta)
        print(f"  [auto] picked provider={provider}", file=sys.stderr)

    if provider == "youtube":
        if meta.get("source_type") != "youtube" or not meta.get("url"):
            fail(
                "--provider=youtube precisa de um source vindo do YouTube",
                hint="esse slug foi ingerido de arquivo local. Use --provider=groq "
                "(requer GROQ_API_KEY) ou --provider=local (offline com faster-whisper).",
            )
        with tempfile.TemporaryDirectory() as td:
            payload = transcribe_youtube(meta["url"], args.language, Path(td))
    elif provider == "local":
        payload = transcribe_local(src, args.language, args.model_size)
    else:  # groq
        payload = transcribe_groq(src, args.language)

    payload["_schema_version"] = SCHEMA_VERSION
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    n_words = sum(1 for w in payload["words"] if w.get("type") == "word")
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(out),
                "n_words": n_words,
                "language": payload["language"],
                "provider": payload["_provider"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
