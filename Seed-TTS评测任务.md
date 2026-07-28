# Seed-TTS 中文外部评测任务

状态：**准备完成，尚未执行任何 Seed-TTS 合成、WER（词错误率）或 SIM（说话人相似度）评分。**

本文是 Seed-TTS-Eval（Seed TTS 官方客观基准）的唯一手动执行手册。它只评测七个冻结模型版本的中文零样本音色克隆能力；它**不是** `task6.md`、`task7.md`、`task8.md`、`task9.md` 或任一 `longAudioTestV*` 长音频任务的一部分。

执行前先阅读本文件和 [Seed-TTS运行阻塞.md](Seed-TTS运行阻塞.md)。本文件提供的命令只在操作者手动执行后才会加载模型、占用 GPU 或生成音频；准备阶段不授权这些操作。

## 1. 不可变范围与解释边界

- 只使用官方中文 `zh/meta.lst`（2,020 条）和 `zh/hardcase.lst`（400 条），共 2,420 条。每条按清单的 `utt|参考文本|参考音频|目标文本` 四列生成一个独立 `<utt>.wav`。
- 不使用 `longAudioTestV*/audio_*.wav`、小说正文、角色设定、`text.md` 或 `ai_deal.json`；不得用长音频成品替代官方条目。
- 每个模型对每个 `utt` 严格串行合成，模型只在本次进程内加载一次；不会并发生成而争抢同一张 GPU。
- Seed-TTS 中文 WER（逐字 token）与 WavLM-large-SV SIM 独立报告。禁止合成为总分、总排名或写入长音频 CER（字符错误率）报告。
- 同一冻结模型版本、权重、源码、参数、随机种子、数据、评分器提交及补丁完全一致时，只能复用同一结果；任一项变化必须用新的 `run-id` 重跑。

本基准只能说明冻结模型在官方中文短句外部集上的客观表现，不能推断小说长音频的自然度、情绪、角色区分度或生产排名。

## 2. 固定模型、脚本与目录

所有入口都在 `Seed-TTS-test/scripts/`，不导入或调用 `~/github/TTS-and-VoiceDesign`。IndexTTS2 与 LongCat-AudioDiT-1B 必须显式指向各自的**官方**源码目录，不能借用另一项目的 `vendor/` 目录。

| 脚本标识 | 模型 | 手动合成脚本 | 默认 Conda 环境 | 结果与报告目录名 |
| --- | --- | --- | --- | --- |
| `dots_tts` | dots.tts-base | `run_dots_tts.sh` | `dots_tts` | `dots_tts` |
| `indextts2` | IndexTTS2 | `run_indextts2.sh` | `indextts2` | `indextts2` |
| `longcat_audiodit` | LongCat-AudioDiT-1B | `run_longcat_audiodit.sh` | `longcat_audiodit` | `longCat` |
| `moss_tts` | MOSS-TTS-Local-Transformer-v1.5 | `run_moss_tts.sh` | `moss-tts-py310` | `moss_tts` |
| `omnivoice` | OmniVoice | `run_omnivoice.sh` | `omnivoice` | `omniVoice` |
| `qwen3_tts` | Qwen3-TTS-12Hz-1.7B-Base | `run_qwen3_tts.sh` | `qwen3-tts` | `qwen3_tts` |
| `voxcpm2` | VoxCPM2 | `run_voxcpm2.sh` | `voxcpm2` | `voxcpm2` |

每个正式 `run-id` 的固定布局如下。`result/` 与 `report/` 的生成内容均被 Git 忽略；不得提交 `utt.wav`、模型缓存、`pip freeze` 或机器专属路径。

```text
Seed-TTS-test/
├── result/<目录名>/<run-id>/
│   ├── freeze/run_metadata.json      # 模型、清单、关键文件哈希与参数
│   ├── inputs.jsonl                  # 官方输入映射，不改写文本
│   ├── synthesis.jsonl               # 逐条音频 SHA-256、种子、耗时和 WAV 元数据
│   ├── meta/                         # 2,020 个 <utt>.wav
│   └── hardcase/                     # 400 个 <utt>.wav
└── report/<目录名>/<run-id>/
    ├── raw/{meta,hardcase}.{wer,sim}.tsv
    ├── freeze/                       # 两个评分环境、GPU、资源与补丁冻结记录
    └── Seed-TTS_ZH_WER&WavLM-large-SV_SIM_标准基准报告.md
```

