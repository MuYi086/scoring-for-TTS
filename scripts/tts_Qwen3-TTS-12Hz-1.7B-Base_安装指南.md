# Qwen3-TTS-12Hz-1.7B-Base 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_qwen3_tts_12hz_1_7b_base.py` 运行 `Qwen3-TTS-12Hz-1.7B-Base` 所需的软件、安装过程和运行方式。

## 目标

- 模型路径：`/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base`
- conda 环境名：`qwen3-tts`
- Python 版本：`3.12`
- 运行脚本：`scripts/tts_local_qwen3_tts_12hz_1_7b_base.py`
- 默认参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 默认合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`

## 1. 创建独立 conda 环境

不同 TTS（文本转语音）模型使用独立环境，避免 `torch`、`transformers`、音频依赖互相污染。

```bash
conda create -n qwen3-tts -y python=3.12
conda activate qwen3-tts
```

验证：

```bash
python --version
```

期望为 `Python 3.12.x`。

## 2. 安装 Qwen3-TTS 运行包

官方推荐直接安装 `qwen-tts`：

```bash
conda run --no-capture-output -n qwen3-tts pip install -U qwen-tts
```

推荐安装 FlashAttention 2（注意力加速库），可降低显存占用并提升速度：

```bash
pip install -U flash-attn --no-build-isolation
```

如果机器内存较小或 CPU 核心很多，限制编译并行数：

```bash
MAX_JOBS=4 pip install -U flash-attn --no-build-isolation
```

说明：

- `flash-attn` 不是脚本的硬依赖；脚本检测不到时会自动回退到 `sdpa`。
- 当前脚本使用 `Qwen3TTSModel.generate_voice_clone()`，不是 Web UI，也不需要启动 `qwen-tts-demo`。
- 本机实测 `qwen-tts==0.1.1` 会安装 `torch==2.12.0+cu130`、`transformers==4.57.3`、`soundfile==0.14.0`。

## 3. 验证环境导入

```bash
conda run -n qwen3-tts python -c "import torch, soundfile; from qwen_tts import Qwen3TTSModel; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('Qwen3TTSModel import ok')"
```

期望看到：

```text
torch 2.12.0+cu130
cuda True
Qwen3TTSModel import ok
```

本机实测导入时会出现两个非阻断警告：

```text
SoX could not be found!
Warning: flash-attn is not installed.
```

说明：

- 当前脚本本机实测不依赖 SoX 二进制即可完成合成。
- 未安装 `flash-attn` 时脚本使用 `--attn-implementation sdpa` 可以正常运行，但速度可能慢于 FlashAttention 2。

## 4. 运行合成脚本

```bash
conda activate qwen3-tts
cd ~/github/timbre-design
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py --local-files-only
```

本机未安装 `flash-attn` 时建议显式使用：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --attn-implementation sdpa
```

脚本默认会：

- 加载本地模型 `/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base`；
- 使用 `sample.wav` 作为克隆参考音频；
- 读取 `第一章.md` 作为合成文本；
- 强制使用 CUDA GPU 推理；
- 按标点把长文本分块，生成后拼接；
- 输出到样例目录，文件名格式为 `Qwen3-TTS-12Hz-1.7B-Base_${t}_${k}khz.wav`。

本机实测生成：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Qwen3-TTS-12Hz-1.7B-Base_47.98s_24khz.wav
```

音频元数据：

```text
sample_rate: 24000 Hz
duration: 78.67s
channels: 1
format: WAV
size: 3.7M
```

## 5. 参考文本与克隆质量

`Qwen3-TTS-12Hz-1.7B-Base` 是 voice clone（声音克隆）模型。官方高质量路径需要同时提供：

- `ref_audio`：参考音频；
- `ref_text`：参考音频对应的逐字文本。

当前样例目录只有 `sample.wav`，没有试听音频对应文本。因此脚本默认启用 `x_vector_only_mode=True`，只从参考音频提取 speaker embedding（说话人嵌入）。这种方式能运行克隆，但音色相似度通常低于完整 `ref_audio + ref_text`。

如果后续补齐参考文本，运行：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --ref-text-file samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample_transcript.txt
```

或者直接传入短文本：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --ref-text "这里填写 sample.wav 对应的准确文本"
```

## 6. 常用参数

调整分块长度：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --max-chars-per-chunk 120 \
  --pause-ms 250
```

使用更保守的注意力后端和精度：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --attn-implementation sdpa \
  --dtype float32
```

说明：

- `--max-chars-per-chunk` 用于降低长文本漏读风险。
- `--pause-ms` 控制分块拼接时的段间静音。
- `--dtype auto` 默认在 CUDA 上使用 `bfloat16`。
- `--attn-implementation auto` 会优先使用 `flash_attention_2`，没有安装时回退到 `sdpa`。

## 7. 输出检查命令

```bash
conda run -n qwen3-tts python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Qwen3-TTS-12Hz-1.7B-Base_47.98s_24khz.wav'; info=sf.info(p); print(info.samplerate, round(info.duration, 2), info.channels)"
```

## 8. 常见问题

### Missing import: qwen_tts

说明没有进入 `qwen3-tts` 环境，或没有安装 `qwen-tts`。

处理：

```bash
conda activate qwen3-tts
pip install -U qwen-tts
```

### CUDA GPU is required

脚本要求 GPU 推理。如果 `torch.cuda.is_available()` 是 `False`，先检查显卡驱动、CUDA 版 PyTorch 和当前 conda 环境。

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### 生成音频接近静音

优先检查是否提供了参考音频和参考文本。当前脚本没有参考文本时会自动使用 `x_vector_only_mode=True`，可以跑通，但克隆质量有限。若音频异常，建议补齐 `sample.wav` 对应的准确文本后使用 `--ref-text-file`。

### flash-attn 安装失败

`flash-attn` 是可选加速依赖。安装失败时可以跳过，并在运行脚本时显式使用：

```bash
python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py \
  --local-files-only \
  --attn-implementation sdpa
```

### SoX could not be found

`qwen_tts` 导入时会检查系统 SoX 二进制。本机实测该警告不阻止当前脚本完成 `sample.wav` 克隆和 WAV 输出。如果后续处理其他音频格式时遇到硬错误，再安装 SoX：

```bash
conda install -n qwen3-tts -y sox
```
