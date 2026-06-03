# Troubleshooting

[English](TROUBLESHOOTING.md) · [Português](TROUBLESHOOTING.pt.md) · **Español**

Cuando algo se rompe. La mayoría de estos casos los golpeamos
personalmente durante dogfooding en sermones reales — el fix queda.

Si no encuentras tu problema aquí, corre `./scripts/pipeline.sh doctor`
(macOS/Linux) o `scripts\pipeline.bat doctor` (Windows) primero —
verifica ffmpeg, yt-dlp, deps Python, fuentes y el layout de symlinks
del skill, y te dice qué está mal antes de gastar un render.

---

## Instalación & setup

### `[AVFilterGraph] No such filter: 'subtitles'`

**Por qué**: la formula predeterminada `ffmpeg` de Homebrew (v8.x+) se
envía sin `libass`, que se requiere para quemar subtítulos en video. El
pipeline detecta esto y cae al fallback si puede — pero a veces el
fallback no está disponible.

**Fix**: instala `ffmpeg-full` de Homebrew:
```bash
brew install ffmpeg-full
```
El pipeline auto-detecta `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` en
la siguiente ejecución. Alternativa: setea
`FFMPEG_BIN=/ruta/a/ffmpeg-con-libass` en tu shell.

### `ffmpeg: command not found`

No tienes ffmpeg instalado. macOS: `brew install ffmpeg-full`.
Ubuntu/Debian: `sudo apt install ffmpeg`. Verifica: `ffmpeg -version`.

### `yt-dlp: command not found`

Lo mismo. macOS: `brew install yt-dlp`. Ubuntu/Debian:
`sudo apt install yt-dlp` (o `pip install yt-dlp`). Verifica:
`yt-dlp --version`.

### `python3 -c "import mediapipe"` falla

No has corrido `pip install -r requirements.txt` aún, o lo ejecutaste
en un venv Python diferente al que llama los scripts. Activa el venv
correcto primero, y reinstala.

### Scripts del skill no se encuentran (`ImportError: _common`)

La instalación del skill crea symlinks de `~/.claude/skills/sermon-cuts/`
al repo. Si algo salió mal:

```bash
ls -la ~/.claude/skills/sermon-cuts/
# Debe mostrar scripts → <repo>/scripts como symlink
```

Si no:
```bash
mkdir -p ~/.claude/skills/sermon-cuts
ln -sf "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -sf "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -sf "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
```

---

## Ingest & fuente

### `yt-dlp` falla con "video unavailable" o 403

El video es privado, region-locked, con restricción de edad o
removido. Intenta con `--cookies-from-browser=chrome` (o
firefox/safari) para que yt-dlp use tu sesión de login:

```bash
yt-dlp --cookies-from-browser=chrome <url>
```

Si es un livestream que acaba de terminar, espera una hora a que
YouTube finalice el archivo de video.

### `ZeroDivisionError` en `07_render_track.py` durante pass 1

OpenCV no puede leer las dimensiones del video fuente — devuelve 0×0.
Dos causas comunes:

1. **El source.mp4 está roto o codec equivocado.** Verifica con
   `ffprobe -v error -show_entries stream=width,height <source>`. Debe
   imprimir dims no-cero. Si no, re-codifica con ffmpeg primero.
2. **El symlink a source.mp4 está colgando.** Comprueba que
   `sources/<slug>/source.mp4` resuelve a un archivo real:
   ```bash
   ls -la sources/<slug>/source.mp4    # debe mostrar el symlink
   readlink sources/<slug>/source.mp4   # debe imprimir ruta real
   ```
   Si no, recrea el symlink.

### `source não encontrado: .../sources/<slug>/source.mp4`

Ejecutaste un render antes del ingest. Ejecuta
`./scripts/01_ingest.py <source> --slug <slug>` primero, o usa el
orquestador `pipeline.sh <source>`.

---

## Transcripción

### `GROQ_API_KEY não configurada`

