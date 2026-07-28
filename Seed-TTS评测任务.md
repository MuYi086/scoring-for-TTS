# Seed-TTS 中文外部评测任务

状态：**已准备好手动执行；尚未生成任何 Seed-TTS 音频、WER（词错误率）或 SIM（说话人相似度）结果。**

这是 Seed-TTS-Eval 官方中文短句基准的唯一操作手册。日常使用只需要执行 `Seed-TTS-test/scripts/` 外层的八个脚本；目录内的 `internal/` 是实现、冻结与兼容代码，**不是日常入口**。

## 1. 评测范围

- 固定输入为官方 `zh/meta.lst`（2,020 条）和 `zh/hardcase.lst`（400 条），每条生成一个 `<utt>.wav`。
- 每个模型严格逐条串行合成；全量回归也严格逐模型串行，绝不并发争抢同一 GPU（图形处理器）。
- 每个模型分别报告中文 WER 与 WavLM-large-SV SIM；不生成跨量纲总分、总排名，也不混入长音频评测。
- 每次新评测使用新的 `run-id` 或 `batch-id`；只有中断同一次运行时才用 `--resume`。

## 2. 你会直接执行的脚本

| 用途 | 脚本 |
| --- | --- |
| dots.tts-base 单模型完整评测 | `test_dots_tts.sh` |
| IndexTTS2 单模型完整评测 | `test_indextts2.sh` |
| LongCat-AudioDiT-1B 单模型完整评测 | `test_longcat_audiodit.sh` |
| MOSS-TTS 单模型完整评测 | `test_moss_tts.sh` |
| OmniVoice 单模型完整评测 | `test_omnivoice.sh` |
| Qwen3-TTS 单模型完整评测 | `test_qwen3_tts.sh` |
| VoxCPM2 单模型完整评测 | `test_voxcpm2.sh` |
| 七模型固定顺序全量回归 | `test_all_models.sh` |

每个单模型脚本都会自动完成：前置检查 → 官方清单逐条串行合成 → WER → SIM → Markdown 报告。无需手工调用预检、合成、评分或报告脚本。

## 3. 开始前只做一次

加载本机配置。当前机器已提供被 Git 忽略的 `Seed-TTS-test/.env`；换机器时以 [`Seed-TTS-test/env.example`](Seed-TTS-test/env.example) 填写本机路径，禁止提交真实路径、令牌或大体积音频。

```bash
source Seed-TTS-test/.env
```

公共入口会自动检查七模型权重、官方清单、参考音频、评分资源、独立 Conda（Python 环境管理器）环境、Qwen3-TTS 所需 SoX（音频处理工具）及评分器补丁。检查失败时，先修复环境，不要通过开始合成来试错。

## 4. 单独完整评测一个模型

从下列七条命令中**只复制一条**执行；每条都会生成独立的 `run-id`，无需手改模型名或脚本名。

### dots.tts-base

```bash
bash Seed-TTS-test/scripts/test_dots_tts.sh --run-id "seedtts-dots-$(date -u +%Y%m%dT%H%M%SZ)"
```

### IndexTTS2

```bash
bash Seed-TTS-test/scripts/test_indextts2.sh --run-id "seedtts-indextts2-$(date -u +%Y%m%dT%H%M%SZ)"
```

### LongCat-AudioDiT-1B

```bash
bash Seed-TTS-test/scripts/test_longcat_audiodit.sh --run-id "seedtts-longcat-$(date -u +%Y%m%dT%H%M%SZ)"
```

### MOSS-TTS-Local-Transformer-v1.5

```bash
bash Seed-TTS-test/scripts/test_moss_tts.sh --run-id "seedtts-moss-$(date -u +%Y%m%dT%H%M%SZ)"
```

### OmniVoice

```bash
bash Seed-TTS-test/scripts/test_omnivoice.sh --run-id "seedtts-omnivoice-$(date -u +%Y%m%dT%H%M%SZ)"
```

### Qwen3-TTS-12Hz-1.7B-Base

```bash
bash Seed-TTS-test/scripts/test_qwen3_tts.sh --run-id "seedtts-qwen3-$(date -u +%Y%m%dT%H%M%SZ)"
```

### VoxCPM2

```bash
bash Seed-TTS-test/scripts/test_voxcpm2.sh --run-id "seedtts-voxcpm2-$(date -u +%Y%m%dT%H%M%SZ)"
```

如果一次单模型评测中断，把当时终端输出的 `run-id` 原样填入下面命令后续跑：

```bash
bash Seed-TTS-test/scripts/test_qwen3_tts.sh --run-id "上次的run-id" --resume
```

如果合成已经完成、仅评分失败，用对应模型的同一脚本补跑评分（不加载 TTS 模型）：

```bash
bash Seed-TTS-test/scripts/test_qwen3_tts.sh --run-id "上次的run-id" --score-only
```

## 5. 七模型顺序全量回归

全量脚本按下列顺序执行，并在任一模型失败时停止：dots.tts-base → IndexTTS2 → LongCat-AudioDiT-1B → MOSS-TTS → OmniVoice → Qwen3-TTS → VoxCPM2。

```bash
bash Seed-TTS-test/scripts/test_all_models.sh --batch-id "seedtts-regression-$(date -u +%Y%m%dT%H%M%SZ)"
```

中断后用相同 `batch-id` 续跑：

```bash
bash Seed-TTS-test/scripts/test_all_models.sh --batch-id "上次的batch-id" --resume
```

续跑时，已有完整报告的模型自动跳过；未完成合成的模型继续；已完成合成但未评分的模型只进入评分。

## 6. 结果位置与验收

每个模型的音频结果位于 `Seed-TTS-test/result/<模型目录>/<run-id>/`，报告位于 `Seed-TTS-test/report/<模型目录>/<run-id>/`。报告必须同时具有两个分集的完整 WAV 覆盖、逐条 WER/SIM 原始输出、模型与资源冻结信息，且 WER 与 SIM 保持独立呈现。

结果目录与报告目录被 Git 忽略；不得提交生成 WAV、模型缓存、`pip freeze` 或机器专属路径。

跨机器重建或维护内部环境时，才需要由维护者使用 `scripts/internal/` 下的工具；它们不属于本手册的日常评测步骤。
