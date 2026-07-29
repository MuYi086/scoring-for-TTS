# Task 9：双模型长文本旁白克隆与公共评测

本任务以 `longAudioTestV9/text.md` 的实际全文为唯一合成台词，分别用 IndexTTS2 与 VoxCPM2 克隆同一位旁白，并按 [公共评测任务.md](公共评测任务.md) 导出双 ASR（自动语音识别）CER（字符错误率）和交付原始测量。所有 Task 9 脚本必须位于 `task-runner/task9/`；不得修改 `modelScript/` 中用于跨设备安装和备份的脚本。

## 1. 固定输入、角色与成品

| 项目 | 固定值 |
| --- | --- |
| 合成原文 | `longAudioTestV9/text.md` |
| 人物 | 旁白 |
| 参考音频 | `longAudioTestV9/mimo_旁白_v9.wav` |
| 参考文案 | 深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。 |
| 音色说明 | 女声，20–30 岁，中音区略偏低；沉静、敏锐、略带暖意；咬字清晰但不刻板，中等偏慢语速，自然停顿；整体像深夜播讲都市传说的悬念播客旁白。 |
| IndexTTS2 成品 | `longAudioTestV9/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV9/audio_voxcpm2.wav` |
| 逐段合成证据 | `longAudioTestV9/.task9_synthesis_evidence/<模型>/<成品 SHA-256>/`（忽略，不提交） |

成品只能使用上述参考音频、参考文案和 `text.md`。禁止以旧 V9 的 `ai_deal.json`、分角色台词或旧字符统计替代实际全文。

## 2. 共享分段与拼接协议

不能把“最多 80 字”当作固定标准。长文本克隆先按语义完整的句子和段落切分，再用参考音频的真实语速换算每段时长预算；这样既避免句内硬切，也不会让不同语速的角色被同一字数阈值错误约束。

Task 9 的已验证默认值如下，均由 `task-runner/task9/text_segments.py` 实现：

- 使用参考文案与参考 WAV 计算语速；本批次为约 2.923 个规范化字符/秒。
- 目标片段时长为 25 秒，最大时长为 35 秒。优先在完整句、完整段落处断开；只有单句超过最大预算时，才依次在次级标点、字符预算处拆分。
- 在任何模型加载前生成 `longAudioTestV9/.task9_segment_manifest.json`。清单必须记录原文/参考音频哈希、语速、预算、每段文本哈希、顺序、估算时长、边界类型和拼接停顿。
- IndexTTS2 和 VoxCPM2 必须读取同一份清单，逐段克隆后按同一规则拼接：强制断开 250ms、句末 500ms、段落末 750ms、末段 0ms。
- 若本地模型没有明确的前后文参数，不得把相邻文本拼入待朗读台词；相邻关系由清单顺序保留，避免污染全文 CER。若模型支持上下文 API，必须冻结其精确传参，并保证上下文不会被朗读到成品中。

此次文本清单共 23 段、1,527 个规范化字符、单段 48–73 字，所有断点均位于句末或段落末。该数字只是本次输入的执行记录，不是后续任务的固定要求。

## 3. 合成执行顺序

模型与源码目录通过参数或环境变量提供，不能把本机绝对路径写入仓库。以下命令中的 `/path/to/...` 必须替换为本机本地镜像位置。

先做无模型预检，确认输入、模型目录、Conda（Python 环境管理器）环境和将要执行的共享清单：

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
INDEXTTS_CODE_PATH=/path/to/index-tts \
python task-runner/task9/run_task9_clone.py --dry-run
```

预检通过后，明确允许覆盖当前两条目标音频时才执行合成。编排器始终串行运行两个模型，避免争用同一张 GPU。

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
INDEXTTS_CODE_PATH=/path/to/index-tts \
python task-runner/task9/run_task9_clone.py --overwrite
```