Pasaste `--provider=groq` pero no seteaste la clave. Obtén una gratis
en [console.groq.com/keys](https://console.groq.com/keys) y agrega a tu
shell o a `~/.env`:

```bash
echo 'GROQ_API_KEY=gsk_tu_clave_aqui' >> ~/.env
```

O solo usa `--provider=youtube` (gratis, sin clave, ligeramente menos
preciso).

### VTT de YouTube tiene palabras obviamente dropeadas

Pasa de vez en cuando en los auto-subtítulos de YouTube, especialmente
en límites de frase: *"superestimamos a Mas"* debería ser
*"superestimamos a missão. Mas"*. El pipeline atrapa muchos de estos:

1. **`06b_scrub_srt`** detecta el patrón `palabra-función +
   palabra-capitalizada` y lo marca para revisión.
2. **Detección de `semantic_gap`** marca cues donde la duración es
   larga pero pocas palabras fueron capturadas (probablemente contenido
   dropeado).
3. **`--use-llm`** ejecuta una pass asistida por LLM sobre el SRT
   completo contra el transcript para proponer correcciones.

Si sigues golpeando errores de transcripción, re-ejecuta con
`--provider=groq` para más precisión.

### "Cut #N tiene 0 cues" en el SRT

El rango de tiempo del corte no se solapa con ninguna palabra en la
transcripción. O los tiempos del corte están mal (revisa
`cuts_proposed.json`) o la transcripción falló silenciosamente para
ese segmento. Re-ejecuta `02_transcribe.py` con `--force`.

---

## Propuestas & validación de cortes

### Cortes propuestos por LLM son todos malos / fuera de tema

Causa más común: la transcripción tiene ruido que el LLM captó
(anuncios, oración, breaks de música). Dos fixes:

1. **Cura el transcript primero** — abre `transcript.json`, borra
   rangos de palabras de las secciones de ruido, guarda, re-ejecuta
   `04_propose_cuts.py`.
2. **Ajusta el prompt** — `prompts/propose_cuts.md` tiene la rúbrica
   de scoring. Si tu audiencia o estilo difiere de un sermón brasileño
   típico, edita la sección de preferencias suaves.

### Corte termina en medio del pensamiento ("...porque", "...para")

`05_validate_cut.py` debería atrapar esto y extender el final. Si no:
- El final no pudo ser extendido dentro de `--max-extend-s`
  (predeterminado 8s).
- Pasa `--max-extend-s 20` e intenta de nuevo.
- O edita manualmente `cuts_proposed.json` para setear nuevo `end`.

### Corte #N tiene warning de duración (>60s o <25s)

Las plataformas short-form (Reels, Shorts, TikTok) penalizan >60s y no
retienen <25s. O:
- Re-propón los cortes (ejecuta `04_propose_cuts.py` de nuevo — el
  prompt ahora tiene 25-60s como ventana dura)
- Ajusta manualmente `end` en `cuts_proposed.json`
- Divide un corte largo en dos con hooks separados

---

## Render & subtítulos

### Video renderizado se ve blanco/negro en macOS Preview

macOS Preview se atasca en verticals H.264 cuando la metadata BT.709
no está taggeada. El pipeline taggea correcto en render, pero si
re-codificas en otro lado, puedes perderlo. Re-tag in place (~2
segundos, sin pérdida de calidad):

```bash
ffmpeg -y -i input.mp4 -c copy \
  -bsf:v "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1" \
  -movflags +faststart fixed.mp4 && mv fixed.mp4 input.mp4
```

Testeado: abre limpio en Preview, QuickTime, Instagram, TikTok.
**Nota**: QuickTime y VLC siempre funcionan — solo Preview es exigente.

### Subtítulos no aparecen en el video renderizado

Tres causas posibles:

1. **libass no está en ffmpeg** — ver el error del filtro `'subtitles'`
   arriba.
2. **Fuente no instalada** — el predeterminado es `arial-black` que
   viene en macOS/Windows/mayoría de Linux. Si cambiaste a
   `outfit-black` sin instalar la fuente, libass cae a fuente
   predeterminada. Instala Outfit:
   [fonts.google.com/specimen/Outfit](https://fonts.google.com/specimen/Outfit)
3. **Archivo SRT vacío o malformado** — abre
   `memory/messages/<slug>/srts/NN-slug.srt` y verifica que tiene cues.

### Subtítulo parpadea / timing equivocado

El SRT se generó contra una transcripción diferente al audio del render
final. Regenera:
```bash
./scripts/06_build_srt.py <slug> <n>
./scripts/pipeline.sh --reburn-srt <n> --slug <slug>
```

### `{\fs22\b1}` aparece literalmente como texto en mi SRT exportado

Es markup ASS intencional para el burn (le da un boost de tamaño a la
primera cue). Es invisible cuando libass lo renderiza en video, pero
aparece como texto si re-subes el SRT a YouTube CC o auto-subtítulos
de Instagram. Strip para export:

```bash
./scripts/export_srt.py <slug> <n>
# Escribe un .clean.srt hermano con todos los bloques {...} removidos.
```

---

## Audio

### "Possible clipped samples in output" / audio suena distorsionado

El normalizer viejo (basado en pyloudnorm) clipeaba al aplicar gain
grande a sources bajos. El nuevo `08_audio_normalize.py` usa el filtro
`loudnorm` de ffmpeg con true-peak limiter — clipping no debería
suceder en el predeterminado `--true-peak-db -1.5`.

Si aún oyes distorsión:
1. Verifica que estás en el normalizer nuevo (el script importa
   `loudnorm`, no `pyloudnorm`)
2. Intenta target más bajo: `--target-lufs -16 --true-peak-db -2.0`

### Audio fuera de sync con video

ffmpeg debería manejar esto automáticamente. Si lo golpeas:
- Re-extrae source: `01_ingest.py <slug> --force`
- Asegúrate que source.mp4 tiene timing estándar (ejecuta `ffprobe`
  y revisa `start_time != 0`)

---

## Output

### MP4 renderizado muy grande para Instagram (>100 MB)

El render predeterminado es alta calidad (CRF 18, preset slow).
Baja un poco la calidad para menor tamaño — edita
`config/render_defaults.yaml`:
```yaml
video:
  crf: 22       # era 18 — número menor = mayor calidad + archivo mayor
  preset: fast  # era slow — encode más rápido, archivo poco más grande
```

O convierte después:
```bash
ffmpeg -i grande.mp4 -c:v libx264 -crf 24 -preset medium pequeño.mp4
```

### Face tracking fue al lado equivocado / cortó persona equivocada

MediaPipe elige la cara más grande en cada frame. Si hay dos oradores
o alguien atraviesa, puede driftar. Opciones:

1. **Re-ejecuta con pose-fallback** (predeterminado): el pipeline ya
   usa midpoint de hombros cuando face detection falla.
2. **Pin manual de la posición X**: abre `cuts_proposed.json` y agrega
   campo `"crop_x_norm": 0.5` (0 = borde izquierdo, 1 = borde derecho).
   El render usa ese X fijo en vez de tracking.
3. **Cambia a Haar cascade** (menos preciso pero más predecible):
   setea `tracking.detector: haar` en `config/render_defaults.yaml`.

---

## Específico de Windows

### `'mklink' is not recognized` durante install.bat

`install.bat` usa `mklink /J` para crear un directory junction cuando
no hay symlinks disponibles (sin admin / Developer Mode). En Windows 7
o con cmd.exe reemplazado por una shell no-estándar, `mklink` puede
faltar. Workarounds:

1. Habilita Developer Mode (Configuración → Actualización y Seguridad
   → Para Programadores → Modo Programador), lo que permite a
   `install.py` usar symlinks reales vía `Path.symlink_to` de Python.
   Sin necesidad de admin.
2. Ejecuta install.bat desde un cmd.exe de Admin.
3. Cae a modo copy — `install.py` copiará los directorios del skill en
   vez de enlazarlos (usa más disco y no rastrea updates futuros del
   repo, pero funciona sin admin).

### `'ffmpeg' is not recognized as an internal or external command`

ffmpeg no está en PATH o no está instalado. La detección de
`install.py` revisa PATH más `C:\ffmpeg\bin\`,
`C:\Program Files\ffmpeg\bin\` y la variante Program Files (x86).
Elige uno:

```cmd
winget install Gyan.FFmpeg
scoop install ffmpeg
choco install ffmpeg
```

O descarga manualmente desde [ffmpeg.org](https://ffmpeg.org/download.html),
descomprime en `C:\ffmpeg\`, y `resolve_ffmpeg` lo encontrará sin
editar el PATH.

### Instalación de MediaPipe falla con `Microsoft Visual C++ 14.0 or greater is required`

Algunas wheels de MediaPipe necesitan las build tools de MSVC. Instala
las [Visual Studio Build Tools](https://aka.ms/vs/17/release/vs_buildtools.exe)
(elige el workload "Desktop development with C++"), luego re-ejecuta
`pip install -r requirements.txt`. La mayoría de usuarios no golpean
esto — MediaPipe envía wheels prebuilt para Python 3.10–3.12 en
Windows.

### Rutas largas causan `FileNotFoundError`

Windows tiene por default un límite de 260 caracteres en path. La
instalación del skill en
`%USERPROFILE%\.claude\skills\sermon-cuts\memory\messages\<slug-largo>\...`
puede golpearlo con nombres de sermón profundamente anidados. Habilita
rutas largas:

```cmd
reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem ^
  /v LongPathsEnabled /t REG_DWORD /d 1 /f
```

O setea `SERMON_CUTS_MESSAGES_DIR=D:\sc` (o similar path corto) en tu
entorno para mantener las rutas cortas.

---

## Doctor del pipeline

En la duda:
```bash
./scripts/pipeline.sh doctor      # macOS / Linux
scripts\pipeline.bat doctor       # Windows
```

Verifica: ffmpeg + libass, yt-dlp, deps Python, disponibilidad de
fuente, layout de symlink del skill, validez del config. Imprime ✓
verde para lo que funciona y ✗ rojo + hint para lo que no.

---

## ¿Aún roto?

- [INSTALL.es.md](INSTALL.es.md) — re-verifica instalación
- [FAQ.es.md](FAQ.es.md) — preguntas comunes de workflow
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  abre uno con la salida completa del error, tu SO y `ffmpeg -version`
- Contacto personal: [netogregorio.com](https://netogregorio.com)

---

Por [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
