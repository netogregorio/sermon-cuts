# Cortes de Sermón

[English](README.md) · [Português](README.pt.md) · **Español**

> **Skill para Claude, Cursor y otros agentes de IA** que transforma videos
> largos de predicación, sermón, conferencia o enseñanza en cortes verticales
> listos para publicar en Reels, Shorts y TikTok — ya encuadrados, subtitulados
> y con audio nivelado. Pega el link de YouTube. Elige tus momentos favoritos.
> Recibe los cortes.

---

## Lo que obtienes

Tiras un mensaje de 30, 40, hasta 60 minutos — tu predicación, tu conferencia,
tu live — y sales con una carpeta de **shorts verticales listos para subir**.
Cada uno:

- Reencuadrado vertical (1080×1920) con el predicador centrado, suave
- Subtitulado en tu estilo de marca — texto dorado, contorno limpio, sin MAYÚSCULAS
- Balanceado al loudness estándar de las plataformas para sonar bien en Insta y TikTok
- Numerado, nombrado y organizado para que sepas qué publicar y cuándo

Lo que era una noche entera de domingo en CapCut se convierte en
**~5 minutos de curación**. Tú decides qué publicas. El pipeline hace el resto.

---

## Hecho para quien predica la Palabra

La mayoría de las herramientas de cortes para short-form están hechas para
marketeros vendiendo zapatillas. Esta está hecha para **pastores, predicadores,
evangelistas, maestros, creadores de contenido cristiano** — gente cuyo mensaje
merece más que una tarde apurada en Premiere.

Ya sabe:

- Que un buen corte necesita un **hook**, un **desarrollo** y una **conclusión** —
  no solo una rebanada aleatoria de 60 segundos de alguien hablando
- Que un corte no puede terminar con "porque…" ni con "pero…" — tiene que aterrizar
- Que la fuente del subtítulo importa, que el nivel de audio importa, que el
  encuadre del rostro del predicador en el frame vertical importa
- Que **tú** eres quien elige los cortes finales — la IA propone, tú decides

Nació con sermones en portugués en mente, pero funciona en cualquier idioma
(`--language=en`, `pt`, `es`, etc).

---

## Úsalo como skill en tu editor de IA

