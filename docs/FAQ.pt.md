# Perguntas Frequentes

[English](FAQ.md) · **Português** · [Español](FAQ.es.md)

Escrito pra pastor, pregador, criador de conteúdo cristão tentando
entender se o Sermon Cuts encaixa no seu fluxo. Sem código pra ler aqui.

---

## Começando

### Preciso saber programar?

**Não.** Se você consegue copiar-colar um comando num terminal, tá
beleza. Se nem quiser abrir terminal, cola o prompt de instalação no
**Claude Code**, **Cursor**, **Cline** ou qualquer agente de IA com
acesso ao terminal — ele cuida de tudo.

### Quanto custa?

**A ferramenta em si: grátis, open-source (MIT).**

Custos que podem aparecer:
- **Transcrição via YouTube** (padrão): R$ 0
- **Transcrição via Groq Whisper** (mais precisa): a tier gratuita cobre
  ~10 sermões/dia. Acima disso, ~R$ 0,25 por sermão de 30min
- **Proposta de cortes via LLM** (Claude/Cursor): você já paga isso
  se usa esses editores — Sermon Cuts usa sua assinatura existente

Pra um pastor que corta 1 sermão por semana: **R$ 0/mês** na prática.

### Vai funcionar com a gravação da minha pregação?

Sim, se seu vídeo for:
- Um **link do YouTube** (público ou não-listado)
- OU um **arquivo local** em MP4, MOV, MKV ou WebM

Qualidade de áudio importa mais que vídeo. Se dá pra ouvir o pregador
claramente, a transcrição funciona.

### Funciona em outros idiomas além do português?

Sim. Passa `--language=en` pra inglês, `--language=es` pra espanhol,
`--language=pt` pra português (padrão). O pipeline em si é agnóstico
de idioma — só o prompt de proposta de cortes tá ajustado pra sermões em
português hoje. Pra inglês/espanhol funciona, mas talvez você queira
ajustar a rubrica em `prompts/propose_cuts.md` pra sua tradição.

### Quanto tempo demora?

Pra um sermão de 30min, end-to-end:

- **Transcrever + analisar**: ~1 minuto
- **Você cura os cortes propostos**: ~5 minutos (a maior parte do tempo)
- **Renderizar os cortes aprovados**: ~30–60s por cut em Apple Silicon,
  ~2min por cut em Mac Intel/Linux antigo

Pra 10 cortes: ~15–25 minutos no total, com a maior parte rodando em
background enquanto você faz outra coisa.

---

## Qualidade do output

### E se a IA escolher momentos ruins?

Você vê cada corte proposto como uma lista ranqueada antes de qualquer
render acontecer. Clica, lê o hook/desenvolvimento/conclusão, aprova ou
rejeita cada um. **Nada renderiza sem seu OK.**

### E se a legenda tiver erro de transcrição?

Três camadas pegam erro:

1. **Scrub automático** flagga cues suspeitas (YouTube dropou palavra,
   transcribed "Quisto" em vez de "Cristo", etc)
2. **Revisão LLM-assisted** (opcional, `--use-llm`) lê o SRT no contexto
   e propõe correções
3. **Edição manual** — o SRT é texto puro. Edita, roda
   `pipeline.sh --reburn-srt N --slug <seu-sermao>` e só a legenda é
   re-queimada (sem re-tracking, ~30s).

### Posso editar os cortes depois de renderizados?

Sim. Output é MP4 padrão — abre no CapCut, Premiere, DaVinci, qualquer
coisa. Maioria não precisa, mas a opção tá lá.

### O tracking facial funciona se eu me mexer muito?

Tracking amostra 2 frames por segundo e suaviza com janela de 2,5s.
Aguenta movimento normal de púlpito, andar pelo palco, virar pra ler a
Bíblia. NÃO aguenta: movimento lateral muito rápido (>1m/s no frame),
ficar totalmente fora da câmera por mais de 1-2s, ou múltiplos
palestrantes ao mesmo tempo (pega a maior face, que pode não ser o que
tá falando).

### Posso usar minha própria fonte / cor / estilo de marca?

Sim. Escolhe um preset built-in (`arial-black`, `helvetica-bold`,
`outfit-black`) em `config/render_defaults.yaml`, ou ajusta na mão em
`config/style_presets/<seu-nome>.txt`. Detalhes em [STYLE.md](STYLE.md).

---

## Plataformas & fontes

### Funciona em Windows?

**Sim, nativamente** desde a v0.2.0 — sem necessidade de WSL. O
orquestrador (`pipeline.py`) e o instalador (`install.py`) são Python
puro. Um wrapper `pipeline.bat` deixa você rodar
`pipeline.bat <youtube-url>` do cmd ou PowerShell do mesmo jeito que
usuários de macOS/Linux rodam `pipeline.sh`.

