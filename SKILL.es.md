---
name: sermon-cuts
description: "End-to-end pipeline for cutting vertical short-form clips from long sermon/preaching videos. Triggered when the user wants to cut a sermon, preaching, pregação, mensagem, or sermon-style talking-head video into multiple short verticals (Reels/Shorts/TikTok). Handles: download (YouTube or local), Groq Whisper transcription, VAD-aware natural cut boundaries, LLM-proposed cuts with narrative-arc scoring, MediaPipe face-tracking smooth pan, brand-style burned subtitles (gold Outfit Black + black outline + footer), LUFS audio normalization. User curates which proposed cuts to render; the rest is automatic."
---

# sermon-cuts — pipeline de cortes para predicaciones

[English](SKILL.en.md) · [Português](SKILL.md) · [**Español**](SKILL.es.md)

## Cuándo invocar

Invoca esta habilidad cuando el usuario pide cosas como:
- "vamos a cortar esa predicación https://..."
- "corta el mensaje en N cortes de 1 minuto"
- "hacer cortes del sermón"
- "transcribir y cortar esa predicación para Reels/Shorts"
- "encontrar los mejores beats de ese mensaje"

Acepta como input una **URL de YouTube** O una ruta local `.mp4`/`.mov`.

## Resultado final

En `<project>/edit/cuts/<slug_del_mensaje>/`:
```
01-tema_del_corte.mp4
02-otro_beat.mp4
...
```

Cada corte es:
- **Vertical 1080×1920 @ 30fps** (scale Lanczos + crop con tracking de cara 5fps + regla de los tercios vertical `face_y_target=0.40`)
- **Subtítulo burned-in** brand-style (Outfit Black, oro `#fbc531`, outline negro 0.8, pie de página MarginV=50, 3-4 palabras/línea, sentence case)
- **Audio normalizado** a -14 LUFS (estándar Insta/TikTok/Reels)
- **Encoder configurable**:
  - default `--quality auto --codec h264` → h264_videotoolbox 8M (Apple Silicon) / libx264 CRF 18 (resto)
  - delivery `--quality max --codec hevc` → libx265 -preset slower -crf 20 + 10-bit Main 10 (yuv420p10le) + hqdn3d + unsharp + hvc1 tag

## Workflow (modo one-at-a-time — Neto prefiere)

### Fase A — Ingest + análisis (automático, ~1 min)

1. **`scripts/01_ingest.py <url-o-ruta>`** — descarga vía yt-dlp (≥1080p, cualquier codec; acepta VP9/AV1 + 1440p/2160p) O copia local a `<sources>/<slug>/source.mp4`. ffprobe registra `source_quality` en `meta.json` + avisa si <1080p / <2Mbps / <24fps.
2. **`scripts/02_transcribe.py`** — auto-pick: source YouTube → VTT auto-captions (gratis); archivo local → Groq Whisper-large si `GROQ_API_KEY` está seteado, si no faster-whisper local. Output: `transcript.json` word-level.
3. **`scripts/03_vad_segments.py`** — silero-vad detecta pausas ≥0.8s → `vad.json` (fronteras candidatas)

### Fase B — Propuesta de cortes (LLM, ~30s)

4. **Tú (Claude) lees** `transcript.json` + `vad.json` y propones cortes siguiendo `prompts/propose_cuts.md`. Output: `cuts_proposed.json` con `[{n, slug, start, end, theme, hook, conclusion, coherence_score, depends_on}]`
5. **Presenta al usuario** una lista ranqueada por score. Él elige cuáles aprobar.

### Fase C — Render por cut aprobado (~30-60s default, ~45min --quality max --codec hevc)

Para cada corte aprobado:
6. **`scripts/05_validate_cut.py --target {all,shorts,reels,tiktok}`** — confirma final + inicio naturales. `forbid_endings` (mas/porque/então/quando/se/...) + `forbid_starts` (warn-only). Ajusta `end` extendiendo hasta la próxima pausa VAD si está truncado.
7. **`scripts/06_build_srt.py`** — genera SRT brand-style del segmento
8. **`scripts/06b_scrub_srt.py`** — scrub heurístico O `--full-llm-review` (manda SRT entera + transcript word-level al LLM, aplica TODOS los fixes — pega `paraa→para a`, `pentec→Pentecostes`, `na seu→no seu`, etc). Costo ~$0.01/cut.
9. **`scripts/07_render_track.py --quality {auto,max} --codec {h264,hevc}`** — MediaPipe face+pose detection 5fps + smoothing 2.5s + scale Lanczos + regla de los tercios Y + crop 1080×1920 + burn subtítulo + encode (videotoolbox auto / libx265 max). A/V sync vía src_fps + ffmpeg fps filter.
10. **`scripts/08_audio_normalize.py`** — ffmpeg loudnorm two-pass -14 LUFS + true-peak -1.5 dBTP
11. **`scripts/09_trim_silences.py`** (opt-in vía `trim_silences: true` en el cut) — colapsa silencios >2.5s
12. **Guarda** en `<renders>/<slug>/NN-cut_slug.mp4` y muestra preview a Neto

