# MOSS-Audio-4B-Thinking 本地音频理解环境安装指南

本文记录 `modelScript/tts_local_moss_audio_4b_thinking.py` 的环境安装、离线模型加载和使用方式。

> 说明：MOSS-Audio-4B-Thinking 是音频理解模型，不是文本转语音（TTS，Text-to-Speech）模型。项目中脚本文件沿用 `tts_local_*` 命名习惯，但本脚本的输出是转写、描述或问答文本，不会生成 WAV 语音。

## 目标与本机资源

- conda 环境名：`moss-audio-4b-thinking`
- Python：官方建议 `3.12`
- 模型目录：`~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking`
- MOSS-Audio 依赖源码：`~/tts-depency/MOSS-Audio`
- 接入脚本：`modelScript/tts_local_moss_audio_4b_thinking.py`
- 默认测试音频：`~/tts-depency/MOSS-Audio/test/test_zh.mp3`
- GPU：本机实测为 NVIDIA GeForce RTX 4070 Ti SUPER，16 GB 显存

脚本默认从上述路径读取模型和依赖，也可以通过参数或环境变量替换路径：

```bash
export MOSS_AUDIO_MODEL_PATH=~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking
export MOSS_AUDIO_DEPENDENCY_PATH=~/tts-depency/MOSS-Audio
export MOSS_AUDIO_AUDIO_PATH=~/tts-depency/MOSS-Audio/test/test_zh.mp3
```

## 1. 检查模型和源码前提

先确认模型权重没有只下载一部分。4B 模型约 9.8 GB，至少应存在以下文件：

```bash
python - <<'PY'
from pathlib import Path

model = Path("~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking").expanduser()
required = [
    "config.json",
    "generation_config.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "model.safetensors.index.json",
    "model-00001-of-00003.safetensors",
    "model-00002-of-00003.safetensors",
    "model-00003-of-00003.safetensors",
    "processing_moss_audio.py",
    "configuration_moss_audio.py",
]
missing = [name for name in required if not (model / name).is_file()]
if missing:
    raise SystemExit("模型文件缺失：" + ", ".join(missing))
print("模型文件检查通过：", model)

dependency = Path("~/tts-depency/MOSS-Audio").expanduser()
for name in ("src/audio_io.py", "src/modeling_moss_audio.py", "src/processing_moss_audio.py"):
    if not (dependency / name).is_file():
        raise SystemExit(f"依赖源码缺失：{dependency / name}")
print("MOSS-Audio 依赖源码检查通过：", dependency)
PY
```

模型目录中的权重分片和 tokenizer（分词器）文件属于本地机器资产，不提交到本项目。

## 2. 创建 conda 环境

官方建议 Python 3.12。联网机器可直接使用清华镜像创建：

```bash
conda create -n moss-audio-4b-thinking -y --override-channels \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main \
  python=3.12
conda activate moss-audio-4b-thinking
python --version
```

本机在 2026-08-02 执行时清华 Conda 镜像元数据请求超时，因此实际采用了本机已有的 Python 3.12/CUDA 环境克隆创建同名环境；详见项目根目录的 `conda环境安装错误.md`。如果需要复现这一无网络回退方式，前提是本机已经有可用的同版本环境：

```bash
conda create -n moss-audio-4b-thinking --clone qwen3-tts -y --offline
conda activate moss-audio-4b-thinking
```

## 3. 安装音频工具和 Python 依赖

### 3.1 推荐联网安装命令

MOSS-Audio 依赖仓库的 `pyproject.toml` 要求 `torch`、`torchaudio`、`transformers`、`accelerate` 和音频/数值处理库。下面的普通 Python 包使用清华 PyPI（Python 包索引）镜像，CUDA 12.8 的 PyTorch 轮子从 PyTorch 官方源补充：

```bash
conda activate moss-audio-4b-thinking
python -m pip install --upgrade pip \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple

python -m pip install --timeout 120 --retries 10 \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cu128 \
  "torch==2.9.1" "torchaudio==2.9.1" \
  "torchcodec==0.9.*" \
  "transformers==4.57.1" "accelerate" \
  "safetensors>=0.4.0" "numpy>=2.0" "soundfile>=0.12.0" \
  "tiktoken>=0.12.0" "einops>=0.8.0" "scipy>=1.12.0" \
  "tqdm>=4.60.0" "packaging" "gradio" "requests" "streamlit"
```

PyTorch CUDA 源不是国内镜像，这是为了获取与 CUDA 绑定的官方 GPU 轮子；其余依赖均指定了清华 PyPI 镜像。若所在网络可以访问阿里云，也可以将 `https://pypi.tuna.tsinghua.edu.cn/simple` 替换为 `https://mirrors.aliyun.com/pypi/simple`。

音频读取建议在环境中安装 ffmpeg（FFmpeg，音视频编解码工具）。联网安装命令如下：

```bash
conda install -n moss-audio-4b-thinking -y --override-channels \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge \
  ffmpeg=7
```

### 3.2 安装本地 MOSS-Audio 源码

依赖源码位于 `~/tts-depency/MOSS-Audio`，使用可编辑安装（editable install，源码修改即时生效）：

```bash
conda activate moss-audio-4b-thinking
python -m pip install --no-deps --no-build-isolation \
  -e ~/tts-depency/MOSS-Audio
```

