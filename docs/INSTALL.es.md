# Instalación

[English](INSTALL.md) · [Português](INSTALL.pt.md) · **Español**

> **Cross-platform.** Sermon Cuts corre nativamente en macOS, Linux y
> Windows. El orquestador y el instalador son Python puro (`pipeline.py`,
> `install.py`); los wrappers específicos de cada plataforma (`.sh` /
> `.bat`) solo hacen handoff hacia ellos.

## Camino rápido: instalador one-shot

```bash
# macOS / Linux
curl -fsSL https://onetogregorio.github.io/sermon-cuts/install.sh | bash
```

```cmd
REM Windows (PowerShell o cmd; Python 3.10+ y git ya instalados)
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
%USERPROFILE%\code\sermon-cuts\scripts\install.bat
```

Ambos instaladores hacen lo mismo (venv, link del skill, .env, preset de
fuente, modelos MediaPipe, doctor check). Las deps del sistema (ffmpeg,
yt-dlp) se auto-instalan en macOS (Homebrew) y Debian/Ubuntu (apt); en
Windows el instalador detecta deps faltantes e imprime el comando
`winget`/`scoop` para que lo ejecutes.

## Instalación manual — por plataforma

### macOS

```bash
brew install ffmpeg yt-dlp python@3.12

# Opcional: instalar la fuente Outfit Black (usada para quemar subtítulos)
# Descargue de https://fonts.google.com/specimen/Outfit
# Mueva el .ttf a ~/Library/Fonts/
```

Necesita ffmpeg compilado con `libass`, `libx264` y `libfontconfig` (el
predeterminado `brew install ffmpeg` los incluye).

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip yt-dlp

# Opcional: instalar Outfit Black (usada en la quema de subtítulo)
mkdir -p ~/.local/share/fonts
curl -L https://fonts.google.com/download?family=Outfit > /tmp/outfit.zip
unzip /tmp/outfit.zip -d ~/.local/share/fonts/
fc-cache -f -v
```

### Windows

Prereqs (una vez): instalar Python 3.10+, git, ffmpeg, yt-dlp vía tu
gestor de paquetes preferido.

```cmd
REM Usando winget (nativo en Windows 10/11):
winget install Python.Python.3.12
winget install Git.Git
winget install Gyan.FFmpeg
winget install yt-dlp.yt-dlp

REM Opcional: instalar la fuente Outfit Black
REM Descarga de https://fonts.google.com/specimen/Outfit
REM Click derecho en los .ttf -> "Instalar para todos los usuarios" (o por-usuario)
```

Gestores alternativos: `scoop install python git ffmpeg yt-dlp` o
`choco install python git ffmpeg yt-dlp`. La descarga manual de ffmpeg
también funciona — install.py revisa `C:\ffmpeg\bin\`,
`C:\Program Files\ffmpeg\bin\` y la variante Program Files (x86) además
del PATH.

Luego clona y ejecuta `install.bat`:

```cmd
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
cd %USERPROFILE%\code\sermon-cuts
scripts\install.bat
```

**Link del skill en Windows**: `install.py` intenta tres estrategias
para enlazar `%USERPROFILE%\.claude\skills\sermon-cuts\` al repo:
symlink (necesita admin o Developer Mode), directory junction vía
`mklink /J` (sin admin), y luego copy (siempre funciona, pero no
captura updates futuros del repo). Habilita Developer Mode en
Configuración de Windows → Actualización y Seguridad → Para Programadores
si quieres que los symlinks rastreen cambios del repo automáticamente.

### Fallback de fuente

Outfit es **opcional**. Si no está instalada, libass cae a la fuente
sans-serif default del sistema (Helvetica Bold en macOS, DejaVu Sans o similar
en Linux). Los cortes se renderizan normalmente, pero no van a coincidir con
el brand style descrito en [STYLE.md](STYLE.es.md). Instale Outfit si la
identidad visual importa para usted.

## Dependencias Python

```bash
pip install -r requirements.txt
```

Si está en un sistema con PEP 668 (distribuciones Python más nuevas), use un
virtualenv o pase `--break-system-packages`.

## Opcional: API Groq para transcripción de mayor calidad

La transcripción predeterminada usa subtítulos automáticos de YouTube (gratis, sin clave).
Para usar Groq Whisper-large-v3 (más preciso, ~30s por 10min de audio):

```bash
# Obtenga una clave API gratuita en https://console.groq.com/keys
echo 'GROQ_API_KEY=gsk_su_clave_aqui' >> ~/.env
```

Luego ejecute cualquier script con `--provider=groq`.

## Opcional: registro de habilidad Claude Code

Los instaladores se encargan de esto automáticamente. Si lo haces a mano:

```bash
# macOS / Linux
mkdir -p ~/.claude/skills/sermon-cuts
ln -s "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -s "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -s "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
cp SKILL.md ~/.claude/skills/sermon-cuts/SKILL.md
```

```cmd
REM Windows (ejecutar desde la raíz del repo en una shell Admin / Developer Mode)
mkdir "%USERPROFILE%\.claude\skills\sermon-cuts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\scripts" "%CD%\scripts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\config"  "%CD%\config"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\prompts" "%CD%\prompts"
copy SKILL.md "%USERPROFILE%\.claude\skills\sermon-cuts\SKILL.md"
```

Claude ahora invocará esta habilidad en solicitudes como "cut this sermon",
"corta esa predicación", o URLs de YouTube con intención de corte.

## Verificar instalación

```bash
python3 -c "import cv2, mediapipe, soundfile, silero_vad, pyloudnorm, yt_dlp, groq, yaml; print('all imports OK')"
ffmpeg -version | head -1
yt-dlp --version
```

Si los tres imprimen sin errores, está listo.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
