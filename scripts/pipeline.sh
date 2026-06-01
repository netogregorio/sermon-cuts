#!/usr/bin/env bash
# Orchestrator for sermon-cuts skill.
#
# Modes:
#   pipeline.sh doctor                         # health-check the environment
#   pipeline.sh <source>                       # ingest + transcribe + vad + propose
#   pipeline.sh --propose-only <source>        # same as above (just clarity)
#   pipeline.sh --render-cut N --slug S        # render cut N for slug S
#   pipeline.sh --render-cuts N,M,P --slug S   # batch render
#   pipeline.sh --reburn-srt N --slug S        # only re-burn subtitles (no retracking)
#
# Render flags:
#   --skip-scrub        skip the 06b SRT lint pass (useful for CI / batch
#                       runs where no human is around to review suspects)
#   --target T          delivery target: all (default, 60-90s), shorts
#                       (re-caps at 60s for YouTube Shorts compatibility),
#                       reels, tiktok. Forwarded to 04_propose_cuts and
#                       05_validate_cut.
#   --quality Q         encoder quality: auto (default — picks hardware
#                       encoder on Apple Silicon for speed) or max (forces
#                       libx264 -preset slower -crf 17 for delivery cuts).
#                       Forwarded to 07_render_track and 09_trim_silences.
#   --codec C           video codec: h264 (default, broadest compat) or
#                       hevc (~40%% smaller files at same visible quality
#                       — Reels/TikTok/Shorts accept HEVC since 2022).
#                       Forwarded to 07_render_track and 09_trim_silences.
#
# Source can be a YouTube URL or a local .mp4/.mov path.

set -euo pipefail
SKILL_ROOT="$HOME/.claude/skills/sermon-cuts"
SCRIPTS="$SKILL_ROOT/scripts"
PY=python3

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

[[ $# -eq 0 ]] && usage

# Short-circuit subcommands that don't need arg parsing.
case "${1:-}" in
  doctor)   exec $PY "$SCRIPTS/doctor.py" ;;
  ui)       shift; exec $PY "$SCRIPTS/ui.py" "$@" ;;
  nightly)  shift; exec $PY "$SCRIPTS/nightly.py" "$@" ;;
  migrate)  shift; exec $PY "$SCRIPTS/migrate_paths.py" "$@" ;;
  review)
    shift
    [[ $# -eq 0 ]] && { echo "usage: pipeline.sh review <slug>"; exit 1; }
    # review.py prints the chosen render command to stdout when the user
    # hits ENTER, then we eval it. If the user cancels (q/ESC) or marks
    # nothing, review.py exits non-zero and we stop here.
    CMD=$($PY "$SCRIPTS/review.py" "$1") || exit $?
    echo "→ executando: $CMD"
    exec bash -c "$CMD"
    ;;
esac

MODE="ingest_propose"
SOURCE=""
SLUG=""
CUTS=""
SKIP_SCRUB=0
TARGET="all"
QUALITY="auto"
CODEC="h264"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --propose-only) MODE="ingest_propose"; shift;;
    --render-cut)   MODE="render"; CUTS="$2"; shift 2;;
    --render-cuts)  MODE="render"; CUTS="$2"; shift 2;;
    --reburn-srt)   MODE="reburn"; CUTS="$2"; shift 2;;
    --slug)         SLUG="$2"; shift 2;;
    --skip-scrub)   SKIP_SCRUB=1; shift;;
    --target)       TARGET="$2"; shift 2;;
    --quality)      QUALITY="$2"; shift 2;;
    --codec)        CODEC="$2"; shift 2;;
    -h|--help)      usage;;
    *)              SOURCE="$1"; shift;;
  esac
done

