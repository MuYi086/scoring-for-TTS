# TTS 与音色设计评估工作区

本仓库用于比较中文文本转语音（TTS）模型的声音克隆、文本忠实度、说话人相似度和自然度。V2 权威入口、Task 4 V3、Task 5 V4、Task 6 V5 与 Task 7 V6 专项评测均使用六个独立后端；分项报告不把不同量纲强行合成一个原始值总分：

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

> 注意：GitHub 仓库包含 V2 和 V3 各三条 `testData/` 原始参考音频、冻结清单和运行记录，但 **不包含** 被 `.gitignore` 忽略的 `cloneData/audio_v2/*.wav`、`cloneData/audio_v3/*.wav`、Task 5 的 `longAudioTest/`、Task 7 的 `longAudioTestV6/*.wav`，也不包含 `hf-mirror` 权重。V5 的 `buildTestV5/*.wav` 体积较大，迁移和提交前也必须单独确认。只执行 `git clone` 不保证能直接开始评测。

## Task 3 V2 复测

当前 V2 使用旁白、辰南、小公主三角色的 24 条克隆音频，输入记录位于 `tts-bench/runs-v2/`，本地音频位于 `cloneData/audio_v2/`。八模型合成入口、固定台词和 IndexTTS2 情感向量见 [`cloneData/README.md`](cloneData/README.md)。恢复音频后先严格预检，再为本次复测创建新输出目录：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_setup.py \
  --runs-root tts-bench/runs-v2 \
  --config tts-bench/config/neutral-evaluation-v2.json \
  --assets tts-bench/config/evaluation-assets-v2.json \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v2.py \
  --output-dir tts-bench/reports/replay-v2-YYYYMMDDTHHMMSSZ \
  --strict
```

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

## Task 5 V4 长音频复测

V4 对 `longAudioTest/` 中 7 条完整多角色音频逐模型串行评价，并以 6 条 MiMo 角色音频提供原始基线或校准对照。SenseVoice 与 Whisper 都使用连续、不重叠的 30 秒分段，避免整条 18–31 分钟 WAV 一次进入模型而引发显存或内存溢出；一次命令必须且只能指定一个 `--model-id`。先预检，再为本次运行使用新目录：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v4_setup.py \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v4.py \
  --model-id dots.tts-base \
  --output-dir longAudioTest/评测结果/task5-v4-YYYYMMDDTHHMMSSZ \
  --strict
```

后续模型对同一次输出目录增加 `--resume`，但每次仍只传一个模型。全部 7 个模型完成后运行 `generate_neutral_v4_reports.py` 生成三份 V4 汇总报告。完整模型清单、续跑顺序、输入恢复和验收规则见跨电脑复测指南第 14 节。

## Task 6 V5 长音频复测

V5 对 `buildTestV5/` 中 7 条《红房间》多角色成品逐模型串行评价，并以 5 条 MiMo 角色音频提供原始基线与说话人校准。成品实际按 `ai_deal.json` 的 93 段台词合成，全文 CER 以其中 4713 个 `zh-v1` 规范化字符为参考；原始 `text.md` 多出的 198 个说话人提示字符不进入 CER。正式运行仍先预检，并为本次运行使用新目录：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v5_setup.py \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v5.py \
  --model-id dots.tts-base \
  --output-dir buildTestV5/评测结果/task6-v5-YYYYMMDDTHHMMSSZ \
  --strict
```

后续按 `IndexTTS2`、`LongCat-AudioDiT-1B`、`MOSS-TTS-Local-Transformer-v1.5`、`OmniVoice`、`Qwen3-TTS-12Hz-1.7B-Base`、`VoxCPM2` 的顺序评价；对同一次输出目录增加 `--resume`，一次仍只传一个模型。全部完成后运行 `generate_neutral_v5_reports.py`，生成三份双后端报告和 `小说转有声TTS_V5综合评价报告.md`。综合报告先把六后端各自的名次换算到统一尺度，再按台词正确性 50%、角色音色 30%、自然听感 20% 加权，不直接平均跨量纲原始值。完整命令与验收规则见跨电脑复测指南第 15 节。

## Task 7 V6 长音频复测

V6 对 `longAudioTestV6/` 中 7 条多角色成品逐模型串行评价，并以旁白、三皇子、小公主、辰南 4 条 MiMo 角色音频提供原始基线与说话人校准。成品按 `ai_deal.json` 的 58 段台词合成，全文 CER 以其中 1783 个 `zh-v1` 规范化字符为参考；`text.md` 多出的 43 个说话人提示字符不进入 CER。正式运行先预检，再使用一个全新的输出目录：

```bash
conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/check_neutral_evaluation_v6_setup.py \
  --strict-versions

conda run --no-capture-output -n audio_eval \
  python tts-bench/scripts/run_neutral_evaluation_v6.py \
  --model-id dots.tts-base \
  --output-dir longAudioTestV6/评测结果/task7-v6-YYYYMMDDTHHMMSSZ \
  --strict
```

其余模型对同一目录增加 `--resume`，每次仍只能传一个 `--model-id`。全部完成后运行 `generate_neutral_v6_reports.py`，生成三份 V6 双后端报告和 task7 明确指定文件名的 `小说转有声TTS_V5综合评价报告.md`；综合报告正文和证据版本均为 V6。统一名次尺度与生产权重沿用台词正确性 50%、角色音色 30%、自然听感 20%。完整命令与验收规则见跨电脑复测指南第 16 节。

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