`<utt>.wav` 必须直接平铺在对应分集目录中；官方 `get_wav_res_ref_text.py` 只读取这个形式。不得改名、嵌套、拼接或混入烟雾样本。

## 3. 一次性准备评分工作副本

### 3.1 本机变量

复制 [`Seed-TTS-test/env.example`](Seed-TTS-test/env.example) 到仓库外的本机文件，填入实际离线资源路径后在当前 shell 加载。不要把该本机文件命名为可提交的配置，也不要提交真实路径、令牌或密钥。

至少必须设置：

- `SEED_TTS_DATA_ROOT`：官方 `seedtts_testset` 根目录；其下必须有 `zh/meta.lst`、`zh/hardcase.lst` 和 `zh/prompt-wavs/`。
- `SEED_TTS_WAVLM_CKPT`：官方 `wavlm_large_finetune.pth`。
- `SEED_TTS_PARAFORMER_DIR`：本地 `funasr/paraformer-zh` 完整目录。
- 七个 `SEED_TTS_*_MODEL_PATH`：各模型的完整离线权重目录。
- `SEED_TTS_INDEXTTS_CODE_PATH` 与 `SEED_TTS_LONGCAT_CODE_PATH`：各自官方源码目录。
- `SEED_TTS_EVAL_SOURCE_ROOT`：干净官方 Seed-TTS-Eval Git 仓库；`SEED_TTS_EVAL_ROOT`：新建的补丁工作副本目录。
- `SEED_TTS_QWEN3_SOX_BIN`：Qwen3-TTS 参考音频预处理所需的可执行 `sox` 的绝对路径。

