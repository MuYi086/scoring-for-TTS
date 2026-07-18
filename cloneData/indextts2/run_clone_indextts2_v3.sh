#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV="${INDEXTTS_CONDA_ENV:-unitale-tts-local}"
exec conda run --no-capture-output -n "$CONDA_ENV" python "$SCRIPT_DIR/test_clone_indextts2_v3.py" "$@"
