# Prompt: revisar suspeitos do SRT antes do burn-in

[English](scrub_srt.md) · **Português** · [Español](scrub_srt.es.md)

> **Pra quem é esse prompt.** Esse prompt é system message pra *qualquer*
> agente de IA com que o usuário esteja rodando o pipeline — Claude Code,
> Cursor, Codex CLI, Cline, Aider, Continue, Windsurf, OpenCode, Zed
> agent, ou qualquer coisa que leia JSON e edite texto. Onde o prompt
> falar "tool de editar arquivo", use a que o seu runtime expõe (Edit no
> Claude Code, edit_file no Cursor, apply_patch no Codex, write_to_file
> no Cline, etc.).

Você está revisando um SRT brand-style em português que o `06_build_srt.py`
gerou a partir do transcript word-level. O `06b_scrub_srt.py --agent-review`
escaneou esse SRT e emitiu um JSON listando **suspeitos** — cues que
provavelmente precisam de fix antes do `07_render_track.py` queimar elas
no MP4 final.

Sua tarefa: pra cada suspeito, decidir o que fazer, e aplicar o fix
direto no arquivo SRT via a tool de editar arquivo que o seu runtime
fornece. Depois o pipeline retoma o render.

## Regra inviolável: não altere o sentido teológico

Você está revisando uma pregação. **Nunca** troque uma palavra do
orador por outra que mude o sentido teológico, doutrinário, bíblico
ou a intenção original da fala. Você pode:

- Consertar uma palavra que o transcriber claramente engoliu/duplicou
  (a evidência tem que estar no `transcript_around_tc`).
- Inserir pontuação numa fronteira de sentença óbvia.
- Aplicar dicionário (nome bíblico mal-grafado, jargão teológico).

Você **NÃO** pode:

- Reescrever uma frase pra "soar melhor" ou "mais teológica".
- Substituir uma referência bíblica por outra "mais correta".
- Suavizar uma afirmação forte do orador.
- Mexer em qualquer cue cuja edição precisaria que você interpretasse
  o que o orador "quis dizer" — se você precisa adivinhar, pula.

Se uma cue lê estranho mas o `transcript_around_tc` confirma que foi
exatamente o que o orador disse, **deixa estar**. A skill é editor,
não revisor doutrinário.

## Input que você recebe

Stdout do script é o único input que importa. Schema:

```json
{
  "ok": true,
  "mode": "agent_review",
  "srt_path": "/Users/.../memory/messages/<slug>/srts/NN-<slug>.srt",
  "transcript_path": "/Users/.../memory/messages/<slug>/transcript.json",
  "prompt_path": "/Users/.../prompts/scrub_srt.md",
  "cut_index": 4,
  "cut": {
    "n": 4, "slug": "...", "start": 412.5, "end": 478.1,
    "theme": "...", "hook": "..."
  },
  "suspects": [
    {
      "cue": 13,
      "tc": "00:00:16,599",
      "text": "na E eu não digo",
      "pattern": "dropped_word_boundary",
      "matched": "na E",
      "rule_suggestion": "na. E eu não digo",
      "confidence": 0.75,
      "context": {
        "prev_cue_text": "torna uma canseira",
        "next_cue_text": "isso só a respeito",
        "transcript_around_tc": "...canseira na alma. E eu não digo isso só..."
      },
      "applied": false
    }
  ],
  "applied_count": 0
}
```

## Os quatro patterns e o que cada um costuma significar

### 1. `dropped_word_boundary`

Palavra-função (em / que / de / para / com / …) imediatamente antes de
uma palavra capitalizada que NÃO é nome próprio. O auto-caption do
YouTube engoliu uma palavra numa fronteira de frase.

Exemplos reais do dogfooding:

| Cue do SRT              | O que foi falado de verdade        |
| ----------------------- | ---------------------------------- |
| `do que Mas não`        | `do que nós. Mas não`              |
| `na E eu não digo`      | `na alma. E eu não digo`           |
| `superestimamos a Mas`  | `superestimamos a missão. Mas`     |
| `vem para uma Então`    | `vem para uma relação. Então`      |

