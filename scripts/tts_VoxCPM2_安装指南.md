# VoxCPM2 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_voxcpm2.py` 运行 `VoxCPM2` 所需的软件、安装过程和运行方式。

## 目标

- TTS（文本转语音）模型路径：`/home/muyi086/hf-mirror/openbmb/VoxCPM2`
- conda 环境名：`voxcpm2`
- Python 版本：`3.10`
- 运行脚本：`scripts/tts_local_voxcpm2.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`
- 默认输出：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_${t}_${k}khz.wav`
- 本机实测输出：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_72.45s_48khz.wav`

说明：项目宪章默认要求 VoxCPM2 使用 `/persistent/home/muyi086/modelscope/VoxCPM2`。本任务明确指定 `/home/muyi086/hf-mirror/openbmb/VoxCPM2`，因此脚本默认按本次任务路径运行；如果要回到宪章默认路径，可通过 `--model-path /persistent/home/muyi086/modelscope/VoxCPM2` 覆盖。

## 1. 创建独立 conda 环境

不同 TTS 模型使用独立环境，避免 `torch`、`transformers`、音频依赖互相污染。

```bash
conda create -n voxcpm2 -y python=3.10
conda activate voxcpm2
```

验证：

```bash
python --version
```

期望为 `Python 3.10.x`。

## 2. 安装 VoxCPM2 运行包

VoxCPM2 官方模型卡给出的基础安装方式是：

```bash
pip install voxcpm
```

如果需要显式安装 CUDA 版 PyTorch，可先按本机 CUDA 版本安装 `torch`，再安装 `voxcpm`。官方模型卡要求 Python `>=3.10`、PyTorch `>=2.5.0`、CUDA `>=12.0`。

本机实测直接安装官方包即可拉起所需依赖：

```bash
conda run --no-capture-output -n voxcpm2 pip install voxcpm soundfile
```

本机实测版本：

```text
voxcpm 2.0.3
torch 2.12.0+cu130
torchaudio 2.11.0
transformers 5.12.0
soundfile 0.14.0
```

说明：

- 当前脚本使用 `from voxcpm import VoxCPM` 加载模型。
- 脚本强制检查 CUDA GPU，可避免误用 CPU 跑 2B 参数模型。
- `soundfile` 用于写出 WAV 文件。

## 3. 验证环境导入

```bash
conda run -n voxcpm2 python -c "import torch, soundfile; from voxcpm import VoxCPM; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('VoxCPM import ok')"
```

期望看到：

```text
cuda True
VoxCPM import ok
```

## 4. 验证模型初始化

```bash
conda run -n voxcpm2 python -c "from voxcpm import VoxCPM; m=VoxCPM.from_pretrained('/home/muyi086/hf-mirror/openbmb/VoxCPM2', load_denoiser=False, local_files_only=True, optimize=False); print('sample_rate', m.tts_model.sample_rate)"
```

模型卡说明 VoxCPM2 输出 `48kHz` 音频；脚本会从 `model.tts_model.sample_rate` 读取实际采样率，并写入输出文件名。

## 5. 运行合成脚本

```bash
conda activate voxcpm2
cd /home/muyi086/github/timbre-design
python scripts/tts_local_voxcpm2.py --local-files-only
```

脚本默认会：

- 加载本地模型 `/home/muyi086/hf-mirror/openbmb/VoxCPM2`；
- 使用 `sample.wav` 作为克隆参考音频；
- 读取 `第一章.md` 作为合成文本；
- 强制使用 CUDA GPU 推理；
- 默认整段一次生成，避免逐块独立克隆导致音色和音量漂移；
- 输出到样例目录，文件名格式为 `VoxCPM2_${t}_${k}khz.wav`。

本机实测生成：

```text
elapsed: 72.45s
sample rate: 48000 Hz (48 kHz)
output: samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_72.45s_48khz.wav
```

音频元数据：

```text
sample_rate: 48000 Hz
duration: 68.64s
channels: 1
format: WAV
size: 6.3M
```

## 6. 克隆模式

当前样例目录只有 `sample.wav`，没有参考音频对应的精确文本。因此脚本默认使用 controllable cloning（可控声音克隆）模式：

