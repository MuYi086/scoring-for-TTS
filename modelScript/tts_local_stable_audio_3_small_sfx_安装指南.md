# Stable Audio 3 Small-SFX 本地音效生成环境安装指南

本文对应 `modelScript/tts_local_stable_audio_3_small_sfx.py`，用于加载本地
`~/hf-mirror/stabilityai/stable-audio-3-small-sfx` 模型，根据英文文字提示生成音效。

Stable Audio 3 Small-SFX 是 text-to-audio（文字生成音频）模型，不是 TTS（文本转语音）模型，
也不支持参考音频声音克隆。模型更适合火车鸣笛、门响、环境声、机械声等音效生成；官方资料显示
Small-SFX 输出 44.1 kHz（千赫兹）立体声音频，最长 120 秒。

## 1. 目录、环境和硬件

- 本地模型：`~/hf-mirror/stabilityai/stable-audio-3-small-sfx`
- 官方源码：`~/tts-depency/stable-audio-3`
- Conda（环境管理器）环境：`stable_audio_3_small_sfx`
- Python：`3.10.x`
- 运行脚本：`modelScript/tts_local_stable_audio_3_small_sfx.py`
- 默认输出目录：`samples/stable-audio-3-small-sfx`
- 官方 Small-SFX 上限：120 秒
- 本机验证 GPU：NVIDIA GeForce RTX 4070 Ti SUPER，CUDA 驱动可用

模型目录至少应包含：

```text
~/hf-mirror/stabilityai/stable-audio-3-small-sfx/model_config.json
~/hf-mirror/stabilityai/stable-audio-3-small-sfx/model.safetensors
~/hf-mirror/stabilityai/stable-audio-3-small-sfx/t5gemma-b-b-ul2/config.json
~/hf-mirror/stabilityai/stable-audio-3-small-sfx/t5gemma-b-b-ul2/model.safetensors
~/hf-mirror/stabilityai/stable-audio-3-small-sfx/t5gemma-b-b-ul2/tokenizer.json
```

本地模型约 3.3 GB，不复制到本仓库。

## 2. 创建独立 Conda 环境

### 2.1 本机推荐方式：复用已验证的 CUDA 基础环境

本机已有 `voxcpm2` 环境，其中包含可用的 CUDA 版 PyTorch（2.12.0+cu130）、torchaudio、
Transformers（模型转换器）和音频依赖。克隆后环境仍然独立，不会修改 `voxcpm2`：

```bash
conda create -n stable_audio_3_small_sfx --clone voxcpm2 -y
conda activate stable_audio_3_small_sfx
python --version
```

### 2.2 没有基础环境时：创建 Python 3.10 空环境

```bash
conda create -n stable_audio_3_small_sfx -y python=3.10
conda activate stable_audio_3_small_sfx
python --version
```

期望看到 `Python 3.10.x`。空环境需要执行第 3 节的完整依赖安装命令；已有 CUDA 基础环境时，
不要重复替换正在使用的 CUDA 栈。

## 3. 安装 Python 依赖

官方 `stable-audio-3` 项目的基础依赖包括 `einops`、`einops-exts`、`numpy`、`safetensors`、
`torch`、`torchaudio`、`huggingface-hub`、`transformers` 和 `soundfile`。下面的 Python 包命令
使用阿里云 PyPI（Python 包索引）镜像。

### 3.1 本机推荐方式：只补装缺少的 Stable Audio 3 依赖

```bash
conda activate stable_audio_3_small_sfx
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple \
  --upgrade pip
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple \
  'einops-exts>=0.0.4' \
  'hatchling>=1.26'
```

然后下载官方推理源码。源码不放进本仓库，脚本通过 `--upstream-path` 或环境变量读取：

```bash
mkdir -p ~/tts-depency
git clone --depth 1 \
  https://github.com/Stability-AI/stable-audio-3.git \
  ~/tts-depency/stable-audio-3
```

