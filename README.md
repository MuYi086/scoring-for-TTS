# TTS 与音色设计评估工作区

本仓库用于比较中文文本转语音（TTS）模型的声音克隆、文本忠实度、说话人相似度和自然度。V2 权威入口及早期专项评测使用六个独立后端；分项报告不把不同量纲强行合成一个原始值总分：

- SenseVoice CER + Whisper CER；
- WavLM SIM + SpeechBrain ECAPA SIM；
- UTMOSv2 + NISQA-TTS。

## 新电脑最快复测

完整安装、权重 revision（修订号）、音频迁移、断点续跑和故障处理见 [`docs/跨电脑复测指南.md`](docs/跨电脑复测指南.md)。最短流程是：

```bash
git clone https://github.com/MuYi086/scoring-for-TTS.git
cd scoring-for-TTS
conda env create -f tts-bench/environment/audio-eval-base.yml
conda activate audio_eval
```

然后按指南安装与 GPU 匹配的 PyTorch、执行 `audio-eval-requirements.txt`、下载 `evaluation-assets-v2.json` 中冻结的评价模型，并从旧电脑或外部制品库恢复 `cloneData/audio_v2/*.wav`。

正式运行前先做一键预检：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --strict-versions
```

预检通过后，为每次复测指定新的 `--output-dir`，再运行 [`run_neutral_evaluation_v2.py`](tts-bench/scripts/run_neutral_evaluation_v2.py)。不要直接复用仓库内的历史结果目录。

> 注意：GitHub 仓库包含 V2 和 V3 各三条 `testData/` 原始参考音频、冻结清单和运行记录，但 **不包含** 被 `.gitignore` 忽略的 `cloneData/audio_v2/*.wav`、`cloneData/audio_v3/*.wav`、Task 5 的 `longAudioTest/`、Task 6 的 `longAudioTestV6/*.wav`、Task 7 的 `longAudioTestV7/*.wav`、V8 公共长音频的 `longAudioTestV8/*.wav`，也不包含 `hf-mirror` 权重。V5 的 `buildTestV5/*.wav` 体积较大，迁移和提交前也必须单独确认。只执行 `git clone` 不保证能直接开始评测。

## Task 6 V6 公共长音频评测

V6 对 `longAudioTestV6/` 中 7 条多角色成品逐模型串行评测。全文 CER 以 `ai_deal.json` 中 58 段实际合成台词的 1,783 个 `zh-v1` 规范化字符为唯一参考；`text.md` 是小说原文，共 1,826 个规范化字符，不能替代 CER 参考。

V6 只运行音频交付原始测量、SenseVoice CER 与 Whisper-large-v3-turbo CER；两个 CER 后端独立排名，不合并为总分。长音频 WavLM / ECAPA、UTMOSv2、NISQA 与自动综合排名均被 [公共评测任务](公共评测任务.md) 排除。正式运行前，以 `seed_tts_eval` 环境预检：

```bash
conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/check_neutral_evaluation_v6_setup.py \
  --strict-versions

conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/run_neutral_evaluation_v6.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV6/评测结果 \
  --strict
```

其余六个模型复用同一目录并增加 `--resume`，每次仍只能传一个 `--model-id`。全部完成后运行 `generate_neutral_v6_reports.py`，只生成 `SenseVoice_CER&Whisper-large-v3-turbo_CER_V6评价报告.md` 与 `音频交付与文本一致性_V6自动检查报告.md`。完整命令与验收规则见 [跨电脑复测指南](docs/跨电脑复测指南.md)。

## Task 7 V7 公共长音频评测

V7 对 `longAudioTestV7/` 中 7 条多角色成品逐模型串行评测。全文 CER 以 `ai_deal.json` 中 77 段实际合成台词的 2,066 个 `zh-v1` 规范化字符为唯一参考；`text.md` 是小说原文，共 2,076 个规范化字符，不能替代 CER 参考。

V7 只运行音频交付原始测量、SenseVoice CER 与 Whisper-large-v3-turbo CER；两个 CER 后端独立排名，不合并为总分。长音频 WavLM / ECAPA、UTMOSv2、NISQA 与自动综合排名均被 [公共评测任务](公共评测任务.md) 排除。正式运行前，以 `seed_tts_eval` 环境预检：

```bash
conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/check_neutral_evaluation_v7_setup.py \
  --strict-versions

conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/run_neutral_evaluation_v7.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV7/评测结果 \
  --strict
```

其余六个模型复用同一目录并增加 `--resume`，每次仍只能传一个 `--model-id`。全部完成后运行 `generate_neutral_v7_reports.py`，只生成 `SenseVoice_CER&Whisper-large-v3-turbo_CER_V7评价报告.md` 与 `音频交付与文本一致性_V7自动检查报告.md`。完整命令与验收规则见 [跨电脑复测指南](docs/跨电脑复测指南.md)。

## Task 8 V8 公共长音频评测

V8 对 `longAudioTestV8/` 中 7 条多角色成品逐模型串行评测。全文 CER 以 `ai_deal.json` 中 97 段实际合成台词的 2,513 个 `zh-v1` 规范化字符为唯一参考；`text.md` 是小说原文，共 2,537 个规范化字符，不能替代 CER 参考。

V8 只运行音频交付原始测量、SenseVoice CER 与 Whisper-large-v3-turbo CER；两个 CER 后端独立排名，不合并为总分。长音频 WavLM / ECAPA、UTMOSv2、NISQA 与自动综合排名均被 [公共评测任务](公共评测任务.md) 排除。正式运行前，以 `seed_tts_eval` 环境预检：

```bash
conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/check_neutral_evaluation_v8_setup.py \
  --strict-versions

conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/run_neutral_evaluation_v8.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV8/评测结果 \
  --strict
```

其余六个模型复用同一目录并增加 `--resume`，每次仍只能传一个 `--model-id`。全部完成后运行 `generate_neutral_v8_reports.py`，只生成 `SenseVoice_CER&Whisper-large-v3-turbo_CER_V8评价报告.md` 与 `音频交付与文本一致性_V8自动检查报告.md`。完整命令与验收规则见 [跨电脑复测指南](docs/跨电脑复测指南.md)。

## Task 10 V9 公共长音频评测

V9 对 `longAudioTestV9/` 中 7 条多角色成品逐模型串行评测。七条成品实际按 `ai_deal.json` 的 77 段台词合成，全文 CER 以其中 1,505 个 `zh-v1` 规范化字符为参考；`text.md` 是相邻小说原文，共 1,527 个字符且部分叙述、引号归属与台词顺序不同，不能作为 CER 参考。

长音频受限入口只运行音频交付原始测量、SenseVoice CER 与 Whisper-large-v3-turbo CER。两个 CER 后端独立排名，不合并为总分；长音频 WavLM / ECAPA、UTMOSv2、NISQA 与自动综合排名均被 [公共评测任务](公共评测任务.md) 排除。先以 `seed_tts_eval` 环境预检，再使用一个尚不存在的新输出目录：

```bash
conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/check_neutral_evaluation_v9_setup.py \
  --strict-versions

conda run --no-capture-output -n seed_tts_eval \
  python tts-bench/scripts/run_neutral_evaluation_v9.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV9/评测结果/task10-v9-YYYYMMDDTHHMMSSZ \
  --strict
```

其余六个模型对同一目录增加 `--resume`，每次仍只能传一个 `--model-id`。全部完成后运行 `generate_neutral_v9_reports.py`，只生成 `SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md` 与 `音频交付与文本一致性_V9自动检查报告.md`。完整命令与验收规则见 [跨电脑复测指南](docs/跨电脑复测指南.md)。

### Seed-TTS-Eval 中文外部基准

Seed-TTS-Eval（Seed TTS 官方客观基准）由独立的 [Seed-TTS评测任务](Seed-TTS评测任务.md) 管理。它使用固定官方中文常规集与难例集，按官方 meta 重新生成独立短音频；不是对 `longAudioTestV9/audio_*.wav` 的重复打分，也不由 `run_neutral_evaluation_v9.py` 执行。七模型的逐一复制命令与严格顺序的全量回归命令均写在该手册中；本机变量（含 Qwen3-TTS 的 SoX 路径）以该手册和 `env.example` 为准。相同冻结模型版本只执行一次并复用结果，WER 与 SIM 分别报告，不与 V9 长音频结果或综合分混合。

## 目录入口

- [`docs/跨电脑复测指南.md`](docs/跨电脑复测指南.md)：跨电脑环境、权重、音频和命令的权威操作手册。
- [`Seed-TTS评测任务.md`](Seed-TTS评测任务.md)：固定官方中文集的独立外部基准、手动执行与结果复用规则。
- [`评估步骤指南.md`](评估步骤指南.md)：从第一性原理定义评估流程、准入门槛与结果解释。
- [`tts-bench/`](tts-bench/)：基准清单、运行记录、冻结配置、评测脚本和报告。
- [`cloneData/`](cloneData/)：八个模型的集中声音克隆入口；只有需要重新生成 WAV 时才安装这些独立环境。
- [`modelScript/`](modelScript/)：各 TTS 模型的安装指南与底层合成脚本。
- [`asr/`](asr/)：自动语音识别与 CER 规范化边界。

评价脚本不会调用 TTS 合成模型，也不会下载缺失权重。模型权重、本地环境、云端密钥和机器专属路径均不得提交到仓库。
