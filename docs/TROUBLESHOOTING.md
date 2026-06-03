# Troubleshooting

**English** · [Português](TROUBLESHOOTING.pt.md) · [Español](TROUBLESHOOTING.es.md)

When something breaks. Most of these we hit personally during dogfooding
on real sermons — the fix sticks.

If you don't find your issue here, run `./scripts/pipeline.sh doctor`
(macOS/Linux) or `scripts\pipeline.bat doctor` (Windows) first — it
checks ffmpeg, yt-dlp, Python deps, fonts, and the skill-symlink
layout, and tells you what's wrong before you waste a render.

---

## Install & setup

### `[AVFilterGraph] No such filter: 'subtitles'`

**Why**: Homebrew's default `ffmpeg` formula (v8.x and later) ships
without `libass`, which is required for burning subtitles into video.
The pipeline detects this and falls back gracefully if it can — but
sometimes that fallback isn't available.

**Fix**: install `ffmpeg-full` from Homebrew:
```bash
brew install ffmpeg-full
```
The pipeline auto-detects `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` on
the next run. Alternative: set `FFMPEG_BIN=/path/to/ffmpeg-with-libass`
in your shell.

### `ffmpeg: command not found`

You don't have ffmpeg installed at all. macOS: `brew install ffmpeg-full`.
Ubuntu/Debian: `sudo apt install ffmpeg`. Verify with `ffmpeg -version`.

### `yt-dlp: command not found`

Same as above. macOS: `brew install yt-dlp`. Ubuntu/Debian: `sudo apt
install yt-dlp` (or `pip install yt-dlp`). Verify: `yt-dlp --version`.

### `python3 -c "import mediapipe"` fails

You haven't run `pip install -r requirements.txt` yet, or you ran it in
a different Python venv than the one calling the scripts. Activate the
right venv first, then re-install.

### Skill scripts can't find each other (`ImportError: _common`)

The skill install creates symlinks from `~/.claude/skills/sermon-cuts/`
to the repo. If something went wrong:

```bash
ls -la ~/.claude/skills/sermon-cuts/
# Should show scripts → <repo>/scripts as a symlink
```

If not, re-link:
```bash
mkdir -p ~/.claude/skills/sermon-cuts
ln -sf "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -sf "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -sf "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
```

---

## Ingest & source

### `yt-dlp` fails with "video unavailable" or 403

The video is private, region-locked, age-restricted, or has been
removed. Try with `--cookies-from-browser=chrome` (or firefox/safari)
so yt-dlp uses your login session:

```bash
yt-dlp --cookies-from-browser=chrome <url>
```

If it's a livestream that just ended, wait an hour for YouTube to
finalize the video archive.

### `ZeroDivisionError` in `07_render_track.py` during pass 1

OpenCV can't read the source video dimensions — it returns 0×0. Two
common causes:

1. **The source.mp4 is broken or wrong codec.** Verify with
   `ffprobe -v error -show_entries stream=width,height <source>`. Should
   print non-zero dims. If not, re-encode with ffmpeg first.
2. **The symlink to source.mp4 is dangling.** Check that
   `sources/<slug>/source.mp4` resolves to a real file:
   ```bash
   ls -la sources/<slug>/source.mp4    # should show the symlink target
   readlink sources/<slug>/source.mp4   # should print real path
   ```
   If not, recreate the symlink.

### `source não encontrado: .../sources/<slug>/source.mp4`

You ran a render before ingest. Run `./scripts/01_ingest.py <source>
--slug <slug>` first, or use the orchestrator `pipeline.sh <source>`.

---

## Transcription

### `GROQ_API_KEY não configurada`

