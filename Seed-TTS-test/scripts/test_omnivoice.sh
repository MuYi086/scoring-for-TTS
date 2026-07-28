#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/internal/load_local_env.sh"
exec "$script_dir/internal/test_model.sh" omnivoice "$@"
