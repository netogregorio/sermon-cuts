# Walkthrough do pipeline

[English](PIPELINE.md) · **Português** · [Español](PIPELINE.es.md)

Cada script grava em `memory/messages/<slug>/` e é idempotente (re-executar
é seguro e pula trabalho concluído, a menos que use `--force`).

## 01_ingest.py

```bash
./scripts/01_ingest.py <youtube-url-ou-caminho-local> [--slug SLUG]
```

URL do YouTube → usa yt-dlp com format string `bestvideo[height>=1080]+
bestaudio/bestvideo+bestaudio/best`. Captura masters 1440p/2160p e
streams VP9/AV1 quando disponíveis (~3-4× mais eficientes que o H.264
1080p do YouTube). Cap o limite superior com
`SERMON_CUTS_MAX_HEIGHT=1080` se uso de disco importar.

Arquivo local → cria symlinks (ou copia se o symlink falhar — comum no
Windows sem Developer Mode).

Depois do download, faz ffprobe do source e armazena resolução, fps,
codec e bitrate em `meta.json.source_quality`. Avisa quando o source
está abaixo do piso prático pra entrega limpa:

- height < 1080 (qualquer upscale no render é lossy)
- bitrate < 2 Mbps (artefatos de compressão do YouTube vão aparecer)
- fps < 24 (motion judder)

Grava:
- `memory/messages/<slug>/source.mp4`
- `memory/messages/<slug>/meta.json` (URL/caminho/título/duração + source_quality + source_quality_warnings)

Derivação do slug: a partir do título do YouTube ou nome do arquivo (slugificado para snake_case).
Sobrescreva com `--slug`.

## 02_transcribe.py

```bash
./scripts/02_transcribe.py <slug> [--provider=youtube|groq] [--language=pt]
```

### YouTube (padrão, grátis, instantâneo)

Chama `yt-dlp --write-auto-subs --skip-download` para pegar o arquivo VTT de auto-legenda
que o YouTube gera para todo vídeo público. Analisa timestamps inline em nível de palavra
do VTT (aquelas tags `<HH:MM:SS.mmm>` entre palavras).

### Groq (pago-ish, qualidade superior)

Extrai áudio (mono 16kHz WAV), envia para Groq Whisper-large-v3 com
`timestamp_granularities=["word"]`. Retorna timestamps em nível de palavra.
Precisa de `GROQ_API_KEY` no env.

Saída (mesmo formato para ambos):

```json
{
  "words": [
    {"text": "Eu", "start": 1.95, "end": 2.12, "type": "word"},
    {"text": " ", "start": 2.12, "end": 2.13, "type": "spacing"},
    ...
  ],
  "language": "pt",
  "_provider": "youtube-vtt"  // ou "groq-whisper-large-v3"
}
```

## 03_vad_segments.py

```bash
./scripts/03_vad_segments.py <slug> [--min-silence 0.5]
```

