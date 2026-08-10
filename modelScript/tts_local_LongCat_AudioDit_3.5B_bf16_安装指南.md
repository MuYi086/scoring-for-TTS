# LongCat-AudioDiT-3.5B-bf16 本地 TTS 环境安装指南

本文对应 `modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py`，用于加载本地
`LongCat-AudioDiT-3.5B-bf16` 权重，使用参考音频进行 zero-shot voice cloning（零样本声音克隆），
输出 24 kHz 单声道 WAV（波形音频）。下面的命令均按本机已验证的目录编写；可直接复制执行，
其中 Python 包使用清华 PyPI（Python 包索引）镜像。

## 1. 目录和运行前提

- 模型目录：`~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16`
- 其他依赖和官方源码：`~/tts-depency/LongCat-AudioDiT`
- UMT5 tokenizer（分词器）目录：`~/hf-mirror/google/umt5-base`
- Conda 环境：`LongCat-AudioDiT-3.5B-bf16`
- Python：`3.10.x`
- 运行脚本：`modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py`
- 模型权重：BF16（bfloat16，保持较大动态范围的半精度）
- 音频采样率：24 kHz
- 单次生成上限：60 秒
- 推理设备：CUDA GPU；本机验证设备为 NVIDIA GeForce RTX 4070 Ti SUPER

模型目录至少需要：

```text
~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16/config.json
~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16/model.safetensors
```

模型目录只包含配置和权重；运行时还需要已经准备好的 `audiodit` 包、tokenizer 和参考音频，
不需要把约 7 GB 权重复制到本仓库。

## 2. 创建独立 Conda 环境

本机已有可用的 `audio_eval` CUDA 环境，因此采用克隆后补齐模型依赖的方式。目标环境已创建，
再次执行前请确认目标名称尚未存在：

```bash
conda create -n LongCat-AudioDiT-3.5B-bf16 --clone audio_eval -y
conda activate LongCat-AudioDiT-3.5B-bf16
python --version
```

如果没有可复用的 CUDA 环境，可创建 Python 3.10 空环境；清华 Conda（环境包管理器）镜像用于基础包：

```bash
conda create -n LongCat-AudioDiT-3.5B-bf16 -y python=3.10 \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
conda activate LongCat-AudioDiT-3.5B-bf16
python --version
```

空环境必须先执行第 3 节提供的 CUDA 版 PyTorch 安装命令；已有 `audio_eval` 时不要重复升级 CUDA 栈。

## 3. 手动安装 Python 依赖（按顺序复制执行）

下面是需要直接运行的完整 Python 安装命令，不需要打开其他依赖文件；所有 Python 包均使用清华 PyPI
（Python 包索引）镜像：

```bash
conda activate LongCat-AudioDiT-3.5B-bf16
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --upgrade pip
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  'torch>=2.0.0' \
  'torchaudio>=2.0.0' \
  'transformers==5.3.0' \
  'safetensors>=0.4.0' \
  'librosa>=0.10.0' \
  'soundfile>=0.12.0' \
  'numpy>=1.24.0' \
  'einops>=0.8.0' \
  'sentencepiece>=0.2.0'
python -m pip check
```

如果目标环境中已经有可用的 CUDA 版 PyTorch，执行上面命令前可从包列表中删除
`'torch>=2.0.0'` 和 `'torchaudio>=2.0.0'`，避免替换现有 CUDA（显卡计算）版本。

本机最终验证版本：

```text
Python 3.10.20
torch 2.13.0+cu130
torchaudio 2.11.0+cu130
transformers 5.3.0
librosa 0.11.0
soundfile 0.14.0
numpy 2.2.6
einops 0.8.2
```

`pip check` 的预期结果为：

```text
No broken requirements found.
```

## 4. 准备 UMT5 tokenizer

模型配置使用 `google/umt5-base` 的 tokenizer。当前本机已准备以下文件：

