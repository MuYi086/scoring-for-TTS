#!/usr/bin/env bash
# 公共入口自动加载本机配置；没有 .env 时保留调用者已导出的变量，交由预检给出缺项。
internal_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
seed_tts_root=$(cd "$internal_dir/../.." && pwd)
local_env="$seed_tts_root/.env"

if [[ -f "$local_env" ]]; then
  # .env 是本机忽略文件，变量使用 export 声明，供后续 Conda 子进程继承。
  source "$local_env"
else
  echo "[提示] 未找到 $local_env；将使用当前 shell 已导出的变量。首次配置请复制 $seed_tts_root/env.example 为 .env 并填写本机路径。" >&2
fi
