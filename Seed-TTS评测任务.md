# Seed-TTS 评测任务

本文定义 Seed-TTS-Eval（Seed TTS 官方客观基准）的中文外部评测。它使用固定的官方中文集，衡量模型版本的零样本音色克隆能力；它**不是** `task8.md`、`task9.md` 或任何 `longAudioTestV*` 长音频的组成部分。

## 1. 与长音频任务的关系

- 输入仅为官方 `zh/meta.lst` 与 `zh/hardcase.lst`，不使用 `longAudioTestV*/audio_*.wav`、角色设定、`text.md` 或 `ai_deal.json`。
- 每个条目按 meta 中给定的参考音频、参考文本和待合成文本生成一个独立的 `<utt>.wav`。
- 同一模型版本、模型权重、推理参数、随机种子、文本规范化、官方数据/权重哈希、评测器提交和兼容补丁哈希完全一致时，只执行一次并复用该结果；不得因 task8 与 task9 各重复执行一次。
- 任一冻结项改变（包括模型 revision（修订版本）、参考提示构造、采样参数、随机种子或评测器补丁）时，必须新建结果目录并重新执行，不能沿用旧分数。
- WER（词错误率）与 WavLM-large-SV SIM（说话人相似度）独立报告，禁止合成为总分，也不得写入公共长音频 CER 报告、交付报告或自动总排名。

## 2. 固定范围与输出布局

仅运行中文分集：

| 分集 | 官方清单 | 条数 | 生成目录 |
| --- | --- | ---: | --- |
| 常规集 | `zh/meta.lst` | 2,020 | `<结果根目录>/meta/` |
| 难例集 | `zh/hardcase.lst` | 400 | `<结果根目录>/hardcase/` |

每个目录必须扁平保存与清单 `utt` 精确同名的 `<utt>.wav`。官方 `get_wav_res_ref_text.py` 只读取该形式的文件；不要改名、分层或把长音频拼接文件放入其中。

推荐每个模型版本使用一个全新的结果根目录，例如：

```text
seed-tts-results/
  Qwen3-TTS-12Hz-1.7B-Base/<run-id>/
    freeze/                 # 哈希、pip freeze、GPU 和兼容补丁
    smoke/                  # 非正式烟雾检查，不进入统计
    meta/                   # 2,020 个 <utt>.wav 与 WER/SIM 原始输出
    hardcase/               # 400 个 <utt>.wav 与 WER/SIM 原始输出
    Seed-TTS_ZH_WER&WavLM-large-SV_SIM_标准基准报告.md
```

音频是大体积资产；除非另获确认，不提交 `utt.wav`。结果目录应置于仓库忽略目录或仓库外的受控位置。

## 3. 环境、资源与冻结项

使用两个隔离的 Conda（Python 环境管理器）环境，严禁混装其 PyTorch、Torchaudio 与 Hydra 依赖：

| 工作内容 | 环境 | 必需资源 |
| --- | --- | --- |
| Seed-TTS 中文 WER（逐字 token） | `seed_tts_eval` | 本地 `funasr/paraformer-zh` |
| WavLM-large-SV SIM | `seed_tts_sim` | Seed-TTS-Eval 的 UniSpeech、官方 `wavlm_large_finetune.pth` |

本次已验证的版本基线如下：

| 项目 | `seed_tts_eval` | `seed_tts_sim` |
| --- | --- | --- |
| Python | 3.10.20 | 3.8.20 |
| PyTorch / Torchaudio | 2.12.0+cu130 / 2.11.0+cu130 | 1.9.0+cu111 / 0.9.0 |
| 核心库 | FunASR 1.3.9、Transformers 5.12.0 | vendored Fairseq `752f4297f090c46bb1a55a1f7439e5944ddefe8d`、S3PRL 0.3.1 |

`seed_tts_sim` 中 Fairseq 必须由当前 Seed-TTS-Eval 仓库的 UniSpeech 源码安装，并以 `READTHEDOCS=1` 跳过未使用的可选原生扩展；不得替换为新版 PyPI `fairseq`。其 `pip check` 的训练/数据集可选依赖告警不作为失败依据，准入标准是官方 speaker verification 入口可导入。

在本机 shell 设置、但不要提交以下变量：

