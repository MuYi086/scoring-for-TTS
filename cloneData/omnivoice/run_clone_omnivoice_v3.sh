#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n omnivoice python "$SCRIPT_DIR/test_clone_omnivoice_v3.py" "$@"