所有合成与评分脚本强制设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`，不会因缺少文件隐式下载。正式评分固定 `ARNOLD_WORKER_GPU=1`，禁止多进程抢同一张 GPU。

首次创建或重建 IndexTTS2 独立环境时，必须按官方 `uv.lock` 同步；不要在运行时从 dots、Qwen 或其他模型环境借包。准备脚本默认只读离线缓存：

```bash
bash Seed-TTS-test/scripts/prepare_indextts2_environment.sh
```

只有当 IndexTTS2 预检失败或重建该环境时才运行此命令；已通过预检的机器不应为一次正式评测重复同步。若脚本明确报告锁定包不在本地缓存，只有在获得下载授权后才运行 `bash Seed-TTS-test/scripts/prepare_indextts2_environment.sh --allow-network`，随后重新运行预检。该同步不加载模型或生成音频。

### 3.2 评分器补丁

首次准备评分器时，在项目根目录、加载本机变量后，创建全新的可审阅工作副本：

```bash
bash Seed-TTS-test/scripts/prepare_seed_tts_evaluator.sh
```

它从 `SEED_TTS_EVAL_SOURCE_ROOT` 的当前提交创建 `SEED_TTS_EVAL_ROOT`，应用 [`0001-seed-tts-local-offline.patch`](Seed-TTS-test/scripts/patches/0001-seed-tts-local-offline.patch)，并写入 `freeze-patch.json`。目标已存在时脚本会停止以避免覆盖；此时直接运行下方预检。补丁只做下列兼容改动：

1. WER 跳过无评分作用、却会准备 Whisper-large-v3 的 `prepare_ckpt.py`。
2. `run_wer.py` 从 `SEED_TTS_PARAFORMER_DIR` 以 `hub="hf"` 加载本地 Paraformer。
3. `cal_wer.sh` 与 `cal_sim.sh` 将 `sudo split` 改为普通用户 `split`。
4. 将 UniSpeech 的 `select.py` 改名为 `select_speakers.py`，避免遮蔽 Python 标准库模块。

不得改动官方清单、生成音频—参考音频配对、ASR 解码、WavLM 嵌入、相似度计算或汇总公式。若补丁不能应用，停止并审阅官方提交差异；不得在原始工作树混入未登记的本机改动。

### 3.3 无模型加载预检

下列预检只读取清单、权重目录、Conda 环境名和评分工作副本；**不导入或加载任何 TTS 模型**：

```bash
python Seed-TTS-test/scripts/check_seed_tts_setup.py
```

预检必须同时确认七模型的运行时发行包、外部音频工具与权重、两个评分环境、2,020 × 400 清单与参考音频、补丁哈希、Paraformer 和 WavLM。任何错误都必须先修复；不要靠后续批量合成试错。

## 4. 手动执行一个模型

先为这个模型创建从未使用过的正式 `run-id`。示例中的时间戳只展示格式；不要复制历史目录或使用已存在目录。

```bash
export RUN_ID="seedtts-$(date -u +%Y%m%dT%H%M%SZ)"
bash Seed-TTS-test/scripts/run_qwen3_tts.sh --run-id "$RUN_ID"
```

将最后一行脚本替换为表中的任一模型脚本，即可只运行一个模型。脚本会：

1. 校验该模型的离线权重、官方清单和参考音频；
2. 只加载该模型一次，并按 `meta` 再 `hardcase` 的官方原始顺序逐条串行合成；
3. 对每个输出使用原子写入，记录逐条 SHA-256、稳定的 `utt` 派生随机种子、耗时和 WAV 元数据；
4. 覆盖数恰为 2,020 与 400 时，才把 `freeze/run_metadata.json` 标记为 `complete`。

中断后仅可对同一个未完成目录继续：

```bash
bash Seed-TTS-test/scripts/run_qwen3_tts.sh --run-id "$RUN_ID" --resume
```

`--resume` 会验证并跳过已有 WAV，绝不用于新批次。正式运行不得传 `--limit`。如需验证安装，只能创建独立、不可评分的烟雾目录，例如 `--run-id smoke-... --limit 1`；烟雾目录不能改名或续作正式运行。

## 5. 合成后立即评分和出报告

合成脚本正常完成后，对**同一模型和同一 `run-id`**执行：

```bash
bash Seed-TTS-test/scripts/score_model.sh qwen3_tts --run-id "$RUN_ID"
```

该脚本在评分前再次验证正式覆盖，依次对 `meta` 与 `hardcase` 运行官方 WER 和官方 WavLM-large-SV SIM，保存两次独立的逐条原始输出，然后生成 Markdown 报告。`cal_sim.sh` 沿用官方输出名，因此脚本会在运行 SIM 前复制 WER 原始文件，避免覆盖证据。

每个分集评分的等价官方命令为：

```bash
conda run --no-capture-output -n seed_tts_eval bash -lc '
  cd "$SEED_TTS_EVAL_ROOT"
  bash cal_wer.sh "$SEED_TTS_DATA_ROOT/zh/meta.lst" "$RESULT_RUN/meta" zh
'

conda run --no-capture-output -n seed_tts_sim bash -lc '
  cd "$SEED_TTS_EVAL_ROOT"
  bash cal_sim.sh "$SEED_TTS_DATA_ROOT/zh/meta.lst" "$RESULT_RUN/meta" "$SEED_TTS_WAVLM_CKPT"
'
```

其中 `RESULT_RUN` 是 `Seed-TTS-test/result/<目录名>/<run-id>`。难例集只将 `meta.lst`/`meta` 替换为 `hardcase.lst`/`hardcase`。通常应使用 `score_model.sh`，因为它还会保存评分环境 `pip freeze`、GPU/驱动、Paraformer 文件哈希、WavLM 哈希、输入清单哈希和补丁冻结记录。

## 6. 验收清单

一个模型的正式结果只有在以下所有条件成立时才可比较：

- `check_seed_tts_setup.py` 预检通过；
- `run_metadata.json` 为 `mode: formal`、`status: complete`，没有 `limit`；
- `meta/` 恰有 2,020 个 WAV，`hardcase/` 恰有 400 个 WAV；
- `synthesis.jsonl`、`inputs.jsonl`、逐条 WER、逐条生成音频—参考音频 SIM 配对证据均存在；
- 两个分集都包含 WER 和 SIM 的独立汇总及原始输出；
- 模型权重、官方清单、评测器提交、补丁、Paraformer、WavLM、参数和随机种子策略均有 SHA-256 或版本记录；
- 报告明确声明只代表官方中文外部基准，不含跨量纲总分。

任意缺失、失败、覆盖不足、配置漂移或烟雾目录都不得产出可比较结论。音频与机器冻结文件是本地生成物，除非另获单独确认，均不提交到仓库。