`stable-audio-3` 当前官方 `pyproject.toml` 将 PyTorch 固定为 2.7.1；本机已有可用的
CUDA 13.0 PyTorch 2.12.0/torchaudio 2.11.0，脚本直接使用官方源码目录并保留这套已验证的
CUDA 栈，避免重复下载数 GB 的 CUDA 运行库。环境检查：

```bash
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
python -c "import torch, torchaudio, transformers; from stable_audio_3.model import StableAudioModel; from stable_audio_3.loading_utils import load_diffusion_cond; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('torchaudio', torchaudio.__version__); print('transformers', transformers.__version__); print('Stable Audio 3 source import ok')"
python -m pip check
```

期望包含 `cuda True`、`Stable Audio 3 source import ok` 和 `No broken requirements found.`。
没有 NVIDIA GPU 时，`cuda` 可以为 `False`，运行时改用第 7 节的 CPU 命令。

### 3.2 空环境的完整安装命令

如果没有可以复用的 CUDA 环境，直接执行下面的完整命令。普通依赖使用阿里云 PyPI 镜像：

```bash
conda activate stable_audio_3_small_sfx
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple \
  --upgrade pip
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
python -m pip check
```

如果阿里云镜像下载 CUDA 版 PyTorch 过慢，可只把两个 PyTorch 包改用官方 CUDA 12.6 wheel，
其余包仍使用阿里云镜像：

```bash
conda activate stable_audio_3_small_sfx
python -m pip install \
  --index-url https://download.pytorch.org/whl/cu126 \
  --extra-index-url https://mirrors.aliyun.com/pypi/simple \
  --trusted-host download.pytorch.org \
  'torch==2.7.1+cu126' \
  'torchaudio==2.7.1+cu126'
```

## 4. 检查本地模型和 T5Gemma 文本编码器

模型自带 `t5gemma-b-b-ul2` 文本编码器，脚本会把官方配置中的远程仓库路径改成本地子目录，
因此 `--local-files-only` 不会再次访问 Hugging Face（模型托管平台）。先检查文件：

```bash
conda activate stable_audio_3_small_sfx
python -c "from pathlib import Path; p=Path('~/hf-mirror/stabilityai/stable-audio-3-small-sfx').expanduser(); names=['model_config.json','model.safetensors','t5gemma-b-b-ul2/config.json','t5gemma-b-b-ul2/model.safetensors','t5gemma-b-b-ul2/tokenizer.json']; missing=[name for name in names if not (p/name).is_file()]; assert not missing, f'missing: {missing}'; print('model files ok:', p); print('size:', round(sum(x.stat().st_size for x in p.rglob('*') if x.is_file())/1024**3, 2), 'GB')"
```

离线检查 CUDA、Tokenizer（分词器）和官方源码导入：

```bash
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -c "from pathlib import Path; import torch; from transformers import AutoTokenizer; p=Path('~/hf-mirror/stabilityai/stable-audio-3-small-sfx/t5gemma-b-b-ul2').expanduser(); tok=AutoTokenizer.from_pretrained(str(p), local_files_only=True); print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print('tokenizer', type(tok).__name__); print('T5Gemma tokenizer ok')"
```

## 5. 最小端到端验证

下面的命令只生成 3 秒音效并写到 `/tmp`，便于确认环境、文本编码器、模型权重和 WAV（波形音频）
写出链路都正常：

```bash
cd ~/github/scoring-for-TTS
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --upstream-path ~/tts-depency/stable-audio-3 \
  --model-path ~/hf-mirror/stabilityai/stable-audio-3-small-sfx \
  --prompt "A single metal door closing in an empty concrete hallway" \
  --duration 3 \
  --steps 8 \
  --seed 20260812 \
  --output /tmp/stable_audio_3_small_sfx_smoke_test.wav \
  --local-files-only
```

成功时输出类似：

```text
device: cuda
precision: float16
sample rate: 44100 Hz (44.1 kHz)
channels: 2
duration: 3.00s
output: /tmp/stable_audio_3_small_sfx_smoke_test.wav
```

检查输出元数据：

