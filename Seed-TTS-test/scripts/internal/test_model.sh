#!/usr/bin/env bash
# 对一个模型执行完整 Seed-TTS 流程：预检、串行合成、官方评分与报告。
set -Eeuo pipefail

usage() {
  cat <<'EOF'
用法：
  test_model.sh <模型脚本标识> [--run-id ID] [--result-root DIR] [--report-root DIR] [--resume | --score-only]

模型脚本标识：dots_tts、indextts2、longcat_audiodit、moss_tts、omnivoice、qwen3_tts、voxcpm2。
省略 --run-id 时会生成新的正式运行标识。--resume 只允许继续同一个未完成或未评分的运行；
--score-only 只为已完成的合成补跑 WER/SIM，不会加载 TTS 模型。
EOF
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi
if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  usage
  exit 0
fi

model_id=$1
shift
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
seed_tts_root=$(cd "$script_dir/../.." && pwd)
result_root="$seed_tts_root/result"
report_root="$seed_tts_root/report"
run_id=
resume=false
score_only=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) run_id=${2:-}; shift 2 ;;
    --result-root) result_root=${2:-}; shift 2 ;;
    --report-root) report_root=${2:-}; shift 2 ;;
    --resume) resume=true; shift ;;
    --score-only) score_only=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ $resume == true && $score_only == true ]]; then
  echo "--resume 与 --score-only 不能同时使用。" >&2
  exit 2
fi
if [[ -z "$run_id" && ( $resume == true || $score_only == true ) ]]; then
  echo "--resume 或 --score-only 必须同时提供已有的 --run-id。" >&2
  exit 2
fi
if [[ -z "$run_id" ]]; then
  run_id="seedtts-${model_id}-$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ ! "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "--run-id 只能包含字母、数字、点、下划线和连字符，且必须以字母或数字开头：$run_id" >&2
  exit 2
fi

model_dir=$(python - "$script_dir/model-config.json" "$model_id" <<'PY'
import json
import sys

config_path, model_id = sys.argv[1:]
with open(config_path, encoding="utf-8") as handle:
    config = json.load(handle)
try:
    print(config["models"][model_id]["output_dir"])
except KeyError:
    raise SystemExit(f"未知模型脚本标识：{model_id}")
PY
)
run_dir="$result_root/$model_dir/$run_id"

# 先校验所有评分前置条件，避免完成数小时合成后才发现评分器或资源缺失。
python "$script_dir/check_seed_tts_setup.py" --model "$model_id"

if [[ $score_only == true ]]; then
  [[ -d "$run_dir" ]] || { echo "不存在可评分的合成目录：$run_dir" >&2; exit 2; }
elif [[ $resume == true ]]; then
  [[ -d "$run_dir" ]] || { echo "不存在可继续的合成目录：$run_dir" >&2; exit 2; }
  state=$(python - "$run_dir/freeze/run_metadata.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print("incomplete")
else:
    payload = json.loads(path.read_text(encoding="utf-8"))
    print("complete" if payload.get("mode") == "formal" and payload.get("status") == "complete" else "incomplete")
PY
)
  if [[ $state == complete ]]; then
    echo "合成已完成，跳过合成并继续评分：$run_dir"
  else
    bash "$script_dir/run_model.sh" "$model_id" --run-id "$run_id" --result-root "$result_root" --resume
  fi
else
  bash "$script_dir/run_model.sh" "$model_id" --run-id "$run_id" --result-root "$result_root"
fi

bash "$script_dir/score_model.sh" "$model_id" --run-id "$run_id" --result-root "$result_root" --report-root "$report_root"
echo "单模型完整评测完成：模型=$model_id，run-id=$run_id"
