# Stable Audio 3 Medium 本地音频生成环境安装指南

本文对应 `modelScript/tts_local_stable_audio_3_medium.py`，用于加载本地
`~/hf-mirror/stabilityai/stable-audio-3-medium` 模型，根据英文文字提示生成音乐、环境声或音效。

Stable Audio 3 Medium 是 text-to-audio（文字生成音频）模型，不是 TTS（文本转语音）模型，
不支持把章节文本朗读成人声，也不支持参考音频声音克隆。它更适合生成配乐、环境声、乐器片段和音效。
模型按英文描述训练，中文提示词的效果可能较弱；输出为 44.1 kHz（千赫兹）立体声音频，最长 380 秒。

## 1. 前提与本地模型目录

- Conda（环境管理器）环境：`stable_audio_3_medium`
- Python：`3.10.x`
- 运行脚本：`modelScript/tts_local_stable_audio_3_medium.py`
- 默认模型目录：`~/hf-mirror/stabilityai/stable-audio-3-medium`
- 默认输出目录：`samples/stable-audio-3-medium`
- 硬件：NVIDIA CUDA GPU；Medium 官方要求 Flash Attention 2（快速注意力实现），不支持 CPU 推理

本机已检测到 NVIDIA GeForce RTX 4070 Ti SUPER（16 GB 显存）。官方 Medium 基准显示生成最长音频的模型侧峰值显存约为 6.52 GB；实际显存还会受 T5Gemma 文本编码器、驱动和其他 GPU 程序影响。运行前请关闭占用显存的进程。

模型目录必须完整，且不应复制进本仓库：

```text
~/hf-mirror/stabilityai/stable-audio-3-medium/model_config.json
~/hf-mirror/stabilityai/stable-audio-3-medium/model.safetensors
~/hf-mirror/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2/config.json
~/hf-mirror/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2/model.safetensors
~/hf-mirror/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2/tokenizer.json
```

先检查本地模型文件：

```bash
python -c "from pathlib import Path; p=Path('~/hf-mirror/stabilityai/stable-audio-3-medium').expanduser(); names=['model_config.json','model.safetensors','t5gemma-b-b-ul2/config.json','t5gemma-b-b-ul2/model.safetensors','t5gemma-b-b-ul2/tokenizer.json']; missing=[name for name in names if not (p/name).is_file()]; assert not missing, f'missing: {missing}'; print('model files ok:', p); print('size:', round(sum(x.stat().st_size for x in p.rglob('*') if x.is_file())/1024**3, 2), 'GB')"
```

## 2. 创建独立 Conda 环境

```bash
conda create -n stable_audio_3_medium -y python=3.10 pip
conda activate stable_audio_3_medium
python --version
```

期望看到 `Python 3.10.x`。环境与其他模型隔离，避免 PyTorch、Transformers（模型转换器）和音频依赖互相污染。

## 3. 安装官方推理依赖

除官方源码和 Flash Attention 2 预编译 wheel（Python 二进制安装包）外，以下 Python 包均通过阿里云 PyPI（Python 包索引）镜像下载。

```bash
conda activate stable_audio_3_medium
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple --upgrade pip
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple \
  'torch==2.7.1' \
  'torchaudio==2.7.1' \
  'einops>=0.8.2' \
  'einops-exts>=0.0.4' \
  'numpy>=2.2.6' \
  'packaging>=26.0' \
  'safetensors>=0.7.0' \
  'tqdm>=4.67.3' \
  'huggingface-hub>=1.7.1' \
  'transformers>=5.8.0' \
  'soundfile>=0.13.1' \
  'hatchling>=1.26'
```

当前 `stable-audio-3` 官方推理库尚未发布到 PyPI，因此需要从官方源码安装；其余 Python 依赖仍使用阿里云镜像。固定提交可避免 `main` 分支后续变化造成环境不可复现：

```bash
conda activate stable_audio_3_medium
mkdir -p "$HOME/tts-dependency"
git clone https://github.com/Stability-AI/stable-audio-3.git "$HOME/tts-dependency/stable-audio-3"
git -C "$HOME/tts-dependency/stable-audio-3" checkout a0b57f5483c4588f827f3552b7d5c6ca2a9687be
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple --no-deps "$HOME/tts-dependency/stable-audio-3"
```

Medium 还必须安装与 Python 3.10、PyTorch 2.7 和 CUDA 12.6 对应的 Flash Attention 2 预编译 wheel。该 wheel 没有可用的清华、中科大或阿里云镜像发布，使用官方项目文档指定的二进制 URL；`--no-deps` 确保其他包仍不绕过阿里云镜像：

```bash
conda activate stable_audio_3_medium
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple --no-deps \
  'https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.16/flash_attn-2.6.3+cu126torch2.7-cp310-cp310-linux_x86_64.whl'
```

如果上述 wheel 的 Python、PyTorch 或 CUDA 标识与本机环境不同，不能混装。请从官方 `stable-audio-3` README 的 Flash Attention 一节选择文件名中 `cu`、`torch` 和 `cp` 都匹配的 wheel；缺少匹配 wheel 时，需要 CUDA Toolkit、C/C++ 编译器和 `ninja`（构建工具）从源码编译 `flash-attn`。

## 4. 验证环境

下面命令直接验证 CUDA、Flash Attention 2、官方库和依赖一致性：

```bash
conda activate stable_audio_3_medium
python -c "import torch, torchaudio, flash_attn; from flash_attn import flash_attn_func; from stable_audio_3.model import StableAudioModel; from stable_audio_3.loading_utils import load_diffusion_cond; print('torch:', torch.__version__); print('torch cuda:', torch.version.cuda); print('cuda available:', torch.cuda.is_available()); print('torchaudio:', torchaudio.__version__); print('flash-attn:', flash_attn.__version__); print('flash_attn_func:', flash_attn_func is not None); print('Stable Audio 3 import ok')"
python -m pip check
```

