# Changelog

[English](CHANGELOG.md) · **Português** · [Español](CHANGELOG.es.md)

## 0.2.0 — Cross-platform + qualidade de entrega (2026-06-03)

### Cross-platform

- **Suporte a Windows, nativo.** Novo `pipeline.py` (orquestrador Python
  cross-platform) substitui a lógica bash-only do `pipeline.sh`. `pipeline.sh`
  e `pipeline.bat` agora são wrappers finos que fazem exec nele — a memória
  muscular do Unix continua funcionando, e usuário Windows ganha a mesma CLI.
- **`install.py`** porta o instalador bash pra Python cross-platform:
  venv, linkagem da skill (symlink → junction `mklink /J` → fallback de
  copy), chave GROQ no `~/.env`, seleção de font preset, pré-download dos
  modelos MediaPipe, doctor check. `install.sh` e `install.bat` empacotam
  ele pro bootstrap específico de cada plataforma (deps do sistema + clone do repo).
- **`resolve_ffmpeg` cross-platform**: `shutil.which("ffmpeg")` pra
  lookup no PATH mais paths de fallback no Windows (`C:\ffmpeg\bin\`,
  Program Files).

### Regras de corte (alinhadas com brief de criador)

- **Janela de duração 60–90s** por padrão. O antigo cap de 25–60s era
  baseado em retenção de short-form do início dos anos 2020; Reels (90s
  nativos) e TikTok (sem cap relevante) aceitam a janela mais larga. O
  YouTube Shorts ainda tem hard-cap em 60s — use `--target shorts` pra
  re-capar.
- **Detecção de início no meio da frase**: `05_validate_cut` agora avisa
  quando um corte começa numa palavra-função (`mas`, `porque`, `então`,
  `quando`, `se`, ...) ou quando a palavra anterior não termina em `.!?`.
  Só warn — o start nunca é movido automaticamente (intenção do curador
  é sagrada).
- **forbid_endings estendido** com `então`, `quando`, `se` — todos três
  abrem cláusulas incompletas.
- **Prompts de scrub** (en/pt/es) endurecidos com regra inviolável
  contra alterar significado teológico durante limpeza de transcrição.

### Qualidade de imagem

- **Fix de teto do source** ([01_ingest.py]): format string do yt-dlp
  agora prefere ≥1080p em qualquer codec (antes: só ≤1080p mp4). Captura
  masters 1440p/2160p e streams VP9/AV1 (~3-4× mais eficientes que o
  H.264 1080p do YouTube). Cap com `SERMON_CUTS_MAX_HEIGHT`.
- **Probe do source + warn** no ingest. ffprobe armazenado em `meta.json
  .source_quality`; avisa quando source é <1080p, <2 Mbps ou <24 fps.
- **Upscale Lanczos**: `cv2.INTER_LANCZOS4` pra escala-pra-1920
  (substitui `INTER_AREA`, que era a escolha errada no upscale).
- **Flag `--codec hevc`** adiciona paths H.265 via `hevc_videotoolbox`
  (auto) ou `libx265` (max). ~40% menores no mesmo nível de qualidade
  visível. `--quality max --codec hevc` entrega 10-bit Main 10
  (`yuv420p10le`) com tag `hvc1` pra compatibilidade no ecossistema
  Apple.
- **Tracking sample_fps 2 → 5** pra follow facial mais apertado em
  pregadores energéticos (~2-3s extras por corte em Apple Silicon).
- **Enquadramento vertical na regra dos terços**: centro da face
  posicionado a 40% da altura de saída (configurável via
  `tracking.face_y_target`). Source escalado pra `OUT_H × 1.25` pra dar
  headroom Y à janela de crop.
- **Filter chain do `--quality max`**: `hqdn3d=1.5:1.5:6:6, unsharp=5:5:0.6`
  antes do burn de legenda. Mata ruído de chroma de câmera-de-igreja
  com ISO alto; recupera crispness perdido no upscale. Pulado no modo
  `auto` (iteração rápida).

### Sync + transcrição

- **Fix de dessync A/V** ([07_render_track.py]): renderer agora lê no
  fps nativo do source e usa filtro `fps={OUT_FPS}` pra conversão de
  rate de saída. O loop antigo assumia source a 30fps e lia ~25% a mais
  de conteúdo em sources a 23.976fps, acelerando o vídeo à frente do
  áudio. Verificado em delta: 6.6ms vs ~16s pré-fix.
- **Robustez do provider YouTube** ([02_transcribe.py]): o path
  `--provider=youtube` hoardava captions válidas quando yt-dlp retornava
  429 em uma sub-language irmã. Reescrito pra percorrer variantes de
  idioma (`pt-orig` → `pt-BR` → `pt` → `pt-PT`) uma por vez, parando na
  primeira que entrega VTT. O exit code do yt-dlp agora é advisory — se
  um VTT parseable tá no disco, a gente usa.
- **Preferência de auto-provider invertida**: sources URL do YouTube
  agora default pra `--provider=youtube` mesmo quando `GROQ_API_KEY`
  está setada. As captions são grátis, instantâneas, e o novo
  `--full-llm-review` pega erros de transcrição melhor do que o
  round-trip antigo do Groq pegava.

### Scrub

- **`--full-llm-review`** ([06b_scrub_srt.py]): limpeza LLM no SRT
  inteiro. Envia toda cue + snippet word-level do transcript por-cue pro
  LLM numa chamada só e aplica todos os fixes retornados. Pega erros
  que as regras heurísticas não conseguem dar match: typos de palavras
  juntas (`paraa festa`), artigos errados (`na seu próprio idioma`),
  letras faltando (`pentec`), nome próprio em minúscula, cadeias de
  filler (`é a é a tipo assim`), duplicados de VTT (`muito muito`).
  Custo em Claude Haiku 4.5: ~$0.01 por corte. Fix de forbidden-ending
  via edits pareados de cue.
- **`pipeline.sh --llm-scrub`** conecta o novo scrub no orquestrador.

## 0.1.0 — Release inicial (2026-05-23)

Primeiro release público. Pipeline end-to-end:

- `01_ingest.py` — yt-dlp ou arquivo local → source gerenciado
- `02_transcribe.py` — YouTube VTT (padrão) ou Groq Whisper, em nível de palavra
- `03_vad_segments.py` — detecção de pausa silero-vad → candidatos de corte
- `04_propose_cuts.py` — prepara input do LLM pra proposta de corte
- `05_validate_cut.py` — auto-estende cortes que terminam no meio do pensamento
- `06_build_srt.py` — legendas brand-style (3-4 palavras, function-word shift)
- `07_render_track.py` — face tracking MediaPipe + smooth pan + burn de legenda
- `08_audio_normalize.py` — pyloudnorm pra -14 LUFS
- `pipeline.sh` — orquestrador

Brand style padrão: Outfit Black, ouro `#fbc531`, outline preto `0.8`,
sentence case, posição de rodapé. Vertical 1080×1920 @ 30fps.

Inclui um `SKILL.md` pra integração com Claude Code.

Testado com dois sermões em PT-BR (~28min cada):
- *Vinde a mim* (Mateus 11) — 12 candidatos de corte propostos, 8 renderizados.
- *Derrubando as fortalezas da mente* — 10 cortes renderizados.

Case studies de amostra em `examples/`.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
