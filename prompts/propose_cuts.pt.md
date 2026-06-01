# Prompt: identificar cortes com arcos narrativos completos

[English](propose_cuts.md) · **Português** · [Español](propose_cuts.es.md)

Você está lendo uma transcrição de pregação/sermão em português com
timestamps em nível de palavra, mais uma lista de limites naturais de pausa do VAD.
Sua tarefa é **propor 8–15 cortes de vídeo curtos** adequados pra Reels,
Shorts ou TikTok.

## Restrições rígidas

1. **Cada corte deve ter um arco narrativo completo.** Começo (hook),
   meio (desenvolvimento), fim (conclusão ou punchline). Se você não consegue nomear
   os três para um span, não proponha.
2. **Duração: respeite a janela `duration_min_s`–`duration_max_s` do input
   JSON (default 60s–90s).** Esse range dá espaço pro arco completo
   (hook → desenvolvimento → conclusão) sem arrastar. Sweet spot: 70–85s.
   Se o input tem `"target": "shorts"`, o teto cai pra 60s — YouTube Shorts
   tem hard cap. Rejeite qualquer coisa fora do range: se o arco precisa
   de mais, divida em dois cortes independentes (cada um com seu próprio
   hook + punchline); se precisa de menos, provavelmente é só transição
   e não deveria ser proposto.
3. **Início/fim devem alinhar com pausas do VAD.** Pegue `start` de
   `candidate_cut_points` perto do começo natural, e `end` de um
   candidato ≥ o fim natural. Nunca divida no meio de palavra, no meio
   de pensamento, ou em uma conjunção/preposição tipo "porque", "mas",
   "então", "quando", "se", "para", "que", "e" — essas sinalizam que a
   frase continua. **A primeira palavra do cut também não pode ser uma
   dessas** — isso indica que o cut começou no meio de um raciocínio
   anterior. Em vez disso, ancore `start` logo após uma pausa que segue
   um `.!?` no transcript.
4. **Self-contained.** Um viewer pela primeira vez (sem contexto prévio do
   sermão) precisa entender o ponto. Se o palestrante diz "como eu disse
   antes…" ou "voltando ao versículo…", o corte precisa do antecedente.
5. **Nenhum clipe pode conter conteúdo de outro clipe aprovado.** Cortes podem
   sobrepor na timeline do source só se ambos forem independentemente valiosos,
   mas flag isso via `overlaps_with`.

## Preferências suaves (pontuação maior)

- **Story-driven** (parábolas, ilustrações, anedotas pessoais) > expositivo.
- **Concreto > abstrato.** "Minha filha no mercado" > "a relação com Deus".
- **Punchline no fim.** Terminar com declaração forte, citação bíblica,
  ou "aplicação" ganha +1 em coherence_score.
- **Phrasing apertado.** Cortes com baixa densidade de filler-word pontuam mais alto.

## Formato de output

JSON estrito, um objeto por corte, em ordem da timeline do source:

```json
{
  "n": 1,
  "slug": "filha_no_mercado",
  "start": 92.40,
  "end": 165.10,
  "duration_s": 72.7,
  "theme": "Relação vs missão — a ilustração da filha no mercado",
  "hook": "Eu gosto de uma ilustração muito boa que eu faço com a minha filha…",
  "development": "Vai pro mercado, ela pede coisas, eu fico bravo, mas ela tá comigo",
  "conclusion": "Jesus pede que a gente vá com Ele, não pra ficar n'Ele",
  "biblical_reference": "Mateus 11:28-30 (implícito); contexto Mt 11",
  "coherence_score": 9.2,
  "tags": ["ilustracao", "relacionamento_com_deus", "pais_e_filhos"],
  "depends_on": null,
  "overlaps_with": null,
  "ending_word": "ele.",
  "ending_punctuation": ".",
  "vad_aligned": true
}
```

### Rubrica de pontuação (0-10)

- **9-10**: Hook matador, arco claro, termina punchy, totalmente self-contained,
  story-driven. Pronto pra publicar.
- **7-8**: Bom arco, esticada menor (ex. precisa de um patch de contexto de 2 palavras na
  intro). Vale renderizar.
- **5-6**: Conteúdo decente mas arco é metade (sem conclusão, ou conclusão é
  fraca). Renderize só se precisar de volume.
- **<5**: Não proponha. Rejeite silenciosamente.

## O que pular

- Pura exposição sem story ou punchline.
- Meio de oração, meio de adoração, breaks de música.
- Q&A a menos que a resposta seja um ensino completo.
- Tangentes do palestrante sobre o local/agenda/avisos.
- Qualquer coisa onde os próximos ~10 segundos depois do seu `end` proposto
  obviamente continuariam o mesmo pensamento.

## Depois de produzir a lista

Ordene por `coherence_score` decrescente. O usuário vai curar quais renderizar.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
