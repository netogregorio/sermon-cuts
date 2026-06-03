# Changelog

**English** · [Português](CHANGELOG.pt.md) · [Español](CHANGELOG.es.md)

## 0.2.0 — Cross-platform + delivery-grade quality (2026-06-03)

### Cross-platform

- **Windows support, native.** New `pipeline.py` (cross-platform Python
  orchestrator) replaces the bash-only `pipeline.sh` logic. `pipeline.sh`
  and `pipeline.bat` are now thin wrappers that exec into it — existing
  Unix muscle memory keeps working, Windows users get the same CLI.
- **`install.py`** ports the bash installer to cross-platform Python:
  venv, skill linking (symlink → junction `mklink /J` → copy fallback),
  `~/.env` GROQ key, font preset selection, MediaPipe model pre-download,
  doctor check. `install.sh` and `install.bat` wrap it for the
  platform-specific bootstrap (system deps + repo clone).
- **`resolve_ffmpeg` cross-platform**: `shutil.which("ffmpeg")` for PATH
  lookup plus Windows fallback paths (`C:\ffmpeg\bin\`, Program Files).

### Cut rules (aligned with creator brief)

- **Duration window 60–90s** by default. Old 25–60s cap was based on
  early-2020s short-form retention; Reels (90s native) and TikTok (no
  relevant cap) accept the wider range. YouTube Shorts still hard-caps
  at 60s — use `--target shorts` to re-cap.
- **Mid-sentence start detection**: `05_validate_cut` now warns when a
  cut begins on a function word (`mas`, `porque`, `então`, `quando`,
  `se`, ...) or when the prior word doesn't end on `.!?`. Warn-only —
  start is never auto-moved (curator intent is sacred).
- **forbid_endings extended** with `então`, `quando`, `se` — all three
  open incomplete clauses.
- **Scrub prompts** (en/pt/es) hardened with an inviolable rule against
  altering theological meaning during transcription cleanup.

### Image quality

- **Source ceiling fix** ([01_ingest.py]): yt-dlp format string now
  prefers ≥1080p in any codec (was: ≤1080p mp4 only). Captures 1440p/
  2160p masters and VP9/AV1 streams (~3-4× more efficient than YouTube
  1080p H.264). Cap with `SERMON_CUTS_MAX_HEIGHT`.
- **Source probe + warn** at ingest. ffprobe stashed in `meta.json
  .source_quality`; warns when source is <1080p, <2 Mbps, or <24 fps.
- **Lanczos upscale**: `cv2.INTER_LANCZOS4` for the scale-to-1920
  (replaces `INTER_AREA`, which was the wrong choice on upscale).
- **`--codec hevc`** flag adds H.265 paths via `hevc_videotoolbox`
  (auto) or `libx265` (max). ~40% smaller files at same visible
  quality. `--quality max --codec hevc` ships 10-bit Main 10
  (`yuv420p10le`) with `hvc1` tag for Apple ecosystem compatibility.
- **Tracking sample_fps 2 → 5** for tighter face follow on energetic
  preachers (~2-3s extra per cut on Apple Silicon).
- **Rule-of-thirds vertical framing**: face center positioned at 40% of
  output height (configurable via `tracking.face_y_target`). Source is
  scaled to `OUT_H × 1.25` to give the crop window Y headroom.
- **`--quality max` filter chain**: `hqdn3d=1.5:1.5:6:6, unsharp=5:5:0.6`
  before subtitle burn. Kills high-ISO chroma noise; recovers crispness
  lost in the upscale. Skipped in `auto` mode (fast iteration).

### Sync + transcription

- **A/V desync fix** ([07_render_track.py]): renderer now reads at the
  source's native fps and uses an `fps={OUT_FPS}` filter for output rate
  conversion. Old loop assumed 30fps source and over-read ~25% of
  content on 23.976fps sources, racing video ahead of audio. Verified
  in delta: 6.6ms vs ~16s pre-fix.
- **YouTube provider robustness** ([02_transcribe.py]): the `--provider=
  youtube` path was hoarding valid captions when yt-dlp returned 429 on
  a sibling sub-language. Rewrote to walk language variants
  (`pt-orig` → `pt-BR` → `pt` → `pt-PT`) one at a time, stopping at the
  first that lands a VTT. yt-dlp's exit code is now advisory — if a
  parseable VTT is on disk, we use it.
- **Auto-provider preference flipped**: YouTube URL sources now default
  to `--provider=youtube` even when `GROQ_API_KEY` is set. The captions
  are free, instant, and the new `--full-llm-review` catches transcription
  errors better than the old Groq round-trip ever did.

### Scrub

- **`--full-llm-review`** ([06b_scrub_srt.py]): whole-SRT LLM cleanup.
  Sends every cue + per-cue word-level transcript snippet to the LLM in
  one call and applies all returned fixes. Catches errors the heuristic
  rules can't pattern-match: joined-word typos (`paraa festa`), wrong
  articles (`na seu próprio idioma`), missing letters (`pentec`),
  lowercase proper nouns, filler chains (`é a é a tipo assim`), VTT
  duplicates (`muito muito`). Cost on Claude Haiku 4.5: ~$0.01 per
  cut. Forbidden-ending fixes via paired cue edits.
- **`pipeline.sh --llm-scrub`** wires the new scrub into the orchestrator.

## 0.1.0 — Initial release (2026-05-23)

First public release. End-to-end pipeline:

- `01_ingest.py` — yt-dlp or local file → managed source
- `02_transcribe.py` — YouTube VTT (default) or Groq Whisper, word-level
- `03_vad_segments.py` — silero-vad pause detection → cut candidates
- `04_propose_cuts.py` — prepares LLM input for cut proposal
- `05_validate_cut.py` — auto-extends cuts that end mid-thought
- `06_build_srt.py` — brand-style subtitles (3-4 words, function-word shift)
- `07_render_track.py` — MediaPipe face tracking + smooth pan + burn subs
- `08_audio_normalize.py` — pyloudnorm to -14 LUFS
- `pipeline.sh` — orchestrator

Default brand style: Outfit Black, gold `#fbc531`, black `0.8` outline,
sentence case, footer position. Vertical 1080×1920 @ 30fps.

Includes a `SKILL.md` for Claude Code integration.

Tested with two PT-BR sermons (~28min each):
- *Vinde a mim* (Mateus 11) — 12 cut candidates proposed, 8 rendered.
- *Derrubando as fortalezas da mente* — 10 cuts rendered.

Sample case studies in `examples/`.
