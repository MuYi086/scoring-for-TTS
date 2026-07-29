# Task 7 V7 旁白克隆合成与评测

Task 7 分为严格顺序的两个阶段：先仅用 IndexTTS2 与 VoxCPM2 克隆 V7 旁白并生成成品，再按 [公共评测任务.md](公共评测任务.md) 评测这两条成品。`audio_*.wav` 是第一阶段的输出，不是开始整个任务前由外部提供的前置条件。

## 固定输入与最终成品

| 项目 | 固定值 |
| --- | --- |
| 合成全文 | `longAudioTestV7/text.md` 全文，原始顺序不变 |
| 旁白参考音频 | `longAudioTestV7/mimo_旁白_v7.wav` |
| 参考文案 | 夜夜如此，我听见头顶传来三声闷响，不像老鼠，更像精准的敲击。 |
| 音色说明 | 成年女性，中频偏暗，音色略带沙哑与气声，声线薄透但不过分尖锐，共鸣自然，发声力度适中偏轻柔。咬字清晰利落，语速中等偏慢，节奏均匀，停顿自然沉稳，默认情绪基调为冷静克制的叙述，隐含一丝不安但波动极小，整体气质内敛而耐听。 |
| IndexTTS2 成品 | `longAudioTestV7/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV7/audio_voxcpm2.wav` |

禁止使用 `ai_deal.json`、历史 V6/V7/V8/V9 音频或其他版本文本替代上述输入。CER（字符错误率）唯一参考是本表中的 `text.md` 全文。

## 模型边界与阶段一合成

Task 7 的模型集合固定且仅为 `indextts2`（IndexTTS2）和 `voxcpm2`（VoxCPM2），按此顺序串行合成与评测。不得加入 Qwen3-TTS、MiMo、dots.tts 或任何其他候选；也不得用历史成品替代本轮产物。成品、模型目录、源码目录、运行缓存和本机计划均不提交；不得在计划或命令行中写入 API 密钥。

从模板建立被忽略的本机计划。`models` 数组必须且只能按 `indextts2`、`voxcpm2` 的顺序保留两项；合成入口会按旁白参考语速冻结一份共享语义分段清单，两个模型都必须读取它并写入逐段证据。IndexTTS2 通过独立 `--emo-text {voice_description}` 接收风格说明；VoxCPM2 只能传旁白参考音频、固定参考文案和正文片段，严禁 `--style-prompt`，因为该本地脚本会将其拼入正文并朗读。

```bash
cp task-runner/task7/synthesis-plan.example.json longAudioTestV7/.task7-synthesis-plan.json

# 先核对本机路径、固定输入与两模型约束，不写入音频。
python task-runner/task7/run_task7_synthesis.py --dry-run

# 先 IndexTTS2、后 VoxCPM2 串行合成；避免争用同一张 GPU。
python task-runner/task7/run_task7_synthesis.py
```

合成器会先按参考语速冻结共享分段清单；两个模型均逐段合成，并按同一停顿规则拼接。确认 WAV 可解码后才原子写入标准 `audio_<model_id>.wav`，同时写入与分段文本、片段 WAV、共享清单及最终成品哈希绑定的本地证据。已有同名候选默认拒绝覆盖；确需重新合成时，显式增加 `--overwrite`。不得在两条成品完成后重新编码或替换任意一条，否则证据失效，必须重新合成。

## 阶段二公共评测

阶段一必须完成 `audio_indextts2.wav`、`audio_voxcpm2.wav` 及其逐段证据后，才进入公共评测。评测器先核验最终 WAV、共享清单和逐段证据的哈希，再让两个 ASR（自动语音识别）后端按语义段独立转写并汇总全文 CER；不得改为固定时间窗口或将整条长音频一次送入 ASR。

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task7/check_task7_evaluation_setup.py

RESULT_DIR="longAudioTestV7/评测结果/task-V7-$(date -u +%Y%m%dT%H%M%SZ)"

HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task7/run_task7_evaluation.py \
  --model-id indextts2 --output-dir "$RESULT_DIR" --strict

HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task7/run_task7_evaluation.py \
  --model-id voxcpm2 --output-dir "$RESULT_DIR" --resume --strict

python task-runner/task7/generate_task7_reports.py \
  --results-dir "$RESULT_DIR" --reports-dir longAudioTestV7/评测结果
```

首次评测会冻结全文、参考音频、两条候选及其 SHA-256（安全散列算法）哈希；续跑时任一项变化都必须新建结果目录。双 ASR（自动语音识别）CER 保持独立名次，禁止平均成综合分；音色贴合、自然度和表演性由人工试听判断。
