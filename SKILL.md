---
name: sermon-cuts
description: "End-to-end pipeline for cutting vertical short-form clips from long sermon/preaching videos. Triggered when the user wants to cut a sermon, preaching, pregação, mensagem, or sermon-style talking-head video into multiple short verticals (Reels/Shorts/TikTok). Handles: download (YouTube or local), Groq Whisper transcription, VAD-aware natural cut boundaries, LLM-proposed cuts with narrative-arc scoring, MediaPipe face-tracking smooth pan, brand-style burned subtitles (gold Outfit Black + black outline + footer), LUFS audio normalization. User curates which proposed cuts to render; the rest is automatic."
---

# sermon-cuts — pipeline de cortes pra pregações

[English](SKILL.en.md) · [**Português**](SKILL.md) · [Español](SKILL.es.md)

## Quando invocar

Você invoca essa skill quando o usuário pede coisas como:
- "vamos cortar essa pregação https://..."
- "corta a mensagem em N cortes de 1 minuto"
- "fazer cortes do sermão"
- "transcrever e cortar essa pregação pra Reels/Shorts"
- "achar os melhores beats dessa mensagem"

Aceita input como **URL do YouTube** OU caminho local de `.mp4`/`.mov`.

## Resultado final

Em `<project>/edit/cuts/<slug_da_mensagem>/`:
```
01-tema_do_corte.mp4
02-outro_beat.mp4
...
```

Cada cut é:
- **Vertical 1080×1920 @ 30fps** (scale Lanczos + crop com face tracking 5fps + rule-of-thirds vertical `face_y_target=0.40`)
- **Legenda burned-in** brand-style (Outfit Black, gold `#fbc531`, outline preto 0.8, rodapé MarginV=50, 3-4 palavras/linha, sentence case)
- **Áudio normalizado** a -14 LUFS (padrão Insta/TikTok/Reels)
- **Encoder configurável**:
  - default `--quality auto --codec h264` → h264_videotoolbox 8M (Apple Silicon) / libx264 CRF 18 (resto)
  - delivery `--quality max --codec hevc` → libx265 -preset slower -crf 20 + 10-bit Main 10 (yuv420p10le) + hqdn3d + unsharp + hvc1 tag

## Workflow (one-at-a-time mode — Neto prefere)

### Fase A — Ingest + análise (automática, ~1 min)

1. **`scripts/01_ingest.py <url-or-path>`** — baixa via yt-dlp (≥1080p, qualquer codec; aceita VP9/AV1 + 1440p/2160p) OU copia local pra `<sources>/<slug>/source.mp4`. ffprobe loga `source_quality` em `meta.json` + avisa se <1080p / <2Mbps / <24fps.
2. **`scripts/02_transcribe.py`** — auto-pick: source YouTube → VTT auto-captions (grátis); local file → Groq Whisper-large se `GROQ_API_KEY` setado, senão faster-whisper local. Output: `transcript.json` word-level.
3. **`scripts/03_vad_segments.py`** — silero-vad detecta pausas ≥0.8s → `vad.json` (fronteiras candidatas)

### Fase B — Proposta de cortes (LLM, ~30s)

4. **Você (Claude) lê** `transcript.json` + `vad.json` e propõe cortes seguindo `prompts/propose_cuts.md`. Output: `cuts_proposed.json` com `[{n, slug, start, end, theme, hook, conclusion, coherence_score, depends_on}]`
5. **Apresenta ao usuário** numa lista ranqueada por score. Ele escolhe quais aprovar.

### Fase C — Render por cut aprovado (~30-60s default, ~45min --quality max --codec hevc)

Pra cada cut aprovado:
6. **`scripts/05_validate_cut.py --target {all,shorts,reels,tiktok}`** — confirma final + início naturais. `forbid_endings` (mas/porque/então/quando/se/...) + `forbid_starts` (warn-only). Ajusta `end` extendendo até próxima pausa VAD se truncado.
7. **`scripts/06_build_srt.py`** — gera SRT brand-style do segmento
8. **`scripts/06b_scrub_srt.py`** — scrub heurístico OU `--full-llm-review` (manda SRT inteira + transcript word-level pro LLM, aplica TODOS os fixes — pega `paraa→para a`, `pentec→Pentecostes`, `na seu→no seu`, etc). Custo ~$0.01/cut.
9. **`scripts/07_render_track.py --quality {auto,max} --codec {h264,hevc}`** — MediaPipe face+pose detection 5fps + smoothing 2.5s + scale Lanczos + rule-of-thirds Y + crop 1080×1920 + burn legenda + encode (videotoolbox auto / libx265 max). A/V sync via src_fps + ffmpeg fps filter.
10. **`scripts/08_audio_normalize.py`** — ffmpeg loudnorm two-pass -14 LUFS + true-peak -1.5 dBTP
11. **`scripts/09_trim_silences.py`** (opt-in via `trim_silences: true` no cut) — colapsa silêncios >2.5s
12. **Salva** em `<renders>/<slug>/NN-cut_slug.mp4` e mostra preview pro Neto

