#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n longcat_audiodit python "$SCRIPT_DIR/test_clone_longcat_audiodit_1b_v3.py" "$@"
