# tts-bench：基准事实源

`tts-bench` 是所有评估的唯一编排层。它不会合成 TTS 音频，但会批量运行客观评价器，确保每个模型面对同一份输入、同一条参考音频、同一份预处理约定，并且每个数字都能回溯到具体音频与配置。

## 目录职责

```text
tts-bench/
├── contracts/       # 机器可读的数据契约（JSON Schema）
├── datasets/        # 样本集说明；本地音频放 datasets/audio/，不提交
├── config/          # 自动评价器、阈值、归一化区间和权重的冻结配置
├── manifests/       # 冻结的 case 清单，JSON Lines（每行一个样本）
├── reports/         # 可提交的汇总报告与决策记录
├── runs/            # 每次模型运行的可追溯证据；其中音频不提交
├── runs-v3/         # Task 4 V3 独立的八模型合成记录
├── scripts/         # 一键批量客观评估入口
└── templates/       # 新建运行和汇总时复制的模板
```

## 四种核心对象

| 对象 | 作用 | 存放位置 |
| --- | --- | --- |
| `case`（评测样本） | 固定参考音频、参考转写、待合成文本和考察维度。 | `manifests/*.jsonl` |
| `run`（一次运行） | 某模型、某配置、某个冻结清单的一次完整执行。 | `runs/<run_id>/` |
| `synthesis record`（合成记录） | 将一个 `case` 的输出音频、哈希、耗时和配置绑定。 | `runs/<run_id>/synthesis.jsonl` |
| `metric record`（指标记录） | 将一个评价器的逐样本结果绑定到合成记录。 | `runs/<run_id>/metrics/` |

`case_id` 与 `run_id` 是跨目录关联的主键。不要用文件名、显示名称或目录扫描顺序作为关联依据。

## 批量自动评估

在完成各模型的合成并登记 `synthesis.jsonl` 后，先复制 `config/automated-evaluation.example.json` 为 `config/automated-evaluation.json`，按校准集调整归一化区间和权重；再一次评估全部运行：

评价模型统一从 `HF_MIRROR_ROOT` 指向的本地 `hf-mirror` 目录解析。为保证全程离线且缓存也落在该目录，可先设置：

```bash
export HF_MIRROR_ROOT=~/hf-mirror
export HF_HOME=~/hf-mirror/huggingface-cache
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

```bash
conda run -n audio_eval python tts-bench/scripts/run_automated_evaluation.py \
  --runs-root tts-bench/runs \
  --config tts-bench/config/automated-evaluation.json
```

脚本默认不下载 WavLM 与 ASR 权重；首次准备好权重后才运行。确实需要首次下载时显式增加 `--allow-model-download`。结果写入新的 `tts-bench/reports/automated-*/` 目录：

- `per_case.jsonl`：每个 `run_id` / `case_id` 的 WavLM、ASR/CER、UTMOSv2、削波检查、长程音色稳定度与错误；
- `model_summary.csv`：每个候选模型的均值、失败数、实时率和 `configured_score`（配置化比较分）；
- `input_errors.jsonl`：不合格或无法定位的合成记录，绝不静默略过；
- `run_metadata.json`：本次配置、模型选择与执行时间。

`configured_score` 是将预先冻结的归一化区间与权重应用到同一批结果的排序工具，不是人类主观 MOS；个人对停顿、语气和情绪的试听记录不参与它。

## V2 双后端中立评测

需要降低单一评价器偏差时，使用 `neutral-evaluation-v2.json` 的六后端流程。它分别运行 SenseVoice CER、Whisper CER、WavLM SIM、SpeechBrain ECAPA SIM、UTMOSv2 和 NISQA-TTS，不计算跨指标加权总分；CER 与自然度包含原始参考音频基线，说话人相似度包含同说话人分段和跨角色校准对照。

新电脑的完整环境与权重准备以 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 为准。基础环境、Python 依赖和冻结评价资产分别在 `environment/` 与 `config/evaluation-assets-v2.json`。

正式运行前先检查包版本、CUDA、权重、24 条克隆 WAV 和登记哈希：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --strict-versions
```

仓库已经包含历史报告；每次复测必须指定新的输出目录：

```bash
HF_MIRROR_ROOT=~/hf-mirror \
HF_HOME=~/hf-mirror/huggingface-cache \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v2.py \
  --output-dir tts-bench/reports/replay-YYYYMMDDTHHMMSSZ \
  --strict
```

评测按后端逐项落盘。中断后使用相同输出目录增加 `--resume`，并可通过 `--metrics` 只重跑指定后端。全部覆盖完整后生成三份报告：

```bash
python tts-bench/scripts/generate_neutral_v2_reports.py \
  --results-dir tts-bench/reports/replay-YYYYMMDDTHHMMSSZ \
  --reports-dir tts-bench/reports/replay-YYYYMMDDTHHMMSSZ/reports
```

V2 原始结果包括 `per_audio.jsonl`、`speaker_similarity.jsonl`、`speaker_calibration.jsonl` 和 `run_metadata.json`。UTMOSv2 固定随机种子并对每条音频做五次裁剪平均，避免默认单次随机裁剪造成批次漂移。

## Task 4 V3 中立评测

V3 沿用同一套六后端和 `evaluation-assets-v2.json` 冻结权重，但参考音频、目标文本、角色与合成记录全部独立。评测输入是 `runs-v3/` 登记的 8 模型 × 3 角色矩阵，对应本地音频位于 `cloneData/audio_v3/`。

正式评分前必须预检：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --runs-root tts-bench/runs-v3 \
  --config tts-bench/config/neutral-evaluation-v3.json \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions
```

每次复测使用新的输出目录：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v3.py \
  --output-dir tts-bench/reports/replay-v3-YYYYMMDDTHHMMSSZ \
  --strict

python tts-bench/scripts/generate_neutral_v3_reports.py \
  --results-dir tts-bench/reports/replay-v3-YYYYMMDDTHHMMSSZ \
  --reports-dir tts-bench/reports/replay-v3-YYYYMMDDTHHMMSSZ/reports
```

断点续跑仅能对同一次未完成运行的相同目录使用 `--resume`。三份报告分别保留双 CER、双 SIM 和双自然度后端的原始值与独立名次，不计算跨量纲总分。

## 新建一次合成运行

1. 从 `templates/run.example.yaml` 复制为 `runs/<run_id>/run.yaml`，填写模型版本、配置快照和冻结的清单路径。
2. 由 `modelScript/` 中相应脚本手工合成，把原始 WAV 放在 `runs/<run_id>/audio/<case_id>.wav`。该目录被忽略，避免大音频进入 Git。
3. 以 `contracts/synthesis-record.schema.json` 为准，逐行填写 `synthesis.jsonl`。每条成功或失败的尝试都应留下记录。
4. 在 TTS 合成进程完全退出并释放显存后，对全部成功样本执行一次自动评估。评价器会按需加载；如需排查显存或依赖问题，可用 `--metrics` 单独运行某一类指标。
5. 只在逐样本结果齐全后比较；`templates/scorecard.csv` 只承载汇总展示，不能替代逐样本证据。

详细操作与停止条件见仓库根目录的 [`评估步骤指南.md`](../评估步骤指南.md)。
