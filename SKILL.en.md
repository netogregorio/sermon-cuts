---
name: sermon-cuts
description: "End-to-end pipeline for cutting vertical short-form clips from long sermon/preaching videos. Triggered when the user wants to cut a sermon, preaching, pregação, mensagem, or sermon-style talking-head video into multiple short verticals (Reels/Shorts/TikTok). Handles: download (YouTube or local), Groq Whisper transcription, VAD-aware natural cut boundaries, LLM-proposed cuts with narrative-arc scoring, MediaPipe face-tracking smooth pan, brand-style burned subtitles (gold Outfit Black + black outline + footer), LUFS audio normalization. User curates which proposed cuts to render; the rest is automatic."
---

# sermon-cuts — pipeline for sermon cuts

[**English**](SKILL.en.md) · [Português](SKILL.md) · [Español](SKILL.es.md)

## When to invoke

You invoke this skill when the user asks things like:
- "let's cut this sermon https://..."
- "cut this message into N 1-minute cuts"
- "make cuts from the sermon"
- "transcribe and cut this preaching for Reels/Shorts"
- "find the best beats of this message"

Accepts as input a **YouTube URL** OR a local `.mp4`/`.mov` path.

## Final output

In `<project>/edit/cuts/<message_slug>/`:
```
01-cut_theme.mp4
02-another_beat.mp4
...
```

Each cut is:
- **Vertical 1080×1920 @ 30fps** (Lanczos scale + crop with 5fps face tracking + rule of thirds vertical `face_y_target=0.40`)
- **Burned-in subtitle** brand-style (Outfit Black, gold `#fbc531`, black outline 0.8, footer MarginV=50, 3-4 words/line, sentence case)
- **Normalized audio** to -14 LUFS (Insta/TikTok/Reels standard)
- **Configurable encoder**:
  - default `--quality auto --codec h264` → h264_videotoolbox 8M (Apple Silicon) / libx264 CRF 18 (everything else)
  - delivery `--quality max --codec hevc` → libx265 -preset slower -crf 20 + 10-bit Main 10 (yuv420p10le) + hqdn3d + unsharp + hvc1 tag

## Workflow (one-at-a-time mode — Neto prefers this)

### Phase A — Ingest + analysis (automatic, ~1 min)

1. **`scripts/01_ingest.py <url-or-path>`** — downloads via yt-dlp (≥1080p, any codec; accepts VP9/AV1 + 1440p/2160p) OR copies local to `<sources>/<slug>/source.mp4`. ffprobe logs `source_quality` in `meta.json` + warns if <1080p / <2Mbps / <24fps.
2. **`scripts/02_transcribe.py`** — auto-pick: YouTube source → VTT auto-captions (free); local file → Groq Whisper-large if `GROQ_API_KEY` is set, otherwise faster-whisper local. Output: `transcript.json` word-level.
3. **`scripts/03_vad_segments.py`** — silero-vad detects pauses ≥0.8s → `vad.json` (candidate boundaries)

### Phase B — Cut proposal (LLM, ~30s)

4. **You (Claude) read** `transcript.json` + `vad.json` and propose cuts following `prompts/propose_cuts.md`. Output: `cuts_proposed.json` with `[{n, slug, start, end, theme, hook, conclusion, coherence_score, depends_on}]`
5. **Present to the user** as a list ranked by score. They pick which to approve.

### Phase C — Render per approved cut (~30-60s default, ~45min --quality max --codec hevc)

For each approved cut:
6. **`scripts/05_validate_cut.py --target {all,shorts,reels,tiktok}`** — confirms natural ending + start. `forbid_endings` (mas/porque/então/quando/se/...) + `forbid_starts` (warn-only). Adjusts `end` extending to next VAD pause if truncated.
7. **`scripts/06_build_srt.py`** — generates brand-style SRT from the segment
8. **`scripts/06b_scrub_srt.py`** — heuristic scrub OR `--full-llm-review` (sends entire SRT + word-level transcript to the LLM, applies ALL fixes — catches `paraa→para a`, `pentec→Pentecostes`, `na seu→no seu`, etc). Cost ~$0.01/cut.
9. **`scripts/07_render_track.py --quality {auto,max} --codec {h264,hevc}`** — MediaPipe face+pose detection 5fps + smoothing 2.5s + Lanczos scale + rule-of-thirds Y + 1080×1920 crop + burn subtitle + encode (videotoolbox auto / libx265 max). A/V sync via src_fps + ffmpeg fps filter.
10. **`scripts/08_audio_normalize.py`** — ffmpeg loudnorm two-pass -14 LUFS + true-peak -1.5 dBTP
11. **`scripts/09_trim_silences.py`** (opt-in via `trim_silences: true` on the cut) — collapses silences >2.5s
12. **Saves** to `<renders>/<slug>/NN-cut_slug.mp4` and shows preview to Neto

