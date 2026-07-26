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
├── runs/            # 历史 V1 合成记录；其中音频不提交
├── runs-v2/         # Task 3 V2 独立的八模型合成记录
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

当前 V2 使用旁白、辰南、小公主三角色，冻结清单为 `manifests/task3-2026-07-19-v2.jsonl`，合成记录和音频分别位于 `runs-v2/` 与 `../cloneData/audio_v2/`。`neutral-evaluation-v2.json` 的六后端流程分别运行 SenseVoice CER、Whisper CER、WavLM SIM、SpeechBrain ECAPA SIM、UTMOSv2 和 NISQA-TTS，不计算跨指标加权总分；CER 与自然度包含原始参考音频基线，说话人相似度包含同说话人分段和跨角色校准对照。

新电脑的完整环境与权重准备以 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 为准。基础环境、Python 依赖和冻结评价资产分别在 `environment/` 与 `config/evaluation-assets-v2.json`。

正式运行前先检查包版本、CUDA、权重、24 条克隆 WAV 和登记哈希：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --runs-root tts-bench/runs-v2 \
  --config tts-bench/config/neutral-evaluation-v2.json \
  --assets tts-bench/config/evaluation-assets-v2.json \
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
  --runs-root tts-bench/runs-v2 \
  --output-dir tts-bench/reports/replay-v2-YYYYMMDDTHHMMSSZ \
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

## Task 5 V4 长音频中立评测

V4 的冻结事实源是 `config/neutral-evaluation-v4.json`。本地输入位于被忽略的 `../longAudioTest/`：7 条模型长音频、6 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。本批成品正文实际对应 `ai_deal.json` 的 148 段 `dialogue`，因此全文 CER 以这些台词按原顺序拼接为参考；`text.md` 与其是相邻但不同的小说片段，不能混用。

V4 一次进程只允许一个 `--model-id`。SenseVoice 与 Whisper 都把单条长音频切为连续、不重叠的 30 秒分段顺序转写，Whisper 的逐段字词时间戳会平移回全局时间轴；时间戳与冻结台词单调对齐，跨角色块按精确匹配字符的角色连续区间线性切分时间，再合并为角色片段，之后才运行 WavLM 与 ECAPA。UTMOSv2 和 NISQA-TTS 对全长固定等距窗口评价。每完成一条记录都会原子写回，终端中断后只对同一次输出目录使用 `--resume`。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v4_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v4.py \
  --model-id dots.tts-base \
  --output-dir longAudioTest/评测结果/task5-v4-YYYYMMDDTHHMMSSZ \
  --strict
```

第二个及后续模型使用同一目录并增加 `--resume`。全部覆盖完整后生成三份独立汇总报告：

```bash
python tts-bench/scripts/generate_neutral_v4_reports.py \
  --results-dir longAudioTest/评测结果/task5-v4-YYYYMMDDTHHMMSSZ \
  --reports-dir longAudioTest/评测结果
```

各模型六后端完成时还会在 `longAudioTest/评测结果/` 写入 `<model_id>_V4评价报告.md`。完整的 7 模型顺序、环境变量、输入恢复和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 14 节。

## Task 6 V5 长音频中立评测

V5 的冻结事实源是 `config/neutral-evaluation-v5.json`，输入位于 `../buildTestV5/`：7 条模型长音频、5 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。七条成品按 `ai_deal.json` 的 93 段 `dialogue` 合成，因此全文 CER 使用其 4713 个 `zh-v1` 规范化字符；`text.md` 多出的 198 个说话人提示字符不进入本批 CER。

V5 复用 V4 的防内存溢出机制：每次进程只处理一个 `--model-id`；双 ASR 对连续、不重叠的 30 秒分段顺序转写；双 SIM 只读取 Whisper 时间戳对齐出的五个角色片段；双自然度只读取固定等距的 12 秒窗口。每条记录原子保存，可以只对同一次输出目录断点续跑。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v5_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v5.py \
  --model-id dots.tts-base \
  --output-dir buildTestV5/评测结果/task6-v5-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，且每次只传一个 `--model-id`。全部覆盖完整后生成三份分项报告和一份生产权重综合报告：

```bash
python tts-bench/scripts/generate_neutral_v5_reports.py \
  --results-dir buildTestV5/评测结果/task6-v5-YYYYMMDDTHHMMSSZ \
  --reports-dir buildTestV5/评测结果