Roda [silero-vad](https://github.com/snakers4/silero-vad) no áudio do
source (reamostrado para 16kHz mono). Detecta segmentos de fala → deriva
os silêncios entre eles → marca o ponto médio de cada silêncio ≥ 0.5s como
**ponto de corte candidato** (lugares onde um corte não vai dividir palavra/respiração).

Saída:

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

Empacota transcrição + VAD em um único `propose_input.json` e imprime
os caminhos que o LLM (Claude) deve ler, mais o prompt em
`prompts/propose_cuts.md`. **Este script não chama um LLM** — apenas
prepara inputs.

Espera-se que o LLM grave os cortes propostos em
`memory/messages/<slug>/cuts_proposed.json`.

Schema esperado para cada corte:

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

Veja `prompts/propose_cuts.md` para a rubrica completa.

## 05_validate_cut.py

```bash
./scripts/05_validate_cut.py <slug> <cut_index> [--write-back] [--max-extend-s 8]
```

Confirma que a última palavra do corte não é um término proibido (configurável em
`config/render_defaults.yaml` — ex. "porque", "mas", "que", "para", "com",
"de"). Se for, tenta estender o fim até o próximo ponto de corte candidato do VAD
dentro de `max-extend-s` segundos onde a palavra não seja mais proibida.

`--write-back` aplica o patch no corte em `cuts_proposed.json`.

## 06_build_srt.py

```bash
./scripts/06_build_srt.py <slug> <cut_index>
```

Gera um SRT brand-styled a partir das palavras da transcrição no range do corte:

- 3-4 palavras por legenda, máx ~20 caracteres (configurável)
- Divide na pontuação (`. ! ?` hard, `, ; :` soft se a legenda tiver ≥3 palavras)
- Divide em pausa ≥0.5s se a legenda tiver ≥3 palavras
- Deslocamento consciente de palavra-função: se uma legenda termina com "para"/"com"/"que"/etc.,
  desloca para a próxima legenda (assim legendas nunca terminam em palavra-função)
- Capitaliza a primeira legenda
- Remove pontuação suave no final do texto da legenda

Grava `memory/messages/<slug>/srts/NN-slug.srt`.

## 06b_scrub_srt.py

```bash
./scripts/06b_scrub_srt.py <slug> <cut_index> [--agent-review]
                                              [--use-llm]
                                              [--full-llm-review]
                                              [--auto-apply]
                                              [--dry-run]
                                              [--corrections PATH]
```

Passo de lint que roda **entre `06_build_srt` e `07_render_track``,
escaneando o SRT em busca dos padrões de erro mais comuns das auto-captions
do YouTube (fronteiras de frase com palavra dropada, hesitações duplicadas,
termos teológicos grafados errado). Permite consertar erros de transcrição
antes do burn-in — economiza um re-encode inteiro por typo.

### O que ele procura

1. **`dropped_word_boundary`** — palavra-função (em / que / de / etc.)
   logo antes de uma palavra capitalizada que não é nome próprio. O
   YouTube engoliu uma palavra numa fronteira de frase.
       `"do que Mas não"`  ←  era na real  `"do que nós. Mas não"`
   Tem whitelist de personagens/lugares bíblicos comuns e pronomes em
   português pra `"em Cristo"` e `"para Ele"` não dispararem falso positivo.

2. **`immediate_repetition`** — `\b(\w+)\s+\1\b` filtrado pra hesitações
   conhecidas (a, o, um, uma, que, eu, ele, ela, …) e palavras curtas.
   Pula repetição estilística separada por vírgula tipo `"cansa, cansa"`.

3. **`forbidden_ending`** — re-checa a lista `cut_validation.forbid_endings`
   por legenda (não só na fronteira do corte como o `05_validate_cut.py`).
   Só reporta; o fix geralmente é mover a palavra final pra próxima
   legenda, melhor feito manualmente.

4. **`dictionary`** — se `memory/messages/<slug>/corrections.txt` existir,
   aplica pares `errado=correto` automaticamente (um por linha, `#` pra
   comentário). Útil pra fixes recorrentes:
   ```
   Quisto=Cristo
   Espirito=Espírito
   ```

### Três caminhos de review

| Caminho | Quando usar |
|---|---|
| **`--agent-review`** (default em non-TTY com suspeitos) | O orquestrador (Claude Code / Cursor / …) está lendo stdout. 06b emite JSON estruturado com texto da cue prev/next, snippet word-level do transcript ao redor de cada suspeito, e o path pro `prompts/scrub_srt.md`. O agente lê o prompt, decide fixes, aplica via Edit tool, e retoma o pipeline com `--skip-scrub`. |
| **`--use-llm`** | Review LLM-assisted **só nas cues flaggadas pelas regras** (cron, nightly, sem agente atrelado). Chama Anthropic Claude (prefere `ANTHROPIC_API_KEY`) ou Groq Llama (`GROQ_API_KEY` fallback). Barato mas perde erros que as heurísticas não flaggaram. |
| **`--full-llm-review`** | Review LLM do **SRT inteiro**. Envia toda cue + snippet word-level do transcript por-cue pro LLM numa chamada só e aplica todos os fixes retornados. Pega erros que os padrões de regra não dão match (typos de palavras juntas `paraa`, artigos errados `na seu`, letras faltando `pentec`, nomes próprios em minúscula, cadeias de filler, duplicados de VTT). Custa ~$0.01/corte em Claude Haiku 4.5. Fixes de forbidden-ending tratados via edits pareados de cue (tira de uma, prependa na próxima). Mesma ordem de preferência de API key do `--use-llm`. |
| **`--auto-apply`** | Só regras, confiança ≥ 0.85. Na prática só colapsa hesitações silenciosamente. Modo mais barato. |

### Outros modos

