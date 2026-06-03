# Frequently Asked Questions

**English** · [Português](FAQ.pt.md) · [Español](FAQ.es.md)

Written for pastors, preachers, and ministry creators trying to figure out
whether Sermon Cuts fits their workflow. No code required to read this.

---

## Getting started

### Do I need to know how to code?

**No.** If you can copy-paste a command into a terminal, you're fine. If
you don't want to touch a terminal at all, paste the install prompt into
**Claude Code**, **Cursor**, **Cline**, or any AI coding agent — it
handles every technical step for you.

### How much does it cost?

**The tool itself: free, open-source (MIT).**

Costs you might pay:
- **YouTube transcription** (the default): $0
- **Groq Whisper transcription** (more accurate): free tier covers
  ~10 sermons/day. Past that, ~$0.05 per 30-minute sermon
- **LLM cut proposals** (Claude/Cursor): you're already paying for those
  if you're using them — Sermon Cuts uses your existing subscription

For a typical preacher cutting 1 sermon a week: **$0/month** in all
practical scenarios.

### Will it work with my sermon recordings?

Yes, if your video is:
- A **YouTube link** (public or unlisted)
- OR a **local file** in MP4, MOV, MKV, or WebM

Audio quality matters more than video. If you can clearly hear the
speaker in your video, the transcription will work.

### Will it work in languages other than Portuguese?

Yes. Pass `--language=en` for English, `--language=es` for Spanish,
`--language=pt` for Portuguese (default). The pipeline itself is
language-agnostic — only the LLM cut-proposal prompt is tuned for
Portuguese sermons today. English/Spanish prompts work too, but you may
want to adjust the rubric in `prompts/propose_cuts.md` for your tradition.

### How long does it take?

For a 30-minute sermon, end-to-end:

- **Transcribe + analyze**: ~1 minute
- **You curate cut proposals**: ~5 minutes (most of your time)
- **Render the cuts you approved**: ~30–60 seconds per cut on Apple
  Silicon, ~2 minutes per cut on older Intel Macs/Linux

So 10 cuts: ~15–25 minutes total, with most of that being the renders
running in the background while you do other things.

---

## Output quality

### What if the AI picks bad moments?

You see every proposed cut as a ranked list before any rendering
happens. Click in, read the hook/development/conclusion, approve or
reject each one. **Nothing gets rendered without your green light.**

### What if a subtitle has a transcription error?

Three layers catch errors:

1. **Automatic scrub** flags suspicious cues (likely YouTube dropped a
   word, said "Quisto" instead of "Cristo", etc.)
2. **LLM-assisted review** (optional `--use-llm`) reads the SRT in
   context and proposes fixes
3. **Manual edit** — the SRT is a plain text file. Edit it, run
   `pipeline.sh --reburn-srt N --slug <your-sermon>` and only the
   subtitle re-burns (no re-tracking, ~30s).

### Can I edit the cuts after they're rendered?

Yes. The output is a standard MP4 — open in CapCut, Premiere, DaVinci,
or anything else. Most people don't need to, but the option is there.

### Will the face tracking work if I move around a lot?

