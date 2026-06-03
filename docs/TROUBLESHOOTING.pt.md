# Troubleshooting

[English](TROUBLESHOOTING.md) · **Português** · [Español](TROUBLESHOOTING.es.md)

Quando algo quebra. A maioria desses casos a gente bateu pessoalmente
durante dogfooding em sermões reais — o fix gruda.

Se não achar seu problema aqui, roda `./scripts/pipeline.sh doctor`
(macOS/Linux) ou `scripts\pipeline.bat doctor` (Windows) primeiro — ele
checa ffmpeg, yt-dlp, deps Python, fontes e o layout de symlinks da
skill, te dizendo o que tá quebrado antes de você gastar um render.

---

## Instalação & setup

### `[AVFilterGraph] No such filter: 'subtitles'`

**Por quê**: a formula padrão `ffmpeg` do Homebrew (v8.x+) saiu sem
`libass`, que é necessário pra queimar legenda em vídeo. O pipeline
detecta isso e cai pro fallback se conseguir — mas às vezes o fallback
não tá disponível.

**Fix**: instala o `ffmpeg-full` do Homebrew:
```bash
brew install ffmpeg-full
```
O pipeline auto-detecta `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` na
próxima execução. Alternativa: seta `FFMPEG_BIN=/caminho/pro/ffmpeg-com-libass`
no shell.

### `ffmpeg: command not found`

Você não tem ffmpeg instalado. macOS: `brew install ffmpeg-full`.
Ubuntu/Debian: `sudo apt install ffmpeg`. Verifica: `ffmpeg -version`.

### `yt-dlp: command not found`

Mesma coisa. macOS: `brew install yt-dlp`. Ubuntu/Debian:
`sudo apt install yt-dlp` (ou `pip install yt-dlp`). Verifica:
`yt-dlp --version`.

### `python3 -c "import mediapipe"` falha

Você ainda não rodou `pip install -r requirements.txt`, ou rodou num
venv Python diferente do que tá chamando os scripts. Ativa o venv
certo primeiro e re-instala.

### Scripts da skill não se acham (`ImportError: _common`)

A instalação da skill cria symlinks de `~/.claude/skills/sermon-cuts/`
pro repo. Se algo deu errado:

```bash
ls -la ~/.claude/skills/sermon-cuts/
# Deve mostrar scripts → <repo>/scripts como symlink
```

Se não:
```bash
mkdir -p ~/.claude/skills/sermon-cuts
ln -sf "$(pwd)/scripts" ~/.claude/skills/sermon-cuts/scripts
ln -sf "$(pwd)/config"  ~/.claude/skills/sermon-cuts/config
ln -sf "$(pwd)/prompts" ~/.claude/skills/sermon-cuts/prompts
```

---

## Ingest & fonte

### `yt-dlp` falha com "video unavailable" ou 403

Vídeo é privado, region-locked, com restrição de idade ou removido.
Tenta com `--cookies-from-browser=chrome` (ou firefox/safari) pra usar
sua sessão de login:

```bash
yt-dlp --cookies-from-browser=chrome <url>
```

Se é um live que acabou agora, espera uma hora pro YouTube finalizar
o arquivo de vídeo.

### `ZeroDivisionError` em `07_render_track.py` na pass 1

OpenCV não consegue ler as dimensões do vídeo source — retorna 0×0.
Duas causas comuns:

1. **O source.mp4 tá quebrado ou codec errado.** Verifica com
   `ffprobe -v error -show_entries stream=width,height <source>`. Deve
   imprimir dims não-zero. Se não, re-encoda com ffmpeg primeiro.
2. **O symlink pra source.mp4 tá quebrado.** Confere se
   `sources/<slug>/source.mp4` resolve pra arquivo real:
   ```bash
   ls -la sources/<slug>/source.mp4    # deve mostrar o symlink
   readlink sources/<slug>/source.mp4   # deve imprimir caminho real
   ```
   Se não, recria o symlink.

### `source não encontrado: .../sources/<slug>/source.mp4`

Você rodou um render antes do ingest. Roda
`./scripts/01_ingest.py <source> --slug <slug>` primeiro, ou usa o
orquestrador `pipeline.sh <source>`.

---

## Transcrição

### `GROQ_API_KEY não configurada`