```text
~/hf-mirror/google/umt5-base/config.json
~/hf-mirror/google/umt5-base/tokenizer_config.json
~/hf-mirror/google/umt5-base/special_tokens_map.json
~/hf-mirror/google/umt5-base/spiece.model
~/hf-mirror/google/umt5-base/tokenizer.json
```

如果目标机器尚未准备，可使用 Hugging Face 国内镜像逐文件下载：

```bash
mkdir -p ~/hf-mirror/google/umt5-base
curl -fL --retry 3 https://hf-mirror.com/google/umt5-base/resolve/main/config.json \
  -o ~/hf-mirror/google/umt5-base/config.json
curl -fL --retry 3 https://hf-mirror.com/google/umt5-base/resolve/main/tokenizer_config.json \
  -o ~/hf-mirror/google/umt5-base/tokenizer_config.json
curl -fL --retry 3 https://hf-mirror.com/google/umt5-base/resolve/main/special_tokens_map.json \
  -o ~/hf-mirror/google/umt5-base/special_tokens_map.json
curl -fL --retry 3 https://hf-mirror.com/google/umt5-base/resolve/main/spiece.model \
  -o ~/hf-mirror/google/umt5-base/spiece.model
curl -fL --retry 3 https://hf-mirror.com/google/umt5-base/resolve/main/tokenizer.json \
  -o ~/hf-mirror/google/umt5-base/tokenizer.json
```

离线验证导入、CUDA、tokenizer 和 `audiodit`：

```bash
conda activate LongCat-AudioDiT-3.5B-bf16
PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -c "import torch, audiodit, einops; from audiodit import AudioDiTModel; from transformers import AutoTokenizer; from pathlib import Path; p=Path('~/hf-mirror/google/umt5-base').expanduser(); tok=AutoTokenizer.from_pretrained(str(p), local_files_only=True); x=tok(['本地分词器验证。'], return_tensors='pt'); print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA'); print('tokenizer', type(tok).__name__, 'input_shape', tuple(x.input_ids.shape)); print('AudioDiTModel import ok')"
```

预期包含 `cuda True`、`tokenizer T5Tokenizer` 和 `AudioDiTModel import ok`。
`transformers==5.3.0` 可能针对该 tokenizer 配置输出一条 regex（正则表达式）兼容性提示；这是警告，
不会阻止导入。接入脚本会先尝试新参数，遇到该版本接口冲突时自动回退到兼容调用。

## 5. 验证本地 3.5B 权重初始化

这一步会加载约 7 GB BF16 权重到显卡；本机验证约占 7.22 GiB 显存：

```bash
conda activate LongCat-AudioDiT-3.5B-bf16
PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -c "import torch, audiodit; from audiodit import AudioDiTModel; from pathlib import Path; p=Path('~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16').expanduser(); m=AudioDiTModel.from_pretrained(str(p), local_files_only=True).to('cuda'); m.vae.to_half(); m.eval(); print('params', sum(x.numel() for x in m.parameters())); print('dtypes', sorted({str(x.dtype) for x in m.parameters()})); print('sample_rate', m.config.sampling_rate, 'max_wav_duration', m.config.max_wav_duration); print('memory_allocated_gb', round(torch.cuda.memory_allocated()/1024**3, 2))"
```

本机输出的关键值为：`params 3833985217`、`torch.bfloat16`/`torch.float16`、`sample_rate 24000`、
`max_wav_duration 60`。

## 6. 运行声音克隆脚本

进入本仓库后，使用官方依赖目录中的 `audiodit` 和本地 tokenizer、模型：

```bash
cd ~/github/scoring-for-TTS
conda activate LongCat-AudioDiT-3.5B-bf16
PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
  --model-path ~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16 \
  --repo-path ~/tts-depency/LongCat-AudioDiT \
  --tokenizer-path ~/hf-mirror/google/umt5-base \
  --ref-audio ~/tts-depency/LongCat-AudioDiT/assets/prompt.wav \
  --prompt-text "小偷却一点也不气馁，继续在抽屉里翻找。" \
  --text "今天晴暖转阴雨，空气质量优至良，空气相对湿度较低。" \
  --output-dir /tmp/longcat-audiodit-3.5b-bf16-verify \
  --local-files-only
```