### Fase D — Iteração

Se ele rejeitar/pedir mudança em um cut:
- Correção de texto da legenda → edita `srt`, reburn (não refaz tracking)
- Trim de início/fim → re-rodar do passo 7
- Cut inteiro errado → marca rejected em `cuts_proposed.json`, propõe substituto

## Estrutura de arquivos

```
~/.claude/skills/sermon-cuts/           # macOS/Linux symlink; Windows junction
├── SKILL.md                 ← este arquivo
├── scripts/
│   ├── 01_ingest.py
│   ├── 02_transcribe.py
│   ├── 03_vad_segments.py
│   ├── 04_propose_cuts.py   ← stub que chama Claude com prompt
│   ├── 05_validate_cut.py
│   ├── 06_build_srt.py
│   ├── 06b_scrub_srt.py     ← lint + (opcional) full-llm-review
│   ├── 07_render_track.py
│   ├── 08_audio_normalize.py
│   ├── 09_trim_silences.py
│   ├── pipeline.py          ← orquestrador cross-platform
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
        └── <slug_mensagem>/
            ├── transcript.json
            ├── vad.json
            ├── meta.json    ← inclui source_quality + warnings
            ├── cuts_proposed.json
            └── srts/NN-slug.srt
```

## Regras hard (não negociar com usuário)

1. **Vertical 1080×1920**. Source horizontal → scale Lanczos + crop dinâmico (X via face/pose, Y via rule-of-thirds `face_y_target=0.40`). **Nunca** letterbox, **nunca** scale+pad com blur background.
2. **Legenda sentence case**, jamais UPPERCASE.
3. **Outline preto 0.8**, FontSize 16, MarginV 50. Não inventar.
4. **Cut precisa ter arco completo**: hook → desenvolvimento → conclusão. Se LLM não consegue identificar conclusão clara, rejeita o cut.
5. **Duração 60–90s** default (sweet spot pra Reels/TikTok). `--target shorts` re-cap em 60s (YouTube Shorts hard cap).
6. **Scrub teológico**: durante limpeza de SRT (heurístico OU LLM), NUNCA altera sentido teológico ou intenção do orador. Só conserta erro óbvio de transcrição.

## Decisões que devem ser deferidas ao usuário (não automatizar)

- Quais cortes aprovar (curadoria final)
- Correção de transcrição quando Whisper erra palavra técnica/teológica
- Override de tema/slug do cut

## Comandos de invocação típicos

Use `pipeline.sh` (macOS/Linux), `pipeline.bat` (Windows), ou `python pipeline.py` (qualquer OS) — mesma surface de flags.

```bash
# Pipeline completa, modo interativo (default)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh "https://youtube.com/watch?v=ZKeORvbgWpA"

# Só ingest + transcribe + propose (sem render)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --propose-only /path/local.mp4

# Renderizar cortes específicos já propostos
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 2,4,7 --slug vinde_a_mim

# Delivery-grade pra cliente: max quality + HEVC + LLM scrub completo
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cut 3 --slug vinde_a_mim \
  --quality max --codec hevc --llm-scrub

# YouTube Shorts (re-cap em 60s)
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --render-cuts 1,2 --slug vinde_a_mim --target shorts

# Reaplicar só legenda (sem retracking) num cut já feito
~/.claude/skills/sermon-cuts/scripts/pipeline.sh --reburn-srt 2 --slug vinde_a_mim
```

## Brand style

Paleta, tipografia, regras de legenda, format default e organização de arquivos vivem em **[docs/STYLE.md](docs/STYLE.md)** — leia antes de propor mudanças visuais. TL;DR: gold `#fbc531` + outline preto, Outfit Black, vertical 1080×1920, sentence case.

Overrides puramente locais (path de fonte custom, paleta de outra marca) ficam no `CLAUDE.md` do projeto que consome a skill, não aqui.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
