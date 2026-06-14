# MOSS-TTS-Local-Transformer 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_moss_tts_local_transformer.py` 运行 `MOSS-TTS-Local-Transformer` 所需的软件、安装过程和当前注意事项。

## 目标

- TTS（文本转语音）模型路径：`/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-TTS-Local-Transformer`
- 参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`
- 运行脚本：`scripts/tts_local_moss_tts_local_transformer.py`
- 默认输出：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer_${t}_${k}khz.wav`
- 本机实测环境：`moss-tts-py310`
- 本机实测输出：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer_178.47s_24khz.wav`

说明：该模型会通过 processor（处理器）调用 `MOSS-Audio-Tokenizer` 作为 codec（音频 tokenizer）。如果本机没有本地 codec 目录，默认 `--codec-path OpenMOSS-Team/MOSS-Audio-Tokenizer` 会按 Hugging Face（模型托管平台）模型 ID 解析；需要完全离线运行时，应先把该 codec 下载到本机并显式传入 `--codec-path /path/to/MOSS-Audio-Tokenizer`。

## 1. 创建 conda 环境

官方 README 建议使用 Python 3.12 和 Transformers 5.0.0：

```bash
conda create -n moss-tts -y python=3.12
conda activate moss-tts
```

验证：

```bash
python --version
```

期望为 `Python 3.12.x`。

本机实测时，为避免影响既有 `cosyvoice` 环境，使用了独立克隆环境：

```bash
conda create -n moss-tts-py310 --clone cosyvoice -y
```

注意：后续所有升级和运行都只在 `moss-tts-py310` 中执行，未修改原 `cosyvoice` 环境。

## 2. 获取官方代码并安装依赖

```bash
cd ~/github
git clone https://github.com/OpenMOSS/MOSS-TTS.git /home/muyi086/github/MOSS-TTS
cd /home/muyi086/github/MOSS-TTS
pip install --extra-index-url https://download.pytorch.org/whl/cu128 -e .
```

官方依赖会安装 `torch`、`torchaudio`、`transformers`、`accelerate`、音频处理库和自定义模型加载所需组件。

注意：现有 `cosyvoice` 环境中的 `transformers 4.51.3` 不满足 MOSS remote code（远端自定义模型代码）要求，会报：

```text
module 'transformers.processing_utils' has no attribute 'MODALITY_TO_BASE_CLASS_MAPPING'
```

因此不要直接复用 `cosyvoice` 环境跑该脚本，除非已经按 MOSS 官方依赖升级过。

本机实测官方完整安装会下载 CUDA 12.8 版 PyTorch 2.9.1 及 NVIDIA 大包，`nvidia-cublas-cu12` 下载多次中断。因此实际采用下面的轻量升级方式，只升级新环境中的 MOSS 必需依赖：

```bash
conda run -n moss-tts-py310 pip install --timeout 120 --retries 10 \
  'transformers==5.0.0' \
  'safetensors==0.6.2' \
  'tiktoken==0.12.0' \
  'orjson==3.11.4'
```

实测版本：

```text
torch 2.3.1+cu121
torchaudio 2.3.1+cu121
transformers 5.0.0
```

## 3. 可选安装 FlashAttention 2

FlashAttention 2（高效注意力实现）可降低显存占用并提升速度，但只适用于支持的 CUDA GPU。可选安装：

```bash
cd /home/muyi086/github/MOSS-TTS
MAX_JOBS=4 pip install --extra-index-url https://download.pytorch.org/whl/cu128 -e ".[flash-attn]"
```

如果安装失败，可以跳过。脚本会自动回退到 `sdpa` 或 `eager` attention（注意力）后端。

## 4. 准备本地模型与 codec

当前任务指定的模型目录已经是：

```bash
ls /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-TTS-Local-Transformer
```

还需要准备 codec：

```bash
# 下载到本地镜像目录：
conda run -n moss-tts-py310 hf download OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --local-dir /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer

# 完全离线运行时使用本地 codec：
python scripts/tts_local_moss_tts_local_transformer.py \
  --codec-path /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --local-files-only
```

本机实测 `MOSS-Audio-Tokenizer` 目录大小约 `6.7G`，包含两个 `safetensors` 权重分片。

## 5. 验证导入

```bash
conda run -n moss-tts python -c "import torch, torchaudio; from transformers import AutoModel, AutoProcessor; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('torchaudio', torchaudio.__version__); print('transformers import ok')"
```

如果安装了 FlashAttention 2，也可验证：

```bash
conda run -n moss-tts python -c "import importlib.util; print(importlib.util.find_spec('flash_attn') is not None)"
```

## 6. 运行合成脚本

```bash
conda activate moss-tts
cd /home/muyi086/github/timbre-design
python scripts/tts_local_moss_tts_local_transformer.py
```

本机实测必须在可访问 GPU 的非沙箱环境中运行。沙箱内 `nvidia-smi` 会报 GPU access blocked（GPU 访问被系统阻止），但非沙箱下 GPU 正常可见：

```text
NVIDIA GeForce RTX 4070 Ti SUPER
```

实际运行命令：

```bash
env HF_HOME=/tmp/hf-moss TRANSFORMERS_CACHE=/tmp/hf-moss/transformers TQDM_DISABLE=1 \
  conda run -n moss-tts-py310 python scripts/tts_local_moss_tts_local_transformer.py \
  --codec-path /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --local-files-only
