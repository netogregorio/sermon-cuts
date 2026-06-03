#!/usr/bin/env bash
# Sermon Cuts — one-liner installer wrapper.
#
# Idempotent: safe to re-run. Handles the macOS/Linux-specific bits
# (Homebrew/apt install of ffmpeg + yt-dlp, repo clone) then hands off
# to install.py which does the cross-platform Python-side work
# (venv, skill link, .env, font preset, MediaPipe models, doctor).
#
# Usage (from anywhere on a fresh machine):
#   curl -fsSL https://onetogregorio.github.io/sermon-cuts/install.sh | bash
#
# Or from a clone of the repo:
#   ./scripts/install.sh
#
# Override the clone location:
#   SERMON_CUTS_DIR=~/projects/sermon-cuts bash install.sh
#
# Windows: use install.bat (or python install.py directly) instead.

set -euo pipefail

REPO_URL="https://github.com/onetogregorio/sermon-cuts.git"
SERMON_CUTS_DIR="${SERMON_CUTS_DIR:-$HOME/code/sermon-cuts}"

# ─── pretty output (kept here for the bootstrap steps below) ──────────────
if [[ -t 1 ]]; then
  GREEN="\033[32m"; YEL="\033[33m"; RED="\033[31m"
  BOLD="\033[1m"; DIM="\033[2m"; RST="\033[0m"
else
  GREEN=""; YEL=""; RED=""; BOLD=""; DIM=""; RST=""
fi

say()  { printf "${BOLD}%s${RST}\n" "$1"; }
ok()   { printf "  ${GREEN}OK${RST} %s\n" "$1"; }
note() { printf "  ${DIM}→ %s${RST}\n" "$1"; }
warn() { printf "  ${YEL}!${RST} %s\n" "$1"; }
die()  { printf "  ${RED}x${RST} %s\n" "$1" >&2; exit 1; }

ask() {
  local q="$1" default="${2:-n}" ans
  if [ ! -t 0 ]; then
    [[ "$default" =~ ^[yY] ]]
    return $?
  fi
  read -r -p "  > $q [y/N] " ans || ans=""
  ans="${ans:-$default}"
  [[ "$ans" =~ ^[yY] ]]
}

# ─── detect OS (Unix only — Windows uses install.bat) ─────────────────────
say "1. Detecting system"
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  MINGW*|MSYS*|CYGWIN*)
    die "On Windows use install.bat (or 'python scripts\\install.py') instead." ;;
  *) die "Unsupported system: $OS (macOS/Linux only here; install.py is cross-platform)" ;;
esac
ok "$PLATFORM/$(uname -m)"

# ─── system deps via native package manager ───────────────────────────────
# install.py only detects + reports missing deps (it doesn't run brew/apt),
# so we handle the bootstrap here on the platforms where it's automatable.
say "2. System dependencies (ffmpeg, yt-dlp)"

if [[ "$PLATFORM" == "macos" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew not installed"
    if ask "Install Homebrew now?"; then
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
      die "Homebrew is required on macOS. See https://brew.sh"
    fi
  fi
  ok "Homebrew present"
  for pkg in ffmpeg-full yt-dlp python@3.12; do
    if brew list --formula "$pkg" >/dev/null 2>&1; then
      ok "$pkg already installed"
    else
      note "installing $pkg via brew"
      brew install "$pkg"
      ok "$pkg installed"
    fi
  done
else
  if ! command -v apt-get >/dev/null 2>&1; then
    warn "Non-Debian distro detected"
    note "Install manually: ffmpeg (with libass), yt-dlp, python3.12+, python3-venv"
    if ! ask "Continue anyway?"; then exit 1; fi
  else
    note "apt-get update..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq ffmpeg python3 python3-pip python3-venv yt-dlp
    ok "ffmpeg, python3, yt-dlp installed"
  fi
fi

# ─── clone or update repo ─────────────────────────────────────────────────
say "3. Repository"
if [[ -d "$SERMON_CUTS_DIR/.git" ]]; then
  ok "already cloned at $SERMON_CUTS_DIR"
  note "git pull for updates"
  (cd "$SERMON_CUTS_DIR" && git pull --ff-only) || warn "git pull failed — continuing with local version"
else
  mkdir -p "$(dirname "$SERMON_CUTS_DIR")"
  note "cloning $REPO_URL into $SERMON_CUTS_DIR"
  git clone "$REPO_URL" "$SERMON_CUTS_DIR"
  ok "cloned"
fi

# ─── hand off to install.py for the cross-platform Python-side work ───────
say "4. Running cross-platform installer (install.py)"
NON_INTERACTIVE_FLAG=""
if [ ! -t 0 ]; then
  NON_INTERACTIVE_FLAG="--non-interactive"
fi
exec python3 "$SERMON_CUTS_DIR/scripts/install.py" --repo "$SERMON_CUTS_DIR" $NON_INTERACTIVE_FLAG
