#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n qwen3-tts python "$SCRIPT_DIR/test_clone_qwen3_tts_12hz_1_7b_base_v2.py" "$@"