```

常用参数：

```bash
python scripts/tts_local_moss_tts_local_transformer.py \
  --model-path /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-TTS-Local-Transformer \
  --codec-path OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --max-new-tokens 4096 \
  --n-vq-for-inference 32 \
  --audio-temperature 1.0 \
  --audio-top-p 0.95 \
  --audio-top-k 50 \
  --audio-repetition-penalty 1.1
```

参数说明：

- `--max-new-tokens` 控制最长生成时长，官方说明约 `12.5 tokens = 1s`。
- `--n-vq-for-inference 32` 是 MOSS-TTSLocal 官方推荐的 RVQ（残差向量量化）深度，音质较高但速度较慢。
- `--audio-temperature 1.0 --audio-top-p 0.95 --audio-top-k 50 --audio-repetition-penalty 1.1` 是 MOSS-TTSLocal 官方推荐的音频采样参数。
- `--attn-implementation auto` 会优先尝试 `flash_attention_2`，否则在 CUDA 上使用 `sdpa`；如果 CUDA 不可用，脚本会直接失败。

生成成功后，脚本会打印：

```text
elapsed: <t>s
sample rate: 24000 Hz (24 kHz)
output: samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer_<t>s_24khz.wav
```

本机实测生成：

```text
elapsed: 178.47s
sample rate: 24000 Hz (24 kHz)
output: samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer_178.47s_24khz.wav
```

音频元数据：

```text
sample_rate: 24000 Hz
duration: 78.48s
channels: 1
format: WAV
subtype: FLOAT
size: 7534160 bytes
```

## 7. 常见问题

### `MOSS-TTS runtime is not importable`

说明当前环境缺少 `torch`、`torchaudio` 或 `transformers`。处理：

```bash
conda activate moss-tts
cd /home/muyi086/github/MOSS-TTS
pip install --extra-index-url https://download.pytorch.org/whl/cu128 -e .
```

### `MODALITY_TO_BASE_CLASS_MAPPING` 不存在

说明 `transformers` 版本过旧。当前本机 `cosyvoice` 环境实测为 `transformers 4.51.3`，会触发该错误。处理：

```bash
conda activate moss-tts
cd /home/muyi086/github/MOSS-TTS
pip install --extra-index-url https://download.pytorch.org/whl/cu128 -e .
```

如果不安装官方仓库，也至少需要升级到支持 MOSS 自定义 processor 的新版 `transformers`。

### `pad_sequence() got an unexpected keyword argument 'padding_side'`

说明当前 `torch 2.3.1` 缺少新版 `padding_side` 参数。脚本内已经加入进程级兼容补丁，只影响当前脚本运行，不修改安装包。

### `torch.is_autocast_enabled() takes no arguments`

说明当前 `torch 2.3.1` 与 `transformers 5.0.0` 的 autocast（自动混合精度）API 有差异。脚本内已经加入进程级兼容补丁，只影响当前脚本运行，不修改安装包。

### 找不到 `MOSS-Audio-Tokenizer`

现象可能是 `OSError`、`Repository Not Found` 或 `local_files_only` 相关报错。处理：

```bash
python scripts/tts_local_moss_tts_local_transformer.py --codec-path OpenMOSS-Team/MOSS-Audio-Tokenizer
```

如果需要离线：

```bash
python scripts/tts_local_moss_tts_local_transformer.py \
  --codec-path /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --local-files-only
```

### FlashAttention 2 安装失败

可以不安装。脚本默认 `--attn-implementation auto`，没有 `flash_attn` 时会使用 PyTorch SDPA（缩放点积注意力）或 eager（普通 PyTorch 实现）。

### 显存不足

可尝试：

```bash
python scripts/tts_local_moss_tts_local_transformer.py \
  --n-vq-for-inference 16 \
  --max-new-tokens 2048
```

代价是音质或最长生成时长可能下降。

### CUDA 不可用

该模型约 1.7B 参数，正式 TTS 合成必须使用 CUDA GPU。脚本不提供 CPU 合成路径；如果沙箱内 GPU 被阻止，应在非沙箱环境运行：

```bash
python scripts/tts_local_moss_tts_local_transformer.py \
  --codec-path /home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer \
  --local-files-only
```