脚本会：

- 加载本地 3.5B BF16 权重，并强制使用 CUDA；
- 把参考音频和目标文本送入官方 `AudioDiTModel` 的声音克隆路径；
- 默认使用 APG（自适应投影引导）和 16 步 ODE（常微分方程）采样；
- 按中文标点和 `--max-chars-per-chunk` 分块，每块独立生成后插入段间静音；
- 根据参考音频时长、文本字符数和模型 60 秒上限估算 latent frames（潜变量帧）；
- 输出 `LongCat-AudioDiT-3.5B-bf16_${t}s_24khz.wav`。

本机端到端验证结果：

```text
output: /tmp/longcat-audiodit-3.5b-bf16-verify-default/LongCat-AudioDiT-3.5B-bf16_8.53s_24khz.wav
sample_rate: 24000 Hz
duration: 6.66s
channels: 1
format: WAV / PCM_16
```

如果已有 Markdown 文本文件，可改用 `--text-file`；参考音频的 `--prompt-text` 必须是准确逐字转写：

```bash
PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
  --model-path ~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16 \
  --repo-path ~/tts-depency/LongCat-AudioDiT \
  --tokenizer-path ~/hf-mirror/google/umt5-base \
  --ref-audio /path/to/reference.wav \
  --prompt-text-file /path/to/reference.txt \
  --text-file /path/to/text.md \
  --output-dir /path/to/output \
  --local-files-only
```

## 7. 常用参数

长文本可降低单块字符数，减少单段达到 60 秒上限而截断的风险：

```bash
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
  --max-chars-per-chunk 120 \
  --pause-ms 250
```

提高质量但增加耗时：

```bash
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
  --nfe 32 \
  --guidance-method apg \
  --guidance-strength 4.0
```

目标文本太短或生成结果偏短时，可小幅调整时长估计：

```bash
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py --duration-scale 1.05
```

## 8. 输出检查

将 `<实际输出 wav>` 替换为脚本打印的 `output:` 路径：

```bash
conda activate LongCat-AudioDiT-3.5B-bf16
python -c "import soundfile as sf; p='<实际输出 wav>'; info=sf.info(p); print('sample_rate:', info.samplerate); print('duration:', round(info.duration, 2)); print('channels:', info.channels); print('format:', info.format); print('subtype:', info.subtype)"
```

## 9. 常见问题

### `Missing import: audiodit`

说明没有找到官方源码目录。目标机器上应确认 `~/tts-depency/LongCat-AudioDiT/audiodit/` 存在，
并设置 `PYTHONPATH` 或显式传入 `--repo-path`：

```bash
PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
  --repo-path ~/tts-depency/LongCat-AudioDiT --help
```

### UMT5 tokenizer 无法离线加载

确认 `~/hf-mirror/google/umt5-base/` 同时包含 `config.json`、`tokenizer_config.json`、
`special_tokens_map.json`、`spiece.model` 和 `tokenizer.json`，并显式传入：

```bash
--tokenizer-path ~/hf-mirror/google/umt5-base --local-files-only
```

### `CUDA GPU is required`

脚本要求 GPU 推理。检查驱动和当前环境：

```bash
nvidia-smi
conda run -n LongCat-AudioDiT-3.5B-bf16 python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA')"
```

### 显存不足或音频被截断

先关闭其他 GPU 进程，保留默认 `--vae-dtype float16`，再降低 `--max-chars-per-chunk`；不要把 BF16
主权重强制转换成 float32。模型单段上限为 60 秒，必要时缩短参考音频或降低单块字符数。

安装期间出现过的最新错误和依赖前提缺失分别记录在仓库根目录的
`conda环境安装错误.md`、`conda环境依赖缺失.md`。依赖缺失记录中的前提需要由用户手动安装并验证；
验证完成后按 `task103.md` 要求删除对应记录文件。
