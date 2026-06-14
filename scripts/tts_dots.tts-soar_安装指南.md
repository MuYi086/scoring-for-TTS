# dots.tts-soar 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_dots_tts_soar.py` 运行 `dots.tts-soar` 所需的软件、安装过程和运行方式。

## 目标

- 模型路径：`/home/muyi086/hf-mirror/rednote-hilab/dots.tts-soar`
- conda 环境名：`dots_tts_soar`
- Python 版本：`3.10`
- 运行脚本：`scripts/tts_local_dots_tts_soar.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

## 1. 创建独立 conda 环境

不同 TTS（文本转语音）模型使用独立环境，避免 `torch`、`transformers`、音频依赖互相污染。

本机最终跑通方案是从已验证 GPU 可用的 `voxcpm2` 环境克隆，再安装 dots.tts 运行包。原因是直接使用官方 recommended constraints（推荐约束版本）里的 `torch==2.8.0` 环境时，本机会出现 CUDA 初始化不可用；从 `cosyvoice` 克隆的 `torch==2.3.1` 又缺少 `torch.nn.RMSNorm`，无法初始化 `dots.tts-soar`。

```bash
conda create -n dots_tts_soar --clone voxcpm2 -y
conda activate dots_tts_soar
```

验证：

```bash
python --version
```

期望为 `Python 3.10.x`。本机实测核心版本：

```text
torch 2.12.0+cu130 cuda True
torchaudio 2.11.0+cu130
transformers 5.12.0
soundfile 0.14.0
```

## 2. 安装官方 dots.tts 运行包

为了保留 `voxcpm2` 环境中已经可用的 CUDA GPU 推理栈，不让 pip 自动替换 `torch` / `torchaudio`，先用 `--no-deps` 安装 dots.tts 包本体，再补齐缺失的轻量运行依赖。

```bash
conda run -n dots_tts_soar python -m pip install \
  --no-deps git+https://github.com/rednote-hilab/dots.tts.git

conda run -n dots_tts_soar python -m pip install \
  loguru \
  torchdiffeq \
  lingua-language-detector \
  WeTextProcessing \
  'langcodes[data]' \
  importlib_resources
```

本机安装的官方源码提交：

```text
a393d2ecbaa485fe833d863889f26054ff513f26
```

本机实测安装后的关键版本包括：

```text
torch==2.12.0+cu130
torchaudio==2.11.0+cu130
transformers==5.12.0
librosa==0.11.0
soundfile==0.14.0
numpy==2.2.6
```

说明：

- 当前脚本使用 `dots_tts.runtime.DotsTtsRuntime`，不是 Web UI，不需要启动 Gradio 服务。
- `dots.tts-soar` 是 `dots.tts-base` 基础上经过 Self-corrective Alignment（自校正对齐）后训练的 2B 参数模型，模型卡推荐用于 production zero-shot voice cloning（生产级零样本声音克隆）。
- 脚本要求 CUDA GPU 推理；如果 `torch.cuda.is_available()` 为 `False`，脚本会直接退出，避免生成 CPU 产物。
- 模型目录已经在本机 `/home/muyi086/hf-mirror/rednote-hilab/dots.tts-soar`，运行脚本时建议加 `--local-files-only` 禁止远端下载。

## 3. 验证环境导入

```bash
conda run -n dots_tts_soar python -c "import torch, soundfile; from dots_tts.runtime import DotsTtsRuntime; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('DotsTtsRuntime import ok')"
```

期望看到：

```text
cuda True
DotsTtsRuntime import ok
```

## 4. 验证模型初始化

```bash
conda run -n dots_tts_soar python -c "from dots_tts.runtime import DotsTtsRuntime; r=DotsTtsRuntime.from_pretrained('/home/muyi086/hf-mirror/rednote-hilab/dots.tts-soar', precision='bfloat16', max_generate_length=500); print('sample_rate', r.sample_rate)"
```

期望采样率为：

```text
sample_rate 48000
```

## 5. 运行合成脚本

```bash
conda activate dots_tts_soar
cd ~/github/timbre-design
python scripts/tts_local_dots_tts_soar.py --local-files-only
```

脚本默认会：

- 加载本地模型 `/home/muyi086/hf-mirror/rednote-hilab/dots.tts-soar`；
- 使用 `sample.wav` 作为克隆参考音频；
- 读取 `第一章.md` 作为合成文本；
- 强制使用 CUDA GPU 推理；
- 按标点把长文本分块，生成后拼接；
- 输出到样例目录，文件名格式为 `dots.tts-soar_${t}_${k}khz.wav`。

本机实测生成：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-soar_210.11s_48khz.wav
```

