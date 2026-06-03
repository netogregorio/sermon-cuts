# Pipeline walkthrough

**English** · [Português](PIPELINE.pt.md) · [Español](PIPELINE.es.md)

Each script writes to `memory/messages/<slug>/` and is idempotent (re-running
is safe and skips done work unless `--force`).

## 01_ingest.py

```bash
./scripts/01_ingest.py <youtube-url-or-local-path> [--slug SLUG]
```

YouTube URL → uses yt-dlp with format string `bestvideo[height>=1080]+
bestaudio/bestvideo+bestaudio/best`. Captures 1440p/2160p masters and
VP9/AV1 streams when available (~3-4× more efficient than YouTube's
1080p H.264). Cap the upper bound with `SERMON_CUTS_MAX_HEIGHT=1080`
if disk usage matters.

Local file → symlinks (or copies if symlink fails — common on Windows
without Developer Mode).

After download, ffprobes the source and stores resolution, fps, codec,
and bitrate in `meta.json.source_quality`. Warns when the source is
below the practical floor for clean delivery:

- height < 1080 (any render upscale is lossy)
- bitrate < 2 Mbps (YouTube compression artifacts will show through)
- fps < 24 (motion judder)

Writes:
- `memory/messages/<slug>/source.mp4`
- `memory/messages/<slug>/meta.json` (URL/path/title/duration + source_quality + source_quality_warnings)

Slug derivation: from YouTube title or filename (slugified to snake_case).
Override with `--slug`.

## 02_transcribe.py

```bash
./scripts/02_transcribe.py <slug> [--provider=youtube|groq] [--language=pt]
```

### YouTube (default, free, instant)

Calls `yt-dlp --write-auto-subs --skip-download` to grab the VTT auto-caption
file YouTube generates for every public video. Parses inline word-level
timestamps from the VTT (those `<HH:MM:SS.mmm>` tags between words).

### Groq (paid-ish, higher quality)

Extracts audio (mono 16kHz WAV), uploads to Groq Whisper-large-v3 with
`timestamp_granularities=["word"]`. Returns word-level timestamps.
Needs `GROQ_API_KEY` in env.

Output (same shape for both):

```json
{
  "words": [
    {"text": "Eu", "start": 1.95, "end": 2.12, "type": "word"},
    {"text": " ", "start": 2.12, "end": 2.13, "type": "spacing"},
    ...
  ],
  "language": "pt",
  "_provider": "youtube-vtt"  // or "groq-whisper-large-v3"
}
```

## 03_vad_segments.py

```bash
./scripts/03_vad_segments.py <slug> [--min-silence 0.5]
```