Você passou `--provider=groq` mas não setou a chave. Pega uma grátis
em [console.groq.com/keys](https://console.groq.com/keys) e adiciona ao
shell ou ao `~/.env`:

```bash
echo 'GROQ_API_KEY=gsk_sua_chave_aqui' >> ~/.env
```

Ou só usa `--provider=youtube` (grátis, sem chave, menos preciso).

### VTT do YouTube com palavras claramente dropadas

Acontece de vez em quando nas auto-legendas do YouTube, especialmente
em boundary de frase: *"superestimamos a Mas"* deveria ser
*"superestimamos a missão. Mas"*. O pipeline pega muitos desses:

1. **`06b_scrub_srt`** detecta o padrão `palavra-função + palavra-com-maiúscula`
   e flagga pra revisão.
2. **Detecção de `semantic_gap`** flagga cues onde a duração é longa
   mas poucas palavras foram capturadas (provavelmente conteúdo dropado).
3. **`--use-llm`** roda uma pass LLM-assisted sobre o SRT inteiro
   contra o transcript pra propor correções.

Se você continua batendo erro de transcrição, re-roda com
`--provider=groq` pra mais precisão.

### "Cut #N tem 0 cues" no SRT

O range de tempo do corte não sobrepõe nenhuma palavra do transcript.
Ou os tempos do corte estão errados (confere `cuts_proposed.json`) ou a
transcrição falhou silenciosamente naquele segmento. Re-roda
`02_transcribe.py` com `--force`.

---

## Propostas & validação de cortes

### Cortes propostos pela LLM são todos ruins / fora do tema

Causa mais comum: a transcrição tem ruído que a LLM pegou (avisos,
oração, breaks de música). Dois fixes:

1. **Cura o transcript primeiro** — abre `transcript.json`, deleta
   ranges de palavras das seções de ruído, salva, re-roda
   `04_propose_cuts.py`.
2. **Ajusta o prompt** — `prompts/propose_cuts.md` tem a rubrica de
   scoring. Se sua audiência ou estilo difere de um sermão brasileiro
   típico, edita a seção de preferências suaves.

### Corte termina no meio do pensamento ("...porque", "...para")

`05_validate_cut.py` deveria pegar isso e estender o fim. Se não pegar:
- O fim não conseguiu ser estendido dentro de `--max-extend-s`
  (padrão 8s).
- Passa `--max-extend-s 20` e tenta de novo.
- Ou edita manualmente `cuts_proposed.json` pra setar novo `end`.

### Corte #N tem warning de duração (>60s ou <25s)

Plataformas short-form (Reels, Shorts, TikTok) penalizam >60s e não
retêm em <25s. Ou:
- Re-propõe os cortes (roda `04_propose_cuts.py` de novo — o prompt
  agora tem 25-60s como janela hard)
- Ajusta manualmente `end` em `cuts_proposed.json`
- Divide um corte longo em dois com hooks separados

---

## Render & legendas

### Vídeo renderizado mostra branco/preto no Preview do macOS

O Preview do macOS engasga em verticals H.264 quando metadata BT.709
não tá taggeada. O pipeline tagga certo no render, mas se você
re-encoda em outro lugar, pode perder. Re-tag in place (~2s, sem perda
de qualidade):

```bash
ffmpeg -y -i input.mp4 -c copy \
  -bsf:v "h264_metadata=video_full_range_flag=0:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1" \
  -movflags +faststart fixed.mp4 && mv fixed.mp4 input.mp4
```

Testado: abre limpo no Preview, QuickTime, Instagram, TikTok.
**Nota**: QuickTime e VLC sempre funcionam — só o Preview que é
exigente.

### Legenda não aparece no vídeo renderizado

Três causas possíveis:

1. **libass não tá no ffmpeg** — veja o erro do filtro `'subtitles'`
   acima.
2. **Fonte não instalada** — o padrão é `arial-black` que vem no
   macOS/Windows/maioria de Linux. Se você trocou pra `outfit-black`
   sem instalar a fonte, libass cai pra fonte default.
   Instala Outfit: [fonts.google.com/specimen/Outfit](https://fonts.google.com/specimen/Outfit)
3. **Arquivo SRT vazio ou malformado** — abre
   `memory/messages/<slug>/srts/NN-slug.srt` e verifica se tem cues.

### Legenda pisca / timing errado

O SRT foi gerado contra um transcript diferente do áudio do render
final. Regenera:
```bash
./scripts/06_build_srt.py <slug> <n>
./scripts/pipeline.sh --reburn-srt <n> --slug <slug>
```

### `{\fs22\b1}` aparece literalmente como texto no meu SRT exportado

É markup ASS intencional pro burn (dá um boost de tamanho na primeira
cue). É invisível quando libass renderiza no vídeo, mas aparece como
texto se você re-uploadar o SRT pro YouTube CC ou auto-legenda do
Instagram. Strip pra exportar:

```bash
./scripts/export_srt.py <slug> <n>
# Escreve um .clean.srt irmão sem nenhum bloco {...}.
```

---

## Áudio

### "Possible clipped samples in output" / áudio soa distorcido

O normalizer antigo (baseado em pyloudnorm) clippava ao aplicar ganho
grande em sources baixos. O novo `08_audio_normalize.py` usa o filtro
`loudnorm` do ffmpeg com true-peak limiter — clipping não deve
acontecer no padrão `--true-peak-db -1.5`.

Se você ainda escuta distorção:
1. Verifica que tá no normalizer novo (script importa `loudnorm`,
   não `pyloudnorm`)
2. Tenta target mais baixo: `--target-lufs -16 --true-peak-db -2.0`

### Áudio fora de sync com vídeo

ffmpeg deveria lidar com isso automaticamente. Se você tá pegando:
- Re-extrai source: `01_ingest.py <slug> --force`
- Garante que source.mp4 tem timing padrão (roda `ffprobe` e confere
  se `start_time != 0`)

---

## Output

### MP4 renderizado grande demais pro Instagram (>100 MB)

Render padrão é alta qualidade (CRF 18, preset slow). Diminui um
pouco a qualidade pra menos tamanho — edita
`config/render_defaults.yaml`:
```yaml
video:
  crf: 22       # era 18 — número menor = maior qualidade + arquivo maior
  preset: fast  # era slow — encode mais rápido, arquivo um pouco maior
```

Ou converte depois:
```bash
ffmpeg -i grande.mp4 -c:v libx264 -crf 24 -preset medium pequeno.mp4
```

### Face tracking foi pro lado errado / cortou pessoa errada

MediaPipe pega a maior face em cada frame. Se tem dois palestrantes
ou alguém atravessa, pode driftar. Opções:

1. **Re-roda com pose-fallback** (padrão): pipeline já usa midpoint
   dos ombros quando face detection falha.
2. **Pin manual da posição X**: abre `cuts_proposed.json` e adiciona
   campo `"crop_x_norm": 0.5` (0 = borda esquerda, 1 = borda direita).
   Render usa esse X fixo em vez de tracking.
3. **Troca pra Haar cascade** (menos preciso mas mais previsível):
   seta `tracking.detector: haar` em `config/render_defaults.yaml`.

---

## Específico de Windows

### `'mklink' is not recognized` durante install.bat

`install.bat` usa `mklink /J` pra criar directory junction quando
symlinks não estão disponíveis (sem admin / Developer Mode). No Windows
7 ou com cmd.exe substituído por um shell não-padrão, o `mklink` pode
estar faltando. Soluções:

1. Ative Developer Mode (Settings → Update & Security → For Developers
   → Developer Mode), que deixa o `install.py` usar symlinks de verdade
   via `Path.symlink_to` do Python. Sem admin.
2. Rode o install.bat de um cmd.exe Admin.
3. Cai pro modo copy — `install.py` vai copiar os dirs da skill em vez
   de linkar (usa mais disco e não acompanha updates futuros do repo,
   mas funciona sem admin).

### `'ffmpeg' is not recognized as an internal or external command`

ffmpeg não tá no PATH ou não tá instalado. A detecção do `install.py`
olha PATH mais `C:\ffmpeg\bin\`, `C:\Program Files\ffmpeg\bin\` e a
variante Program Files (x86). Escolhe um:

```cmd
winget install Gyan.FFmpeg
scoop install ffmpeg
choco install ffmpeg
```

Ou baixa manualmente de [ffmpeg.org](https://ffmpeg.org/download.html),
descompacta em `C:\ffmpeg\` e o `resolve_ffmpeg` pega sem editar PATH.

### Install do MediaPipe falha com `Microsoft Visual C++ 14.0 or greater is required`

Alguns wheels do MediaPipe precisam das MSVC build tools. Instala as
[Visual Studio Build Tools](https://aka.ms/vs/17/release/vs_buildtools.exe)
(seleciona o workload "Desktop development with C++") e re-roda
`pip install -r requirements.txt`. A maioria dos usuários não vai bater
isso — MediaPipe entrega wheels pré-compilados pra Python 3.10–3.12 no
Windows.

### Paths longos causam `FileNotFoundError`

Windows tem limite default de 260 caracteres no path. A instalação da
skill em
`%USERPROFILE%\.claude\skills\sermon-cuts\memory\messages\<long-slug>\...`
pode bater esse limite em nomes de sermão profundos. Ative paths longos:

```cmd
reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem ^
  /v LongPathsEnabled /t REG_DWORD /d 1 /f
```

Ou seta `SERMON_CUTS_MESSAGES_DIR=D:\sc` (ou path curto similar) no
seu ambiente pra manter paths curtos.

---

## Doctor do pipeline

Na dúvida:
```bash
./scripts/pipeline.sh doctor      # macOS / Linux
scripts\pipeline.bat doctor       # Windows
```

Checa: ffmpeg + libass, yt-dlp, deps Python, disponibilidade de fonte,
layout de symlink da skill, validade do config. Imprime ✓ verde pro
que tá OK e ✗ vermelho + dica pro que tá quebrado.

---

## Ainda quebrado?

- [INSTALL.pt.md](INSTALL.pt.md) — re-verifica instalação
- [FAQ.pt.md](FAQ.pt.md) — perguntas comuns de workflow
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  abre uma com o output completo do erro, seu SO e `ffmpeg -version`
- Contato pessoal: [netogregorio.com](https://netogregorio.com)

---

Por [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
