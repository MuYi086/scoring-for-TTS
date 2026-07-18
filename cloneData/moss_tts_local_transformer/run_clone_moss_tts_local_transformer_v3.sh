#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n moss-tts-py310 python "$SCRIPT_DIR/test_clone_moss_tts_local_transformer_v3.py" "$@"
