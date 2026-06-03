# Changelog

[English](CHANGELOG.md) · [Português](CHANGELOG.pt.md) · **Español**

## 0.2.0 — Cross-platform + calidad de entrega (2026-06-03)

### Cross-platform

- **Soporte Windows, nativo.** Nuevo `pipeline.py` (orquestrador Python
  cross-platform) reemplaza la lógica bash-only de `pipeline.sh`. `pipeline.sh`
  y `pipeline.bat` ahora son wrappers finos que hacen exec hacia él — la
  memoria muscular Unix sigue funcionando, y los usuarios de Windows ganan
  la misma CLI.
- **`install.py`** porta el instalador bash a Python cross-platform: venv,
  linking del skill (symlink → junction `mklink /J` → fallback de copy),
  clave GROQ en `~/.env`, selección de preset de fuente, pre-download de
  modelos MediaPipe, doctor check. `install.sh` e `install.bat` lo envuelven
  para el bootstrap específico de cada plataforma (deps del sistema + clone
  del repo).
- **`resolve_ffmpeg` cross-platform**: `shutil.which("ffmpeg")` para lookup
  en PATH más paths de fallback en Windows (`C:\ffmpeg\bin\`, Program Files).

### Reglas de corte (alineadas con brief de creador)

- **Ventana de duración 60–90s** por defecto. El antiguo cap de 25–60s estaba
  basado en retención de short-form de inicios de los 2020s; Reels (90s
  nativos) y TikTok (sin cap relevante) aceptan la ventana más ancha. YouTube
  Shorts aún tiene hard-cap en 60s — usa `--target shorts` para re-capar.
- **Detección de inicio en medio de la frase**: `05_validate_cut` ahora avisa
  cuando un corte empieza en una palabra-función (`mas`, `porque`, `então`,
  `quando`, `se`, ...) o cuando la palabra previa no termina en `.!?`.
  Solo warn — el start nunca se mueve automáticamente (la intención del
  curador es sagrada).
- **forbid_endings extendido** con `então`, `quando`, `se` — los tres abren
  cláusulas incompletas.
- **Prompts de scrub** (en/pt/es) endurecidos con regla inviolable contra
  alterar significado teológico durante la limpieza de transcripción.

### Calidad de imagen

- **Fix del techo del source** ([01_ingest.py]): format string de yt-dlp
  ahora prefiere ≥1080p en cualquier codec (antes: solo ≤1080p mp4).
  Captura masters 1440p/2160p y streams VP9/AV1 (~3-4× más eficientes que
  el H.264 1080p de YouTube). Cap con `SERMON_CUTS_MAX_HEIGHT`.
- **Probe del source + warn** en el ingest. ffprobe guardado en `meta.json
  .source_quality`; avisa cuando el source es <1080p, <2 Mbps o <24 fps.
- **Upscale Lanczos**: `cv2.INTER_LANCZOS4` para el escalado a 1920
  (reemplaza `INTER_AREA`, que era la elección equivocada en upscale).
- **Flag `--codec hevc`** agrega paths H.265 vía `hevc_videotoolbox`
  (auto) o `libx265` (max). ~40% más chicos al mismo nivel de calidad
  visible. `--quality max --codec hevc` entrega 10-bit Main 10
  (`yuv420p10le`) con tag `hvc1` para compatibilidad en el ecosistema Apple.
- **Tracking sample_fps 2 → 5** para follow facial más apretado en
  predicadores energéticos (~2-3s extra por corte en Apple Silicon).
- **Encuadre vertical regla de los tercios**: centro de la cara
  posicionado al 40% de la altura de salida (configurable vía
  `tracking.face_y_target`). Source escalado a `OUT_H × 1.25` para dar
  headroom Y a la ventana de crop.
- **Filter chain de `--quality max`**: `hqdn3d=1.5:1.5:6:6, unsharp=5:5:0.6`
  antes del burn de subtítulo. Mata ruido de chroma de cámara-de-iglesia
  con ISO alto; recupera la crispness perdida en el upscale. Saltado en
  modo `auto` (iteración rápida).

### Sync + transcripción

- **Fix de desync A/V** ([07_render_track.py]): el renderer ahora lee al
  fps nativo del source y usa un filtro `fps={OUT_FPS}` para conversión
  de rate de salida. El loop antiguo asumía source a 30fps y leía ~25% más
  contenido en sources a 23.976fps, acelerando el video por delante del
  audio. Verificado en delta: 6.6ms vs ~16s pre-fix.
- **Robustez del provider YouTube** ([02_transcribe.py]): el path
  `--provider=youtube` acaparaba captions válidas cuando yt-dlp retornaba
  429 en un sub-language hermano. Reescrito para recorrer variantes de
  idioma (`pt-orig` → `pt-BR` → `pt` → `pt-PT`) una por una, parando en la
  primera que entrega VTT. El exit code de yt-dlp ahora es advisory — si
  un VTT parseable está en disco, lo usamos.
- **Preferencia auto-provider invertida**: sources URL de YouTube ahora
  default a `--provider=youtube` aún cuando `GROQ_API_KEY` está seteada.
  Las captions son gratis, instantáneas, y el nuevo `--full-llm-review`
  atrapa errores de transcripción mejor que el round-trip antiguo de Groq.

### Scrub

- **`--full-llm-review`** ([06b_scrub_srt.py]): limpieza LLM del SRT
  completo. Envía cada cue + snippet word-level del transcript por-cue al
  LLM en una llamada y aplica todos los fixes retornados. Atrapa errores
  que las reglas heurísticas no pueden hacer pattern-match: typos de
  palabras juntas (`paraa festa`), artículos equivocados (`na seu próprio
  idioma`), letras faltantes (`pentec`), nombre propio en minúscula,
  cadenas de filler (`é a é a tipo assim`), duplicados de VTT (`muito
  muito`). Costo en Claude Haiku 4.5: ~$0.01 por corte. Fix de
  forbidden-ending vía edits pareados de cue.
- **`pipeline.sh --llm-scrub`** conecta el nuevo scrub al orquestrador.

## 0.1.0 — Release inicial (2026-05-23)

Primer release público. Pipeline end-to-end:

- `01_ingest.py` — yt-dlp o archivo local → source administrado
- `02_transcribe.py` — YouTube VTT (predeterminado) o Groq Whisper, a nivel de palabra
- `03_vad_segments.py` — detección de pausa silero-vad → candidatos de corte
- `04_propose_cuts.py` — prepara input del LLM para la propuesta de corte
- `05_validate_cut.py` — auto-extiende cortes que terminan en medio del pensamiento
- `06_build_srt.py` — subtítulos brand-style (3-4 palabras, function-word shift)
- `07_render_track.py` — face tracking MediaPipe + smooth pan + burn de subtítulos
- `08_audio_normalize.py` — pyloudnorm a -14 LUFS
- `pipeline.sh` — orquestador

Brand style predeterminado: Outfit Black, oro `#fbc531`, outline negro `0.8`,
sentence case, posición de pie de página. Vertical 1080×1920 @ 30fps.

Incluye un `SKILL.md` para integración con Claude Code.

Testeado con dos sermones en PT-BR (~28min cada uno):
- *Vinde a mim* (Mateo 11) — 12 candidatos de corte propuestos, 8 renderizados.
- *Derrubando as fortalezas da mente* — 10 cortes renderizados.

Case studies de muestra en `examples/`.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
