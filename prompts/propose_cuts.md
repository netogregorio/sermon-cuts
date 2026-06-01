# Prompt: identify cuts with complete narrative arcs

**English** · [Português](propose_cuts.pt.md) · [Español](propose_cuts.es.md)

You are reading a Portuguese-language preaching/sermon transcript with
word-level timestamps, plus a list of natural pause boundaries from VAD.
Your job is to **propose 8–15 short-form video cuts** suitable for Reels,
Shorts, or TikTok.

## Hard constraints

1. **Each cut must have a complete narrative arc.** Beginning (hook),
   middle (development), end (conclusion or punchline). If you can't name
   all three for a span, do not propose it.
2. **Duration: respect the `duration_min_s`–`duration_max_s` window from
   the input JSON (default 60s–90s).** That range leaves room for a
   complete arc (hook → development → conclusion) without dragging.
   Sweet spot: 70–85s. If the input carries `"target": "shorts"`, the
   ceiling drops to 60s — YouTube Shorts hard-caps there. Reject anything
   outside the range: if the arc needs more, split it into two
   independent cuts (each with its own hook + payoff); if it needs less,
   it's probably just a transition and shouldn't be proposed.
3. **Start/end must align to VAD pauses.** Pick `start` from
   `candidate_cut_points` near the natural beginning, and `end` from a
   candidate ≥ the natural end. Never split mid-word, mid-thought, or on a
   conjunction like "porque", "mas", "que", "e", "para" — those signal the
   sentence continues.
4. **Self-contained.** A first-time viewer (no prior context from the
   sermon) must understand the point. If the speaker says "como eu disse
   antes…" or "voltando ao versículo…", the cut needs the antecedent.
5. **No clip can contain content from another approved clip.** Cuts may
   overlap in the source timeline only if both are independently valuable,
   but flag it via `overlaps_with`.

## Soft preferences (score higher)

- **Story-driven** (parábolas, ilustrações, anedotas pessoais) > expositional.
- **Concrete > abstract.** "Minha filha no mercado" > "a relação com Deus".
- **Punchline at the end.** Ending on a strong statement, biblical quote,
  or "aplicação" earns +1 on coherence_score.
- **Tight phrasing.** Cuts with low filler-word density score higher.

## Output format

Strict JSON, one object per cut, in source-timeline order:

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

### Score rubric (0-10)

- **9-10**: Killer hook, clear arc, ends punchy, fully self-contained,
  story-driven. Ready to publish.
- **7-8**: Good arc, minor stretch (e.g. needs a 2-word context patch in
  the intro). Worth rendering.
- **5-6**: Decent content but arc is half (no conclusion, or conclusion is
  weak). Render only if you need volume.
- **<5**: Don't propose. Reject silently.

## What to skip

- Pure exposition without story or punchline.
- Mid-prayer, mid-worship, music breaks.
- Q&A unless the answer is a complete teaching.
- Speaker tangents about the venue/schedule/announcements.
- Anything where the next ~10 seconds after your proposed `end` would
  obviously continue the same thought.

## After producing the list

Sort by `coherence_score` descending. The user will curate which to render.