```bash
export SEED_TTS_EVAL_ROOT="$HOME/github/seed-tts-eval"
export SEED_TTS_DATA_ROOT="$HOME/github/seed-tts-test-data/seedtts_testset"
export SEED_TTS_WAVLM_CKPT="$HOME/github/seed-tts-test-data/wavlm_large_finetune.pth"
export SEED_TTS_PARAFORMER_DIR="$HOME/hf-mirror/funasr/paraformer-zh"
export SEED_TTS_RESULT_ROOT="$PWD/seed-tts-results/<模型版本>/<run-id>"
export ARNOLD_WORKER_GPU=1
```

正式评分前，在 `<结果根目录>/freeze/` 记录：两个环境的 `pip freeze`、Seed-TTS-Eval 提交、`meta.lst`、`hardcase.lst`、WavLM 权重、Paraformer 权重/配置的 SHA-256、GPU/驱动/CUDA、模型 revision、推理参数、文本规范化和随机种子。

## 4. 官方脚本兼容补丁

先在单独工作副本中完成补丁、审阅 `git diff`、保存补丁文件并记录 SHA-256；不得直接把未记录的本机改动当作正式基线。仅允许下列运行兼容改动：

1. 中文 WER 跳过无评分作用、却会准备 Whisper-large-v3 的 `prepare_ckpt.py`。
2. `run_wer.py` 从 `SEED_TTS_PARAFORMER_DIR` 以 `hub="hf"` 加载本地 Paraformer。
3. `cal_wer.sh` 与 `cal_sim.sh` 的 `sudo split` 改为普通用户可执行的 `split`。
4. 将 SIM 目录的 `select.py` 改名，避免遮蔽 Python 标准库 `select`。
5. 固定上述 UniSpeech/Fairseq 安装方式与源码提交。

不得改变 meta 输入、分集、生成音频—参考音频配对、ASR 解码、WavLM 嵌入、相似度计算或汇总公式。

## 5. 执行顺序

1. 预检两个环境和冻结资源；确认 `ARNOLD_WORKER_GPU` 不大于实际 GPU 数。
2. 使用一个常规集样本和一个最长难例样本，在 `<结果根目录>/smoke/` 验证模型合成、Paraformer WER、WavLM SIM 和结果文件写入。烟雾检查不进入最终统计。
3. 在模型常驻、可断点续跑的合成器中，逐条读取两个官方清单，以每条自身的参考音频、参考文本和目标文本写出 `<utt>.wav`。不得复用公共长音频或用其他模型补音频。
4. 对 `meta/` 和 `hardcase/` 分别运行已冻结补丁后的官方 WER 与 SIM 脚本；单卡设置 `ARNOLD_WORKER_GPU=1`，不要用多个进程抢占同一张 GPU。
5. 保留逐条输出和分集均值，检查覆盖数恰为 2,020 和 400；任意缺失、失败或配置漂移都不得生成可比较结论。

假设补丁工作副本为 `$SEED_TTS_EVAL_ROOT`，每个分集的手动评分命令形如：

```bash
conda run --no-capture-output -n seed_tts_eval bash -lc '
  cd "$SEED_TTS_EVAL_ROOT"
  bash cal_wer.sh "$SEED_TTS_DATA_ROOT/zh/meta.lst" "$SEED_TTS_RESULT_ROOT/meta" zh
'

conda run --no-capture-output -n seed_tts_sim bash -lc '
  cd "$SEED_TTS_EVAL_ROOT"
  bash cal_sim.sh "$SEED_TTS_DATA_ROOT/zh/meta.lst" "$SEED_TTS_RESULT_ROOT/meta" "$SEED_TTS_WAVLM_CKPT"
'
```

难例集仅将两个命令中的 `meta.lst` 与 `meta/` 对应替换为 `hardcase.lst` 与 `hardcase/`。`SEED_TTS_RESULT_ROOT` 必须是本次全新结果目录；正式运行不得覆盖烟雾目录。

## 6. 报告与复用判定

最终报告必须分别列出常规集和难例集的：

- Seed-TTS 中文 WER（逐字 token）；
- WavLM-large-SV SIM；
- 逐条生成文件、逐条 WER、逐条生成音频—参考音频 SIM 配对证据；
- 覆盖数、冻结版本、推理配置和兼容补丁 SHA-256。

报告必须显式写明“该结果仅代表冻结模型版本在官方中文外部基准上的表现”，不得推断小说长音频的自然度、情绪、角色区分度或最终生产排名。

当前未完成执行所需条件见 [Seed-TTS运行阻塞.md](Seed-TTS运行阻塞.md)。本文档的修改本身不授权下载模型、安装依赖、批量生成 16,940 条音频或启动 GPU 评分。
