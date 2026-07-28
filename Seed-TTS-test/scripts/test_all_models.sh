#!/usr/bin/env bash
# 七模型顺序全量评测入口；实现位于 internal，外层只保留可直接执行的脚本。
set -Eeuo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/internal/test_all_models.sh" "$@"
