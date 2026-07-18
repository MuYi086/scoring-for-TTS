#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n dots_tts python "$SCRIPT_DIR/test_clone_dots_tts_base_v3.py" "$@"