`--no-deps` 只用于本机已经按 3.1 安装好依赖的情况；如果是全新环境，应先执行 3.1 的完整安装命令。脚本仍保留 `--dependency-path`，所以即使不做可编辑安装，也可以直接从源码目录运行。

## 4. 验证环境

先检查 GPU、核心包和本地源码：

```bash
conda run -n moss-audio-4b-thinking python -c "import torch, torchaudio, transformers, accelerate, soundfile; from src.modeling_moss_audio import MossAudioModel; from src.processing_moss_audio import MossAudioProcessor; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('torchaudio', torchaudio.__version__); print('transformers', transformers.__version__); print('MOSS-Audio source import ok')"
```

期望至少看到 `cuda True`、三个版本号和 `MOSS-Audio source import ok`。本机实际验证版本为：

```text
Python 3.12.13
torch 2.12.0+cu130
torchaudio 2.11.0+cu130
transformers 4.57.3
accelerate 1.12.0
```

本机当前已安装 `torchcodec 0.9.1`、`tiktoken 0.13.0` 和 `streamlit 1.60.0`。但 `torchcodec` 在当前 `torch 2.12.0+cu130` 环境中无法加载 `libtorchcodec`，因为目标 conda 环境没有 FFmpeg 共享库；脚本会在 TorchCodec 不可用时回退到系统 ffmpeg。详情见 `conda环境依赖缺失.md`。

检查 ffmpeg：

```bash
conda run -n moss-audio-4b-thinking ffmpeg -version
```

本机 conda 环境未成功安装独立 ffmpeg 包，但系统 `/usr/bin/ffmpeg` 为 `6.1.1`。由于目标环境的 `torchaudio 2.11` 默认调用 TorchCodec，当前脚本在 TorchCodec 不可用时使用该 ffmpeg 做音频解码回退。

## 5. 运行转写

从项目根目录执行，`--local-files-only` 会禁止 Hugging Face（模型托管平台）联网请求：

```bash
conda run --no-capture-output -n moss-audio-4b-thinking \
  python modelScript/tts_local_moss_audio_4b_thinking.py \
  --model-path ~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking \
  --dependency-path ~/tts-depency/MOSS-Audio \
  --audio-path ~/tts-depency/MOSS-Audio/test/test_zh.mp3 \
  --prompt "请准确转写这段音频，仅输出转写文本。" \
  --local-files-only \
  --strip-thinking \
  --output-path work/moss_audio_4b_thinking_test.txt
```

脚本会打印模型路径、音频路径、设备、耗时和最终文本；指定 `--output-path` 时还会写出 UTF-8 文本文件。模型权重加载和首次推理会占用较长时间及约 10 GB 以上显存，不建议同时启动多个实例。

本机使用上述测试音频和 `--max-new-tokens 64` 实测成功，输出为：

```text
notice: TorchCodec 不可用，已使用 ffmpeg 音频加载回退。
elapsed: 2.72s
遇到我们的时候你才是挑战者。哇哦！
```

实测证明本地模型分片加载、CUDA 推理、MP3 读取回退和文本文件导出链路均可用。

## 6. 其他提示词示例

音频描述：

```bash
python modelScript/tts_local_moss_audio_4b_thinking.py \
  --audio-path ~/tts-depency/MOSS-Audio/test/test_zh.mp3 \
  --prompt "请描述这段音频中的说话内容、场景和主要声音事件。" \
  --local-files-only \
  --strip-thinking
```

音频问答：

```bash
python modelScript/tts_local_moss_audio_4b_thinking.py \
  --audio-path ~/tts-depency/MOSS-Audio/test/test_zh.mp3 \
  --prompt "这段音频主要使用什么语言？请说明判断依据。" \
  --local-files-only \
  --strip-thinking
```

如果需要保留 Thinking 模型的 `<think>...</think>` 推理文本，去掉 `--strip-thinking`。如需随机采样，可追加 `--do-sample --temperature 1.0 --top-p 1.0 --top-k 50`；转写场景建议保持默认的非采样模式。

## 7. 常见问题

### CUDA 不可用

检查：

```bash
conda run -n moss-audio-4b-thinking python -c "import torch; print(torch.__version__); print('cuda:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda device')"
nvidia-smi
```

`cuda False` 时脚本会在加载大模型前直接报错。需要在能访问 NVIDIA GPU 的运行环境中执行，并安装 CUDA 版 PyTorch。

### 本地离线加载失败

确认模型目录包含三个 `.safetensors` 权重分片、`model.safetensors.index.json`、tokenizer 文件以及 `config.json`。如果模型目录不完整，先补齐模型资产后再使用 `--local-files-only`。

### 显存不足

可以尝试降低生成长度：

```bash
python modelScript/tts_local_moss_audio_4b_thinking.py \
  --max-new-tokens 512 \
  --dtype float16 \
  --local-files-only
```

`float16` 可能影响个别 GPU 上的稳定性；默认 `auto` 会遵循模型配置的 `bfloat16`。

### 输入不是 MP3/WAV

依赖源码通过 `torchaudio.load()` 读取音频并重采样到模型所需采样率。若某种格式无法读取，先用 ffmpeg 转为 WAV：

```bash
ffmpeg -i input.m4a -ar 16000 -ac 1 work/input.wav
```