### Phase D — Iteration

If he rejects/asks for change in a cut:
- Subtitle text correction → edit `srt`, reburn (no re-tracking)
- Trim start/end → re-run from step 7
- Whole cut wrong → mark rejected in `cuts_proposed.json`, propose replacement

## File structure

```
~/.claude/skills/sermon-cuts/           # macOS/Linux symlink; Windows junction
├── SKILL.md                 ← this file
├── scripts/
│   ├── 01_ingest.py
│   ├── 02_transcribe.py
│   ├── 03_vad_segments.py
│   ├── 04_propose_cuts.py   ← stub that calls Claude with prompt
│   ├── 05_validate_cut.py
│   ├── 06_build_srt.py
│   ├── 06b_scrub_srt.py     ← lint + (optional) full-llm-review
│   ├── 07_render_track.py
│   ├── 08_audio_normalize.py
│   ├── 09_trim_silences.py
│   ├── pipeline.py          ← cross-platform orchestrator
│   ├── pipeline.sh          ← Unix wrapper (exec → pipeline.py)
│   └── pipeline.bat         ← Windows wrapper
├── config/
│   ├── render_defaults.yaml
│   ├── style_presets/
│   └── corrections_pt.txt
├── prompts/
│   ├── propose_cuts.{md,pt.md,es.md}
│   └── scrub_srt.{md,pt.md,es.md}
└── memory/
    └── messages/
        └── <message_slug>/
            ├── transcript.json
            ├── vad.json
            ├── meta.json    ← includes source_quality + warnings
            ├── cuts_proposed.json
            └── srts/NN-slug.srt
```

## Hard rules (don't negotiate with user)

1. **Vertical 1080×1920**. Horizontal source → Lanczos scale + dynamic crop (X via face/pose, Y via rule of thirds `face_y_target=0.40`). **Never** letterbox, **never** scale+pad with blur background.
2. **Subtitle sentence case**, never UPPERCASE.
3. **Black outline 0.8**, FontSize 16, MarginV 50. Don't invent.
4. **Cut must have complete arc**: hook → development → conclusion. If LLM can't identify a clear conclusion, reject the cut.
5. **Duration 60–90s** default (sweet spot for Reels/TikTok). `--target shorts` re-caps at 60s (YouTube Shorts hard cap).
6. **Theological scrub**: during SRT cleanup (heuristic OR LLM), NEVER alter theological meaning or speaker intent. Only fix obvious transcription errors.

## Decisions that should be deferred to the user (don't automate)

- Which cuts to approve (final curation)
- Transcription correction when Whisper misses a technical/theological word
- Override of cut theme/slug

## Typical invocation commands

Use `pipeline.sh` (macOS/Linux), `pipeline.bat` (Windows), or `python pipeline.py` (any OS) — same flag surface.

```bash
# Full pipeline, interactive mode (default)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh "https://youtube.com/watch?v=ZKeORvbgWpA"

# Just ingest + transcribe + propose (no render)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --propose-only /path/local.mp4

# Render specific cuts already proposed
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 2,4,7 --slug vinde_a_mim

# Delivery-grade for client: max quality + HEVC + full LLM scrub
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cut 3 --slug vinde_a_mim \
  --quality max --codec hevc --llm-scrub

# YouTube Shorts (re-cap at 60s)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 1,2 --slug vinde_a_mim --target shorts

# Re-apply only subtitle (no retracking) on an already done cut
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --reburn-srt 2 --slug vinde_a_mim
```

## Brand style

Palette, typography, subtitle rules, format default, and file organization live in **[docs/STYLE.en.md](docs/STYLE.en.md)** — read it before proposing any visual change. TL;DR: gold `#fbc531` + black outline, Outfit Black, vertical 1080×1920, sentence case.

Purely local overrides (custom font path, alternate palette for a different brand) belong in the consuming project's `CLAUDE.md`, not here.

---

By [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
