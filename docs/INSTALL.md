# Installation

**English** · [Português](INSTALL.pt.md) · [Español](INSTALL.es.md)

> **Cross-platform.** Sermon Cuts runs natively on macOS, Linux, and
> Windows. The orchestrator and installer are pure Python (`pipeline.py`,
> `install.py`); platform-specific wrappers (`.sh` / `.bat`) just hand
> off to them.

## Quick path: one-shot installer

```bash
# macOS / Linux
curl -fsSL https://onetogregorio.github.io/sermon-cuts/install.sh | bash
```

```cmd
REM Windows (PowerShell or cmd; Python 3.10+ and git already installed)
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
%USERPROFILE%\code\sermon-cuts\scripts\install.bat
```

Both installers do the same thing (venv, skill link, .env, font preset,
MediaPipe models, doctor check). System deps (ffmpeg, yt-dlp) are
auto-installed on macOS (Homebrew) and Debian/Ubuntu (apt); on Windows
the installer detects missing deps and prints the `winget`/`scoop`
install command for you to run.

## Manual install — by platform

### macOS

```bash
brew install ffmpeg yt-dlp python@3.12

# Optional: install Outfit Black font (used by subtitle burn)
# Download from https://fonts.google.com/specimen/Outfit
# Move the .ttf to ~/Library/Fonts/
```

You need ffmpeg compiled with `libass`, `libx264`, and `libfontconfig` (the
default `brew install ffmpeg` includes these).

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip yt-dlp

# Optional: install Outfit Black (used by subtitle burn)
mkdir -p ~/.local/share/fonts
curl -L https://fonts.google.com/download?family=Outfit > /tmp/outfit.zip
unzip /tmp/outfit.zip -d ~/.local/share/fonts/
fc-cache -f -v
```

### Windows

Prereqs (one-time): install Python 3.10+, git, ffmpeg, yt-dlp via your
preferred package manager.

```cmd
REM Using winget (Windows 10/11 native):
winget install Python.Python.3.12
winget install Git.Git
winget install Gyan.FFmpeg
winget install yt-dlp.yt-dlp

REM Optional: install Outfit Black font
REM Download from https://fonts.google.com/specimen/Outfit
REM Right-click the .ttf files -> "Install for all users" (or per-user)
```

Alternative package managers: `scoop install python git ffmpeg yt-dlp`
or `choco install python git ffmpeg yt-dlp`. Manual ffmpeg download
also works — install.py checks `C:\ffmpeg\bin\`, `C:\Program Files\ffmpeg\bin\`,
and the Program Files (x86) variant in addition to PATH.

Then clone and run `install.bat`:

```cmd
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
cd %USERPROFILE%\code\sermon-cuts
scripts\install.bat
```

**Skill link on Windows**: `install.py` tries three strategies for
linking `%USERPROFILE%\.claude\skills\sermon-cuts\` into the repo:
symlink (needs admin or Developer Mode), directory junction via
`mklink /J` (no admin needed), then copy (always works, but won't
auto-pick-up future repo updates). Enable Developer Mode in Windows
Settings → Update & Security → For Developers if you want symlinks
to track repo changes seamlessly.

### Font fallback

Outfit is **optional**. If it's not installed on the system, libass falls
back to the system's default sans-serif (Helvetica Bold on macOS, DejaVu Sans
or similar on Linux). Cuts will still render, but they won't match the brand
style described in [STYLE.md](STYLE.en.md). Install Outfit if the brand look
matters to you.

## Python deps

```bash
pip install -r requirements.txt
```

If you're on a system with PEP 668 (newer Python distributions), use a
virtualenv or pass `--break-system-packages`.

## Optional: Groq API for higher-quality transcription

The default transcription uses YouTube auto-captions (free, no key needed).
To use Groq Whisper-large-v3 (more accurate, ~30s per 10min audio):

```bash
# Get a free API key at https://console.groq.com/keys
echo 'GROQ_API_KEY=gsk_your_key_here' >> ~/.env
```

Then run any script with `--provider=groq`.

## Optional: Claude Code skill registration

The installers handle this automatically. If you're doing it manually:

```bash
# macOS / Linux
mkdir -p ~/.claude/skills/sermon-cuts
ln -s "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -s "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -s "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
cp SKILL.md ~/.claude/skills/sermon-cuts/SKILL.md
```

```cmd
REM Windows (run from the repo root in an Admin / Developer Mode shell)
mkdir "%USERPROFILE%\.claude\skills\sermon-cuts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\scripts" "%CD%\scripts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\config"  "%CD%\config"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\prompts" "%CD%\prompts"
copy SKILL.md "%USERPROFILE%\.claude\skills\sermon-cuts\SKILL.md"
```

Claude will now invoke this skill on requests like "cut this sermon",
"corta essa pregação", or YouTube URLs paired with cutting intent.

## Verify install

```bash
python3 -c "import cv2, mediapipe, soundfile, silero_vad, pyloudnorm, yt_dlp, groq, yaml; print('all imports OK')"
ffmpeg -version | head -1
yt-dlp --version
```

If all three print without errors, you're set.
