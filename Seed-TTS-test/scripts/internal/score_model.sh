#!/usr/bin/env bash
# 对一个已完整合成的模型运行官方 WER 和 SIM，并保存原始输出和冻结证据。
set -Eeuo pipefail

if [[ $# -lt 3 ]]; then
  echo "用法：$0 <模型脚本标识> --run-id <唯一运行标识> [--result-root DIR] [--report-root DIR]" >&2
  exit 2
fi

model_id=$1
shift
run_id=
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
seed_tts_root=$(cd "$script_dir/../.." && pwd)
result_root="$seed_tts_root/result"
report_root="$seed_tts_root/report"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) run_id=${2:-}; shift 2 ;;
    --result-root) result_root=${2:-}; shift 2 ;;
    --report-root) report_root=${2:-}; shift 2 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done
[[ -n "$run_id" ]] || { echo "必须传入 --run-id。" >&2; exit 2; }

: "${SEED_TTS_DATA_ROOT:?必须设置 SEED_TTS_DATA_ROOT}"
: "${SEED_TTS_EVAL_ROOT:?必须设置 SEED_TTS_EVAL_ROOT（补丁工作副本）}"
: "${SEED_TTS_WAVLM_CKPT:?必须设置 SEED_TTS_WAVLM_CKPT}"
: "${SEED_TTS_PARAFORMER_DIR:?必须设置 SEED_TTS_PARAFORMER_DIR}"
export ARNOLD_WORKER_GPU=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

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
run_dir="$(cd "$result_root/$model_dir/$run_id" && pwd)"
report_dir="$report_root/$model_dir/$run_id"
raw_dir="$report_dir/raw"
freeze_dir="$report_dir/freeze"
mkdir -p "$raw_dir" "$freeze_dir"

python "$script_dir/check_seed_tts_setup.py" --model "$model_id" --result-run "$run_dir"
python "$script_dir/render_seed_tts_report.py" --result-run "$run_dir" --report-dir "$report_dir" --validate-only

cp "$SEED_TTS_EVAL_ROOT/freeze-patch.json" "$freeze_dir/seed-tts-eval-patch.json"
git -C "$SEED_TTS_EVAL_ROOT" rev-parse HEAD > "$freeze_dir/seed-tts-eval-head.txt"
sha256sum "$SEED_TTS_WAVLM_CKPT" "$SEED_TTS_DATA_ROOT/zh/meta.lst" "$SEED_TTS_DATA_ROOT/zh/hardcase.lst" > "$freeze_dir/assets.sha256"
find "$SEED_TTS_PARAFORMER_DIR" -type f -print0 | sort -z | xargs -0 sha256sum > "$freeze_dir/paraformer-files.sha256"
conda run --no-capture-output -n seed_tts_eval python -m pip freeze > "$freeze_dir/seed_tts_eval-pip-freeze.txt"
conda run --no-capture-output -n seed_tts_sim python -m pip freeze > "$freeze_dir/seed_tts_sim-pip-freeze.txt"
(nvidia-smi || true) > "$freeze_dir/nvidia-smi.txt"

for split in meta hardcase; do
  export SEED_TTS_LIST_PATH="$SEED_TTS_DATA_ROOT/zh/$split.lst"
  export SEED_TTS_OUTPUT_DIR="$run_dir/$split"
  conda run --no-capture-output -n seed_tts_eval bash -lc '
    set -Eeuo pipefail
    cd "$SEED_TTS_EVAL_ROOT"
    bash cal_wer.sh "$SEED_TTS_LIST_PATH" "$SEED_TTS_OUTPUT_DIR" zh
  '
  cp "$run_dir/$split/wav_res_ref_text.wer" "$raw_dir/$split.wer.tsv"
  conda run --no-capture-output -n seed_tts_sim bash -lc '
    set -Eeuo pipefail
    cd "$SEED_TTS_EVAL_ROOT"
    bash cal_sim.sh "$SEED_TTS_LIST_PATH" "$SEED_TTS_OUTPUT_DIR" "$SEED_TTS_WAVLM_CKPT"
  '
  cp "$run_dir/$split/wav_res_ref_text.wer" "$raw_dir/$split.sim.tsv"
done

python "$script_dir/render_seed_tts_report.py" --result-run "$run_dir" --report-dir "$report_dir"
echo "已完成官方评分与报告：$report_dir"