```

分项报告保留六个后端的原始值与独立名次。综合报告不直接混合 CER、SIM 与预测 MOS 原始值，而是先转换各后端的本批名次分，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权。完整迁移、运行顺序和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 15 节。

## Task 7 V6 长音频中立评测

V6 的冻结事实源是 `config/neutral-evaluation-v6.json`，输入位于 `../longAudioTestV6/`：7 条模型长音频、4 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。七条成品按 `ai_deal.json` 的 58 段 `dialogue` 合成，因此全文 CER 使用其 1783 个 `zh-v1` 规范化字符；`text.md` 多出的 43 个说话人提示字符不进入本批 CER。

V6 复用经过测试的长音频流程：每次进程只处理一个 `--model-id`；双 ASR 对连续、不重叠的 30 秒分段顺序转写；双 SIM 使用 Whisper 时间戳对齐出的四角色片段；双自然度只读取 8 个固定等距的 12 秒窗口。每条记录原子保存，只能对同一次未完成运行的原目录断点续跑。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v6_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v6.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV6/评测结果/task7-v6-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，且每次只传一个 `--model-id`。全部覆盖完整后生成三份分项报告和一份生产权重综合报告：

```bash
python tts-bench/scripts/generate_neutral_v6_reports.py \
  --results-dir longAudioTestV6/评测结果/task7-v6-YYYYMMDDTHHMMSSZ \
  --reports-dir longAudioTestV6/评测结果
```

前三份报告文件名使用 V6；综合报告按 `task7.md` 的明确要求保留文件名 `小说转有声TTS_V5综合评价报告.md`，但正文、配置和原始证据均标识为 V6。综合分只对六后端的本批名次做统一尺度转换，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权。完整迁移、运行顺序和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 16 节。

## Task 8 V7 长音频中立评测

V7 的冻结事实源是 `config/neutral-evaluation-v7.json`，输入位于 `../longAudioTestV7/`：7 条模型长音频、3 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。七条成品按 `ai_deal.json` 的 77 段 `dialogue` 合成，因此全文 CER 使用其 2066 个 `zh-v1` 规范化字符；`text.md` 多出的 10 个字符是两处叙述性说话提示，不进入本批 CER。

V7 继续使用长音频中立流程：每次进程只处理一个 `--model-id`；双 ASR 对连续、不重叠的 30 秒分段顺序转写；双 SIM 使用 Whisper 时间戳对齐出的三角色片段；角色若完全没有达到 4 个精确匹配字符的标准候选，才使用至少 2 个精确匹配字符且满足其余门槛的短台词回退片段，并在原始结果和报告中显式标记；双自然度只读取 8 个固定等距的 12 秒窗口。每条记录原子保存，只能对同一次未完成运行的原目录断点续跑。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v7_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v7.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV7/评测结果/task8-v7-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，且每次只传一个 `--model-id`。全部覆盖完整后生成三份分项报告和一份生产权重综合报告：

```bash
python tts-bench/scripts/generate_neutral_v7_reports.py \
  --results-dir longAudioTestV7/评测结果/task8-v7-YYYYMMDDTHHMMSSZ \
  --reports-dir longAudioTestV7/评测结果
```

按 `task8.md` 的明确要求，前三份报告沿用 V6 文件名，综合报告沿用 `小说转有声TTS_V5综合评价报告.md`，但正文、配置和原始证据均标识为 V7。综合分只对六后端的本批名次做统一尺度转换，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权。完整迁移、运行顺序和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 17 节。

## Task 9 V8 长音频中立评测

V8 的冻结事实源是 `config/neutral-evaluation-v8.json`，输入位于 `../longAudioTestV8/`：7 条模型长音频、4 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。七条成品按 `ai_deal.json` 的 97 段 `dialogue` 合成，因此全文 CER 使用其 2513 个 `zh-v1` 规范化字符；`text.md` 多出的 24 个叙述性字符不进入本批 CER。

V8 继续使用长音频中立流程：每次进程只处理一个 `--model-id`；双 ASR 对连续、不重叠的 30 秒分段顺序转写；双 SIM 使用 Whisper 时间戳对齐出的四角色片段；若某角色没有达到 4 个精确匹配字符的标准候选，才允许使用至少 2 个精确匹配字符且满足其余门槛的短台词回退片段，并在原始结果与报告中显式标记；双自然度只读取 8 个固定等距的 12 秒窗口。每条记录原子保存，只能对同一次未完成运行的原目录断点续跑。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v8_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v8.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV8/评测结果/task9-v8-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，且每次只传一个 `--model-id`。全部覆盖完整后生成三份分项报告和一份生产权重综合报告：

```bash
python tts-bench/scripts/generate_neutral_v8_reports.py \
  --results-dir longAudioTestV8/评测结果/task9-v8-YYYYMMDDTHHMMSSZ \
  --reports-dir longAudioTestV8/评测结果
