# LongCat-AudioDiT-1B 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_longcat_audiodit_1b.py` 运行 `LongCat-AudioDiT-1B` 所需的软件、安装过程和运行方式。

## 目标

- 模型路径：`/home/muyi086/hf-mirror/meituan-longcat/LongCat-AudioDiT-1B`
- conda 环境名：`longcat_audiodit`
- Python 版本：建议 `3.10`
- 官方源码目录：建议 `/home/muyi086/github/LongCat-AudioDiT`
- 运行脚本：`scripts/tts_local_longcat_audiodit_1b.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

## 1. 创建独立 conda 环境

不同 TTS（文本转语音）模型使用独立环境，避免 `torch`、`transformers`、音频依赖互相污染。

本机本轮实测为了复用已经验证 CUDA 可用的基础依赖，采用从 `audio_eval` 克隆后补齐 `einops` 的方式：

```bash
conda create -n longcat_audiodit --clone audio_eval -y
conda install -n longcat_audiodit -y -c conda-forge einops
conda activate longcat_audiodit
python --version
```

期望为 `Python 3.10.x`。

如果没有可复用的 `audio_eval` 环境，也可以从空环境开始：

```bash
conda create -n longcat_audiodit -y python=3.10
conda activate longcat_audiodit
```

## 2. 获取官方 LongCat-AudioDiT 源码

官方模型卡说明需要 `audiodit` 包注册 `AudioDiTModel`，该包位于官方 GitHub 仓库中。建议把源码单独放在仓库外部：

```bash
git clone https://github.com/meituan-longcat/LongCat-AudioDiT /home/muyi086/github/LongCat-AudioDiT
```

如果已经克隆过，后续运行脚本时只需要把该目录加入 `PYTHONPATH`，或者传给脚本的 `--repo-path`。

## 3. 安装运行依赖

官方 `requirements.txt` 当前列出的核心依赖为：

```text
transformers>=5.3.0
torch>=2.0.0
torchaudio>=2.0.0
safetensors>=0.4.0
librosa>=0.10.0
soundfile>=0.12.0
numpy>=1.24.0
einops>=0.8.0
```

从空环境开始时，安装命令为：

```bash
conda activate longcat_audiodit
python -m pip install --upgrade pip
python -m pip install -r /home/muyi086/github/LongCat-AudioDiT/requirements.txt
```

说明：

- 本脚本要求 CUDA GPU 推理；如果 `torch.cuda.is_available()` 是 `False`，需要重新安装匹配显卡驱动的 CUDA 版 PyTorch。
- 官方示例默认把 `AudioDiTModel` 放到 CUDA，并调用 `model.vae.to_half()`，即 VAE（波形变分自编码器）使用 FP16，主模型按权重默认精度运行。
- `LongCat-AudioDiT-1B` 模型目录已有本地权重，但 tokenizer（分词器）默认来自 `google/umt5-base`，离线运行前需要本地缓存或单独下载。

## 4. 准备 tokenizer

如果可以联网，首次运行时可让 `AutoTokenizer.from_pretrained("google/umt5-base")` 自动下载。若要离线运行，建议提前下载到本地镜像目录：

本机本轮实测使用 `huggingface_hub.snapshot_download()` 下载 tokenizer 相关文件：

```bash
conda run -n longcat_audiodit python -c "from huggingface_hub import snapshot_download; snapshot_download('google/umt5-base', local_dir='/home/muyi086/hf-mirror/google/umt5-base', allow_patterns=['*.json','*.model','*.txt','tokenizer*','spiece.model'])"
```

离线运行脚本时传入：

```bash
--tokenizer-path /home/muyi086/hf-mirror/google/umt5-base --local-files-only
```

## 5. 验证环境导入

```bash
conda activate longcat_audiodit
PYTHONPATH=/home/muyi086/github/LongCat-AudioDiT \
python -c "import torch, soundfile, audiodit; from audiodit import AudioDiTModel; from transformers import AutoTokenizer; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('AudioDiTModel import ok')"
```

期望看到：

```text
cuda True
AudioDiTModel import ok
```

## 6. 运行合成脚本

进入本项目仓库：

```bash
conda activate longcat_audiodit
cd ~/github/timbre-design
```

在线或已有 Hugging Face tokenizer 缓存时：

```bash
PYTHONPATH=/home/muyi086/github/LongCat-AudioDiT \
python scripts/tts_local_longcat_audiodit_1b.py \
  --repo-path /home/muyi086/github/LongCat-AudioDiT
```

完全离线运行时：

```bash
PYTHONPATH=/home/muyi086/github/LongCat-AudioDiT \
python scripts/tts_local_longcat_audiodit_1b.py \
  --repo-path /home/muyi086/github/LongCat-AudioDiT \
  --tokenizer-path /home/muyi086/hf-mirror/google/umt5-base \
  --local-files-only