```bash
conda activate stable_audio_3_small_sfx
python -c "import soundfile as sf; p='/tmp/stable_audio_3_small_sfx_smoke_test.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels); print('format:', info.format); print('subtype:', info.subtype)"
```

## 6. 常用运行方式

### 6.1 直接传入英文音效提示词

```bash
cd ~/github/scoring-for-TTS
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --prompt "A busy night market with distant conversations, footsteps, and soft rain" \
  --duration 12 \
  --seed 20260812 \
  --local-files-only
```

默认输出到 `samples/stable-audio-3-small-sfx/`，文件名包含模型名、耗时和采样率。

### 6.2 从文本或 Markdown 文件读取提示词

```bash
cd ~/github/scoring-for-TTS
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --prompt-file /path/to/sound_effect_prompt.md \
  --duration 7 \
  --output /path/to/output.wav \
  --local-files-only
```

提示词建议使用英文描述主体、环境、材质、距离和变化过程；该模型主要按英文音效描述训练。

### 6.3 调整采样步数、提示词遵循度和输出格式

```bash
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --prompt "A close-up wooden drawer opening slowly with a soft creak" \
  --duration 5 \
  --steps 12 \
  --cfg-scale 1.0 \
  --seed 20260812 \
  --subtype PCM_16 \
  --local-files-only
```

- `--steps` 默认为 8；提高会增加耗时。
- `--cfg-scale` 默认为 1.0；Small-SFX 后训练模型建议先保持默认值。
- `--seed -1` 每次随机；固定整数可复现同一随机起点。
- `--subtype FLOAT` 保留 32 位浮点波形；`PCM_16` 便于常见播放器和剪辑工具兼容。
- `--device auto` 自动优先 CUDA；也可显式传 `--device cuda` 或 `--device cpu`。
- `--dtype auto` 在 CUDA 使用 float16（半精度），CPU 使用 float32（单精度）。

## 7. CPU 运行

Small-SFX 官方支持 CPU，但速度会明显慢于 CUDA。没有 NVIDIA GPU 时使用：

```bash
cd ~/github/scoring-for-TTS
conda activate stable_audio_3_small_sfx
PYTHONPATH=~/tts-depency/stable-audio-3 \
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --device cpu \
  --dtype float32 \
  --prompt "A short glass bottle clink on a wooden table" \
  --duration 3 \
  --local-files-only
```

## 8. 常见问题

### `Stable Audio 3 runtime is not importable`

确认官方源码目录存在，并显式传入：

```bash
PYTHONPATH=~/tts-depency/stable-audio-3 \
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --upstream-path ~/tts-depency/stable-audio-3 --help
```

### 模型目录缺少文件

重新准备完整的 `model_config.json`、`model.safetensors` 和 `t5gemma-b-b-ul2/` 子目录。
脚本会在加载大模型前直接报告缺少的文件名。

### `torch.cuda.is_available() is False`

检查驱动和当前环境是否使用 CUDA 版 PyTorch：

```bash
nvidia-smi
conda activate stable_audio_3_small_sfx
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

如果没有 GPU，去掉 CUDA 选项并按第 7 节使用 CPU；如果明确传了 `--device cuda`，脚本会安全失败，
不会悄悄退回 CPU。

### 显存不足

先降低生成时长，确认短音效可运行；Small-SFX 约 433M 参数，但文本编码器也会占用显存：

```bash
python modelScript/tts_local_stable_audio_3_small_sfx.py \
  --duration 3 --steps 8 --local-files-only
```

也可以用 `--device cpu --dtype float32` 验证功能链路。

### 生成的是音效而不是人声

这是模型用途限制，不是脚本故障。Stable Audio 3 Small-SFX 不用于 TTS、人声朗读或参考音色克隆；
中文提示词也可能明显弱于英文提示词。

## 9. 许可说明

使用前请阅读模型目录中的 `LICENSE.md`、`LICENSE_GEMMA.md` 和 `NOTICE`，并遵守 Stability AI
Community License（社区许可）及其中关于商业用途、Gemma 文本编码器和内容生成的限制。