期望包含：

```text
cuda available: True
flash_attn_func: True
Stable Audio 3 import ok
No broken requirements found.
```

如果 `cuda available` 为 `False`，先检查显卡驱动和当前环境中的 CUDA PyTorch；脚本会明确失败，而不是静默退回 CPU：

```bash
nvidia-smi
conda activate stable_audio_3_medium
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA GPU')"
```

## 5. 最小端到端验证

下面命令只生成 3 秒音频并写到 `/tmp`，用于确认本地模型、T5Gemma（文本编码器）、CUDA、Flash Attention 和 WAV（波形音频）写出链路。`--local-files-only` 会禁止 Hugging Face 网络访问；脚本把配置中的远程 T5Gemma 路径改为本地模型子目录。

```bash
cd /path/to/scoring-for-TTS
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --model-path "$HOME/hf-mirror/stabilityai/stable-audio-3-medium" \
  --prompt "A calm cinematic ambient track with soft piano, warm strings, and gentle rain" \
  --duration 3 \
  --steps 8 \
  --seed 20260812 \
  --output /tmp/stable_audio_3_medium_smoke_test.wav \
  --local-files-only
```

成功时输出类似：

```text
device: cuda
precision: float16
sample rate: 44100 Hz (44.1 kHz)
channels: 2
duration: 3.00s
output: /tmp/stable_audio_3_medium_smoke_test.wav
```

检查输出元数据：

```bash
conda activate stable_audio_3_medium
python -c "import soundfile as sf; p='/tmp/stable_audio_3_medium_smoke_test.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels); print('format:', info.format); print('subtype:', info.subtype)"
```

## 6. 常用运行方式

### 6.1 直接传入英文音乐或音效提示词

```bash
cd /path/to/scoring-for-TTS
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --prompt "A dreamy synthpop instrumental, 120 BPM, bright arpeggiators and a warm bassline" \
  --duration 30 \
  --seed 20260812 \
  --local-files-only
```

默认输出到 `samples/stable-audio-3-medium/`，文件名包含模型名、耗时和采样率。

### 6.2 从文本或 Markdown 文件读取提示词

```bash
cd /path/to/scoring-for-TTS
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --prompt-file /path/to/audio_prompt.md \
  --duration 20 \
  --output /path/to/output.wav \
  --local-files-only
```

提示词建议用英文说明音频类型、乐器或声源、节奏、氛围、空间感和变化过程。请传提示词描述，不要传需要朗读的文章正文。

### 6.3 调整时长、采样步数、提示词遵循度和输出格式

```bash
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --prompt "A close-up wooden drawer opening slowly with a soft creak in a quiet room" \
  --duration 5 \
  --steps 12 \
  --cfg-scale 1.0 \
  --seed 20260812 \
  --subtype PCM_16 \
  --local-files-only
```

- `--duration` 范围为 0 到 380 秒；更长音频会增加显存和存储需求。
- `--steps` 默认 8；提高会增加耗时，后训练 Medium 模型建议从默认值开始。
- `--cfg-scale` 默认 1.0；增大并不一定更好。
- `--seed -1` 每次随机；固定整数可复现同一随机起点。
- `--dtype float16` 为默认值，适合 CUDA；`--dtype float32` 会显著提高显存占用，仅用于排查精度问题。
- `--subtype FLOAT` 保留 32 位浮点波形；`PCM_16` 便于常见播放器和剪辑工具兼容。

## 7. 常见问题

### `Stable Audio 3 runtime is not importable`

确认已在目标环境安装官方源码包：

```bash
conda activate stable_audio_3_medium
python -c "import stable_audio_3; print(stable_audio_3.__file__)"
```

若未安装，重新执行第 3 节中的 `git clone` 和 `python -m pip install --no-deps` 命令。

### `Stable Audio 3 Medium requires Flash Attention 2`

确认 wheel 与环境一致，并检查导入：

```bash
conda activate stable_audio_3_medium
python -c "import flash_attn; from flash_attn import flash_attn_func; print(flash_attn.__version__); print(flash_attn_func)"
```

不要把为其他 CUDA、PyTorch 或 Python 版本构建的 `flash-attn` wheel 安装到本环境。

### 模型目录缺少文件或脚本尝试联网

重新检查第 1 节列出的完整模型目录，并使用 `--local-files-only`：

```bash
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --model-path "$HOME/hf-mirror/stabilityai/stable-audio-3-medium" \
  --prompt "short ambient sound" \
  --duration 3 \
  --local-files-only
```

### 显存不足

先用 3 秒、8 步验证：

```bash
conda activate stable_audio_3_medium
python modelScript/tts_local_stable_audio_3_medium.py \
  --prompt "short ambient sound" \
  --duration 3 \
  --steps 8 \
  --local-files-only
```

关闭其他 GPU 程序后逐步增加时长。Medium 不支持 CPU 回退，不能通过 `--device cpu` 解决显存不足。

### 生成的不是人声朗读

这是模型用途限制，不是脚本故障。Stable Audio 3 Medium 面向音乐和声音生成，不用于 TTS、人声朗读或参考音色克隆；中文提示词也可能明显弱于英文提示词。

## 8. 许可说明

使用前请阅读模型目录中的 `LICENSE.md`、`LICENSE_GEMMA.md` 和 `NOTICE`，并遵守 Stability AI Community License（社区许可）及其中关于商业用途、Gemma 文本编码器和内容生成的限制。
