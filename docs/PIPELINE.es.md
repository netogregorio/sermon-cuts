# Walkthrough del pipeline

[English](PIPELINE.md) · [Português](PIPELINE.pt.md) · **Español**

Cada script escribe en `memory/messages/<slug>/` y es idempotente (re-ejecutar
es seguro y omite el trabajo hecho a menos que use `--force`).

## 01_ingest.py

```bash
./scripts/01_ingest.py <youtube-url-o-ruta-local> [--slug SLUG]
```

URL de YouTube → usa yt-dlp con format string `bestvideo[height>=1080]+
bestaudio/bestvideo+bestaudio/best`. Captura masters 1440p/2160p y
streams VP9/AV1 cuando están disponibles (~3-4× más eficientes que el
H.264 1080p de YouTube). Cap el límite superior con
`SERMON_CUTS_MAX_HEIGHT=1080` si el uso de disco importa.

Archivo local → enlaces simbólicos (o copia si el symlink falla — común
en Windows sin Developer Mode).

Tras la descarga, hace ffprobe al source y guarda resolución, fps,
codec y bitrate en `meta.json.source_quality`. Avisa cuando el source
está por debajo del piso práctico para entrega limpia:

- height < 1080 (cualquier upscale del render es con pérdida)
- bitrate < 2 Mbps (los artefactos de compresión de YouTube se notarán)
- fps < 24 (judder de movimiento)

Escribe:
- `memory/messages/<slug>/source.mp4`
- `memory/messages/<slug>/meta.json` (URL/ruta/título/duración + source_quality + source_quality_warnings)

Derivación del slug: desde el título del YouTube o nombre del archivo (convertido a snake_case).
Sobrescriba con `--slug`.

## 02_transcribe.py

```bash
./scripts/02_transcribe.py <slug> [--provider=youtube|groq] [--language=pt]
```

### YouTube (predeterminado, gratis, instantáneo)

Llama a `yt-dlp --write-auto-subs --skip-download` para obtener el archivo VTT de subtítulos automáticos
que YouTube genera para cada video público. Analiza marcas de tiempo a nivel de palabra
del VTT (esas etiquetas `<HH:MM:SS.mmm>` entre palabras).

### Groq (pagado-ish, mayor calidad)

Extrae audio (WAV mono 16kHz), sube a Groq Whisper-large-v3 con
`timestamp_granularities=["word"]`. Devuelve marcas de tiempo a nivel de palabra.
Necesita `GROQ_API_KEY` en env.

Salida (mismo formato para ambos):

```json
{
  "words": [
    {"text": "Eu", "start": 1.95, "end": 2.12, "type": "word"},
    {"text": " ", "start": 2.12, "end": 2.13, "type": "spacing"},
    ...
  ],
  "language": "pt",
  "_provider": "youtube-vtt"  // o "groq-whisper-large-v3"
}
```

## 03_vad_segments.py

```bash
./scripts/03_vad_segments.py <slug> [--min-silence 0.5]
```

