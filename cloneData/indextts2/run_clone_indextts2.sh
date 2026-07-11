#!/usr/bin/env bash
# 在 IndexTTS2 对应的独立 conda 环境内直接运行本地测试脚本。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ENV="${INDEXTTS_CONDA_ENV:-unitale-tts-local}"

exec conda run --no-capture-output -n "$CONDA_ENV" \
  python "$SCRIPT_DIR/test_clone_indextts2.py" "$@"
