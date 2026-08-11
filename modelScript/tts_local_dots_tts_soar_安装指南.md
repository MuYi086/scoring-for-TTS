# dots.tts-soar 本地 TTS 环境安装指南

本文记录 `modelScript/tts_local_dots_tts_soar.py` 运行 `dots.tts-soar` 的环境安装、模型验证和本地声音克隆方式。

## 目标

- 模型路径：`~/hf-mirror/rednote-hilab/dots.tts-soar`
- conda 环境名：`dots_tts_soar`
- Python 版本：`3.10`
- 运行脚本：`modelScript/tts_local_dots_tts_soar.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`
- 默认输出：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-soar_${t}_${k}khz.wav`

脚本也支持通过环境变量 `DOTS_TTS_SOAR_MODEL_PATH` 或命令行参数 `--model-path` 指定其他模型目录。

当前本机已验证：Python 3.10.20、`dots.tts` 0.2.1、PyTorch 2.8.0+cu128、CUDA 可用、GPU 为 NVIDIA GeForce RTX 4070 Ti SUPER；SOAR 模型本地初始化成功，采样率为 48000 Hz。

## 1. 创建独立 conda 环境

不同 TTS（文本转语音）模型使用独立环境，避免 PyTorch、Transformers 和音频依赖互相污染。下面使用中科大 Anaconda 镜像：

```bash
conda create -n dots_tts_soar -y python=3.10 \
  -c https://mirrors.ustc.edu.cn/anaconda/pkgs/main
conda activate dots_tts_soar
```

验证 Python：

```bash
python --version
```

期望为 `Python 3.10.x`。

## 2. 安装 dots.tts 运行依赖

官方项目的推荐约束文件固定了主要依赖版本。下面直接写出已核验的推荐版本，所有 PyPI 包均通过清华镜像安装；`dots.tts` 运行包本身不是普通 PyPI 包，需要在下一节从官方源码仓库安装。

先安装官方约束中的核心运行依赖：

```bash
python -m pip install --upgrade pip setuptools wheel \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple

python -m pip install --disable-pip-version-check \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  torch==2.8.0 torchaudio==2.8.0 transformers==4.57.0 \
  huggingface-hub loguru 'langcodes[data]' einops librosa==0.11.0 \
  soundfile==0.13.1 numpy==2.2.6 pydantic==2.12.5 PyYAML==6.0.3 \
  safetensors==0.8.0rc0 torchdiffeq tqdm \
  lingua-language-detector WeTextProcessing
```

注意：官方约束文件中的 `gradio==6.17.0` 在官方 PyPI、清华、中科大和阿里云镜像均没有可安装发行版；项目自身的 `pyproject.toml` 要求是 `gradio>=6.17,<7`。因此使用满足该范围的现行版本 `6.17.3`：

```bash
python -m pip install --disable-pip-version-check \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  gradio==6.17.3
```

## 3. 安装官方 dots.tts 源码包

官方运行包从 GitHub 源码安装，当前验证提交为 `4947d364baa5afb2daf1feb00a247b5f23f97878`。PyPI 依赖仍使用清华镜像，源码安装使用官方仓库：

```bash
python -m pip install --disable-pip-version-check \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --no-deps \
  git+https://github.com/rednote-hilab/dots.tts.git@4947d364baa5afb2daf1feb00a247b5f23f97878
```

`--no-deps` 是因为上一节已经按官方约束和兼容范围分步安装了完整依赖，避免 pip（Python 包安装器）再次长时间解析并重新选择版本。

## 4. 验证环境导入和 CUDA

```bash
python -c "import importlib.metadata as md, torch, soundfile, gradio; from dots_tts.runtime import DotsTtsRuntime; print('python', __import__('sys').version.split()[0]); print('dots.tts', md.version('dots.tts')); print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('gradio', gradio.__version__); print('soundfile', soundfile.__version__); print('DotsTtsRuntime import ok')"
```

期望至少看到：

```text
python 3.10.x
dots.tts 0.2.1
torch 2.8.0+cu128
cuda_available True
gradio 6.17.3
DotsTtsRuntime import ok
```

如果需要确认显卡名称：

```bash
python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
```

## 5. 验证 SOAR 模型初始化

模型目录必须包含 `config.json`、`model.safetensors`、`speaker_encoder.safetensors`、`vocoder.safetensors` 和 tokenizer 文件。使用本地路径并关闭 Hugging Face（模型托管平台）联网访问：

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -c "from dots_tts.runtime import DotsTtsRuntime; r=DotsTtsRuntime.from_pretrained('~/hf-mirror/rednote-hilab/dots.tts-soar', precision='bfloat16', max_generate_length=500); print('model_init ok'); print('sample_rate', r.sample_rate)"
```