合成完成后先核对两条 WAV 均可解码、非空，并确认它们使用的清单哈希相同；不要因两模型原生采样率不同而重采样或覆盖，除非评测契约已经冻结该要求。

编排器会在写出每条成品后自动保存逐段音频证据：每段证据的文本哈希必须对应共享清单，片段 WAV 哈希、片段在成品中的时间位置和最终 WAV 哈希均会被记录。该目录是本地可复核资产，已忽略；不要手工编辑、移动或将其提交到仓库。若成品 WAV 被外部工具替换、响度处理或重编码，原证据会因最终哈希不匹配而失效；应通过编排器重新合成并重新评测，避免把不属于该成品的逐段转写当作评测依据。

## 4. 公共评测执行顺序

正式评测前，先以只读方式检查两条成品、本地 SenseVoiceSmall、Whisper-large-v3-turbo、CUDA 和 `python -m pip check`：

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task9/check_task9_evaluation_setup.py
```

每次完整复测都必须使用全新的结果目录；只有同一批次的第二个模型才使用 `--resume`。先评测 IndexTTS2，再续跑 VoxCPM2：

```bash
RESULT_DIR="longAudioTestV9/评测结果/task9-v2-$(date -u +%Y%m%dT%H%M%SZ)"

HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task9/run_task9_evaluation.py \
  --model-id indextts2 --output-dir "$RESULT_DIR" --strict

HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task9/run_task9_evaluation.py \
  --model-id voxcpm2 --output-dir "$RESULT_DIR" --resume --strict

python task-runner/task9/generate_task9_reports.py \
  --results-dir "$RESULT_DIR" \
  --reports-dir longAudioTestV9/评测结果
```

SenseVoice 的输出中可能带有 `<|zh|>`、`<|HAPPY|>` 等语言、情绪或事件控制标记。评测器必须保存逐段 `raw_transcription` 以供复核，但只能从 CER 输入中移除这类非朗读控制标记；不得修改实际转写台词、纠错或补字。Whisper-large-v3-turbo 的模型名必须完整保留，两个后端的 CER 只能独立排名，禁止平均为综合分。

v2 不再把最终长音频机械地切成连续的 30 秒窗口，而是对与最终 WAV 哈希绑定的每个合成语义段独立转写，并把错误定位限定在该段内。每个后端同时给出三类信息：

- 严格汉字 CER：保留字面替换、插入、删除，是唯一的正式文本差异测量；同音字仍会计入。
- 带声调拼音 CER：使用冻结的 `pypinyin==0.55.0` 和 `tone3` 读法，只作“严格差异可能是同音字”的辅助线索，不能取代严格 CER，也不能证明实际没有错读。
- ASR 健康门控：当单段转写长度明显异常、连续删除过长，或 SenseVoice 与 Whisper 在同段分歧过大时，该后端不参与名次。原始 CER、逐段转写和错误位置仍会保留，供人工试听时复核。

强制对齐、读法词典校准和角色路由分类仍属中高风险项目；当前契约明确记录为未执行，不能把它们的结论伪装成自动评测结果。

固定报告名为：

- `longAudioTestV9/评测结果/SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md`
- `longAudioTestV9/评测结果/音频交付与文本一致性_V9自动检查报告.md`

## 5. 历史执行摘要（v1，不可与 v2 比较）

此前一次本地复测以固定 30 秒窗口转写最终长音频。该方法会在窗口边界发生漏转写时把后续差异串联放大，已经被 v2 的逐段证据评测取代。以下数值仅保留为历史记录，不能作为当前模型错误率、名次或 v2 基线：

| 模型 | SenseVoice CER | Whisper-large-v3-turbo CER |
| --- | ---: | ---: |
| IndexTTS2 | 0.036018 | 0.187950 |
| VoxCPM2 | 0.098887 | 0.178782 |

重新合成并按本任务第 4 节生成全新的 v2 结果目录后，才可比较当前的严格 CER、拼音辅助指标、ASR 健康状态、逐段转写和人工试听结果。