```python
model.generate(text=..., reference_wav_path="sample.wav")
```

如果后续补齐 `sample.wav` 的逐字文本，可使用 ultimate cloning（高保真克隆）模式：

```bash
python scripts/tts_local_voxcpm2.py \
  --local-files-only \
  --prompt-text-file samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample_transcript.txt
```

或直接传入文本：

```bash
python scripts/tts_local_voxcpm2.py \
  --local-files-only \
  --prompt-text "这里填写 sample.wav 对应的准确文本"
```

## 7. 常用参数

调整分块长度和段间静音：

```bash
python scripts/tts_local_voxcpm2.py \
  --local-files-only \
  --max-chars-per-chunk 120 \
  --pause-ms 250
```

说明：当前样例文本只有 406 字，默认 `--max-chars-per-chunk 0` 会整段一次生成。旧版默认 `120` 字分块会让每个 chunk 独立做一次可控声音克隆，实测会造成句间音色漂移，且第 2 个 chunk 音量明显偏低。只有遇到更长文本或显存不足时，才建议手动启用分块。

调整风格控制：

```bash
python scripts/tts_local_voxcpm2.py \
  --local-files-only \
  --style-prompt "低沉、沉稳、克制，像深夜电台主持一样叙述。"
```

关闭风格前缀：

```bash
python scripts/tts_local_voxcpm2.py \
  --local-files-only \
  --style-prompt ""
```

说明：

- `--max-chars-per-chunk` 用于降低长文本漏读和不稳定风险。
- `--pause-ms` 控制分块拼接时的段间静音。
- `--cfg-value` 默认 `2.0`，来自 VoxCPM2 模型卡示例。
- `--inference-timesteps` 默认 `10`，来自 VoxCPM2 模型卡示例。
- `--optimize` 默认关闭。开启后会触发 `torch.compile` / Triton 编译，当前机器如果没有 C 编译器会失败。

## 8. 输出检查命令

生成成功后，可用下面命令检查采样率、时长和通道数：

```bash
conda run -n voxcpm2 python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_<t>s_<k>khz.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels); print('format:', info.format)"
```

## 9. 常见问题

### Missing import: voxcpm

说明没有进入 `voxcpm2` 环境，或没有安装 `voxcpm`。

处理：

```bash
conda activate voxcpm2
pip install voxcpm
```

### CUDA GPU is required

脚本要求 GPU 推理。如果 `torch.cuda.is_available()` 是 `False`，先检查显卡驱动、CUDA 版 PyTorch 和当前 conda 环境。

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

本机实测在普通沙箱命令中 `torch.cuda.is_available()` 可能是 `False`，但提权运行后为 `True`。实际合成命令使用可访问 GPU 的运行方式完成。

### Failed to find C compiler

现象：

```text
RuntimeError: Failed to find C compiler. Please specify via CC environment variable or set triton.knobs.build.impl.
```

原因：

- `VoxCPM.from_pretrained()` 安装版默认 `optimize=True`，会在 warmup 阶段触发 `torch.compile` / Triton 编译。
- 当前环境没有可用 C 编译器时会失败。

处理：

- 当前脚本默认传入 `optimize=False`，不触发编译，已实测可成功合成。
- 如果后续安装了 C 编译器并希望测试加速，可显式加 `--optimize`。

### 本地离线加载失败

脚本传入 `--local-files-only` 时会设置：

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

如果仍然尝试联网，优先检查 `--model-path` 是否指向完整本地模型目录，并确认目录内包含：

```text
config.json
model.safetensors
audiovae.pth
tokenizer.json
tokenization_voxcpm2.py
```

### 参考文本缺失导致克隆相似度有限

没有 `--prompt-text` 或 `--prompt-text-file` 时，脚本只能使用参考音频做基础克隆，并通过 `--style-prompt` 控制语气。若需要更高相似度，建议补齐 `sample.wav` 对应逐字文本后启用 ultimate cloning。

### 长文本漏读或不稳定

降低单块长度：

```bash
python scripts/tts_local_voxcpm2.py --local-files-only --max-chars-per-chunk 80
```

VoxCPM2 模型卡也提示长文本或高表现力输入可能偶发不稳定，必要时可生成 1 到 3 次后人工选择。
