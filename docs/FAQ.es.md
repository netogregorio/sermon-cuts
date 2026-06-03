# Preguntas Frecuentes

[English](FAQ.md) · [Português](FAQ.pt.md) · **Español**

Escrito para pastores, predicadores y creadores de contenido cristiano
que intentan averiguar si Sermon Cuts encaja en su flujo. Sin código
para leer aquí.

---

## Empezando

### ¿Necesito saber programar?

**No.** Si puedes copiar-pegar un comando en una terminal, está bien. Si
ni siquiera quieres tocar la terminal, pega el prompt de instalación en
**Claude Code**, **Cursor**, **Cline** o cualquier agente de IA con
acceso al shell — se encarga de todo.

### ¿Cuánto cuesta?

**La herramienta en sí: gratis, open-source (MIT).**

Costos que pueden aparecer:
- **Transcripción vía YouTube** (predeterminado): $0
- **Transcripción vía Groq Whisper** (más precisa): el tier gratuito
  cubre ~10 sermones/día. Más allá, ~$0.05 por sermón de 30min
- **Propuesta de cortes vía LLM** (Claude/Cursor): ya pagas eso si
  usas esos editores — Sermon Cuts usa tu suscripción existente

Para un predicador que corta 1 sermón por semana: **$0/mes** en la
práctica.

### ¿Funcionará con la grabación de mi predicación?

Sí, si tu video es:
- Un **enlace de YouTube** (público o no listado)
- O un **archivo local** en MP4, MOV, MKV o WebM

La calidad del audio importa más que el video. Si puedes oír al orador
claramente, la transcripción funciona.

### ¿Funciona en idiomas además del portugués?

Sí. Pasa `--language=en` para inglés, `--language=es` para español,
`--language=pt` para portugués (predeterminado). El pipeline en sí es
agnóstico de idioma — solo el prompt de propuesta de cortes está
ajustado para sermones en portugués hoy. Para inglés/español funciona,
pero quizás quieras ajustar la rúbrica en `prompts/propose_cuts.md`
para tu tradición.

### ¿Cuánto tarda?

Para un sermón de 30 min, end-to-end:

- **Transcribir + analizar**: ~1 minuto
- **Tú curas los cortes propuestos**: ~5 minutos (la mayor parte de tu tiempo)
- **Renderizar los cortes aprobados**: ~30–60s por corte en Apple
  Silicon, ~2min por corte en Mac Intel/Linux antiguo

Para 10 cortes: ~15–25 minutos en total, con la mayor parte corriendo en
segundo plano mientras haces otra cosa.

---

## Calidad de salida

### ¿Y si la IA elige malos momentos?

Ves cada corte propuesto como una lista ranqueada antes de que cualquier
render suceda. Entra, lee el hook/desarrollo/conclusión, aprueba o
rechaza cada uno. **Nada se renderiza sin tu visto bueno.**

### ¿Y si un subtítulo tiene un error de transcripción?

Tres capas atrapan errores:

1. **Scrub automático** marca cues sospechosas (YouTube dejó caer una
   palabra, transcribió "Quisto" en lugar de "Cristo", etc.)
2. **Revisión asistida por LLM** (opcional `--use-llm`) lee el SRT en
   contexto y propone correcciones
3. **Edición manual** — el SRT es texto plano. Edita, ejecuta
   `pipeline.sh --reburn-srt N --slug <tu-sermon>` y solo el subtítulo
   se vuelve a quemar (sin re-tracking, ~30s).

### ¿Puedo editar los cortes después de renderizados?

Sí. La salida es un MP4 estándar — abre en CapCut, Premiere, DaVinci,
cualquier cosa. La mayoría no necesita, pero la opción está ahí.

### ¿El seguimiento facial funciona si me muevo mucho?

El tracking muestrea 2 frames por segundo y promedia sobre una ventana
de 2.5s. Maneja movimiento normal de púlpito, caminar por el escenario,
girar para leer tu Biblia. NO maneja: movimiento lateral rápido (más de
~1m/s a través del frame), estar completamente fuera de cámara por más
de un par de segundos, o múltiples oradores al mismo tiempo (elegirá la
cara más grande, que puede no ser la que habla).

### ¿Puedo usar mi propia fuente / color / estilo de marca?

Sí. Elige un preset built-in (`arial-black`, `helvetica-bold`,
`outfit-black`) en `config/render_defaults.yaml`, o ajusta a mano en
`config/style_presets/<tu-nombre>.txt`. Detalles en [STYLE.es.md](STYLE.es.md).

---

## Plataformas & fuentes

### ¿Funciona en Windows?

**Sí, nativamente** desde v0.2.0 — no requiere WSL. El orquestador
(`pipeline.py`) y el instalador (`install.py`) son Python puro. Un
wrapper `pipeline.bat` te deja ejecutar `pipeline.bat <url-youtube>`
desde cmd o PowerShell igual que los usuarios macOS/Linux ejecutan
`pipeline.sh`.

