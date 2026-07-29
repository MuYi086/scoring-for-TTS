# Task 9 专用合成脚本

本目录仅维护 Task 9 的运行逻辑，不修改 `modelScript/` 中用于跨设备迁移的模型安装与配置备份。

`run_task9_clone.py` 会严格串行调用 `indextts2.py` 与 `voxcpm2.py`，使用：

- `longAudioTestV9/text.md` 作为两条成品唯一的合成文本；
- `longAudioTestV9/mimo_旁白_v9.wav` 及其任务文案作为克隆参考；
- `longAudioTestV9/audio_indextts2.wav`、`longAudioTestV9/audio_voxcpm2.wav` 作为固定输出。

每次实际合成还会在 `longAudioTestV9/.task9_synthesis_evidence/` 写入逐段音频证据。该目录按“模型标识 / 最终 WAV 的 SHA-256”组织，保存每段的文本哈希、片段 WAV 哈希、在成品中的时间位置和段间停顿；已被 `.gitignore` 排除，不能手工修改或提交。Task 9 v2 评测只接受与当前成品 WAV 哈希、共享分段清单哈希均一致的证据。因此，只要手工替换了成品 WAV，就必须重新通过本编排器合成，不能复用旧证据。

模型根目录和 IndexTTS2 源码目录必须通过参数或环境变量提供，不在仓库中记录机器专属路径。先进行无模型预检：

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
INDEXTTS_CODE_PATH=/path/to/index-tts \
python task-runner/task9/run_task9_clone.py --dry-run
```

确认预检后，移除 `--dry-run` 才会开始合成。脚本默认禁止覆盖已有 WAV；只有明确传入 `--overwrite` 才会覆盖。

IndexTTS2 与 VoxCPM2 必须使用同一份 `text_segments.py` 生成的隐藏清单 `.task9_segment_manifest.json`。它先用旁白参考音频的实际语速换算时长预算（默认目标 25 秒、上限 35 秒），再优先按完整句和段落切分；只有单句超预算时才在次级标点或字符预算处切分。两者逐段克隆后，按相同的边界规则拼接：强制切分 250ms、句末 500ms、段落 750ms，末段不补静音。清单记录每段文本哈希、估算时长、边界类型及停顿，评测结果会冻结清单哈希，确保两个模型的文本片段、顺序和停顿条件完全一致。

该规则吸收了长文本工作室的通用实践：优先语义完整的句段、根据参考声线语速而不是死板字数控制单段长度、以显式停顿表达句/段落边界，并把清单作为可复现证据。相邻上下文仅记录在清单中，不会作为待朗读文本注入模型，以免污染全文 CER。

## 公共评测

合成两条成品后，使用同一份本地 ASR 镜像进行只读预检。Task 9 的唯一严格 CER（字符错误率）参考是 `longAudioTestV9/text.md` 的实际全文和原始顺序；不能使用旧 V9 的 `ai_deal.json` 或字符数。预检还会校验两条成品的逐段证据、共享清单、`pypinyin==0.55.0`、本地 ASR 权重和 CUDA。

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
conda run --no-capture-output -n audio_eval \
  python task-runner/task9/check_task9_evaluation_setup.py
```

正式评测的原始结果目录必须是新目录。首次评测 IndexTTS2，随后只对同一次未完成目录使用 `--resume` 评测 VoxCPM2：

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

最后一条命令固定生成 `SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md` 与 `音频交付与文本一致性_V9自动检查报告.md`。评测器会按冻结的语义段分别转写，避免旧版固定 30 秒切块造成前后错误串联；它同时报告严格汉字 CER、带声调拼音 CER（仅作同音字假阳性辅助）及 ASR 健康状态。只有全部片段健康且双后端无异常分歧的后端才参与各自的 CER 名次，原始转写和原始数值仍完整保留。V9 尚未冻结交付阈值，且没有冻结的强制对齐器或角色分类器，因此不会自行判定通过、失败或音色优劣。