| Flag | Comportamento |
|---|---|
| (nenhuma, TTY)  | review interativo — prompt `y/n/edit/skip` por suspeito |
| `--dry-run`     | só reporta, nunca escreve o SRT |

O `pipeline.sh` integra esse passo automaticamente (interativo em TTY,
JSON `--agent-review` em non-TTY pra o agente orquestrador agir). Pula
com `--skip-scrub`:

```bash
./scripts/pipeline.sh --render-cuts 1,2 --slug minha_msg --skip-scrub
```

Escreve em `memory/messages/<slug>/srts/NN-slug.srt` in-place. JSON em stdout:

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

Renderização em duas passes:

**Pass 1 — amostragem de posição da face.** A 5 fps (padrão), roda o
detector MediaPipe BlazeFace short-range em cada frame amostrado.
Registra o centro do bounding-box (X e Y) da maior face detectada.
Fallback em ordem: MediaPipe Pose Landmarker (midpoint dos ombros pro X,
nariz pro Y), depois OpenCV Haar cascade, depois hold-last-position.
Lê o FPS nativo do source via `cv2.CAP_PROP_FPS` e usa esse pro loop
de leitura — necessário pro sync A/V em sources com fps != 30
(24, 23.976, 60).

**Suavização.** Média móvel de 2.5s das posições (X, Y) da face remove
jitter de detecção mantendo a câmera responsiva ao movimento real.

**Pass 2 — renderiza frame por frame.** Para cada frame do source:
1. Escala para altura `OUT_H × (1 + vertical_headroom)` (padrão 2400)
   preservando aspect, usando `cv2.INTER_LANCZOS4` (Lanczos preserva
   detalhe de alta frequência no upscale).
2. Interpola (X, Y) suavizados pro timestamp do frame atual.
3. Crop 1080×1920: X centrado no X da face (clamped), Y posicionado pro
   centro da face aterrissar em `face_y_target × OUT_H` (padrão 0.40 ≈
   regra dos terços — bias cinemático pra cima). Seta `face_y_target:
   null` no config pra desativar ajuste Y e preservar enquadramento do
   source.
4. Pipe de raw BGR frames pro ffmpeg no FPS nativo do source; um filtro
   `fps={OUT_FPS}` cuida da conversão pro rate de saída.

**Seleção de quality / codec.** `pick_video_encoder` retorna o argv do
encoder com base em `--quality` e `--codec`:

| Combo | Encoder | Notas |
|---|---|---|
| `auto h264` (padrão) | h264_videotoolbox @ 8 Mbps em Apple Silicon; libx264 CRF 18 preset slow no resto | Iteração rápida |
| `auto hevc` | hevc_videotoolbox @ 5 Mbps + tag hvc1 | Arquivos menores, rápido |
| `max h264` | libx264 -preset slower -crf 17, yuv420p | Encode em software qualidade de entrega |
| `max hevc` | libx265 -preset slower -crf 20, **yuv420p10le** (Main 10) + tag hvc1 | Entrega mais limpa e enxuta |

`--quality max` também insere uma filter chain
`hqdn3d=1.5:1.5:6:6, unsharp=...` antes do burn da legenda — mata ruído
de chroma de câmera-de-igreja com ISO alto e recupera parte da
crispness perdida no upscale.

**Mux de áudio.** Combina vídeo encodado com o segmento de áudio do
source (seekado via `-ss`/`-to`).

**Burn de legenda.** Aplica filtro ffmpeg `subtitles=` com `force_style`
de `config/style_presets/<preset>.txt`. Pule com `--no-subs`.

Grava `memory/messages/<slug>/renders/NN-slug.mp4`.

## 08_audio_normalize.py

```bash
./scripts/08_audio_normalize.py <slug> <cut_index> [--target-lufs -14] [--in-place]
```

Mede loudness integrado com pyloudnorm (ITU-R BS.1770-4), aplica
ganho pra acertar o LUFS alvo. Re-encoda áudio para AAC 192k, copia stream de vídeo.

`--in-place` sobrescreve o render original. Caso contrário grava um
sibling `.normalized.mp4`.

## pipeline.py / pipeline.sh / pipeline.bat

Orquestrador cross-platform. Mesmas flags em todo lugar — `pipeline.sh`
é um wrapper Unix que faz exec no `pipeline.py`; `pipeline.bat` faz o
mesmo pro Windows. Escolhe o que combinar com a memória muscular do seu
shell, ou invoca direto `python pipeline.py`.

