#!/usr/bin/env bash
# 七模型顺序全量评测入口；实现位于 internal，外层只保留可直接执行的脚本。
set -Eeuo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/internal/load_local_env.sh"
exec "$script_dir/internal/test_all_models.sh" "$@"
