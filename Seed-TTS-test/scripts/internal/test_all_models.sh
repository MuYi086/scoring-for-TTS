#!/usr/bin/env bash
# 按冻结顺序逐模型执行完整 Seed-TTS 流程；任一模型失败即停止，绝不并发抢占 GPU。
set -Eeuo pipefail

usage() {
  cat <<'EOF'
用法：
  test_all_models.sh [--batch-id ID] [--result-root DIR] [--report-root DIR] [--resume]

按 dots.tts-base、IndexTTS2、LongCat-AudioDiT-1B、MOSS-TTS、OmniVoice、Qwen3-TTS、VoxCPM2 的顺序，
逐个完成合成、WER、SIM 和报告。--resume 必须使用同一 --batch-id：已生成报告的模型会跳过，
未完成合成的模型会继续，已完成合成但未评分的模型只会进入评分。
EOF
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
seed_tts_root=$(cd "$script_dir/../.." && pwd)
result_root="$seed_tts_root/result"
report_root="$seed_tts_root/report"
batch_id=
resume=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch-id) batch_id=${2:-}; shift 2 ;;
    --result-root) result_root=${2:-}; shift 2 ;;
    --report-root) report_root=${2:-}; shift 2 ;;
    --resume) resume=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$batch_id" && $resume == true ]]; then
  echo "--resume 必须同时提供已有的 --batch-id。" >&2
  exit 2
fi
if [[ -z "$batch_id" ]]; then
  batch_id="seedtts-all-$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ ! "$batch_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "--batch-id 只能包含字母、数字、点、下划线和连字符，且必须以字母或数字开头：$batch_id" >&2
  exit 2
fi

# 一次全量预检在任何模型开始前完成；单模型入口仍会再检查本模型，防止中途环境漂移。
python "$script_dir/check_seed_tts_setup.py"
models=(dots_tts indextts2 longcat_audiodit moss_tts omnivoice qwen3_tts voxcpm2)

for model_id in "${models[@]}"; do
  model_dir=$(python - "$script_dir/model-config.json" "$model_id" <<'PY'
import json
import sys

config_path, model_id = sys.argv[1:]
with open(config_path, encoding="utf-8") as handle:
    print(json.load(handle)["models"][model_id]["output_dir"])
PY
)
  run_id="${batch_id}-${model_id}"
  run_dir="$result_root/$model_dir/$run_id"
  report_manifest="$report_root/$model_dir/$run_id/report_manifest.json"

  if [[ $resume == true && -f "$report_manifest" ]]; then
    echo "已完成并有报告，跳过：模型=$model_id，run-id=$run_id"
    continue
  fi

  args=(--run-id "$run_id" --result-root "$result_root" --report-root "$report_root")
  if [[ $resume == true && -d "$run_dir" ]]; then
    args+=(--resume)
  fi
  echo "开始单模型完整评测：模型=$model_id，run-id=$run_id"
  bash "$script_dir/test_model.sh" "$model_id" "${args[@]}"
done

echo "七模型顺序全量评测完成：batch-id=$batch_id"
