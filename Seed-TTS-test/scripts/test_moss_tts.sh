#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/internal/test_model.sh" moss_tts "$@"