El setup es un `winget` único de Python + git + ffmpeg + yt-dlp, luego
`scripts\install.bat` desde el repo clonado. Ver
[INSTALL.es.md](INSTALL.es.md#windows) para el walkthrough completo.

WSL2 y Docker aún funcionan si los prefieres — pero Windows nativo es
el camino recomendado ahora.

### ¿Y Linux?

Soporte completo. Testeado en Ubuntu 22.04+. Instrucciones en
[INSTALL.es.md](INSTALL.es.md).

### ¿Puedo usar con fuentes que no sean YouTube?

Sí. Pasa la ruta del archivo local en lugar de URL:
```bash
./scripts/pipeline.sh ~/Downloads/mi_sermon.mp4
```
Vimeo, Twitch VOD y la mayoría de plataformas que yt-dlp soporta también
funcionan como URL — pero los auto-subtítulos son generalmente solo de
YouTube, así que querrás `--provider=groq` para esas.

### ¿Y si mi video de YouTube no tiene auto-subtítulos?

YouTube genera auto-subtítulos automáticamente en las primeras horas
después del upload para la mayoría de videos públicos. Si el tuyo aún no
los tiene (o los desactivaste), usa `--provider=groq` — extrae audio y
transcribe directamente vía Groq Whisper.

### ¿Se puede correr 100% offline?

Casi. El modelo de tracking facial se descarga en la primera ejecución
(~10 MB, una vez). Después de eso:
- Transcripción: necesita internet para YouTube VTT o Groq
- Propuesta de cortes: necesita tu editor de IA (Claude/Cursor), que
  generalmente necesita internet
- Render: 100% local
- Scrub de subtítulos: 100% local (a menos que uses `--use-llm`)

Si transcribes con Whisper local (planeado, aún no enviado) y propones
cortes manualmente en lugar de vía LLM, puedes correr end-to-end offline.

---

## Privacidad & datos

### ¿A dónde va el audio de mi predicación?

Depende del proveedor de transcripción que elijas:

- **Auto-subtítulos de YouTube** (predeterminado): solo la URL de
  YouTube se consulta. Ningún audio sale de tu máquina.
- **Groq Whisper**: el audio de tu sermón se sube a los servidores de
  Groq para transcribir. Ver su [política de
  privacidad](https://groq.com/privacy-policy/).
- **Propuesta de cortes LLM**: el *texto de la transcripción* (no audio)
  se comparte con el proveedor de tu editor de IA (Anthropic, OpenAI,
  etc.).

El render en sí es **100% local**. Tu cara, tu voz, tu archivo de
video — nunca salen de tu computadora a menos que los subas
explícitamente.

Desglose completo en [PRIVACY.es.md](PRIVACY.es.md).

### ¿Sermon Cuts registra algo?

El pipeline escribe en `memory/messages/<slug>/` en tu máquina —
transcripciones, propuestas de corte, renders. **Nada se envía a
ningún lado por el pipeline en sí.** Lo que se comparte depende
completamente de las APIs en las que optas (Groq para transcripción, tu
editor de IA para propuestas).

### ¿Está afiliado a alguna denominación / tradición teológica?

**No.** Sermon Cuts es solo una herramienta de edición. Los prompts de
ejemplo están escritos en portugués con framing de sermón cristiano
(porque es lo que [@netogregorio](https://github.com/netogregorio)
corta), pero la herramienta no asume nada sobre tu mensaje, audiencia o
teología.

---

## Flujo de trabajo

### ¿Puedo procesar varios sermones en lote?

Sí. Ejecuta `./scripts/pipeline.sh <url-1>`, luego `pipeline.sh <url-2>`,
etc. Cada uno obtiene su propio slug y directorio de trabajo. No hay
cola built-in, pero puedes encadenar en un loop de shell.

### ¿Dónde terminan los videos finales?

Dos rutas por defecto:
- `renders/<slug>/NN-slug.mp4` — salida del pipeline
- Mueve los aprobados manualmente a `edit/cuts/<Nombre del Sermón>/`
  para tu flujo de curación (el ritual de `CLAUDE.md`)

### ¿Puedo usar esto para contenido que no es sermón?

Al pipeline no le importa qué sea tu video — funciona en podcasts,
estudios bíblicos, conferencias, clases universitarias, cualquier cosa
donde una persona habla a cámara. Pero el **prompt de propuesta de
cortes** está ajustado para estructura de sermón (hook + ilustración
bíblica + aplicación). Para contenido no-sermón querrás intercambiar
`prompts/propose_cuts.md` por algo mejor para tu caso.

### ¿Puedo contribuir de vuelta?

¡Sí! Pull requests bienvenidos. Ver `CONTRIBUTING.md` en el repo.
Contribuciones comunes:

- Prompts en otros idiomas (rúbricas para sermón en español/inglés)
- Style presets de subtítulo para otras estéticas de marca
- Entradas en `config/corrections_pt.txt` (o `_es.txt`, `_en.txt`)
  para errores recurrentes de transcripción que tu tradición encuentra
- Correcciones de documentación, traducciones
- Reportes de bug con URLs reproducibles

---

## ¿Atascado?

- [TROUBLESHOOTING.es.md](TROUBLESHOOTING.es.md) — errores comunes y soluciones
- [INSTALL.es.md](INSTALL.es.md) — instalar + verificar
- [PIPELINE.es.md](PIPELINE.es.md) — qué hace cada script
- [GitHub Issues](https://github.com/onetogregorio/sermon-cuts/issues) —
  abre uno con la salida del error

---

Construido por [@netogregorio](https://github.com/netogregorio) · [netogregorio.com](https://netogregorio.com) · [@onetogregorio](https://instagram.com/onetogregorio)