Setup é um único `winget` de Python + git + ffmpeg + yt-dlp, depois
`scripts\install.bat` do repo clonado. Walkthrough completo em
[INSTALL.pt.md](INSTALL.pt.md#windows).

WSL2 e Docker ainda funcionam se preferir — mas Windows nativo é o
caminho recomendado agora.

### E Linux?

Suporte completo. Testado em Ubuntu 22.04+. Instruções em
[INSTALL.pt.md](INSTALL.pt.md).

### Posso usar com fontes que não sejam do YouTube?

Sim. Passa o caminho do arquivo local em vez de URL:
```bash
./scripts/pipeline.sh ~/Downloads/meu_sermao.mp4
```
Vimeo, Twitch VOD e a maioria de plataformas que o yt-dlp suporta
funcionam também como URL — mas auto-legenda é geralmente só do YouTube,
então você vai querer `--provider=groq` pra essas.

### E se meu vídeo do YouTube não tiver auto-legenda?

YouTube gera auto-legenda automaticamente nas primeiras horas após
upload pra maioria dos vídeos públicos. Se o seu ainda não tem (ou você
desativou), usa `--provider=groq` — extrai áudio e transcreve
diretamente via Groq Whisper.

### Dá pra rodar 100% offline?

Quase. O modelo de tracking facial baixa na primeira execução (~10 MB,
uma vez). Depois disso:
- Transcrição: precisa de internet pra YouTube VTT ou Groq
- Proposta de cortes: precisa do seu editor de IA (Claude/Cursor), que
  geralmente precisa de internet
- Render: 100% local
- Scrub de legenda: 100% local (a menos que use `--use-llm`)

Então se transcrever com Whisper local (planejado, ainda não shipado) e
propor cortes manualmente em vez de via LLM, dá pra rodar end-to-end
offline.

---

## Privacidade & dados

### Pra onde vai o áudio da minha pregação?

Depende do provedor de transcrição que você escolhe:

- **Auto-legenda do YouTube** (padrão): só a URL do YouTube é consultada.
  Nenhum áudio sai da sua máquina.
- **Groq Whisper**: o áudio do seu sermão é enviado pros servidores do
  Groq pra transcrever. Veja a [política de privacidade
  deles](https://groq.com/privacy-policy/).
- **Proposta de cortes LLM**: o *texto da transcrição* (não áudio) é
  compartilhado com o provedor do seu editor de IA (Anthropic, OpenAI,
  etc).

O render em si é **100% local**. Sua face, sua voz, seu arquivo de
vídeo — não saem do seu computador a menos que você suba explicitamente.

Análise completa em [PRIVACY.pt.md](PRIVACY.pt.md).

### O Sermon Cuts loga alguma coisa?

O pipeline escreve em `memory/messages/<slug>/` na sua máquina —
transcrições, propostas de corte, renders. **Nada é enviado pra lugar
nenhum pelo pipeline em si.** O que é compartilhado depende
inteiramente das APIs que você opta usar (Groq pra transcrição, seu
editor de IA pra propostas).

### Tem afiliação com alguma denominação / tradição teológica?

**Não.** Sermon Cuts é só uma ferramenta de edição. Os prompts de
exemplo estão escritos em português com framing de sermão cristão
(porque é o que o [@netogregorio](https://github.com/netogregorio)
corta), mas a ferramenta não assume nada sobre sua mensagem, audiência
ou teologia.

---

## Fluxo de trabalho

### Posso processar vários sermões em lote?

Sim. Roda `./scripts/pipeline.sh <url-1>`, depois `pipeline.sh <url-2>`,
etc. Cada um ganha seu próprio slug e diretório de trabalho. Não tem
fila built-in, mas dá pra encadear num loop de shell.

### Onde os vídeos finais ficam?

Dois caminhos por padrão:
- `renders/<slug>/NN-slug.mp4` — output do pipeline
- Move os aprovados manualmente pra `edit/cuts/<Nome da Mensagem>/` pro
  seu fluxo de curadoria (ritual do `CLAUDE.md`)

### Posso usar isso pra conteúdo que não é sermão?

O pipeline não se importa com o que é seu vídeo — funciona em podcast,
estudo bíblico, palestra de conferência, aula de faculdade, qualquer
coisa onde uma pessoa fala na câmera. Mas o **prompt de proposta de
cortes** tá ajustado pra estrutura de sermão (hook + ilustração bíblica
+ aplicação). Pra conteúdo não-sermão você vai querer trocar o
`prompts/propose_cuts.md` por algo melhor pro seu caso.

### Posso contribuir de volta?

Sim! Pull requests bem-vindos. Veja `CONTRIBUTING.md` no repo.
Contribuições comuns:

- Prompts em outros idiomas (rubricas pra sermão em espanhol/inglês)
- Style presets de legenda pra outras estéticas de marca
- Entradas em `config/corrections_pt.txt` (ou `_es.txt`, `_en.txt`) pra
  erros recorrentes de transcrição que sua tradição encontra
- Correções de documentação, traduções
- Bug reports com URLs reproduzíveis

---

## Travou?

- [TROUBLESHOOTING.pt.md](TROUBLESHOOTING.pt.md) — erros comuns e soluções
- [INSTALL.pt.md](INSTALL.pt.md) — instalar + verificar
- [PIPELINE.pt.md](PIPELINE.pt.md) — o que cada script faz
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  abre uma com o output do erro

---

Construído por [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