You passed `--provider=groq` but haven't set the key. Get a free one at
[console.groq.com/keys](https://console.groq.com/keys) and add to your
shell or to `~/.env`:

```bash
echo 'GROQ_API_KEY=gsk_your_key_here' >> ~/.env
```

Or just use `--provider=youtube` instead (free, no key, slightly less
accurate).

### YouTube VTT has obviously dropped words

This happens occasionally on YouTube auto-captions, especially at
sentence boundaries: *"superestimamos a Mas"* should be *"superestimamos
a missão. Mas"*. The pipeline catches many of these:

1. **`06b_scrub_srt`** detects the `function_word + capitalized_word`
   pattern and flags it for review.
2. **`semantic_gap` detection** flags cues where the duration is long
   but few words were captured (likely dropped content).
3. **`--use-llm`** runs an LLM-assisted pass over the whole SRT
   against the transcript to propose corrections.

If you keep hitting transcription errors, re-run with `--provider=groq`
for higher accuracy.

### "Cut #N has 0 cues" in the SRT

The cut's time range doesn't overlap any words in the transcript. Either
the cut times are wrong (check `cuts_proposed.json`) or transcription
silently failed for that segment. Re-run `02_transcribe.py` with
`--force`.

---

## Cut proposals & validation

### LLM proposed cuts are all bad / off-topic

Most common cause: the transcript has noise the LLM picked up on
(announcements, prayer time, music breaks). Two fixes:

1. **Curate the transcript first** — open `transcript.json`, delete
   word-ranges for the noise sections, save, re-run `04_propose_cuts.py`.
2. **Tune the prompt** — `prompts/propose_cuts.md` has the scoring
   rubric. If your audience or style differs from a typical Brazilian
   sermon, edit the soft preferences section.

### Cut ends mid-thought ("...porque", "...para")

`05_validate_cut.py` should catch this and extend the end. If it
doesn't:
- The end couldn't be extended within `--max-extend-s` (default 8s).
- Pass `--max-extend-s 20` and try again.
- Or manually edit `cuts_proposed.json` to set a new `end`.

### Cut #N has duration warnings (>60s or <25s)

Short-form platforms (Reels, Shorts, TikTok) penalize >60s and don't
retain on <25s. Either:
- Re-propose the cuts (run `04_propose_cuts.py` again — the prompt now
  has 25-60s as the hard window)
- Manually trim `end` in `cuts_proposed.json`
- Split a long cut into two with separate hooks

---

## Render & subtitles

### Rendered video shows blank/black in macOS Preview

macOS Preview chokes on H.264 verticals when BT.709 color metadata
isn't tagged. The pipeline tags it correctly on render, but if you
re-encode somewhere else, you can lose it. Re-tag in place (~2 seconds,
no quality loss):

```bash
ffmpeg -y -i input.mp4 -c copy \
  -bsf:v "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1" \
  -movflags +faststart fixed.mp4 && mv fixed.mp4 input.mp4
```

Tested: opens cleanly in Preview, QuickTime, Instagram, TikTok.
**Note**: QuickTime and VLC always work — only Preview is picky.

### Subtitles don't appear in the rendered video

Three possible causes:

1. **libass not in ffmpeg** — see the `'subtitles'` filter error above.
2. **Font not installed** — pipeline default is `arial-black` which
   ships on macOS/Windows/most Linux. If you switched to `outfit-black`
   without installing the font, libass falls back to a default font.
   Install Outfit: [fonts.google.com/specimen/Outfit](https://fonts.google.com/specimen/Outfit)
3. **SRT file empty or malformed** — open
   `memory/messages/<slug>/srts/NN-slug.srt` and verify it has cues.

### Subtitles flash/blink / wrong timing

The SRT was generated against a different transcript than the audio
in the final render. Regenerate:
```bash
./scripts/06_build_srt.py <slug> <n>
./scripts/pipeline.sh --reburn-srt <n> --slug <slug>
```

### `{\fs22\b1}` shows up literally as text in my exported SRT

That's intentional ASS markup for the burn-in (gives the first cue a
size boost). It's invisible when libass renders it into video, but
appears as text if you re-upload the SRT to YouTube CC or Instagram
auto-captions. Strip it for export:

```bash
./scripts/export_srt.py <slug> <n>
# Writes a sibling .clean.srt with all {...} blocks removed.
```

---

## Audio

### "Possible clipped samples in output" / audio sounds distorted

The old pyloudnorm-based normalizer would clip when applying large gain
to quiet sources. The new `08_audio_normalize.py` uses ffmpeg's
`loudnorm` filter with a true-peak limiter — clipping should not
happen at the default `--true-peak-db -1.5`.

If you still hear distortion:
1. Verify you're on the new normalizer (check the script imports
   `loudnorm`, not `pyloudnorm`)
2. Try a lower target: `--target-lufs -16 --true-peak-db -2.0`

