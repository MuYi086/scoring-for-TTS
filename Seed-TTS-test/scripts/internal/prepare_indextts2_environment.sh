#!/usr/bin/env bash
# 以 IndexTTS2 官方 uv.lock 同步独立 Conda 环境；不加载权重，也不执行合成。
set -Eeuo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode=offline
if [[ ${1:-} == "--allow-network" ]]; then
  mode=network
elif [[ $# -gt 0 ]]; then
  echo "用法：$0 [--allow-network]" >&2
  exit 2
fi

: "${SEED_TTS_INDEXTTS_CODE_PATH:?必须设置 SEED_TTS_INDEXTTS_CODE_PATH（独立官方 index-tts 源码）。}"
conda_env=${SEED_TTS_INDEXTTS2_CONDA_ENV:-indextts2}
[[ -f "$SEED_TTS_INDEXTTS_CODE_PATH/uv.lock" ]] || { echo "官方源码缺少 uv.lock：$SEED_TTS_INDEXTTS_CODE_PATH" >&2; exit 2; }

conda_prefix=$(conda env list --json | python3 -c '
import json
import sys
name = sys.argv[1]
for path in json.load(sys.stdin).get("envs", []):
    if path.rstrip("/").endswith("/" + name):
        print(path)
        break
else:
    raise SystemExit(f"未找到 Conda 环境：{name}")
' "$conda_env")

# 优先使用目标 Conda 环境内的 uv，避免把宿主环境的工具误用于隔离环境。
uv_bin=${SEED_TTS_UV_BIN:-}
if [[ -z "$uv_bin" && -x "$conda_prefix/bin/uv" ]]; then
  uv_bin="$conda_prefix/bin/uv"
fi
if [[ -z "$uv_bin" ]]; then
  uv_bin=$(command -v uv || true)
fi
[[ -n "$uv_bin" && -x "$uv_bin" ]] || { echo "未找到 uv；请安装到 $conda_env，或设置 SEED_TTS_UV_BIN 后重试。" >&2; exit 2; }

args=(sync --active --no-dev)
if [[ $mode == offline ]]; then
  args+=(--offline)
fi
(
  cd "$SEED_TTS_INDEXTTS_CODE_PATH"
  VIRTUAL_ENV="$conda_prefix" PATH="$conda_prefix/bin:$PATH" "$uv_bin" "${args[@]}"
)
conda run --no-capture-output -n "$conda_env" python -m pip check
echo "IndexTTS2 官方锁文件同步完成：$conda_env"
