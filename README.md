# TTS 与音色设计评估工作区

本仓库用于比较中文文本转语音（TTS）模型的声音克隆、文本忠实度、说话人相似度和自然度。V2 权威入口与 Task 4 V3 专项评测均使用六个独立后端，不把不同量纲强行合成一个总分：

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

然后按指南安装与 GPU 匹配的 PyTorch、执行 `audio-eval-requirements.txt`、下载 `evaluation-assets-v2.json` 中冻结的评价模型，并从旧电脑或外部制品库恢复 `cloneData/*.wav`。

正式运行前先做一键预检：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --strict-versions
```

预检通过后，为每次复测指定新的 `--output-dir`，再运行 [`run_neutral_evaluation_v2.py`](tts-bench/scripts/run_neutral_evaluation_v2.py)。不要直接复用仓库内的历史结果目录。

> 注意：GitHub 仓库包含 V2 和 V3 各三条 `testData/` 原始参考音频、冻结清单和运行记录，但 **不包含** 被 `.gitignore` 忽略的 `cloneData/*.wav` 与 `cloneData/audio_v3/*.wav`，也不包含 `hf-mirror` 权重。只执行 `git clone` 不能直接开始评测。

## Task 4 V3 复测

V3 使用旁白、小公主、三皇子三角色的 24 条克隆音频，输入记录与 V2 隔离在 `tts-bench/runs-v3/`。恢复 `cloneData/audio_v3/*.wav` 后，先用 V3 配置预检，再使用新输出目录运行：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --runs-root tts-bench/runs-v3 \
  --config tts-bench/config/neutral-evaluation-v3.json \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v3.py \
  --output-dir tts-bench/reports/replay-v3-YYYYMMDDTHHMMSSZ \
  --strict
```

完整的 V2/V3 权重、音频迁移、断点续跑与报告命令见 [`docs/跨电脑复测指南.md`](docs/跨电脑复测指南.md)。

## 目录入口

- [`docs/跨电脑复测指南.md`](docs/跨电脑复测指南.md)：跨电脑环境、权重、音频和命令的权威操作手册。
- [`评估步骤指南.md`](评估步骤指南.md)：从第一性原理定义评估流程、准入门槛与结果解释。
- [`tts-bench/`](tts-bench/)：基准清单、运行记录、冻结配置、评测脚本和报告。
- [`cloneData/`](cloneData/)：八个模型的集中声音克隆入口；只有需要重新生成 WAV 时才安装这些独立环境。
- [`modelScript/`](modelScript/)：各 TTS 模型的安装指南与底层合成脚本。
- [`asr/`](asr/)：自动语音识别与 CER 规范化边界。
- [`wavlm/`](wavlm/)：说话人相似度与校准边界。
- [`utmosv2/`](utmosv2/)：自然度预测器说明。
- [`listener-review/`](listener-review/)：人工盲听材料，不进入自动总分。

评价脚本不会调用 TTS 合成模型，也不会下载缺失权重。模型权重、本地环境、云端密钥和机器专属路径均不得提交到仓库。
