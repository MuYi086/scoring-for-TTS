# Task 8：V8 长文本旁白克隆合成与评测

Task 8 分为严格顺序的两个阶段：先仅用 IndexTTS2 与 VoxCPM2 克隆 V8 旁白并生成成品，再按 [公共评测任务.md](公共评测任务.md) 评测这两条成品。公共任务只约束第二阶段的评测规则、执行顺序和报告边界；本文件定义 V8 的合成输入、合成入口与两阶段衔接。

`audio_*.wav` 是第一阶段的本地生成产物，不是启动整个 Task 8 前必须由外部提供的条件。它们只是在第二阶段正式评测前必须存在的候选成品。

## 1. V8 固定输入与成品命名

| 项目 | 固定值 |
| --- | --- |
| `<评测目录>` | `longAudioTestV8` |
| `<版本标识>` | `V8` |
| 合成原文 / `<实际台词串>` | `longAudioTestV8/text.md` 的实际全文与原始顺序 |
| 人物 | 旁白 |
| 参考音频 | `longAudioTestV8/mimo_旁白_v8.wav` |
| 参考文案 | 车轮碾过积雪，细碎声响中驯鹿的身影在漆黑的夜里纹丝不动。 |
| 音色说明 | 男性，三十至四十五岁，中低音域，音色厚实沉稳，略带沙哑质感，明亮度偏暗，共鸣饱满。咬字清晰有力，语速中等偏慢，节奏平稳，停顿自然，默认情绪基调冷静克制，带有成人叙述故事的神秘感和沉稳气质。 |
| IndexTTS2 成品 | `longAudioTestV8/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV8/audio_voxcpm2.wav` |
| 合成入口 | `task-runner/task8/run_task8_synthesis.py` |
| `<评测运行目录>` | `task-runner/task8` |
| `<输出目录>` | `longAudioTestV8/评测结果` |

当前 V8 目录不含 `ai_deal.json`。禁止使用历史 V8 的分角色台词、字符数、报告或其他版本的文本/音频；每条 V8 成品都必须由上述 `text.md` 全文、原始顺序和同一旁白参考音频生成。

Task 8 的模型集合固定且仅为 `indextts2`（IndexTTS2）和 `voxcpm2`（VoxCPM2），按此顺序串行合成与评测。不得加入 Qwen3-TTS、MiMo、dots.tts 或任何其他候选；也不得用历史 V8 或 V9 的同名音频替代本轮产物。成品、模型目录、源码目录、运行缓存和本地计划均不提交；不得在计划或命令行中写入 API 密钥。

## 2. 阶段一：先合成 V8 候选成品

先从仓库内模板建立本机计划；计划文件包含 IndexTTS2 与 VoxCPM2 各自的 Conda 环境、模型目录和源码目录，因此只能保存在被忽略的本地路径。`models` 数组必须且只能按 `indextts2`、`voxcpm2` 的顺序保留两项，合成入口会为两个模型冻结同一份 V9 同款 `{segment_manifest}`，并要求二者均写入 `{segment_evidence_root}`。IndexTTS2 可通过独立 `--emo-text {voice_description}` 接收风格说明；VoxCPM2 只能传 `{reference_audio}`、`{reference_transcript}` 和正文片段，严禁 `--style-prompt`，因为该本地脚本会把它拼进正文并朗读。

```bash
cp task-runner/task8/synthesis-plan.example.json \
  longAudioTestV8/.task8-synthesis-plan.json

# 编辑本机模型/源码路径；先只验证计划、固定输入和展开后的命令。
python task-runner/task8/run_task8_synthesis.py \
  --plan longAudioTestV8/.task8-synthesis-plan.json --dry-run

# 先 IndexTTS2、后 VoxCPM2 串行合成两条成品；避免争用同一张 GPU。
python task-runner/task8/run_task8_synthesis.py \
  --plan longAudioTestV8/.task8-synthesis-plan.json
```

合成入口只接受 JSON 字符串数组形式的命令，不经 shell 解释。它会在临时目录中生成并解码检查 WAV，随后原子写入 `audio_<模型标识>.wav`，避免失败时留下半成品；每条成品还会保存本地合成记录，登记原文、参考音频、输出哈希、共享清单哈希和已脱敏命令。已有同名成品时，必须显式传入 `--overwrite` 才能重新合成；也可用 `--models <模型标识> ...` 只重跑指定模型。

阶段一会按参考音频语速生成共享语义分段清单；清单严格校验分段串接后等于 `text.md` 全文与原始顺序，且不得把相邻上下文、参考文案或音色说明朗读进成品。两个模型都逐段合成、按同一停顿规则拼接，并在 `longAudioTestV8/.task8_synthesis_evidence/<模型>/<成品 SHA-256>/` 写入与最终 WAV 哈希绑定的片段音频、片段文本哈希和时间位置。该目录为本地可复核资产，已忽略，不能手工编辑或提交；任何重编码或替换成品 WAV 都会令证据失效，必须重新合成。

## 3. 阶段二：评测已生成的成品

阶段一必须完成 `audio_indextts2.wav` 和 `audio_voxcpm2.wav` 两条成品后，才进入公共评测。V8 的受限评测入口如下；先预检，再以 `indextts2` 创建新结果目录，随后仅以 `voxcpm2` 对同一目录使用 `--resume`。完整命令、双 ASR（自动语音识别）规则、报告边界和人工试听边界均以公共任务为准。

| 公共任务占位符 | V8 实际文件 |
| --- | --- |
| `<预检器>` | `check_task8_evaluation_setup.py` |
| `<评测器>` | `run_task8_evaluation.py` |
| `<报告生成器>` | `generate_task8_reports.py` |
| 冻结契约 | `task-runner/task8/evaluation-contract.json` |

阶段一的候选集合固定为 `longAudioTestV8/audio_indextts2.wav` 与 `longAudioTestV8/audio_voxcpm2.wav`；首次评测会冻结二者及哈希。因此在某一结果目录首次运行后，不得新增、替换、删除或重编码其中任意成品，必须新建结果目录。
