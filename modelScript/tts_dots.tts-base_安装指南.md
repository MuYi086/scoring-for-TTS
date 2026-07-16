# dots.tts-base 本地 TTS 环境安装指南

本文记录 `modelScript/tts_local_dots_tts_base.py` 运行 `dots.tts-base` 所需的软件、安装过程和运行方式。

## 目标

- 模型路径：`/path/to/dots.tts-base`
- conda 环境名：`dots_tts`
- Python 版本：`3.10`
- 运行脚本：`modelScript/tts_local_dots_tts_base.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

运行前设置 `DOTS_TTS_MODEL_PATH=/path/to/dots.tts-base`，或在命令中通过 `--model-path /path/to/dots.tts-base` 单次指定模型目录。

## 1. 创建独立 conda 环境

不同 TTS（文本转语音）模型使用独立环境，避免 `torch`、`transformers`、音频依赖互相污染。

```bash
conda create -n dots_tts -y python=3.10
conda activate dots_tts
```

验证：

```bash
python --version
```

期望为 `Python 3.10.x`。

## 2. 安装官方 dots.tts 运行包

模型卡推荐从官方 GitHub 仓库安装，并使用 recommended constraints（推荐约束版本）固定关键依赖。直接安装命令如下：

```bash
conda run -n dots_tts python -m pip install --upgrade pip
conda run -n dots_tts python -m pip install \
  git+https://github.com/rednote-hilab/dots.tts.git \
  -c https://raw.githubusercontent.com/rednote-hilab/dots.tts/main/constraints/recommended.txt
```

本机实测直接安装会长时间停留在依赖解析阶段，环境目录未写入核心依赖。实际跑通采用分步安装：先安装官方约束版本的核心运行依赖，再用 `--no-deps` 安装 `dots.tts` 包本身。

```bash
conda run -n dots_tts python -m pip install --upgrade pip

conda run -n dots_tts python -m pip install \
  -c https://raw.githubusercontent.com/rednote-hilab/dots.tts/main/constraints/recommended.txt \
  torch==2.8.0 \
  torchaudio==2.8.0 \
  transformers==4.57.0 \
  librosa==0.11.0 \
  soundfile==0.13.1 \
  numpy==2.2.6 \
  pydantic==2.12.5 \
  PyYAML==6.0.3 \
  safetensors==0.8.0rc0 \
  huggingface-hub \
  loguru \
  'langcodes[data]' \
  einops \
  torchdiffeq \
  tqdm \
  lingua-language-detector \
  WeTextProcessing

conda run -n dots_tts python -m pip install --no-deps \
  git+https://github.com/rednote-hilab/dots.tts.git
```

本机安装的官方源码提交：

```text
a393d2ecbaa485fe833d863889f26054ff513f26
```

官方约束当前锁定的核心版本包括：

```text
torch==2.8.0
torchaudio==2.8.0
transformers==4.57.0
librosa==0.11.0
soundfile==0.13.1
numpy==2.2.6
pydantic==2.12.5
PyYAML==6.0.3
safetensors==0.8.0rc0
```

说明：

- 当前脚本使用 `dots_tts.runtime.DotsTtsRuntime`，不是 Web UI，不需要启动 Gradio 服务。
- `dots.tts-base` 是 2B 参数模型，脚本要求 CUDA GPU 推理；如果 `torch.cuda.is_available()` 为 `False`，脚本会直接退出。
- 模型目录已经在本机 `/path/to/dots.tts-base`，运行脚本时建议加 `--local-files-only` 禁止远端下载。

## 3. 验证环境导入

```bash
conda run -n dots_tts python -c "import torch, soundfile; from dots_tts.runtime import DotsTtsRuntime; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('DotsTtsRuntime import ok')"
```

期望看到：

```text
cuda True
DotsTtsRuntime import ok
```

## 4. 验证模型初始化

```bash
conda run -n dots_tts python -c "from dots_tts.runtime import DotsTtsRuntime; r=DotsTtsRuntime.from_pretrained('/path/to/dots.tts-base', precision='bfloat16', max_generate_length=500); print('sample_rate', r.sample_rate)"
```

期望采样率为：

```text
sample_rate 48000
```

## 5. 运行合成脚本

```bash
conda activate dots_tts
cd ~/github/scoring-for-TTS
python modelScript/tts_local_dots_tts_base.py --local-files-only
```

脚本默认会：

- 加载本地模型 `/path/to/dots.tts-base`；
- 使用 `sample.wav` 作为克隆参考音频；
- 读取 `第一章.md` 作为合成文本；
- 强制使用 CUDA GPU 推理；
- 按标点把长文本分块，生成后拼接；
- 输出到样例目录，文件名格式为 `dots.tts-base_${t}_${k}khz.wav`。

本机实测生成：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-base_232.67s_48khz.wav
```

音频元数据：

```text
sample_rate: 48000 Hz
duration: 85.23s
channels: 1
format: WAV
size: 7.9M
```

## 6. 参考文本与克隆质量

`dots.tts-base` 推荐 continuation voice cloning（续写式声音克隆），也就是同时提供：

- `--ref-audio`：参考音频；
- `--prompt-text` 或 `--prompt-text-file`：参考音频对应的准确转写文本。

当前样例目录只有 `sample.wav`，没有试听音频对应转写文本。脚本默认使用一段通用中文参考文本，方便本地验证推理链路；如果后续补齐 `sample.wav` 的准确转写，建议改用：

```bash
python modelScript/tts_local_dots_tts_base.py \
  --local-files-only \
  --prompt-text-file samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample_transcript.txt
```

如果只想使用参考音频，不传转写文本：

```bash
python modelScript/tts_local_dots_tts_base.py \
  --local-files-only \
  --prompt-text ""
```

## 7. 常用参数

提升质量但降低速度：

```bash
python modelScript/tts_local_dots_tts_base.py \
  --local-files-only \
  --num-steps 32
```

调整分块和段间静音：

```bash
python modelScript/tts_local_dots_tts_base.py \
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
conda run -n dots_tts python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-base_替换为实际时间_48khz.wav'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels)"
```

## 9. 常见问题

### Missing import: dots_tts

说明没有进入 `dots_tts` 环境，或没有安装官方包。

处理：

```bash
conda activate dots_tts
python -c "from dots_tts.runtime import DotsTtsRuntime; print('ok')"
```

### CUDA GPU is required

脚本要求 GPU 推理。如果 `torch.cuda.is_available()` 是 `False`，先检查显卡驱动、CUDA 版 PyTorch 和当前 conda 环境。

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### `max_generate_length must exceed prompt audio patch count`

说明参考音频加转写文本占用的音频 patch 已经超过 `--max-generate-length`。可以缩短参考音频，或提高上限：

```bash
python modelScript/tts_local_dots_tts_base.py \
  --local-files-only \
  --max-generate-length 800
```

### 合成音频内容不完整

优先降低单段文本长度：

```bash
python modelScript/tts_local_dots_tts_base.py \
  --local-files-only \
  --max-chars-per-chunk 80
```

如果仍然漏读，再提高 `--max-generate-length` 或降低 `--num-steps` 做排查。
