# OmniVoice 本地 TTS 环境安装指南

本文记录 `modelScript/tts_local_omnivoice.py` 运行 `OmniVoice` 所需的软件、模型文件和使用方式。脚本直接调用模型运行时，不依赖 HTTP 服务或云端 API。

## 目标与工作原理

- 模型目录：`/path/to/OmniVoice`
- conda 环境名：`omnivoice`
- Python 版本：`3.11`
- 运行脚本：`modelScript/tts_local_omnivoice.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

OmniVoice 的推理分为两个相互独立的阶段：先由参考音频（以及可选的准确转写）创建 `voice_clone_prompt`（声音克隆提示），再把待合成文本和该提示传入 `generate()`。长文本会按标点分段，但所有分段复用同一个声音克隆提示，因此不会为每段重新估计音色。脚本最后拼接各段波形并插入可配置的静音。

运行前设置模型目录：

```bash
export OMNIVOICE_MODEL_PATH=/path/to/OmniVoice
```

也可在单次命令中使用 `--model-path /path/to/OmniVoice`。`OMNIVOICE_MODEL_DIR` 也被识别，便于兼容已有的本地启动配置。

## 1. 创建独立环境

OmniVoice 当前本机运行时为 Python 3.11、`omnivoice==0.1.5`、CUDA 版 `torch==2.8.0`。不同 TTS（文本转语音）模型应使用独立环境，避免 `transformers`、PyTorch 与音频库版本相互影响。

```bash
conda create -n omnivoice -y python=3.11
conda activate omnivoice
```

安装与显卡驱动匹配的 CUDA 版 PyTorch。下例对应 PyTorch 2.8 的 CUDA 12.8 轮子；如果本机驱动或 CUDA 版本不同，请按 PyTorch 官方指引替换来源。

```bash
python -m pip install --upgrade pip
python -m pip install --index-url https://download.pytorch.org/whl/cu128 "torch==2.8.*" "torchaudio==2.8.*"
python -m pip install "omnivoice==0.1.5" soundfile
conda install -y -c conda-forge ffmpeg
```

`ffmpeg` 建议安装：OmniVoice 依赖链中的音频预处理可能需要它处理非 WAV 参考音频。实际合成输出由 `soundfile` 写为 WAV。

## 2. 下载并核对模型

OmniVoice 模型由主模型和同目录的 `audio_tokenizer/` 子目录共同组成；只下载顶层权重会导致模型无法把语音转换为音频 token。可用 Hugging Face CLI 下载完整快照：

```bash
python -m pip install "huggingface_hub[cli]"
hf download k2-fsa/OmniVoice --local-dir /path/to/OmniVoice
```

离线运行前至少确认下列文件存在：

```text
/path/to/OmniVoice/config.json
/path/to/OmniVoice/model.safetensors
/path/to/OmniVoice/tokenizer.json
/path/to/OmniVoice/audio_tokenizer/config.json
/path/to/OmniVoice/audio_tokenizer/model.safetensors
```

脚本默认启用 `--local-files-only`，会设置 Hugging Face 离线环境变量，避免缺文件时悄悄发起下载。需要联网下载或更新模型时，显式传入 `--no-local-files-only`。

## 3. 验证运行时

```bash
conda run -n omnivoice python -c "import torch, soundfile; from omnivoice import OmniVoice; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('OmniVoice import ok')"
```

预期至少包含：

```text
cuda True
OmniVoice import ok
```

该脚本要求 CUDA GPU。若 `torch.cuda.is_available()` 为 `False`，应先安装与 NVIDIA 驱动兼容的 CUDA 版 PyTorch，而不是在 CPU 上等待大模型推理完成。

## 4. 运行合成

从项目根目录运行。最小离线命令如下：

```bash
conda run -n omnivoice python modelScript/tts_local_omnivoice.py \
  --model-path /path/to/OmniVoice \
  --local-files-only
```

为获得更稳定的克隆效果，建议提供参考音频的准确文本：

```bash
conda run -n omnivoice python modelScript/tts_local_omnivoice.py \
  --model-path /path/to/OmniVoice \
  --ref-audio samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav \
  --ref-text "这里填写 sample.wav 对应的准确文本" \
  --local-files-only
```

`--ref-text` 缺省时，OmniVoice 仍可构建提示，但会依赖内部预处理路径推断参考内容；准确转写能减少参考音频识别误差。也可用 `--ref-text-file` 读取长转写文件。

默认输出到样例目录，文件名为 `OmniVoice_${t}_${k}khz.wav`。使用 `--output /path/to/result.wav` 可以指定精确输出位置。

## 5. 质量与性能控制

常用参数如下：

- `--num-step 32`：流匹配生成步数；提高步数通常更慢，但可能提升细节稳定性。
- `--guidance-scale 2.0`：条件引导强度；过高可能让语音不自然。
- `--speed 1.0` 与 `--duration`：分别控制语速或目标时长；同时指定时以模型实际行为为准。
- `--max-chars-per-chunk 120`：限制单次生成文本长度；设为 `0` 禁用外部按字分段。
- `--audio-chunk-duration 15`、`--audio-chunk-threshold 30`：传给 OmniVoice 的内部音频分块控制。
- `--preprocess-prompt`、`--postprocess-output`、`--denoise`：默认开启；如需排查音频差异，可分别使用 `--no-preprocess-prompt`、`--no-postprocess-output`、`--no-denoise`。

每次运行后脚本会释放模型引用和 CUDA 缓存。不要并发运行多个本地大模型合成任务，以免显存不足。
