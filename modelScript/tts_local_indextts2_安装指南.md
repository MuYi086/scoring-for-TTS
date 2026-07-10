# IndexTTS2 本地 TTS 环境安装指南

本文记录 `modelScript/tts_local_indextts2.py` 运行 `IndexTTS2` 所需的软件、完整模型文件和使用方式。脚本直接调用官方 `indextts.infer_v2.IndexTTS2`，不依赖 Web UI 或 HTTP 服务。

## 目标与工作原理

- 模型目录：`/path/to/IndexTTS-2`
- 官方源码目录：`/path/to/index-tts`
- 运行脚本：`modelScript/tts_local_indextts2.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

IndexTTS2 从参考音频提取说话人条件，结合文本生成语音。未提供独立情感控制时，参考音频同时提供默认情感风格；可额外传入情感参考音频、八维情感向量，或情感描述文本。长文本不由本脚本按字符切分，而是交给官方 `infer()` 的 `max_text_tokens_per_segment`（每段最大文本 token 数）控制，避免外部拼接破坏模型的原生段落策略。

运行前配置本地路径：

```bash
export INDEXTTS_MODEL_PATH=/path/to/IndexTTS-2
export INDEXTTS_CODE_PATH=/path/to/index-tts
```

如配置文件不在模型根目录，可额外设置 `INDEXTTS_CONFIG_PATH=/path/to/config.yaml`。兼容已有环境变量 `INDEXTTS_MODEL_DIR`、`INDEXTTS_CODE_DIR`。

## 1. 安装官方运行环境

官方项目要求 Python `>=3.10`，并推荐使用 `uv`（Python 包与虚拟环境管理器）锁定依赖；这是因为 IndexTTS2 依赖 `transformers==4.52.1`、`tokenizers==0.21.0`、`torch==2.8.*` 等精确组合，和其他 TTS 模型共用环境容易发生冲突。

先安装 Git、Git LFS（大文件存储）与 `uv`，再克隆官方源码：

```bash
git lfs install
git clone https://github.com/index-tts/index-tts.git /path/to/index-tts
cd /path/to/index-tts
python -m pip install --upgrade uv
uv sync
```

如需官方 Web UI 或 DeepSpeed（分布式推理加速）功能，可按官方说明使用 `uv sync --all-extras`；本项目的命令行脚本不需要 Web UI。GPU 环境应使用 CUDA 版 PyTorch。官方依赖元数据使用 CUDA 12.8 索引；遇到 CUDA 错误时，先确认 NVIDIA 驱动与该 PyTorch 轮子兼容。

## 2. 下载完整模型包

下载模型到独立目录：

```bash
cd /path/to/index-tts
uv tool install "huggingface-hub[cli,hf_xet]"
hf download IndexTeam/IndexTTS-2 --local-dir /path/to/IndexTTS-2
```

模型目录不只有 `gpt.pth` 与 `s2mel.pth`。为了在离线模式下可靠加载，脚本在开始推理前会校验：

- 主模型文件：`bpe.model`、`wav2vec2bert_stats.pt`、`gpt.pth`、`s2mel.pth`、`feat1.pt`、`feat2.pt`；
- 情感模型：`qwen0.6bemo4-merge/` 中的配置、权重与 tokenizer；
- 辅助模型：`hf_cache/w2v-bert-2.0/`、`semantic_codec_model.safetensors`、`campplus_cn_common.bin`、`bigvgan/`；
- 配置文件：`config.yaml`。

缺少其中任一项时，脚本会在加载大模型前明确报出缺失相对路径，而不会自动下载或在半途失败。

## 3. 验证环境

在官方源码目录中使用其 `uv` 环境执行：

```bash
cd /path/to/index-tts
uv run python -c "import torch; from indextts.infer_v2 import IndexTTS2; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('IndexTTS2 import ok')"
```

预期至少包含：

```text
cuda True
IndexTTS2 import ok
```

该脚本默认要求 CUDA GPU。仅在确认可以接受极慢的推理时，才使用 `--allow-cpu`；也可通过 `--device cpu` 显式选择 CPU。

## 4. 运行合成

在官方 `uv` 环境内从当前项目根目录调用脚本：

```bash
cd /path/to/index-tts
uv run python /path/to/timbre-design/modelScript/tts_local_indextts2.py \
  --model-path /path/to/IndexTTS-2 \
  --code-path /path/to/index-tts \
  --local-files-only
```

如果已经激活包含 `indextts` 的环境，也可直接运行：

```bash
python modelScript/tts_local_indextts2.py \
  --model-path /path/to/IndexTTS-2 \
  --code-path /path/to/index-tts \
  --local-files-only
```

默认输出到样例目录，文件名为 `IndexTTS-2_${timestamp}.wav`。使用 `--output /path/to/result.wav` 可指定精确输出位置。

## 5. 情感控制

仅使用音色参考时：

```bash
uv run python /path/to/timbre-design/modelScript/tts_local_indextts2.py \
  --model-path /path/to/IndexTTS-2 \
  --code-path /path/to/index-tts \
  --ref-audio /path/to/speaker.wav
```

使用另一段音频提供情感，但保留 `--ref-audio` 的音色：

```bash
uv run python /path/to/timbre-design/modelScript/tts_local_indextts2.py \
  --model-path /path/to/IndexTTS-2 \
  --code-path /path/to/index-tts \
  --ref-audio /path/to/speaker.wav \
  --emo-audio /path/to/emotion.wav \
  --emo-alpha 0.8
```

使用文本情感描述：

```bash
uv run python /path/to/timbre-design/modelScript/tts_local_indextts2.py \
  --model-path /path/to/IndexTTS-2 \
  --code-path /path/to/index-tts \
  --emo-text "语气紧张、急促，但发音清晰"
```

也可使用 `--emo-vector` 传入八个 `0.0` 到 `1.0` 的值，依次表示：高兴、愤怒、悲伤、害怕、厌恶、忧郁、惊讶、平静。例如：

```bash
--emo-vector "0,0,0.8,0,0,0,0,0"
```

`--emo-text` 与 `--emo-vector` 会覆盖独立情感参考音频；这是官方 `infer_v2` 的逻辑，用于避免同时混用两种不同的情感条件。

## 6. 性能与排错

- `--use-fp16` 默认开启，可降低 CUDA 显存占用；若硬件或驱动不兼容，使用 `--no-use-fp16`。
- `--use-cuda-kernel` 默认关闭；它会尝试使用 BigVGAN 的可选融合 CUDA 内核，只有在本机已正确编译时才建议开启。
- `--num-beams 1` 为参考项目的默认值；提高 beam 数会增加生成时间。
- `--interval-silence 200` 与 `--max-text-tokens-per-segment 120` 传给官方长文本推理逻辑。
- 每次运行后脚本都会丢弃模型对象并清理 CUDA 缓存。不要和 OmniVoice、Qwen3-TTS 等大模型并行占用同一张 GPU。