```

脚本默认会：

- 加载本地模型 `/home/muyi086/hf-mirror/meituan-longcat/LongCat-AudioDiT-1B`；
- 使用 `sample.wav` 作为 voice cloning（声音克隆）参考音频；
- 读取 `第一章.md` 作为合成文本；
- 强制使用 CUDA GPU 推理；
- 按标点把长文本分块，避免单段超过模型 `max_wav_duration=30` 秒限制；
- 使用官方推荐的 APG guidance（自适应投影引导）克隆路径；
- 输出到样例目录，文件名格式为 `LongCat-AudioDiT-1B_${t}_${k}khz.wav`。

## 7. 参考文本与克隆质量

`LongCat-AudioDiT-1B` 的官方克隆示例同时提供：

- `--prompt_audio`：参考音频；
- `--prompt_text`：参考音频对应的准确文本；
- `--guidance_method apg`：克隆时使用 APG guidance（自适应投影引导）。

当前样例目录只有 `sample.wav`，没有试听音频对应转写文本。脚本默认使用一段通用中文短句作为兜底，方便验证 GPU 推理链路；如果后续补齐 `sample.wav` 的准确转写，建议改用：

```bash
PYTHONPATH=/home/muyi086/github/LongCat-AudioDiT \
python scripts/tts_local_longcat_audiodit_1b.py \
  --repo-path /home/muyi086/github/LongCat-AudioDiT \
  --prompt-text-file samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample_transcript.txt
```

也可以直接传入文本：

```bash
python scripts/tts_local_longcat_audiodit_1b.py \
  --prompt-text "这里填写 sample.wav 对应的准确文本"
```

## 8. 常用参数

调整分块和段间静音：

```bash
python scripts/tts_local_longcat_audiodit_1b.py \
  --max-chars-per-chunk 90 \
  --pause-ms 250
```

调整推理步数和引导强度：

```bash
python scripts/tts_local_longcat_audiodit_1b.py \
  --nfe 16 \
  --guidance-method apg \
  --guidance-strength 4.0
```

控制时长估算：

```bash
python scripts/tts_local_longcat_audiodit_1b.py --duration-scale 1.05
```

说明：

- `--max-chars-per-chunk` 默认 `90`，适配 `LongCat-AudioDiT-1B` 的 30 秒单段上限和 8.23 秒参考音频。
- `--nfe` 对应官方 `steps` 参数，默认 `16`。
- `--guidance-strength` 对应官方 `cfg_strength` 参数，默认 `4.0`。
- `--vae-dtype float16` 对齐官方示例的 `model.vae.to_half()`。
- `--duration-scale` 用于微调官方字符数时长估算，遇到截断可略微调大。

## 9. 本机实测输出

本轮实测命令：

```bash
conda run -n longcat_audiodit python scripts/tts_local_longcat_audiodit_1b.py \
  --repo-path /tmp/LongCat-AudioDiT \
  --tokenizer-path /home/muyi086/hf-mirror/google/umt5-base \
  --local-files-only
```

生成结果：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/LongCat-AudioDiT-1B_16.45s_24khz.wav
```

音频元数据：

```text
sample_rate: 24000 Hz
duration: 85.64s
channels: 1
format: WAV
frames: 2055472
```

## 10. 输出检查命令

生成后用 `soundfile` 检查采样率、时长和通道：

```bash
conda run -n longcat_audiodit python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/LongCat-AudioDiT-1B_替换为实际时间_24khz.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels)"
```

## 11. 常见问题

### Missing import: audiodit

说明没有把官方源码目录加入 Python 搜索路径，或源码没有克隆。

处理：

```bash
git clone https://github.com/meituan-longcat/LongCat-AudioDiT /home/muyi086/github/LongCat-AudioDiT
PYTHONPATH=/home/muyi086/github/LongCat-AudioDiT python scripts/tts_local_longcat_audiodit_1b.py --repo-path /home/muyi086/github/LongCat-AudioDiT
```

### tokenizer 无法离线加载

说明本地没有 `google/umt5-base` tokenizer 缓存。处理方式是先下载 tokenizer，或在线运行时去掉 `--local-files-only`。

### CUDA GPU is required

脚本要求 GPU 推理。如果 `torch.cuda.is_available()` 是 `False`，先检查显卡驱动、CUDA 版 PyTorch 和当前 conda 环境。

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### 生成音频被截断

`LongCat-AudioDiT-1B` 配置的 `max_wav_duration` 是 30 秒。优先减小 `--max-chars-per-chunk`，必要时小幅增大 `--duration-scale`。