Ejecuta [silero-vad](https://github.com/snakers4/silero-vad) en el audio
fuente (remuestreado a 16kHz mono). Detecta segmentos de habla → deriva
los silencios entre ellos → marca el punto medio de cada silencio ≥ 0.5s como
**punto de corte candidato** (lugares donde un corte no dividirá palabra/respiración).

Salida:

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

Empaqueta transcripción + VAD en un único `propose_input.json` y imprime
las rutas que el LLM (Claude) debe leer, más el prompt en
`prompts/propose_cuts.md`. **Este script no llama a un LLM** — solo
prepara entradas.

Se espera que el LLM escriba los cortes propuestos en
`memory/messages/<slug>/cuts_proposed.json`.

Esquema esperado para cada corte:

```json
{
  "n": 1,
  "slug": "filha_no_mercado",
  "start": 92.40,
  "end": 165.10,
  "duration_s": 72.7,
  "theme": "Relación vs misión — ilustración de la hija en el mercado",
  "hook": "Eu gosto de uma ilustração muito boa...",
  "development": "...",
  "conclusion": "Jesus pede que a gente vá COM ele, não pra ficar n'Ele",
  "coherence_score": 9.2,
  "tags": ["ilustracao", "relacionamento_com_deus"],
  "vad_aligned": true
}
```

Vea `prompts/propose_cuts.md` para la rúbrica completa.

## 05_validate_cut.py

```bash
./scripts/05_validate_cut.py <slug> <cut_index> [--write-back] [--max-extend-s 8]
```

Confirma que la última palabra del corte no es un final prohibido (configurable en
`config/render_defaults.yaml` — ej. "porque", "mas", "que", "para", "com",
"de"). Si lo es, intenta extender el final hasta el siguiente punto de corte candidato del VAD
dentro de `max-extend-s` segundos donde la palabra ya no esté prohibida.

`--write-back` aplica el parche al corte en `cuts_proposed.json`.

## 06_build_srt.py

```bash
./scripts/06_build_srt.py <slug> <cut_index>
```

Genera un SRT brand-styled desde las palabras de la transcripción en el rango del corte:

- 3-4 palabras por subtítulo, máx ~20 caracteres (configurable)
- Divide en la puntuación (`. ! ?` hard, `, ; :` soft si el subtítulo tiene ≥3 palabras)
- Divide en pausa ≥0.5s si el subtítulo tiene ≥3 palabras
- Desplazamiento consciente de palabra-función: si un subtítulo termina con "para"/"com"/"que"/etc.,
  desplaza al siguiente subtítulo (así los subtítulos nunca terminan en palabra-función)
- Capitaliza el primer subtítulo
- Quita la puntuación suave final del texto del subtítulo

Escribe `memory/messages/<slug>/srts/NN-slug.srt`.

## 06b_scrub_srt.py

```bash
./scripts/06b_scrub_srt.py <slug> <cut_index> [--agent-review]
                                              [--use-llm]
                                              [--full-llm-review]
                                              [--auto-apply]
                                              [--dry-run]
                                              [--corrections PATH]
```

Paso de lint que corre **entre `06_build_srt` y `07_render_track`**,
escaneando el SRT en busca de los patrones de error más comunes de las
auto-captions de YouTube (límites de frase con palabra perdida, vacilaciones
duplicadas, términos teológicos mal escritos). Permite corregir errores de
transcripción antes del burn-in en lugar de después — ahorra un re-encode
entero por typo.

### Qué busca

1. **`dropped_word_boundary`** — palabra funcional (en / que / de / etc.)
   inmediatamente antes de una palabra capitalizada que no es nombre propio.
   YouTube se comió una palabra en una frontera de oración.
       `"do que Mas não"`  ←  era en realidad  `"do que nós. Mas não"`
   Tiene whitelist de personajes/lugares bíblicos comunes y pronombres en
   portugués para que `"em Cristo"` y `"para Ele"` no falsifiquen positivo.

2. **`immediate_repetition`** — `\b(\w+)\s+\1\b` filtrado a vacilaciones
   conocidas (a, o, um, uma, que, eu, ele, ela, …) y palabras cortas.
   Salta repetición estilística separada por coma como `"cansa, cansa"`.

3. **`forbidden_ending`** — re-verifica la lista
   `cut_validation.forbid_endings` por subtítulo (no solo en la frontera
   del corte como `05_validate_cut.py`). Solo reporta; el fix suele ser
   mover la palabra final al siguiente subtítulo, mejor hecho a mano.

4. **`dictionary`** — si existe `memory/messages/<slug>/corrections.txt`,
   aplica pares `wrong=right` automáticamente (uno por línea, `#` para
   comentarios). Útil para fixes recurrentes:
   ```
   Quisto=Cristo
   Espirito=Espírito
   ```

### Tres caminos de review

| Camino | Cuándo usar |
|---|---|
| **`--agent-review`** (default en non-TTY con sospechosos) | El orquestador (Claude Code / Cursor / …) está leyendo stdout. 06b emite JSON estructurado con texto del cue prev/next, snippet word-level del transcript alrededor de cada sospechoso, y la ruta a `prompts/scrub_srt.md`. El agente lee el prompt, decide fixes, aplica vía Edit tool, y reanuda el pipeline con `--skip-scrub`. |
| **`--use-llm`** | Review LLM-asistido **solo en cues flaggeados por reglas** (cron, nightly, sin agente atado). Llama Anthropic Claude (prefiere `ANTHROPIC_API_KEY`) o Groq Llama (`GROQ_API_KEY` fallback). Barato pero pierde errores que las heurísticas no flaggearon. |
| **`--full-llm-review`** | Review LLM del **SRT completo**. Envía cada cue + snippet word-level del transcript por-cue al LLM en una llamada y aplica todos los fixes retornados. Atrapa errores que las reglas no pueden hacer pattern-match (typos de palabras juntas `paraa`, artículos equivocados `na seu`, letras faltantes `pentec`, nombres propios en minúscula, cadenas de filler, duplicados de VTT). Costo ~$0.01/corte en Claude Haiku 4.5. Los fixes de forbidden-ending se manejan vía edits pareados de cue (strip de uno, prepend al siguiente). Mismo orden de preferencia de API key que `--use-llm`. |
| **`--auto-apply`** | Solo reglas, confianza ≥ 0.85. En la práctica solo colapsa vacilaciones silenciosamente. Modo más barato. |

### Otros modos

| Flag | Comportamiento |
|---|---|
| (ninguna, TTY)  | review interactivo — prompt `y/n/edit/skip` por sospechoso |
| `--dry-run`     | solo reporta, nunca escribe el SRT |

`pipeline.sh` integra este paso automáticamente (interactivo en TTY,
JSON `--agent-review` en non-TTY para que el agente orquestador actúe).
Salta con `--skip-scrub`:

```bash
./scripts/pipeline.sh --render-cuts 1,2 --slug mi_msg --skip-scrub
```

Escribe en `memory/messages/<slug>/srts/NN-slug.srt` in-place. JSON en stdout:

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

Renderizado de dos pases:

**Pase 1 — muestreo de posición facial.** A 5 fps (predeterminado), ejecuta
el detector MediaPipe BlazeFace short-range en cada frame muestreado.
Registra el centro de bounding-box (X e Y) de la cara más grande detectada.
Fallback en orden: MediaPipe Pose Landmarker (midpoint de hombros para X,
nariz para Y), luego Haar cascade de OpenCV, luego hold-last-position. Lee
el FPS nativo del source vía `cv2.CAP_PROP_FPS` y lo usa para el loop de
lectura — requerido para sync A/V con sources non-30fps (24, 23.976, 60).

**Suavizado.** Media móvil sobre 2.5s de las posiciones (X, Y) de la cara
elimina el jitter de detección manteniendo la cámara responsiva al
movimiento real.

**Pase 2 — renderiza frame por frame.** Por cada frame del source:
1. Escala a altura `OUT_H × (1 + vertical_headroom)` (default 2400)
   preservando aspecto, usando `cv2.INTER_LANCZOS4` (Lanczos preserva
   detalle de alta frecuencia en el upscale).
2. Interpola (X, Y) suavizado para el timestamp del frame actual.
3. Recorta 1080×1920: X centrado en la X de la cara (clamped), Y
   posicionado para que el centro de la cara caiga en
   `face_y_target × OUT_H` (default 0.40 ≈ regla de los tercios — sesgo
   cinemático hacia arriba). Setea `face_y_target: null` en el config
   para deshabilitar el ajuste Y y preservar el encuadre del source.
4. Pipe de raw BGR frames a ffmpeg al FPS nativo del source; un filtro
   `fps={OUT_FPS}` maneja la conversión al rate de salida.

**Selección de calidad / codec.** `pick_video_encoder` retorna el argv del
encoder basado en `--quality` y `--codec`:

| Combo | Encoder | Notas |
|---|---|---|
| `auto h264` (default) | h264_videotoolbox @ 8 Mbps en Apple Silicon; libx264 CRF 18 preset slow en otros | Iteración rápida |
| `auto hevc` | hevc_videotoolbox @ 5 Mbps + tag hvc1 | Archivos más chicos, rápido |
| `max h264` | libx264 -preset slower -crf 17, yuv420p | Encode por software calidad de entrega |
| `max hevc` | libx265 -preset slower -crf 20, **yuv420p10le** (Main 10) + tag hvc1 | Entrega más chica + más limpia |

`--quality max` también inserta una filter chain `hqdn3d=1.5:1.5:6:6,
unsharp=...` antes del burn de subtítulo — mata el ruido de chroma de
cámara-de-iglesia con ISO alto y recupera parte de la nitidez perdida
en el upscale.

**Mux de audio.** Combina video codificado con el segmento de audio del
source (seek vía `-ss`/`-to`).

**Burn de subtítulos.** Aplica el filtro ffmpeg `subtitles=` con
`force_style` de `config/style_presets/<preset>.txt`. Omita con
`--no-subs`.

Escribe `memory/messages/<slug>/renders/NN-slug.mp4`.

## 08_audio_normalize.py

```bash
./scripts/08_audio_normalize.py <slug> <cut_index> [--target-lufs -14] [--in-place]
```

Mide loudness integrado con pyloudnorm (ITU-R BS.1770-4), aplica
ganancia para alcanzar el LUFS objetivo. Re-codifica audio a AAC 192k, copia stream de video.

`--in-place` sobrescribe el render original. De lo contrario escribe un
hermano `.normalized.mp4`.

## pipeline.py / pipeline.sh / pipeline.bat

Orquestador cross-platform. Mismos flags en todas partes — `pipeline.sh`
es un wrapper Unix que hace exec hacia `pipeline.py`; `pipeline.bat`
hace lo mismo para Windows. Elige el que encaje con tu memoria muscular
de shell, o invoca `python pipeline.py` directamente.

```bash
# Ingest + transcribe + VAD + prepare propose-input
./scripts/pipeline.sh "https://youtube.com/watch?v=XXX"

# Renderiza índices específicos end-to-end (validate + SRT + render + normalize)
./scripts/pipeline.sh --render-cuts 1,2,4,7 --slug mi_sermon

# Solo re-burn de subtítulos (después de corregir transcripción) sin re-tracking
./scripts/pipeline.sh --reburn-srt 3 --slug mi_sermon
```

### Flags de render

| Flag | Qué hace |
|---|---|
| `--target {all,shorts,reels,tiktok}` | Target de entrega. `shorts` re-capa los cortes a 60s (hard limit de YouTube Shorts). Default `all` usa la ventana 60–90s. |
| `--quality {auto,max}` | `auto` (default) elige el encoder de hardware en Apple Silicon para velocidad. `max` fuerza libx264/libx265 `-preset slower` más una filter chain `hqdn3d + unsharp` para output calidad de entrega. |
| `--codec {h264,hevc}` | Codec de video. Default `h264` es la compatibilidad más amplia. `hevc` (H.265) es ~40% más chico a la misma calidad visible, aceptado por Reels/TikTok/Shorts desde 2022. `--quality max --codec hevc` entrega en 10-bit Main 10. |
| `--llm-scrub` | Rutea el scrub del SRT a través de `06b_scrub_srt --full-llm-review` — envía cada cue + snippet word-level del transcript por-cue al LLM y aplica todos los fixes (no solo los flaggeados por reglas). Necesita `ANTHROPIC_API_KEY` o `GROQ_API_KEY`. ~$0.01 por corte. |
| `--skip-scrub` | Salta el paso de scrub del SRT por completo (CI / batch). |

```bash
# Master calidad de entrega para cliente que paga
./scripts/pipeline.sh --render-cut 3 --slug mi_sermon \
                      --quality max --codec hevc --llm-scrub

# Corte safe para YouTube Shorts (fuerza ≤60s)
./scripts/pipeline.sh --render-cuts 1,2 --slug mi_sermon --target shorts
```

## Layout de directorio por mensaje

El pipeline divide cada mensaje en **dos carpetas visibles** dentro
del repo y **una carpeta oculta de estado** dentro de la instalación
del skill:

```
<repo>/sources/<slug>/                    # visible — colocas/descargas aquí
└── source.mp4                            # descarga de YouTube O symlink local

<repo>/renders/<slug>/                    # visible — cortes finales aparecen aquí
├── 01-tema_del_corte.mp4
├── 02-otro_beat.mp4
└── …                                     # listos para subir a Reels/TikTok

~/.claude/skills/sermon-cuts/memory/messages/<slug>/   # estado oculto
├── meta.json                             # URL/título/duración
├── transcript.json                       # transcripción word-level
├── vad.json                              # segmentos de habla + cut candidates
├── propose_input.json                    # input combinado para el LLM
├── cuts_proposed.json                    # output del LLM (tú lo curas)
├── srts/NN-slug.srt                      # archivos de subtítulo
└── corrections.txt                       # dict opcional de scrub por mensaje
```

La división es deliberada: lo que un humano navega (el source.mp4 que
ingeriste, los cortes listos para publicar) queda visible en el top
del repo. Lo que el pipeline lee/escribe entre runs (transcripts,
intermedios) queda en la carpeta oculta `memory/messages/`.

### Override de rutas

Tres env vars sobrescriben los defaults:

- `SERMON_CUTS_SOURCES_DIR` — dónde viven los source .mp4
- `SERMON_CUTS_RENDERS_DIR` — dónde caen los cortes finales
- `SERMON_CUTS_MESSAGES_DIR` — dónde vive el estado por-mensaje

### Migrando desde un layout antiguo

Instalaciones pre-2026-05 mantenían `source.mp4` y `renders/` dentro
de `memory/messages/<slug>/`. `pipeline.sh doctor` detecta esto al
inicio; corre la migration una vez para mover a las nuevas rutas:

```bash
./scripts/pipeline.sh migrate --dry-run    # preview
./scripts/pipeline.sh migrate              # mover de verdad
```

Idempotente y conservador — no sobreescribe archivos existentes en
destino.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