### Fase D — Iteración

Si él rechaza/pide cambio en un corte:
- Corrección de texto de subtítulo → edita `srt`, reburn (no rehace tracking)
- Trim de inicio/fin → re-correr desde paso 7
- Corte entero equivocado → marca rejected en `cuts_proposed.json`, propone sustituto

## Estructura de archivos

```
~/.claude/skills/sermon-cuts/           # macOS/Linux symlink; junction de Windows
├── SKILL.md                 ← este archivo
├── scripts/
│   ├── 01_ingest.py
│   ├── 02_transcribe.py
│   ├── 03_vad_segments.py
│   ├── 04_propose_cuts.py   ← stub que llama Claude con prompt
│   ├── 05_validate_cut.py
│   ├── 06_build_srt.py
│   ├── 06b_scrub_srt.py     ← lint + (opcional) full-llm-review
│   ├── 07_render_track.py
│   ├── 08_audio_normalize.py
│   ├── 09_trim_silences.py
│   ├── pipeline.py          ← orquestador cross-platform
│   ├── pipeline.sh          ← wrapper Unix (exec → pipeline.py)
│   └── pipeline.bat         ← wrapper Windows
├── config/
│   ├── render_defaults.yaml
│   ├── style_presets/
│   └── corrections_pt.txt
├── prompts/
│   ├── propose_cuts.{md,pt.md,es.md}
│   └── scrub_srt.{md,pt.md,es.md}
└── memory/
    └── messages/
        └── <slug_mensaje>/
            ├── transcript.json
            ├── vad.json
            ├── meta.json    ← incluye source_quality + warnings
            ├── cuts_proposed.json
            └── srts/NN-slug.srt
```

## Reglas hard (no negociar con usuario)

1. **Vertical 1080×1920**. Source horizontal → scale Lanczos + crop dinámico (X vía face/pose, Y vía regla de los tercios `face_y_target=0.40`). **Nunca** letterbox, **nunca** scale+pad con blur background.
2. **Subtítulo sentence case**, jamás UPPERCASE.
3. **Outline negro 0.8**, FontSize 16, MarginV 50. No inventar.
4. **Cut debe tener arco completo**: hook → desarrollo → conclusión. Si LLM no logra identificar conclusión clara, rechaza el cut.
5. **Duración 60–90s** default (sweet spot para Reels/TikTok). `--target shorts` re-cap en 60s (YouTube Shorts hard cap).
6. **Scrub teológico**: durante limpieza de SRT (heurístico O LLM), NUNCA altera sentido teológico ni intención del orador. Solo arregla error obvio de transcripción.

## Decisiones que deben ser diferidas al usuario (no automatizar)

- Cuáles cortes aprobar (curación final)
- Corrección de transcripción cuando Whisper falla en palabra técnica/teológica
- Override de tema/slug del corte

## Comandos de invocación típicos

Usa `pipeline.sh` (macOS/Linux), `pipeline.bat` (Windows), o `python pipeline.py` (cualquier OS) — misma surface de flags.

```bash
# Pipeline completo, modo interactivo (default)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh "https://youtube.com/watch?v=ZKeORvbgWpA"

# Solo ingest + transcribe + propose (sin render)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --propose-only /path/local.mp4

# Renderizar cortes específicos ya propuestos
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 2,4,7 --slug vinde_a_mim

# Calidad de entrega para cliente: max quality + HEVC + LLM scrub completo
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cut 3 --slug vinde_a_mim \
  --quality max --codec hevc --llm-scrub

# YouTube Shorts (re-cap en 60s)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 1,2 --slug vinde_a_mim --target shorts

# Reaplicar solo subtítulo (sin retracking) en un corte ya hecho
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --reburn-srt 2 --slug vinde_a_mim
```

## Brand style

Paleta, tipografía, reglas de subtítulo, format default y organización de archivos viven en **[docs/STYLE.es.md](docs/STYLE.es.md)** — léelo antes de proponer cualquier cambio visual. TL;DR: gold `#fbc531` + outline negro, Outfit Black, vertical 1080×1920, sentence case.

Overrides puramente locales (ruta de fuente custom, paleta de otra marca) van en el `CLAUDE.md` del proyecto consumidor, no aquí.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