Tracking samples 2 frames per second and averages over a 2.5-second
window. It handles normal pulpit movement, walking across stage,
turning to read your Bible. It doesn't handle: rapid lateral movement
(more than ~1m/sec across the frame), being completely off-screen for
more than a couple seconds, or multiple speakers at the same time
(it'll pick the largest face, which may not be the one talking).

### Can I use my own subtitle style / brand font / colors?

Yes. Pick a built-in preset (`arial-black`, `helvetica-bold`,
`outfit-black`) in `config/render_defaults.yaml`, or hand-tune one in
`config/style_presets/<your-name>.txt`. See
[STYLE.md](STYLE.md) for the palette/typography rules.

---

## Platforms & sources

### Will it work on Windows?

**Yes, natively** since v0.2.0 — no WSL required. The orchestrator
(`pipeline.py`) and installer (`install.py`) are pure Python. A
`pipeline.bat` wrapper lets you run `pipeline.bat <youtube-url>` from
cmd or PowerShell the same way macOS/Linux users run `pipeline.sh`.

Setup is one-time `winget` of Python + git + ffmpeg + yt-dlp, then
`scripts\install.bat` from the cloned repo. See
[INSTALL.md](INSTALL.md#windows) for the full walkthrough.

WSL2 and Docker still work if you prefer them — but native Windows is
the recommended path now.

### What about Linux?

Fully supported. Tested on Ubuntu 22.04+. Install instructions in
[INSTALL.md](INSTALL.md).

### Can I use this with non-YouTube sources?

Yes. Pass a local file path instead of a URL:
```bash
./scripts/pipeline.sh ~/Downloads/my_sermon.mp4
```
Vimeo, Twitch VOD, and most platforms that yt-dlp supports also work
when passed as a URL — but auto-captions are usually YouTube-only, so
you'll want `--provider=groq` for those.

### What if my YouTube video doesn't have auto-captions?

YouTube generates auto-captions automatically within a few hours of
upload for most public videos. If yours doesn't have them yet (or
you've disabled them), use `--provider=groq` instead — that uses Groq
Whisper which extracts and transcribes the audio directly.

### Can I do this fully offline?

Almost. The face-tracking model downloads on first run (~10 MB, one
time). After that:
- Transcription: needs internet for YouTube VTT or Groq
- Cut proposal: needs your AI editor (Claude/Cursor), which usually
  needs internet
- Render: 100% local
- Subtitle scrub: 100% local (unless you opt into `--use-llm`)

So if you transcribe with a local Whisper model (planned, not shipped
yet) and propose cuts manually instead of via LLM, you can run end-to-end
offline.

---

## Privacy & data

### Where does my sermon audio go?

Depends on which transcription provider you choose:

- **YouTube auto-captions** (default): only the YouTube URL is queried.
  No audio leaves your machine.
- **Groq Whisper**: your sermon audio is uploaded to Groq's servers for
  transcription. See their [privacy
  policy](https://groq.com/privacy-policy/).
- **LLM cut proposal**: the *transcript text* (not audio) is shared with
  your AI editor's provider (Anthropic, OpenAI, etc.).

The render itself is **100% local**. Your face, your voice, your video
file — never leave your computer unless you explicitly upload them.

Full breakdown in [PRIVACY.md](PRIVACY.md).

### Does Sermon Cuts log anything?

The pipeline writes to `memory/messages/<slug>/` on your machine —
transcripts, cut proposals, renders. **Nothing is sent anywhere by the
pipeline itself.** What gets shared depends entirely on which APIs you
opt into (Groq for transcription, your AI editor for cut proposals).

### Is this affiliated with any denomination / theological tradition?

**No.** Sermon Cuts is just an editing tool. The example prompts are
written in Portuguese with Christian-sermon framing (because that's what
[@netogregorio](https://github.com/netogregorio) cuts), but the tool
makes no assumptions about your message, audience, or theology.

---

## Workflow questions

### Can I batch process multiple sermons?

Yes. Run `./scripts/pipeline.sh <url-1>`, then `pipeline.sh <url-2>`,
etc. Each gets its own slug and working directory. There's no built-in
queue, but you can chain in a shell loop.

### Where do the final videos end up?

Two paths by default:
- `renders/<slug>/NN-slug.mp4` — pipeline output
- Move approved ones manually to `edit/cuts/<Sermon Name>/` for your
  curation workflow (the `CLAUDE.md` ritual)

### Can I use this for non-sermon content?

The pipeline doesn't care what your video is — it'll work on podcasts,
Bible studies, conference talks, university lectures, anything where one
person is talking on camera. The **cut-proposal prompt** is tuned for
sermon structure (hook + biblical illustration + application), so for
non-sermon content you may want to swap `prompts/propose_cuts.md` for
something better suited.

### Can I contribute back?

Yes! Pull requests welcome. See `CONTRIBUTING.md` in the repo. Common
contributions:

- New language prompts (Spanish/English sermon rubrics)
- Subtitle style presets for other brand looks
- `config/corrections_pt.txt` entries (or `_es.txt`, `_en.txt`) for
  recurring transcriber mistakes your tradition encounters
- Documentation fixes, translations
- Bug reports with reproducible source URLs

---

## Still stuck?

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common errors and fixes
- [INSTALL.md](INSTALL.md) — install + verify
- [PIPELINE.md](PIPELINE.md) — what each script does
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  open one with the error output

---

Built by [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