Runs [silero-vad](https://github.com/snakers4/silero-vad) on the source
audio (resampled to 16kHz mono). Detects speech segments → derives the
silences between them → marks the midpoint of each silence ≥ 0.5s as a
**candidate cut point** (places where a cut won't snap mid-word/mid-breath).

Output:

```json
{
  "speech": [{"start": 0.34, "end": 12.18}, ...],
  "silences": [{"start": 12.18, "end": 13.05, "duration": 0.87}, ...],
  "candidate_cut_points": [12.18, 28.71, ...]
}
```

## 04_propose_cuts.py

```bash
./scripts/04_propose_cuts.py <slug>
```

Packages transcript + VAD into a single `propose_input.json` and prints
the paths the LLM (Claude) should read, plus the prompt at
`prompts/propose_cuts.md`. **This script does not call an LLM** — it just
prepares inputs.

The LLM is expected to write proposed cuts to
`memory/messages/<slug>/cuts_proposed.json`.

The expected schema for each cut:

```json
{
  "n": 1,
  "slug": "filha_no_mercado",
  "start": 92.40,
  "end": 165.10,
  "duration_s": 72.7,
  "theme": "Relação vs missão — ilustração da filha no mercado",
  "hook": "Eu gosto de uma ilustração muito boa...",
  "development": "...",
  "conclusion": "Jesus pede que a gente vá COM ele, não pra ficar n'Ele",
  "coherence_score": 9.2,
  "tags": ["ilustracao", "relacionamento_com_deus"],
  "vad_aligned": true
}
```

See `prompts/propose_cuts.md` for the full rubric.

## 05_validate_cut.py

```bash
./scripts/05_validate_cut.py <slug> <cut_index> [--write-back] [--max-extend-s 8]
```

Confirms the cut's last word isn't a forbidden ending (configurable in
`config/render_defaults.yaml` — e.g. "porque", "mas", "que", "para", "com",
"de"). If it is, tries to extend the end to the next VAD candidate cut
point within `max-extend-s` seconds where the word is no longer forbidden.

`--write-back` patches the cut in `cuts_proposed.json`.

## 06_build_srt.py

```bash
./scripts/06_build_srt.py <slug> <cut_index>
```

Generates a brand-styled SRT from the transcript words in the cut's range:

- 3-4 words per cue, max ~20 chars (configurable)
- Splits on punctuation (`. ! ?` hard, `, ; :` soft if cue has ≥3 words)
- Splits on ≥0.5s pause if cue has ≥3 words
- Function-word-aware shift: if a cue ends with "para"/"com"/"que"/etc.,
  shifts it to the next cue (so cues never end on a function word)
- Capitalizes the first cue
- Strips trailing soft punctuation from cue text

Writes `memory/messages/<slug>/srts/NN-slug.srt`.

## 06b_scrub_srt.py

```bash
./scripts/06b_scrub_srt.py <slug> <cut_index> [--agent-review]
                                              [--use-llm]
                                              [--full-llm-review]
                                              [--auto-apply]
                                              [--dry-run]
                                              [--corrections PATH]
```

Lint pass that runs **between `06_build_srt` and `07_render_track`**,
scanning the SRT for the YouTube-auto-caption error patterns we see most
often (dropped sentence boundaries, hesitation duplications, theological
term misspellings). Lets you fix transcription errors before burn-in
instead of after — saves a full re-encode per typo.

### What it looks for

1. **`dropped_word_boundary`** — a function word (em / que / de / etc.)
   immediately before a capitalized non-proper-noun. YouTube ate a word
   at a sentence boundary.
       `"do que Mas não"`  ←  was actually  `"do que nós. Mas não"`
   Whitelists common Bible characters/places and Portuguese pronouns so
   `"em Cristo"` and `"para Ele"` don't false-positive.

2. **`immediate_repetition`** — `\b(\w+)\s+\1\b` filtered to known
   hesitations (a, o, um, uma, que, eu, ele, ela, …) and short words.
   Skips stylistic repetition separated by commas like `"cansa, cansa"`.

3. **`forbidden_ending`** — re-checks the
   `cut_validation.forbid_endings` list per cue (not just at the cut
   boundary like `05_validate_cut.py` does). Reports only; the fix
   usually means shifting the trailing word into the next cue, which
   the human should do.

4. **`dictionary`** — if `memory/messages/<slug>/corrections.txt`
   exists, applies `wrong=right` pairs automatically (one per line,
   `#` for comments). Useful for recurring fixes:
   ```
   Quisto=Cristo
   Espirito=Espírito
   ```

### Three review paths

| Path | When to use |
|---|---|
| **`--agent-review`** (default in non-TTY with suspects) | The orchestrator (Claude Code / Cursor / …) is reading stdout. 06b emits structured JSON with prev/next cue text, a word-level transcript snippet around each suspect, and the path to `prompts/scrub_srt.md`. The agent reads the prompt, decides fixes, applies them via its Edit tool, and resumes the pipeline with `--skip-scrub`. |
| **`--use-llm`** | LLM-assisted review on **rule-flagged cues only** (cron, nightly, no agent attached). Calls Anthropic Claude (prefers `ANTHROPIC_API_KEY`) or Groq Llama (`GROQ_API_KEY` fallback). Cheap but misses errors the heuristics didn't flag. |
| **`--full-llm-review`** | **Whole-SRT** LLM review. Sends every cue + per-cue word-level transcript snippet to the LLM in one call and applies all returned fixes. Catches errors the rule patterns don't match (joined-word typos `paraa`, wrong articles `na seu`, missing letters `pentec`, lowercase proper nouns, filler chains, VTT duplicates). Costs ~$0.01/cut on Claude Haiku 4.5. Forbidden-ending fixes are handled via paired cue edits (strip from one, prepend to next). Same API-key preference order as `--use-llm`. |
| **`--auto-apply`** | Rule-only, confidence ≥ 0.85. Effectively just collapses hesitation repetitions silently. Cheapest mode. |

### Other modes

| Flag | Behavior |
|---|---|
| (none, TTY)     | interactive review — prompts `y/n/edit/skip` per suspect |
| `--dry-run`     | only reports, never writes the SRT |

`pipeline.sh` integrates this step automatically (interactive on TTY,
`--agent-review` JSON in non-TTY so the orchestrating agent can act).
Skip with `--skip-scrub`:

```bash
./scripts/pipeline.sh --render-cuts 1,2 --slug my_msg --skip-scrub
```

Writes back to `memory/messages/<slug>/srts/NN-slug.srt` in place. JSON
report goes to stdout:

```json
{
  "ok": true,
  "srt": "...",
  "suspects": [
    {"cue": 27, "tc": "00:00:36,080", "text": "do que Mas não",
     "pattern": "dropped_word_boundary",
     "suggestion": "do que. Mas não",
     "confidence": 0.75, "applied": false}
  ],
  "applied_count": 0,
  "dry_run": false
}
```

## 07_render_track.py

```bash
./scripts/07_render_track.py <slug> <cut_index> [--no-subs]
                                                [--preset NAME]
                                                [--quality {auto,max}]
                                                [--codec {h264,hevc}]
```

Two-pass render:

**Pass 1 — face position sampling.** At 5 fps (default), runs MediaPipe
BlazeFace short-range detector on each sampled frame. Records the
bounding-box center (X and Y) of the largest detected face. Falls back
in order: MediaPipe Pose Landmarker (shoulder midpoint for X, nose for
Y), then OpenCV Haar cascade, then hold-last-position. Reads the
source's native FPS via `cv2.CAP_PROP_FPS` and uses that for the read
loop — required for A/V sync with non-30fps sources (24, 23.976, 60).

**Smoothing.** Moving average over 2.5s of face (X, Y) positions
removes detection jitter while keeping the camera responsive to real
movement.

**Pass 2 — render frame-by-frame.** For each source frame:
1. Scale to height `OUT_H × (1 + vertical_headroom)` (default 2400)
   preserving aspect, using `cv2.INTER_LANCZOS4` (Lanczos preserves
   high-frequency detail on the upscale).
2. Interpolate smoothed (X, Y) for the current frame timestamp.
3. Crop 1080×1920: X centered on face X (clamped), Y positioned so
   the face center lands at `face_y_target × OUT_H` (default 0.40 ≈
   rule of thirds — cinematic upward bias). Set `face_y_target: null`
   in config to disable Y adjustment and preserve source framing.
4. Pipe raw BGR frames to ffmpeg at the source's native FPS; an
   `fps={OUT_FPS}` filter handles conversion to the output rate.

**Quality / codec selection.** `pick_video_encoder` returns the encoder
argv based on `--quality` and `--codec`:

| Combo | Encoder | Notes |
|---|---|---|
| `auto h264` (default) | h264_videotoolbox @ 8 Mbps on Apple Silicon; libx264 CRF 18 preset slow elsewhere | Fast iteration |
| `auto hevc` | hevc_videotoolbox @ 5 Mbps + hvc1 tag | Smaller files, fast |
| `max h264` | libx264 -preset slower -crf 17, yuv420p | Delivery-grade software encode |
| `max hevc` | libx265 -preset slower -crf 20, **yuv420p10le** (Main 10) + hvc1 tag | Smallest + cleanest delivery |

`--quality max` also inserts an `hqdn3d=1.5:1.5:6:6, unsharp=...` filter
chain before subtitle burn — kills high-ISO church-camera chroma noise
and recovers some of the crispness lost in the upscale.

**Audio mux.** Combines encoded video with the source audio segment
(seeked via `-ss`/`-to`).

**Subtitle burn.** Applies ffmpeg `subtitles=` filter with `force_style`
from `config/style_presets/<preset>.txt`. Skip with `--no-subs`.

Writes `memory/messages/<slug>/renders/NN-slug.mp4`.

## 08_audio_normalize.py

```bash
./scripts/08_audio_normalize.py <slug> <cut_index> [--target-lufs -14] [--in-place]
```

Measures integrated loudness with pyloudnorm (ITU-R BS.1770-4), applies
gain to hit target LUFS. Re-encodes audio to AAC 192k, copies video stream.

`--in-place` overwrites the original render. Otherwise writes a
`.normalized.mp4` sibling.

## pipeline.py / pipeline.sh / pipeline.bat

Cross-platform orchestrator. Same flags everywhere — `pipeline.sh` is a
Unix wrapper that exec's into `pipeline.py`; `pipeline.bat` does the
same for Windows. Pick the one that matches your shell muscle memory,
or invoke `python pipeline.py` directly.

```bash
# Ingest + transcribe + VAD + prepare propose-input
./scripts/pipeline.sh "https://youtube.com/watch?v=XXX"

# Render specific cut indices end-to-end (validate + SRT + render + normalize)
./scripts/pipeline.sh --render-cuts 1,2,4,7 --slug my_sermon

# Just re-burn subtitles (after correcting transcription) without re-tracking
./scripts/pipeline.sh --reburn-srt 3 --slug my_sermon
```

### Render flags

| Flag | What it does |
|---|---|
| `--target {all,shorts,reels,tiktok}` | Delivery target. `shorts` re-caps cuts at 60s (YouTube Shorts hard limit). Default `all` uses the 60–90s window. |
| `--quality {auto,max}` | `auto` (default) picks the hardware encoder on Apple Silicon for speed. `max` forces libx264/libx265 `-preset slower` plus an `hqdn3d + unsharp` filter chain for delivery-grade output. |
| `--codec {h264,hevc}` | Video codec. Default `h264` is broadest compatibility. `hevc` (H.265) is ~40% smaller at the same visible quality, accepted by Reels/TikTok/Shorts since 2022. `--quality max --codec hevc` ships in 10-bit Main 10. |
| `--llm-scrub` | Routes the SRT scrub through `06b_scrub_srt --full-llm-review` — sends every cue + per-cue word-level transcript snippet to the LLM and applies all fixes (not just rule-flagged ones). Needs `ANTHROPIC_API_KEY` or `GROQ_API_KEY`. ~$0.01 per cut. |
| `--skip-scrub` | Skip the SRT scrub pass entirely (CI / batch). |

```bash
# Delivery-grade master for a paying client
./scripts/pipeline.sh --render-cut 3 --slug my_sermon \
                      --quality max --codec hevc --llm-scrub

# YouTube Shorts–safe cut (forces ≤60s)
./scripts/pipeline.sh --render-cuts 1,2 --slug my_sermon --target shorts
```

## Per-message directory layout

The pipeline splits each message across **two visible folders** under the
repo and **one hidden state folder** under the skill install:

```
<repo>/sources/<slug>/                    # visible — drop or download here
└── source.mp4                            # YouTube download OR symlink to local

<repo>/renders/<slug>/                    # visible — final cuts land here
├── 01-tema_do_corte.mp4
├── 02-outro_beat.mp4
└── …                                     # ready to upload to Reels/TikTok

~/.claude/skills/sermon-cuts/memory/messages/<slug>/   # hidden state
├── meta.json                             # URL/title/duration
├── transcript.json                       # word-level transcription
├── vad.json                              # speech segments + cut candidates
├── propose_input.json                    # combined input for the LLM
├── cuts_proposed.json                    # LLM output, you curate this
├── srts/NN-slug.srt                      # subtitle files
└── corrections.txt                       # optional per-message scrub dict
```

The split is deliberate: anything a human navigates to (the source mp4
you ingested, the rendered cuts ready to publish) sits in plain sight at
the top of the repo. Anything the pipeline reads/writes between runs
(transcripts, intermediates) stays in the hidden `memory/messages/`
state folder so the visible dirs don't get cluttered.

### Overriding paths

Three env vars override the defaults:

- `SERMON_CUTS_SOURCES_DIR` — where source .mp4 files live
- `SERMON_CUTS_RENDERS_DIR` — where final cuts land
- `SERMON_CUTS_MESSAGES_DIR` — where per-message state lives

Useful when keeping renders on an external drive or in a synced
Dropbox/iCloud folder.

### Migrating from an older layout

Pre-2026-05 installs kept `source.mp4` and `renders/` inside
`memory/messages/<slug>/`. `pipeline.sh doctor` flags this on startup;
run the migration once to move them to the new visible paths:

```bash
./scripts/pipeline.sh migrate --dry-run    # preview
./scripts/pipeline.sh migrate              # actually move
```

Idempotent and conservative — won't clobber existing files at the
destination.