```bash
# Ingest + transcribe + VAD + prepare propose-input
./scripts/pipeline.sh "https://youtube.com/watch?v=XXX"

# Renderiza índices específicos end-to-end (validate + SRT + render + normalize)
./scripts/pipeline.sh --render-cuts 1,2,4,7 --slug meu_sermao

# Só re-burn de legendas (depois de corrigir transcrição) sem re-tracking
./scripts/pipeline.sh --reburn-srt 3 --slug meu_sermao
```

### Flags de render

| Flag | O que faz |
|---|---|
| `--target {all,shorts,reels,tiktok}` | Alvo de entrega. `shorts` re-capa cortes em 60s (limite hard do YouTube Shorts). Padrão `all` usa a janela 60–90s. |
| `--quality {auto,max}` | `auto` (padrão) escolhe o encoder de hardware em Apple Silicon pra velocidade. `max` força libx264/libx265 `-preset slower` mais filter chain `hqdn3d + unsharp` pra output qualidade de entrega. |
| `--codec {h264,hevc}` | Codec de vídeo. Padrão `h264` é compatibilidade ampla. `hevc` (H.265) é ~40% menor na mesma qualidade visível, aceito por Reels/TikTok/Shorts desde 2022. `--quality max --codec hevc` entrega em 10-bit Main 10. |
| `--llm-scrub` | Roteia o scrub do SRT pelo `06b_scrub_srt --full-llm-review` — envia toda cue + snippet word-level do transcript por-cue pro LLM e aplica todos os fixes (não só os flaggados por regra). Precisa de `ANTHROPIC_API_KEY` ou `GROQ_API_KEY`. ~$0.01 por corte. |
| `--skip-scrub` | Pula o pass de scrub do SRT inteiro (CI / batch). |

```bash
# Master qualidade de entrega pra cliente pagante
./scripts/pipeline.sh --render-cut 3 --slug meu_sermao \
                      --quality max --codec hevc --llm-scrub

# Corte safe pra YouTube Shorts (força ≤60s)
./scripts/pipeline.sh --render-cuts 1,2 --slug meu_sermao --target shorts
```

## Layout de diretório por mensagem

A pipeline divide cada mensagem em **duas pastas visíveis** dentro do
repo e **uma pasta escondida de estado** dentro da instalação da skill:

```
<repo>/sources/<slug>/                    # visível — você coloca/baixa aqui
└── source.mp4                            # download do YouTube OU symlink do local

<repo>/renders/<slug>/                    # visível — cortes finais aparecem aqui
├── 01-tema_do_corte.mp4
├── 02-outro_beat.mp4
└── …                                     # prontos pra subir no Reels/TikTok

~/.claude/skills/sermon-cuts/memory/messages/<slug>/   # estado escondido
├── meta.json                             # URL/título/duração
├── transcript.json                       # transcrição word-level
├── vad.json                              # speech segments + cut candidates
├── propose_input.json                    # input combinado pro LLM
├── cuts_proposed.json                    # output do LLM (você cura aqui)
├── srts/NN-slug.srt                      # arquivos de legenda
└── corrections.txt                       # dict opcional de scrub por mensagem
```

A divisão é proposital: o que um humano vai navegar (source.mp4 que
você ingeriu, cortes prontos pra publicar) fica visível no topo do
repo. O que a pipeline lê/escreve entre runs (transcripts, intermediários)
fica na pasta escondida `memory/messages/`, pra as pastas visíveis não
ficarem poluídas.

### Overriding paths

Três env vars sobrescrevem os defaults:

- `SERMON_CUTS_SOURCES_DIR` — onde os source .mp4 vivem
- `SERMON_CUTS_RENDERS_DIR` — onde os cortes finais caem
- `SERMON_CUTS_MESSAGES_DIR` — onde o estado por-mensagem vive

Útil pra manter renders num HD externo ou numa pasta sincada de
Dropbox/iCloud.

### Migrando de um layout antigo

Instalações pré-2026-05 mantinham `source.mp4` e `renders/` dentro de
`memory/messages/<slug>/`. O `pipeline.sh doctor` detecta isso no
startup; rode a migration uma vez pra mover pros novos paths visíveis:

```bash
./scripts/pipeline.sh migrate --dry-run    # preview
./scripts/pipeline.sh migrate              # move de verdade
```

Idempotente e conservador — não sobrescreve arquivos existentes no
destino.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