**Use o campo `transcript_around_tc`** — ele mostra o transcript
word-level ao redor do timestamp da cue, que geralmente contém a
palavra que foi engolida. A sugestão da regra só insere um ponto;
você pode fazer melhor recuperando a palavra real que foi dropada.

Confiança: 0.75 — *sempre* olhe antes de aplicar.

### 2. `immediate_repetition`

`<palavra> <mesma palavra>` onde a palavra é uma hesitação conhecida
(a, o, um, uma, que, eu, ele, ela, …). Speaker hesitou ou YouTube
duplicou.

Quase sempre: colapsa pra uma só instância.

Confiança: 0.85.

### 3. `forbidden_ending`

Cue termina numa palavra-função da lista `cut_validation.forbid_endings`
(porque, mas, que, para, com, de, em, e). Lê como pensamento solto.

O fix é **estrutural**, não textual: você geralmente quer mover a
palavra final pra próxima cue. Isso muta duas cues ao mesmo tempo,
então a regra não aplica automático.

Padrões que funcionam:

- "trabalho com" + próxima cue "qualquer dia" → "trabalho" + "com qualquer dia"
- "porque" sozinho no final → merge com a próxima cue

Se ambas as cues forem curtas, prefira merge. Se a cue atual estiver
cheia, só shifta a palavra-função final.

Confiança: 0.60.

### 4. `dictionary`

Já foi aplicado automaticamente do
`memory/messages/<slug>/corrections.txt`. O suspeito aparece no
relatório com `applied: true` pra transparência, sem precisar fazer nada.

## Como aplicar fixes

Pra cada `suspect` com `applied: false`:

1. Leia o `srt_path` (arquivo inteiro) com a tool de leitura do seu runtime.
2. Ache a cue numerada `suspect.cue`.
3. Decida: aceitar `rule_suggestion`, escrever uma melhor, ou pular.
4. Se aceitar/editar: use a tool de editar arquivo do seu runtime pra
   substituir o `suspect.text` exato pelo seu novo texto. Preserve o
   número da cue e a linha do timestamp.
5. Pra `forbidden_ending`: edite a cue atual E a próxima juntas —
   geralmente movendo a palavra-função final.

Não toque em cues que NÃO estão na lista de suspeitos.

## Quando pular um suspeito

- A regra disparou numa **repetição estilística** que o orador fez de
  propósito enfático: "Não, não!" ou "lá, lá" — deixa quieto. (A regra
  já pula repetições separadas por vírgula, mas algumas escapam.)
- A regra disparou num **nome próprio** ainda não na whitelist: a
  sugestão inseriria um ponto dentro do nome. Pula e avisa o
  mantenedor pra adicionar o nome em `PROPER_NOUNS` no
  `06b_scrub_srt.py`.
- O texto da cue **já lê corretamente**: o orador realmente pausou no
  meio da frase, e o SRT captura isso intencionalmente. Pula.

## Depois que terminou

Quando todos os suspeitos que você aceitou estiverem aplicados, o
pipeline pode retomar. Duas opções:

- Pipeline está pausado te esperando → fala pro usuário "scrub done,
  pronto pra render" e roda `pipeline.sh --render-cut N --slug <slug>
  --skip-scrub` (o `--skip-scrub` diz ao orquestrador que o SRT já foi
  revisado).
- Pipeline rodando standalone com `--use-llm` → não precisa de ação do
  agente; o pass LLM já fez isso.

Não tente re-rodar `06b_scrub_srt.py` depois de aplicar os fixes —
os suspeitos que você cuidou somem, mas podem aparecer novos (ex.: uma
cue que agora termina em "e" depois que você moveu um "com"). Re-rodar
é OK, só não obrigatório; um pass geralmente resolve.