音频元数据：

```text
sample_rate: 48000 Hz
duration: 83.47s
channels: 1
format: WAV
size: 7.7M
```

## 6. 参考文本与克隆质量

`dots.tts-soar` 推荐 continuation voice cloning（续写式声音克隆），也就是同时提供：

- `--ref-audio`：参考音频；
- `--prompt-text` 或 `--prompt-text-file`：参考音频对应的准确转写文本。

当前样例目录只有 `sample.wav`，没有试听音频对应转写文本。脚本默认使用一段通用中文参考文本，方便本地验证推理链路；如果后续补齐 `sample.wav` 的准确转写，建议改用：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --prompt-text-file samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample_transcript.txt
```

如果只想使用参考音频，不传转写文本：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --prompt-text ""
```

## 7. 常用参数

提升质量但降低速度：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --num-steps 32
```

调整分块和段间静音：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-chars-per-chunk 120 \
  --pause-ms 250
```

说明：

- `--num-steps` 是 flow-matching（流匹配）采样步数，模型卡推荐 `10` 到 `32`。
- `--guidance-scale` 默认 `1.2`，用于控制文本和音色遵循度。
- `--speaker-scale` 默认 `1.5`，用于控制参考说话人嵌入强度。
- `--max-generate-length` 默认 `500`，限制每个分块的最大音频 patch 数。
- `--precision bfloat16` 是模型卡推荐精度。

## 8. 输出检查命令

生成后用 `soundfile` 检查采样率、时长和通道：

```bash
conda run -n dots_tts_soar python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-soar_替换为实际时间_48khz.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels)"
```

## 9. 常见问题

### Missing import: dots_tts

说明没有进入 `dots_tts_soar` 环境，或没有安装官方包。

处理：

```bash
conda activate dots_tts_soar
python -c "from dots_tts.runtime import DotsTtsRuntime; print('ok')"
```

### CUDA GPU is required

脚本要求 GPU 推理。如果 `torch.cuda.is_available()` 是 `False`，先检查显卡驱动、CUDA 版 PyTorch 和当前 conda 环境。

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

如果 `nvidia-smi` 能看到显卡，但 Python 里出现类似下面的错误，说明当前环境的 PyTorch CUDA 运行栈不可用，不要继续合成：

```text
UserWarning: Can't initialize NVML
RuntimeError: Found no NVIDIA driver on your system.
```

处理方向：

- 先确认没有混用其他 conda 环境的 `torch`、`torchaudio` 或 `transformers`。
- 重新安装与本机驱动匹配的 CUDA 版 PyTorch 和同版本 `torchaudio`。
- 修复后重新运行第 3 节的导入验证，必须看到 `cuda True` 再执行合成脚本。

### `max_generate_length must exceed prompt audio patch count`

说明参考音频加转写文本占用的音频 patch 已经超过 `--max-generate-length`。可以缩短参考音频，或提高上限：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-generate-length 800
```

### 合成音频内容不完整

优先降低单段文本长度：

```bash
python scripts/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-chars-per-chunk 80
```

如果仍然漏读，再提高 `--max-generate-length` 或降低 `--num-steps` 做排查。
