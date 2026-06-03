#!/usr/bin/env python3
"""Cross-platform installer for sermon-cuts.

Python port of install.sh. Idempotent: safe to re-run. Handles the
parts of the install that are identical across macOS / Linux / Windows
(Python venv, skill symlink/junction, .env writes, font preset selection,
MediaPipe model pre-download, doctor health check). For system-level
deps (ffmpeg, yt-dlp), prints the platform-specific install command and
verifies availability rather than trying to run package managers
ourselves — those vary wildly across distros and Windows package
managers.

Usage:
  python install.py                  # auto-detect repo dir (this file's parent.parent)
  python install.py --repo /path     # explicit repo path
  python install.py --no-interactive # use defaults, don't prompt

On Windows, the install.bat wrapper bootstraps Python and calls into
this. On macOS/Linux, install.sh is the wrapper.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# ─── output formatting ────────────────────────────────────────────────────

_TTY = sys.stdout.isatty()
# Windows Terminal handles ANSI fine; legacy cmd.exe doesn't but anyone
# using legacy cmd should bear the slightly-ugly output without breaking.
_G = "\033[32m" if _TTY else ""
_Y = "\033[33m" if _TTY else ""
_R = "\033[31m" if _TTY else ""
_B = "\033[1m" if _TTY else ""
_D = "\033[2m" if _TTY else ""
_RST = "\033[0m" if _TTY else ""


def say(msg: str) -> None:
    print(f"{_B}{msg}{_RST}")


def ok(msg: str) -> None:
    print(f"  {_G}OK{_RST} {msg}")


def note(msg: str) -> None:
    print(f"  {_D}→ {msg}{_RST}")


def warn(msg: str) -> None:
    print(f"  {_Y}!{_RST} {msg}")


def die(msg: str) -> None:
    print(f"  {_R}x{_RST} {msg}", file=sys.stderr)
    sys.exit(1)


def ask(prompt: str, *, default: bool = False, non_interactive: bool) -> bool:
    """Yes/no prompt with platform-safe TTY check. Returns ``default`` in
    non-interactive mode so curl|bash style installs don't hang or die."""
    if non_interactive or not sys.stdin.isatty():
        return default
    suffix = "Y/n" if default else "y/N"
    try:
        ans = input(f"  > {prompt} [{suffix}] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if not ans:
        return default
    return ans.startswith("y") or ans.startswith("s")  # s for PT-BR sim


def prompt_str(prompt: str, *, default: str, non_interactive: bool) -> str:
    """String input with default fallback. Same TTY semantics as ``ask``."""
    if non_interactive or not sys.stdin.isatty():
        return default
    try:
        val = input(f"  > {prompt} ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return val or default


# ─── platform detection ───────────────────────────────────────────────────


def detect_platform() -> str:
    s = platform.system()
    if s == "Darwin":
        return "macos"
    if s == "Linux":
        return "linux"
    if s == "Windows":
        return "windows"
    return s.lower()


def system_install_hint(platform_name: str, pkg: str) -> str:
    """Return the user-facing command to install a system package."""
    if platform_name == "macos":
        return f"brew install {pkg}"
    if platform_name == "linux":
        return f"sudo apt-get install -y {pkg}  # or your distro's equivalent"
    if platform_name == "windows":
        return f"winget install {pkg}  # or scoop install {pkg}, or download manually"
    return f"(install {pkg} via your OS package manager)"


# ─── steps ────────────────────────────────────────────────────────────────


def check_system_deps(platform_name: str) -> None:
    """Verify ffmpeg and yt-dlp resolve — don't try to install them.

    The previous install.sh ran brew/apt itself, which works on Mac/Debian
    but breaks on Fedora/Arch/Windows. Detecting + reporting is portable;
    the user runs the right command for their OS.
    """
    say("1. System dependencies")
    missing: list[tuple[str, str]] = []
    for pkg, friendly in (("ffmpeg", "ffmpeg"), ("yt-dlp", "yt-dlp")):
        if shutil.which(pkg):
            ok(f"{friendly} on PATH ({shutil.which(pkg)})")
        else:
            missing.append((pkg, friendly))
    if missing:
        for pkg, friendly in missing:
            warn(f"{friendly} not found")
            note(f"install: {system_install_hint(platform_name, pkg)}")
        warn("re-run this script after installing the missing dependencies above")


def setup_venv(repo: Path) -> None:
    """Create .venv if missing, install requirements.txt into it."""
    say("2. Python venv + dependencies")
    venv_dir = repo / ".venv"
    if not venv_dir.exists():
        note(f"creating .venv at {venv_dir}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    # The venv's pip is at .venv/bin/pip on Unix, .venv/Scripts/pip.exe on Win.
    if platform.system() == "Windows":
        pip = venv_dir / "Scripts" / "pip.exe"
    else:
        pip = venv_dir / "bin" / "pip"
    if not pip.exists():
        die(f"pip not found in venv at {pip} — venv creation likely failed")
    note("pip install -r requirements.txt (silent)")
    subprocess.run(
        [str(pip), "install", "--upgrade", "pip", "--quiet"], check=True
    )
    subprocess.run(
        [str(pip), "install", "-r", str(repo / "requirements.txt"), "--quiet"],
        check=True,
    )
    ok("Python deps installed in .venv")


def setup_skill_link(repo: Path) -> None:
    """Create ~/.claude/skills/sermon-cuts/ with subdirs pointing at the repo.

    Uses symlinks where possible. On Windows without Developer Mode or
    admin, falls back to junctions (for dirs) via ``mklink /J``. As a
    last resort, copies the content (less ideal — won't pick up future
    repo changes).
    """
    say("3. Skill install ~/.claude/skills/sermon-cuts/")
    skill_dir = Path.home() / ".claude" / "skills" / "sermon-cuts"
    skill_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("scripts", "config", "prompts"):
        target = skill_dir / sub
        source = repo / sub
        if not source.exists():
            warn(f"{sub} doesn't exist in repo; skipping")
            continue
        if target.is_symlink() or _is_junction(target):
            ok(f"{sub}: already linked")
            continue
        if target.exists():
            warn(f"{target} exists and is not a symlink — leaving it alone")
            continue
        if not _try_link(source, target):
            warn(f"could not link {sub}; copying instead (won't auto-update)")
            shutil.copytree(source, target)
        else:
            ok(f"{sub}: linked")
    skill_md_target = skill_dir / "SKILL.md"
    skill_md_source = repo / "SKILL.md"
    if not skill_md_target.exists() and skill_md_source.exists():
        shutil.copy2(skill_md_source, skill_md_target)
        ok("SKILL.md copied")


def _is_junction(path: Path) -> bool:
    """True if ``path`` is a Windows directory junction. Symlinks have
    their own check (is_symlink); junctions aren't reported as symlinks
    by pathlib but look like them to most callers."""
    if platform.system() != "Windows":
        return False
    try:
        return bool(path.is_dir() and os.path.realpath(str(path)) != str(path.absolute()))
    except OSError:
        return False


def _try_link(source: Path, target: Path) -> bool:
    """Best-effort directory link. Returns True on success.

    Tries:
      1. ``Path.symlink_to`` — works on macOS/Linux always, Windows only
         with admin / Developer Mode.
      2. ``mklink /J`` (Windows junction) — works without admin for dirs.
    """
    try:
        target.symlink_to(source, target_is_directory=True)
        return True
    except OSError:
        pass
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                check=True, capture_output=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    return False


def setup_env_key(non_interactive: bool) -> None:
    """Add GROQ_API_KEY to ~/.env if user has one to provide. Optional —
    YouTube auto-captions are the default and require no key."""
    say("4. Groq Whisper API key (optional)")
    env_file = Path.home() / ".env"
    if env_file.exists() and "GROQ_API_KEY=" in env_file.read_text():
        ok(f"GROQ_API_KEY already in {env_file}")
        return
    if os.environ.get("GROQ_API_KEY"):
        ok("GROQ_API_KEY already in shell env")
        return
    note("open https://console.groq.com/keys, create a key (free tier works)")
    if not ask("Save GROQ_API_KEY to ~/.env now?", default=False,
               non_interactive=non_interactive):
        note("skipped. Default provider is 'youtube' (auto-captions, free)")
        return
    key = prompt_str("paste key (gsk_...):", default="",
                     non_interactive=non_interactive)
    if not key.startswith("gsk_"):
        warn("key doesn't start with gsk_ — not saving")
        return
    with env_file.open("a") as f:
        f.write(f"\nGROQ_API_KEY={key}\n")
    ok(f"saved to {env_file}")


def setup_font_preset(repo: Path, non_interactive: bool) -> None:
    """Let the user pick a subtitle font preset; patch render_defaults.yaml
    and download Outfit Black if selected."""
    say("5. Subtitle font preset")
    note("Default: Arial Black (universal, no download).")
    print("  1) arial-black     — Arial Black (default)")
    print("  2) helvetica-bold  — Helvetica Bold (macOS-native, lighter)")
    print("  3) outfit-black    — Outfit Black (requires download)")
    choice = prompt_str("choose [1-3, default 1]:", default="1",
                        non_interactive=non_interactive)
    presets = {"1": ("arial-black", False), "2": ("helvetica-bold", False),
               "3": ("outfit-black", True)}
    preset, download_outfit = presets.get(choice.strip(), ("arial-black", False))
    ok(f"preset: {preset}")

    yaml_path = repo / "config" / "render_defaults.yaml"
    text = yaml_path.read_text()
    new_text = re.sub(
        r"^(\s*preset:\s*)[a-z-]+",
        rf"\g<1>{preset}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_text != text:
        yaml_path.write_text(new_text)
        ok(f"render_defaults.yaml preset → {preset}")

    if download_outfit:
        _install_outfit_font()


def _outfit_font_dirs() -> list[Path]:
    """Per-platform locations where Outfit Black might already live."""
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return [
            home / "Library" / "Fonts" / "Outfit-Black.ttf",
            Path("/Library/Fonts/Outfit-Black.ttf"),
        ]
    if system == "Linux":
        return [
            home / ".local" / "share" / "fonts" / "Outfit-Black.ttf",
            Path("/usr/share/fonts/truetype/outfit/Outfit-Black.ttf"),
        ]
    if system == "Windows":
        return [
            # Per-user fonts dir — writable without admin (since Win10 1809).
            home / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "Outfit-Black.ttf",
            Path(r"C:\Windows\Fonts\Outfit-Black.ttf"),
        ]
    return []


def _outfit_install_dir() -> Path:
    """Where to install Outfit Black on this platform."""
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Fonts"
    if system == "Linux":
        d = home / ".local" / "share" / "fonts"
        d.mkdir(parents=True, exist_ok=True)
        return d
    if system == "Windows":
        d = home / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return home / ".fonts"


def _install_outfit_font() -> None:
    """Download Outfit family from Google Fonts; extract Outfit-Black.ttf
    to the per-user fonts dir for this OS."""
    for candidate in _outfit_font_dirs():
        if candidate.exists():
            ok(f"Outfit Black already installed at {candidate}")
            return
    dest = _outfit_install_dir()
    note(f"downloading Outfit family from Google Fonts to {dest}")
    url = "https://fonts.google.com/download?family=Outfit"
    with tempfile.TemporaryDirectory() as td:
        zip_path = Path(td) / "outfit.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
        except urllib.error.URLError as e:
            warn(f"font download failed: {e}; skipping")
            return
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
    if platform.system() == "Linux":
        # Refresh fontconfig cache so libass finds the new fonts.
        subprocess.run(["fc-cache", "-f", str(dest)],
                       check=False, capture_output=True)
    ok(f"Outfit Black installed at {dest}")


def setup_mediapipe_models(repo: Path) -> None:
    """Pre-download MediaPipe models so the first render doesn't need
    network. Models live in <repo>/config/ where 07_render_track looks
    for them."""
    say("6. MediaPipe models (face + pose tracking)")
    config_dir = repo / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    models = [
        (
            "blaze_face_short_range.tflite",
            "https://storage.googleapis.com/mediapipe-models/face_detector/"
            "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
        ),
        (
            "pose_landmarker_lite.task",
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
        ),
    ]
    for fname, url in models:
        dest = config_dir / fname
        if dest.exists():
            ok(f"{fname} already present")
            continue
        try:
            urllib.request.urlretrieve(url, dest)
            ok(f"{fname} downloaded")
        except urllib.error.URLError as e:
            warn(f"{fname} failed: {e} — face tracking may fall back to Haar")
            if dest.exists():
                dest.unlink()


def run_doctor(repo: Path) -> None:
    """Final health check. Doctor's exit code is best-effort — install
    completes either way so the user can fix issues incrementally."""
    say("7. Health check")
    doctor = repo / "scripts" / "doctor.py"
    if not doctor.exists():
        warn("doctor.py not found; skipping health check")
        return
    subprocess.run([sys.executable, str(doctor)], check=False)


# ─── entry point ──────────────────────────────────────────────────────────


def find_repo_root() -> Path:
    """Default repo path is two directories up from this file (since this
    file lives in <repo>/scripts/). Allows the user to run install.py
    from the cloned repo without --repo."""
    return Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-platform sermon-cuts installer.")
    ap.add_argument("--repo", default=None,
                    help="path to the cloned repo (default: auto-detect from "
                    "this script's location)")
    ap.add_argument("--non-interactive", action="store_true",
                    help="skip all prompts, use defaults (CI / curl|bash style)")
    args = ap.parse_args()

    repo = Path(args.repo).resolve() if args.repo else find_repo_root()
    if not (repo / "scripts" / "pipeline.py").exists():
        die(f"{repo} doesn't look like a sermon-cuts checkout "
            "(missing scripts/pipeline.py)")

    platform_name = detect_platform()
    say(f"sermon-cuts installer — {platform_name}/{platform.machine()}")
    print()

    check_system_deps(platform_name)
    print()
    setup_venv(repo)
    print()
    setup_skill_link(repo)
    print()
    setup_env_key(args.non_interactive)
    print()
    setup_font_preset(repo, args.non_interactive)
    print()
    setup_mediapipe_models(repo)
    print()
    run_doctor(repo)
    print()

    say("Installation done.")
    print(f"  {_D}cd {repo}{_RST}")
    if platform.system() == "Windows":
        print(f"  {_D}.venv\\Scripts\\activate{_RST}")
        print(f"  {_B}python scripts\\pipeline.py https://youtube.com/watch?v=...{_RST}")
    else:
        print(f"  {_D}source .venv/bin/activate{_RST}")
        print(f"  {_B}./scripts/pipeline.sh https://youtube.com/watch?v=...{_RST}")


if __name__ == "__main__":
    main()