```

输出为 `SenseVoice_CER&Whisper_CER_V8评价报告.md`、`WavLM_SIM&SpeechBrain_ECAPA_SIM_V8评价报告.md`、`UTMOSv2&NISQA_V8评价报告.md` 和 task9 指定文件名的 `小说转有声TTS_V5综合评价报告.md`。前三份报告保留原始量纲和独立名次；综合报告只转换六个后端的本批名次，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权。完整迁移、运行顺序和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 18 节。

## Task 10 V9 长音频中立评测

V9 的冻结事实源是 `config/neutral-evaluation-v9.json`，输入位于 `../longAudioTestV9/`：7 条模型长音频、5 条 MiMo 角色参考音频、`ai_deal.json` 与 `text.md`。七条成品按 `ai_deal.json` 的 77 段 `dialogue` 合成，因此全文 CER 使用其 1,505 个 `zh-v1` 规范化字符；`text.md` 有 1,527 个字符且与实际合成输入存在叙述、引号归属与顺序差异，不进入本批 CER。

V9 延续中立长音频流程：每次进程只处理一个 `--model-id`；SenseVoice 与 Whisper 对连续、不重叠的 30 秒分段顺序转写；双 SIM 使用 Whisper 字词时间戳对齐出的五角色片段；某角色无至少 4 个精确匹配字符的标准候选时，才使用至少 2 个精确匹配字符且满足其余门槛的短台词回退片段，并在原始结果和报告中显式标记；双自然度仅处理 8 个固定等距的 12 秒窗口。每条记录原子保存，只能对同一次未完成运行的原目录断点续跑。

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v9_setup.py \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v9.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV9/评测结果/task10-v9-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，且每次只传一个 `--model-id`。全部覆盖完整后生成三份分项报告和一份生产权重综合报告：

```bash
python tts-bench/scripts/generate_neutral_v9_reports.py \
  --results-dir longAudioTestV9/评测结果/task10-v9-YYYYMMDDTHHMMSSZ \
  --reports-dir longAudioTestV9/评测结果
```

输出为 `SenseVoice_CER&Whisper_CER_V9评价报告.md`、`WavLM_SIM&SpeechBrain_ECAPA_SIM_V9评价报告.md`、`UTMOSv2&NISQA_V9评价报告.md` 和任务明确指定的 `小说转有声TTS_V5综合评价报告.md`。前三份报告保留原始量纲和独立名次；综合报告只转换六后端的本批名次，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权。完整迁移、运行顺序和验收步骤见 [`../docs/跨电脑复测指南.md`](../docs/跨电脑复测指南.md) 第 19 节。

## 新建一次合成运行

1. 从 `templates/run.example.yaml` 复制为 `runs/<run_id>/run.yaml`，填写模型版本、配置快照和冻结的清单路径。
2. 由 `modelScript/` 中相应脚本手工合成，把原始 WAV 放在 `runs/<run_id>/audio/<case_id>.wav`。该目录被忽略，避免大音频进入 Git。
3. 以 `contracts/synthesis-record.schema.json` 为准，逐行填写 `synthesis.jsonl`。每条成功或失败的尝试都应留下记录。
4. 在 TTS 合成进程完全退出并释放显存后，对全部成功样本执行一次自动评估。评价器会按需加载；如需排查显存或依赖问题，可用 `--metrics` 单独运行某一类指标。
5. 只在逐样本结果齐全后比较；`templates/scorecard.csv` 只承载汇总展示，不能替代逐样本证据。

详细操作与停止条件见仓库根目录的 [`评估步骤指南.md`](../评估步骤指南.md)。