期望看到：

```text
model_init ok
sample_rate 48000
```

## 6. 运行声音克隆脚本

进入项目根目录并运行：

```bash
conda activate dots_tts_soar
cd ~/github/scoring-for-TTS
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --model-path ~/hf-mirror/rednote-hilab/dots.tts-soar
```

脚本默认会：

- 加载本地 `dots.tts-soar` 模型；
- 使用 `sample.wav` 作为参考音频；
- 读取 `第一章.md` 作为合成文本；
- 使用 CUDA 和 `bfloat16`（脑浮点 16 位）推理；
- 按标点把文本分成不超过 120 字的分块并拼接；
- 输出 48 kHz 单声道 WAV 文件，文件名格式为 `dots.tts-soar_${t}_${k}khz.wav`。

如果当前仓库没有 `samples` 目录，请用自己的文本和参考音频替换参数：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --model-path ~/hf-mirror/rednote-hilab/dots.tts-soar \
  --text-file /path/to/text.md \
  --ref-audio /path/to/reference.wav \
  --output-dir /path/to/output
```

## 7. 参考文本和克隆质量

`dots.tts-soar` 推荐 continuation voice cloning（续写式声音克隆），即同时提供参考音频和该音频的准确转写文本：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --prompt-text-file /path/to/reference_transcript.txt
```

也可以直接传入准确文本：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --prompt-text "这里填写 reference.wav 对应的准确文本"
```

如果只有参考音频、暂时没有参考文本，可以显式关闭 prompt text（参考文本）：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --prompt-text ""
```

不应使用与参考音频不一致的虚构文本，否则会降低续写式声音克隆的稳定性和音色相似度。

## 8. 常用参数

提高质量、降低速度：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --num-steps 32
```

调整文本分块和段间静音：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-chars-per-chunk 80 \
  --pause-ms 250
```

常用参数说明：

- `--num-steps`：flow matching（流匹配）采样步数，通常使用 `10` 到 `32`；越大越慢。
- `--guidance-scale`：文本和音色遵循强度，默认 `1.2`。
- `--speaker-scale`：参考说话人向量强度，默认 `1.5`。
- `--max-generate-length`：每块音频 patch（音频块）上限，默认 `500`；参考音频较长时报错时可提高。
- `--max-chars-per-chunk`：每块文本最大字符数，设置为 `0` 可关闭分块。
- `--language`：默认 `chinese`，也可使用 `auto_detect`；设置为 `none` 可关闭语言标签。
- `--precision`：默认 `bfloat16`，显存不足时可按模型运行时支持情况调整。

## 9. 输出检查命令

将 `<实际输出文件>` 替换为脚本打印的实际路径：

```bash
python -c "import soundfile as sf; p='<实际输出文件>'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels); print('format:', info.format)"
```

期望采样率为 `48000`，通道数为 `1`。

## 10. 常见问题

### `Missing import: dots_tts`

确认已激活正确环境并完成源码包安装：

```bash
conda activate dots_tts_soar
python -c "from dots_tts.runtime import DotsTtsRuntime; print('ok')"
```

### `CUDA GPU is required`

脚本要求 GPU 推理。检查驱动和 PyTorch CUDA：

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

### `gradio==6.17.0` 无法安装

这是官方约束文件的历史版本缺失问题，不是本地机器缺少依赖。使用项目兼容范围内可用的 `gradio==6.17.3`：

```bash
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple gradio==6.17.3
```

### `max_generate_length` 不足

参考音频占用的音频 patch 数过多时，提高上限：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-generate-length 800
```

### 文本漏读或显存不足

降低单块文本长度，必要时提高 `--max-generate-length`：

```bash
python modelScript/tts_local_dots_tts_soar.py \
  --local-files-only \
  --max-chars-per-chunk 80 \
  --max-generate-length 800
```
