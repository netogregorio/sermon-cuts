# Prompt: identificar cortes con arcos narrativos completos

[English](propose_cuts.md) · [Português](propose_cuts.pt.md) · **Español**

Está leyendo una transcripción de predicación/sermón en portugués con
marcas de tiempo a nivel de palabra, más una lista de límites naturales de pausa del VAD.
Su tarea es **proponer 8–15 cortes de video cortos** adecuados para Reels,
Shorts o TikTok.

## Restricciones duras

1. **Cada corte debe tener un arco narrativo completo.** Comienzo (hook),
   medio (desarrollo), fin (conclusión o punchline). Si no puede nombrar
   los tres para un span, no lo proponga.
2. **Duración: respete la ventana `duration_min_s`–`duration_max_s` del
   input JSON (default 60s–90s).** Ese rango da espacio para el arco
   completo (hook → desarrollo → conclusión) sin arrastrar. Sweet spot:
   70–85s. Si el input trae `"target": "shorts"`, el techo baja a 60s —
   YouTube Shorts tiene hard cap. Rechace cualquier cosa fuera del rango:
   si el arco necesita más, divídalo en dos cortes independientes (cada
   uno con su propio hook + punchline); si necesita menos, probablemente
   sea solo transición y no debería proponerse.
3. **Inicio/fin deben alinear con pausas del VAD.** Tome `start` de
   `candidate_cut_points` cerca del comienzo natural, y `end` de un
   candidato ≥ el fin natural. Nunca divida en medio de palabra, en medio de pensamiento, o en
   una conjunción como "porque", "mas", "que", "e", "para" — esas señalan que la
   frase continúa.
4. **Self-contained.** Un viewer por primera vez (sin contexto previo del
   sermón) debe entender el punto. Si el orador dice "como eu disse
   antes…" o "voltando ao versículo…", el corte necesita el antecedente.
5. **Ningún clip puede contener contenido de otro clip aprobado.** Los cortes pueden
   superponerse en la timeline del fuente solo si ambos son independientemente valiosos,
   pero marque eso vía `overlaps_with`.

## Preferencias suaves (puntuación más alta)

- **Story-driven** (parábolas, ilustraciones, anécdotas personales) > expositivo.
- **Concreto > abstracto.** "Minha filha no mercado" > "a relação com Deus".
- **Punchline al final.** Terminar con declaración fuerte, cita bíblica,
  o "aplicación" gana +1 en coherence_score.
- **Phrasing apretado.** Los cortes con baja densidad de filler-word puntúan más alto.

## Formato de salida

JSON estricto, un objeto por corte, en orden de la timeline del fuente:

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

### Rúbrica de puntuación (0-10)

- **9-10**: Hook matador, arco claro, termina punchy, totalmente self-contained,
  story-driven. Listo para publicar.
- **7-8**: Buen arco, estirada menor (ej. necesita un parche de contexto de 2 palabras en la
  intro). Vale renderizar.
- **5-6**: Contenido decente pero arco es la mitad (sin conclusión, o conclusión es
  débil). Renderice solo si necesita volumen.
- **<5**: No lo proponga. Rechace silenciosamente.

## Qué saltarse

- Pura exposición sin story o punchline.
- Medio de oración, medio de adoración, breaks de música.
- Q&A a menos que la respuesta sea una enseñanza completa.
- Tangentes del orador sobre el lugar/agenda/anuncios.
- Cualquier cosa donde los próximos ~10 segundos después de su `end` propuesto
  obviamente continuarían el mismo pensamiento.

## Después de producir la lista

Ordene por `coherence_score` descendente. El usuario curará cuáles renderizar.

---

Por [@onetogregorio](https://github.com/onetogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
