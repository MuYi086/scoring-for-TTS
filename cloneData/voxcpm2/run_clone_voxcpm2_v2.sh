#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec conda run --no-capture-output -n voxcpm2 python "$SCRIPT_DIR/test_clone_voxcpm2_v2.py" "$@"
