#!/usr/bin/env bash
# Backward-compatible Unix wrapper around pipeline.py.
#
# All orchestration logic lives in pipeline.py (cross-platform). This
# wrapper exists so existing docs, cron jobs, and muscle memory that
# reference ``pipeline.sh`` keep working on macOS and Linux without
# changes. Windows users invoke pipeline.bat or pipeline.py directly.
#
# Run ``pipeline.py --help`` (or this script with --help) for the full
# flag surface.

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/pipeline.py" "$@"