### Audio out of sync with video

ffmpeg should handle this automatically. If you're hitting it:
- Re-extract source: `01_ingest.py <slug> --force`
- Make sure source.mp4 has standard timing (run `ffprobe` and check
  for `start_time != 0`)

---

## Output

### Rendered MP4 too large for Instagram (>100 MB)

Default render is high-quality (CRF 18, preset slow). Lower quality
slightly for smaller file size — edit `config/render_defaults.yaml`:
```yaml
video:
  crf: 22       # was 18 — lower number = higher quality + larger file
  preset: fast  # was slow — faster encode, slightly larger file
```

Or convert after the fact:
```bash
ffmpeg -i big.mp4 -c:v libx264 -crf 24 -preset medium small.mp4
```

### Face tracking went the wrong way / cropped the wrong person

MediaPipe picks the largest face in each frame. If there are two
speakers or someone walks across, it can drift. Options:

1. **Re-run with the pose-fallback** (default): the pipeline already
   uses shoulder midpoint when face detection misses.
2. **Hard-pin the X position**: open `cuts_proposed.json` and add a
   `"crop_x_norm": 0.5` field (0 = left edge, 1 = right edge). The
   render then uses that fixed X instead of tracking.
3. **Switch to Haar cascade** (less accurate but more predictable):
   set `tracking.detector: haar` in `config/render_defaults.yaml`.

---

## Windows-specific

### `'mklink' is not recognized` during install.bat

`install.bat` uses `mklink /J` to create a directory junction when
symlinks aren't available (no admin / Developer Mode). On Windows 7
or with cmd.exe replaced by a non-standard shell, `mklink` may be
missing. Workarounds:

1. Enable Developer Mode (Settings → Update & Security → For
   Developers → Developer Mode), which lets `install.py` use real
   symlinks via Python's `Path.symlink_to`. No admin required.
2. Run install.bat from an Admin cmd.exe.
3. Fall back to copy mode — `install.py` will copy the skill dirs
   instead of linking them (uses more disk and won't track future
   repo updates, but works without admin).

### `'ffmpeg' is not recognized as an internal or external command`

ffmpeg isn't on PATH or installed. `install.py`'s detection looks at
PATH plus `C:\ffmpeg\bin\`, `C:\Program Files\ffmpeg\bin\`, and the
Program Files (x86) variant. Pick one of:

```cmd
winget install Gyan.FFmpeg
scoop install ffmpeg
choco install ffmpeg
```

Or download manually from [ffmpeg.org](https://ffmpeg.org/download.html),
unzip to `C:\ffmpeg\`, and `resolve_ffmpeg` will pick it up without
PATH editing.

### MediaPipe install fails with `Microsoft Visual C++ 14.0 or greater is required`

Some MediaPipe wheels need the MSVC build tools. Install the
[Visual Studio Build Tools](https://aka.ms/vs/17/release/vs_buildtools.exe)
(select the "Desktop development with C++" workload), then re-run
`pip install -r requirements.txt`. Most users won't hit this — MediaPipe
ships prebuilt wheels for Python 3.10–3.12 on Windows.

### Long paths cause `FileNotFoundError`

Windows defaults to a 260-character path limit. The skill install at
`%USERPROFILE%\.claude\skills\sermon-cuts\memory\messages\<long-slug>\...`
can hit it on deeply nested sermon names. Enable long paths:

```cmd
reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem ^
  /v LongPathsEnabled /t REG_DWORD /d 1 /f
```

Or set `SERMON_CUTS_MESSAGES_DIR=D:\sc` (or similar short path) in
your environment to keep paths short.

---

## Pipeline doctor

When in doubt:
```bash
./scripts/pipeline.sh doctor      # macOS / Linux
scripts\pipeline.bat doctor       # Windows
```

It checks: ffmpeg + libass, yt-dlp, Python deps, font availability,
skill-symlink layout, and config validity. Prints a green ✓ for what
works and a red ✗ + hint for what doesn't.

---

## Still broken?

- [INSTALL.md](INSTALL.md) — re-verify install
- [FAQ.md](FAQ.md) — common workflow questions
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  open one with the full error output, your OS, and `ffmpeg -version`
- Personal contact: [netogregorio.com](https://netogregorio.com)

---

By [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