# scrub() — runs 06b unless --skip-scrub was passed. Behavior depends on
# context:
#   • TTY      → interactive review (y/n/edit/skip per suspect)
#   • non-TTY  → 06b defaults to --agent-review when suspects exist, so
#                whichever AI coding agent is orchestrating the run
#                (Claude Code, Cursor, Codex, Cline, Aider, Continue,
#                Windsurf, …) gets the JSON report with cue context +
#                transcript snippet and can apply file-edit fixes
#                before pipeline.sh continues into 07_render_track.
#                The JSON goes to the caller's stdout so the agent
#                sees it directly.
# To bypass entirely (CI without an agent, or after the SRT has already
# been vetted), pass --skip-scrub.
scrub() {
  local idx="$1"
  if [[ "$SKIP_SCRUB" -eq 1 ]]; then
    echo "→ cut #$idx: scrub SRT [skipped — --skip-scrub]"
    return
  fi
  echo "→ cut #$idx: scrub SRT (review suspeitos)"
  if [[ -t 0 ]]; then
    # Interactive: 06b runs its TTY review loop. We can swallow stdout
    # because the user sees the prompts on stderr.
    $PY "$SCRIPTS/06b_scrub_srt.py" "$SLUG" "$idx" >/dev/null
  else
    # Non-TTY: let 06b emit its --agent-review JSON to our caller's
    # stdout (most likely an agent reading our output). We don't pipe
    # through /dev/null — the JSON IS the contract here.
    $PY "$SCRIPTS/06b_scrub_srt.py" "$SLUG" "$idx"
  fi
}

case "$MODE" in
  ingest_propose)
    [[ -z "$SOURCE" ]] && { echo "source required"; exit 1; }
    echo "→ [1/4] ingest"
    INGEST_JSON=$($PY "$SCRIPTS/01_ingest.py" "$SOURCE")
    echo "$INGEST_JSON"
    SLUG=$(echo "$INGEST_JSON" | $PY -c "import json,sys; print(json.load(sys.stdin)['slug'])")
    echo "→ [2/4] transcribe (slug=$SLUG)"
    $PY "$SCRIPTS/02_transcribe.py" "$SLUG"
    echo "→ [3/4] VAD"
    $PY "$SCRIPTS/03_vad_segments.py" "$SLUG"
    echo "→ [4/4] propose-cuts input ready (target=$TARGET)"
    $PY "$SCRIPTS/04_propose_cuts.py" "$SLUG" --target "$TARGET"
    echo
    echo "Next: your AI editor reads propose_input.json + prompts/propose_cuts.md"
    echo "and writes memory/messages/$SLUG/cuts_proposed.json"
    ;;

  render)
    [[ -z "$SLUG" ]] && { echo "--slug required"; exit 1; }
    [[ -z "$CUTS" ]] && { echo "cut index required"; exit 1; }
    IFS=',' read -ra IDXS <<< "$CUTS"
    for IDX in "${IDXS[@]}"; do
      echo "→ cut #$IDX: validate (target=$TARGET)"
      $PY "$SCRIPTS/05_validate_cut.py" "$SLUG" "$IDX" --target "$TARGET" --write-back
      echo "→ cut #$IDX: build SRT"
      $PY "$SCRIPTS/06_build_srt.py" "$SLUG" "$IDX"
      scrub "$IDX"
      echo "→ cut #$IDX: render with tracking + burn legenda (quality=$QUALITY codec=$CODEC)"
      $PY "$SCRIPTS/07_render_track.py" "$SLUG" "$IDX" --quality "$QUALITY" --codec "$CODEC"
      echo "→ cut #$IDX: normalize audio"
      $PY "$SCRIPTS/08_audio_normalize.py" "$SLUG" "$IDX" --in-place
      echo "→ cut #$IDX: trim long silences (opt-in)"
      $PY "$SCRIPTS/09_trim_silences.py" "$SLUG" "$IDX" --quality "$QUALITY" --codec "$CODEC" --in-place
    done
    ;;

  reburn)
    [[ -z "$SLUG" ]] && { echo "--slug required"; exit 1; }
    IFS=',' read -ra IDXS <<< "$CUTS"
    for IDX in "${IDXS[@]}"; do
      echo "→ cut #$IDX: rebuild SRT + reburn (quality=$QUALITY codec=$CODEC)"
      $PY "$SCRIPTS/06_build_srt.py" "$SLUG" "$IDX"
      scrub "$IDX"
      $PY "$SCRIPTS/07_render_track.py" "$SLUG" "$IDX" --quality "$QUALITY" --codec "$CODEC"
      $PY "$SCRIPTS/08_audio_normalize.py" "$SLUG" "$IDX" --in-place
      $PY "$SCRIPTS/09_trim_silences.py" "$SLUG" "$IDX" --quality "$QUALITY" --codec "$CODEC" --in-place
    done
    ;;
esac
