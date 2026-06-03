# Instalação

[English](INSTALL.md) · **Português** · [Español](INSTALL.es.md)

> **Cross-platform.** O Sermon Cuts roda nativamente em macOS, Linux e
> Windows. Orquestrador e instalador são Python puro (`pipeline.py`,
> `install.py`); wrappers específicos por plataforma (`.sh` / `.bat`) só
> entregam pra eles.

## Caminho rápido: instalador em um comando

```bash
# macOS / Linux
curl -fsSL https://onetogregorio.github.io/sermon-cuts/install.sh | bash
```

```cmd
REM Windows (PowerShell ou cmd; Python 3.10+ e git já instalados)
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
%USERPROFILE%\code\sermon-cuts\scripts\install.bat
```

Os dois instaladores fazem a mesma coisa (venv, link da skill, .env,
preset de fonte, modelos MediaPipe, doctor check). Deps do sistema
(ffmpeg, yt-dlp) são auto-instaladas em macOS (Homebrew) e Debian/Ubuntu
(apt); no Windows o instalador detecta deps faltando e printa o comando
de install `winget`/`scoop` pra você rodar.

## Instalação manual — por plataforma

### macOS

```bash
brew install ffmpeg yt-dlp python@3.12

# Opcional: instalar a fonte Outfit Black (usada para queima de legenda)
# Baixe em https://fonts.google.com/specimen/Outfit
# Mova o .ttf para ~/Library/Fonts/
```

Você precisa do ffmpeg compilado com `libass`, `libx264` e `libfontconfig` (o
padrão `brew install ffmpeg` já inclui).

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip yt-dlp

# Opcional: instalar a Outfit Black (usada na queima de legenda)
mkdir -p ~/.local/share/fonts
curl -L https://fonts.google.com/download?family=Outfit > /tmp/outfit.zip
unzip /tmp/outfit.zip -d ~/.local/share/fonts/
fc-cache -f -v
```

### Windows

Pré-requisitos (uma única vez): instala Python 3.10+, git, ffmpeg, yt-dlp
pelo seu gerenciador de pacotes preferido.

```cmd
REM Usando winget (nativo no Windows 10/11):
winget install Python.Python.3.12
winget install Git.Git
winget install Gyan.FFmpeg
winget install yt-dlp.yt-dlp

REM Opcional: instalar a fonte Outfit Black
REM Baixe em https://fonts.google.com/specimen/Outfit
REM Botão direito nos .ttf -> "Instalar para todos os usuários" (ou por usuário)
```

Gerenciadores alternativos: `scoop install python git ffmpeg yt-dlp`
ou `choco install python git ffmpeg yt-dlp`. Download manual do ffmpeg
também funciona — o install.py confere `C:\ffmpeg\bin\`,
`C:\Program Files\ffmpeg\bin\` e a variante Program Files (x86) além do
PATH.

Depois clona e roda `install.bat`:

```cmd
git clone https://github.com/onetogregorio/sermon-cuts %USERPROFILE%\code\sermon-cuts
cd %USERPROFILE%\code\sermon-cuts
scripts\install.bat
```

**Link da skill no Windows**: `install.py` tenta três estratégias pra
linkar `%USERPROFILE%\.claude\skills\sermon-cuts\` no repo: symlink
(precisa admin ou Developer Mode), directory junction via `mklink /J`
(sem admin), e por fim copy (sempre funciona, mas não pega updates
futuros do repo automaticamente). Ative Developer Mode em Settings →
Update & Security → For Developers se quiser symlinks que acompanhem
as mudanças do repo sem fricção.

### Fallback de fonte

A Outfit é **opcional**. Se não estiver instalada, o libass cai pra fonte
sans-serif padrão do sistema (Helvetica Bold no macOS, DejaVu Sans ou similar
no Linux). Os cortes renderizam normalmente, mas não vão bater com o brand
style descrito em [STYLE.md](STYLE.md). Instale a Outfit se a identidade
visual importa pra você.

## Dependências Python

```bash
pip install -r requirements.txt
```

Se estiver em um sistema com PEP 668 (distribuições Python mais novas), use um
virtualenv ou passe `--break-system-packages`.

## Opcional: API Groq para transcrição de maior qualidade

A transcrição padrão usa auto-legendas do YouTube (grátis, sem chave).
Para usar Groq Whisper-large-v3 (mais preciso, ~30s por 10min de áudio):

```bash
# Obtenha uma chave API gratuita em https://console.groq.com/keys
echo 'GROQ_API_KEY=gsk_sua_chave_aqui' >> ~/.env
```

Depois rode qualquer script com `--provider=groq`.

## Opcional: registro de skill do Claude Code

Os instaladores fazem isso automaticamente. Se for fazer na mão:

```bash
# macOS / Linux
mkdir -p ~/.claude/skills/sermon-cuts
ln -s "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -s "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -s "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
cp SKILL.md ~/.claude/skills/sermon-cuts/SKILL.md
```

```cmd
REM Windows (rode da raiz do repo num shell Admin / Developer Mode)
mkdir "%USERPROFILE%\.claude\skills\sermon-cuts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\scripts" "%CD%\scripts"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\config"  "%CD%\config"
mklink /J "%USERPROFILE%\.claude\skills\sermon-cuts\prompts" "%CD%\prompts"
copy SKILL.md "%USERPROFILE%\.claude\skills\sermon-cuts\SKILL.md"
```

Claude agora invocará essa skill em pedidos como "cut this sermon",
"corta essa pregação", ou URLs do YouTube com intenção de corte.

## Verificar instalação

```bash
python3 -c "import cv2, mediapipe, soundfile, silero_vad, pyloudnorm, yt_dlp, groq, yaml; print('all imports OK')"
ffmpeg -version | head -1
yt-dlp --version
```

Se todos os três imprimirem sem erros, está pronto.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