El pipeline completo viene empaquetado como skill de
[Claude Code](https://claude.com/claude-code) — o sea, hablas con tu asistente
de IA tipo:

> *"corta esta predicación: https://youtube.com/watch?v=…"*
> *"haz 8 cortes verticales de este mensaje para Instagram"*
> *"separa los mejores momentos de este video para Reels"*

…y el agente se encarga de la transcripción, la propuesta de cortes, el
seguimiento facial, los subtítulos, la normalización de audio y el render.
Tú solo entras en la parte que importa: **elegir cuáles momentos de tu mensaje
merecen volverse contenido**.

Funciona igual con **Cursor**, **Cline**, **Aider** o cualquier IDE/agente que
lea un `SKILL.md` y ejecute scripts.

---

## Instala — elige tu camino

Corre en **macOS, Linux y Windows** (Windows nativo desde v0.2.0 — no
requiere WSL).

### 🟢 Lo más fácil: un comando en cualquier terminal

**macOS / Linux** (bash):
```bash
curl -fsSL https://onetogregorio.github.io/sermon-cuts/install.sh | bash
```

**Windows** (PowerShell o cmd):
```cmd
winget install Python.Python.3.12 Git.Git
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
%USERPROFILE%\code\sermon-cuts\scripts\install.bat
```

Ambos instaladores detectan tu SO, instalan ffmpeg/yt-dlp/Python (auto en
macOS/Linux vía Homebrew/apt; instrucciones impresas en Windows), clonan
el repo, crean un venv Python, enlazan el skill en
`~/.claude/skills/sermon-cuts/` (symlink → junction → fallback de copy en
Windows), opcionalmente configuran Groq + Outfit, y corren health check
al final. **Se puede re-ejecutar sin riesgo** — no sobrescribe nada
existente.

### 🟡 A través de tu editor de IA (Claude Code, Cursor, Codex…)

Pega este prompt en cualquier editor con acceso al terminal:

> Instala el skill **Sermon Cuts** (https://github.com/onetogregorio/sermon-cuts)
> en mi máquina. Guíame por estos pasos y detente si alguno falla:
>
> 1. Detecta mi SO (macOS o Linux). En macOS, asegura Homebrew.
> 2. Instala deps del sistema: `ffmpeg` (con libass), `yt-dlp`, Python 3.12+.
> 3. Clona el repo en `~/code/sermon-cuts` (o pregúntame dónde).
> 4. Crea venv Python dentro del repo y ejecuta `pip install -r requirements.txt`.
> 5. Crea symlinks de `scripts/`, `config/`, `prompts/` hacia
>    `~/.claude/skills/sermon-cuts/` y copia `SKILL.md` allí.
> 6. Pregúntame si quiero transcripción mejor vía Groq Whisper. Si sí,
>    abre https://console.groq.com/keys, pídeme pegar la clave y agrega
>    `GROQ_API_KEY=...` en `~/.env`.
> 7. Pregúntame si quiero la fuente Outfit Black
>    (https://fonts.google.com/specimen/Outfit). Si sí, descárgala.
> 8. Ejecuta `./scripts/pipeline.sh doctor` para confirmar la instalación.
> 9. Dame un ejemplo de una línea de cómo cortar mi primer sermón.
>
> Reporta éxito o el paso que falló al final.

Después del install, solo dile *"corta esta predicación: \<URL de YouTube\>"* al mismo agente.

### 🐳 Docker (Linux/Windows/sin pip)

```bash
docker run --rm \
  -v "$(pwd)/out:/work/memory/messages" \
  -e GROQ_API_KEY=$GROQ_API_KEY \
  ghcr.io/onetogregorio/sermon-cuts <url-de-youtube>
```

> Build local: `docker build -t sermon-cuts .` si quieres ajustar la imagen.

---

## Workflow diario — los cuatro comandos que importan

macOS/Linux usa `pipeline.sh`, Windows usa `pipeline.bat`. Ambos son
wrappers finos sobre el `pipeline.py` cross-platform — invoca el que
encaje con tu shell.

```bash
pipeline.sh doctor                              # health check (corre esto primero)
pipeline.sh <url-o-mp4>                         # ingest + transcribe + propone cortes
pipeline.sh review <slug>                       # ↑↓ + SPACE + ENTER para elegir + render
pipeline.sh ui                                  # abre la UI web en localhost:7860
```

```cmd
REM Equivalente Windows — mismos flags, mismo comportamiento
pipeline.bat doctor
pipeline.bat <url-o-mp4>
pipeline.bat review <slug>
```

### Render calidad de entrega

Para entrega a cliente, agrega los flags de calidad:

```bash
pipeline.sh --render-cut 3 --slug mi_sermon \
            --quality max --codec hevc --llm-scrub
```

- `--quality max` — libx264/libx265 -preset slower + filtros denoise + sharpen
- `--codec hevc` — H.265 Main 10 (~40% archivo más chico a la misma calidad visible)
- `--llm-scrub` — review LLM completo del SRT (atrapa typos que el scrub basado en reglas se pierde)
- `--target shorts` — re-capa el corte a 60s para compatibilidad YouTube Shorts

> 💡 **¿Sin clave Groq?** El default ahora es `--provider=youtube`
> al ingestar una URL de YouTube (gratis, instantáneo, lo suficientemente
> preciso — el scrub LLM atrapa las palabras dropeadas). Los archivos
> locales prefieren Groq si `GROQ_API_KEY` está seteado, de lo contrario
> caen a faster-whisper local.

---

## Inicio rápido (manual)

Si prefieres ejecutarlo a mano:

```bash
# 1. Descarga + transcribe + encuentra las pausas naturales  (~1 min para un sermón de 30min)
./scripts/pipeline.sh "https://youtube.com/watch?v=ZKeORvbgWpA"

# 2. Claude (o tú) lee la transcripción y propone ~10 cortes.
#    Aparece una lista ranqueada; eliges cuáles renderizar.

# 3. Renderiza los cortes aprobados  (~30–60s por corte en Apple Silicon)
./scripts/pipeline.sh --render-cuts 1,2,4,7 --slug mi_predicacion
```

Los cortes finales aparecen en:

```
~/Movies/SermonCuts/renders/<slug>/01-cut_slug.mp4    # macOS
~/.local/share/sermon-cuts/renders/<slug>/...          # Linux
%USERPROFILE%\SermonCuts\renders\<slug>\...            # Windows
~/SermonCuts/renders/<slug>/...                        # otros
```

(Sobrescribe con `SERMON_CUTS_DATA_DIR=/tu/ruta` para poner todo en otro lugar.)

Vertical 1080×1920, subtítulo brand-style quemado, audio a -14 LUFS — listos
para subir a Reels, Shorts o TikTok. Vea [`examples/sample_cuts/`](examples/sample_cuts/)
para un output real.

> Setup inicial: ver [INSTALL.md](docs/INSTALL.es.md) — necesita `ffmpeg`,
> deps Python y un symlink único para que los scripts del skill resuelvan en
> `~/.claude/skills/sermon-cuts/`.

---

## Qué hay dentro

Cada paso es un script independiente — combínalos como quieras, o solo ejecuta
`pipeline.sh` end-to-end.

| Script | Qué hace |
|---|---|
| `01_ingest.py` | URL de YouTube o video local → archivo source administrado |
| `02_transcribe.py` | Transcripción a nivel de palabra (gratis vía YouTube, o premium vía Groq Whisper) |
| `03_vad_segments.py` | Encuentra pausas naturales para que los cortes nunca dividan palabras |
| `04_propose_cuts.py` | Empaqueta el mensaje para que la IA proponga cortes con arco narrativo |
| `05_validate_cut.py` | Arregla automáticamente cortes que terminan en medio del pensamiento |
| `06_build_srt.py` | Subtítulos brand-style: 3-4 palabras, dorado, sentence case |
| `07_render_track.py` | Reencuadre vertical con tracking facial + subtítulo quemado |
| `08_audio_normalize.py` | Audio nivelado a -14 LUFS (estándar Reels/TikTok) |
| `pipeline.py` / `pipeline.sh` / `pipeline.bat` | Un comando para ejecutar todo (cross-platform) |

Walkthrough completo en [`docs/PIPELINE.es.md`](docs/PIPELINE.es.md).
Instalación en [`docs/INSTALL.es.md`](docs/INSTALL.es.md).

---

## Instalación

```bash
# macOS
brew install ffmpeg yt-dlp python@3.12
pip install -r requirements.txt
```

```cmd
REM Windows
winget install Python.Python.3.12 Git.Git
REM ffmpeg + yt-dlp: instala vía winget, scoop o chocolatey (tú eliges)
winget install Gyan.FFmpeg yt-dlp.yt-dlp
pip install -r requirements.txt
```

(Instrucciones de Linux, walkthrough completo de Windows y setup
opcional de la API Groq en [`docs/INSTALL.es.md`](docs/INSTALL.es.md).)

---

## Hazlo con tu cara

Tres formas de personalizar los subtítulos, del más rápido al más completo:

```bash
# 1. Por render — flag CLI (prueba una fuente sin editar nada):
./scripts/07_render_track.py mi_sermon 1 --preset helvetica-bold

# 2. Por sermón — pon un style.yaml en la carpeta del sermón:
echo "preset: outfit-black" > memory/messages/mi_sermon/style.yaml
# O personaliza la string ASS completa:
echo "force_style: 'FontName=Custom,FontSize=18,Outline=1.2,Alignment=2,MarginV=80'" \
  >> memory/messages/mi_sermon/style.yaml

# 3. Default global — cambia para todo render de aquí en adelante:
# edita config/render_defaults.yaml -> subtitle.preset
```

Presets built-in: `arial-black` (predeterminado, viene en cualquier máquina),
`helvetica-bold` (macOS-native, más ligero), `outfit-black` (requiere instalar
la fuente Outfit). Crea los tuyos en
`config/style_presets/<tu-nombre>.txt`. Paleta y guía de marca completa en
[STYLE.es.md](docs/STYLE.es.md).

---

## Verlo funcionando

Revisa [`examples/`](examples/) para dos case studies completos — los cortes
propuestos, las decisiones de curación y los outputs verticales finales listos
para publicar.

O visita la [landing page del proyecto](https://onetogregorio.github.io/sermon-cuts/es/) →

---

## Patrocinadores

Construido con apoyo de organizaciones invirtiendo en herramientas que sirven
a la iglesia y a los creadores de contenido cristiano.

<!-- SPONSORS:START -->
- **[Midvash](https://midvash.com/es)** — Biblia online con IA · 9 idiomas,
  70 versiones de la Biblia, búsqueda semántica y herramientas de estudio impulsadas por modelos de lenguaje.
<!-- SPONSORS:END -->

¿Quieres apoyar este proyecto? [Vuélvete patrocinador →](https://github.com/sponsors/onetogregorio)

---

## Sobre mí

Hola, soy **Neto Gregório** — construyo herramientas en la intersección entre
fe, creatividad e IA. Hice Cortes de Sermón porque me cansé de pasar la noche
del domingo cortando mis propias predicaciones para Reels a mano, e imaginé
que más gente predicando, enseñando y creando contenido cristiano estaba
cansada también.

Si este proyecto te ahorra una noche, me encantaría saberlo.

→ **Blog**: [netogregorio.com](https://netogregorio.com) — ensayos sobre fe,
  tecnología y construir con agentes de IA
→ **Instagram**: [@onetogregorio](https://instagram.com/onetogregorio) —
  detrás de cámaras, cortes de predicación, pensamientos del día
→ **GitHub**: [@onetogregorio](https://github.com/onetogregorio)

Construido con [Claude Code](https://claude.com/claude-code).

---

## Documentación rápida

**Para pastor / usuario no-técnico:**
- **[FAQ](docs/FAQ.es.md)** — respuestas para pastor: costo, idiomas, privacidad, qué funciona
- **[Casos de uso](docs/USE_CASES.es.md)** — tres flujos concretos (sermón dominical, serie, conferencia)
- **[Privacidad](docs/PRIVACY.es.md)** — qué datos salen de tu máquina (spoiler: por defecto, casi nada)
- **[Troubleshooting](docs/TROUBLESHOOTING.es.md)** — errores comunes con solución
- **[Glosario](docs/GLOSSARY.es.md)** — definiciones en lenguaje directo de los términos que verás

**Para instalador / dev curioso:**
- **[Instalación](docs/INSTALL.es.md)** — deps de sistema + verificar
- **[Pipeline](docs/PIPELINE.es.md)** — qué hace cada script, paso a paso
- **[Style](docs/STYLE.es.md)** — fuente/color/marca del subtítulo

---

## Licencia

MIT — vea [`LICENSE`](LICENSE). Úsalo libremente. Corta más mensajes. Alcanza más gente.
