#!/usr/bin/env bash
# 在对应的隔离 Conda（Python 环境管理器）环境中启动一个模型的串行 Seed-TTS 合成。
set -Eeuo pipefail

if [[ $# -lt 1 ]]; then
  echo "用法：$0 <模型脚本标识> [seed_tts_runner.py 参数...]" >&2
  exit 2
fi

model_id=$1
shift
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

case "$model_id" in
  dots_tts) default_env=dots_tts ;;
  indextts2) default_env=indextts2 ;;
  longcat_audiodit) default_env=longcat_audiodit ;;
  moss_tts) default_env=moss-tts-py310 ;;
  omnivoice) default_env=omnivoice ;;
  qwen3_tts) default_env=qwen3-tts ;;
  voxcpm2) default_env=voxcpm2 ;;
  *) echo "未知模型脚本标识：$model_id" >&2; exit 2 ;;
esac

conda_env_var="SEED_TTS_${model_id^^}_CONDA_ENV"
conda_env_var=${conda_env_var//-/_}
conda_env=${!conda_env_var:-$default_env}

command -v conda >/dev/null || { echo "未找到 conda。" >&2; exit 2; }
python_exec=python
if [[ "$model_id" == "qwen3_tts" ]]; then
  : "${SEED_TTS_QWEN3_SOX_BIN:?Qwen3-TTS 必须设置 SEED_TTS_QWEN3_SOX_BIN（可执行的 sox）。}"
  [[ -x "$SEED_TTS_QWEN3_SOX_BIN" ]] || { echo "SEED_TTS_QWEN3_SOX_BIN 不是可执行文件：$SEED_TTS_QWEN3_SOX_BIN" >&2; exit 2; }
  conda_prefix=$(conda env list --json | python3 -c '
import json
import sys
name = sys.argv[1]
for value in json.load(sys.stdin).get("envs", []):
    if value.rstrip("/").endswith("/" + name):
        print(value)
        break
else:
    raise SystemExit(f"未找到 Conda 环境：{name}")
' "$conda_env")
  python_exec="$conda_prefix/bin/python"
  [[ -x "$python_exec" ]] || { echo "Qwen3-TTS Conda 环境缺少 Python：$python_exec" >&2; exit 2; }
  export PATH="$(dirname "$SEED_TTS_QWEN3_SOX_BIN"):$PATH"
fi
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$script_dir${PYTHONPATH:+:$PYTHONPATH}"

exec conda run --no-capture-output -n "$conda_env" \
  "$python_exec" "$script_dir/seed_tts_runner.py" --model "$model_id" "$@"
