@echo off
REM Sermon Cuts — Windows installer wrapper.
REM
REM Assumes Python 3.10+ and git are already installed (winget install
REM Python.Python.3.12 ; winget install Git.Git). Clones the repo if
REM missing, then hands off to install.py which does the Python-side
REM work (venv, skill link, .env, font preset, MediaPipe models).
REM
REM System deps ffmpeg + yt-dlp are NOT auto-installed — install.py
REM detects them and prints the winget/scoop command if missing.
REM
REM Usage:
REM   install.bat
REM
REM Override clone location:
REM   set SERMON_CUTS_DIR=C:\projects\sermon-cuts
REM   install.bat

setlocal enabledelayedexpansion

set REPO_URL=https://github.com/onetogregorio/sermon-cuts.git
if "%SERMON_CUTS_DIR%"=="" set SERMON_CUTS_DIR=%USERPROFILE%\code\sermon-cuts

echo Sermon Cuts installer (Windows)
echo.

REM ─── verify Python + git ──────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
  echo   x Python not found on PATH.
  echo     Install: winget install Python.Python.3.12
  echo     Then re-run install.bat.
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo   x git not found on PATH.
  echo     Install: winget install Git.Git
  echo     Then re-run install.bat.
  exit /b 1
)

REM ─── clone or update repo ─────────────────────────────────────────────
if exist "%SERMON_CUTS_DIR%\.git" (
  echo   OK repo already at %SERMON_CUTS_DIR%
  pushd "%SERMON_CUTS_DIR%"
  git pull --ff-only
  popd
) else (
  for %%I in ("%SERMON_CUTS_DIR%\..") do md "%%~fI" 2>nul
  echo   ^> cloning %REPO_URL% into %SERMON_CUTS_DIR%
  git clone "%REPO_URL%" "%SERMON_CUTS_DIR%"
)

REM ─── hand off to install.py ───────────────────────────────────────────
echo.
echo Running cross-platform installer (install.py)
python "%SERMON_CUTS_DIR%\scripts\install.py" --repo "%SERMON_CUTS_DIR%"
