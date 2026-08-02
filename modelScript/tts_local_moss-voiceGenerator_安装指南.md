# MOSS-VoiceGenerator 本地运行指南

本文对应 `modelScript/tts_local_moss-voiceGenerator.py`。它是外层入口，内部调用同目录的 `tts_local_moss_voiceGenerator.py`；模型通过文字描述设计音色，不需要参考音频，但必须提供 MOSS 音频 tokenizer。

## 路径与已验证结果

- Conda 环境：`moss-voiceGenerator`
- Python：3.12
- 语音模型：`~/hf-mirror/OpenMOSS-Team/MOSS-VoiceGenerator`
- 音频 tokenizer：`~/hf-mirror/openmoss/MOSS-Audio-Tokenizer-v2`
- MOSS 源码：`~/tts-depency/MOSS-TTS`
- 脚本：`/home/muyi086/github/scoring-for-TTS/modelScript/tts_local_moss-voiceGenerator.py`
- 当前核心版本：`torch 2.12.0`、`torchaudio 2.11.0`、`transformers 5.12.0`
- `pip check`：通过；CUDA 可用
- 实测结果：模型和 tokenizer 均能加载，生成 24 kHz、单声道 WAV

## 从零重建环境（仅在环境损坏时执行）

当前环境已经配置完成，不要重复执行安装命令。确需重建时，使用清华源安装已验证的运行时版本：

```bash
conda create -n moss-voiceGenerator python=3.12 -y
conda activate moss-voiceGenerator
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary --no-cache-dir \
  "torch==2.12.0" "torchaudio==2.11.0" "transformers==5.12.0" \
  "safetensors==0.6.2" "numpy==2.1.0" "orjson==3.11.4" "tqdm==4.67.1" \
  "PyYAML==6.0.3" "einops==0.8.1" "scipy==1.16.2" "librosa==0.11.0" \
  "tiktoken==0.12.0" psutil packaging ninja setuptools wheel gradio \
  "typer>=0.20,<0.26"
python -m pip install --no-build-isolation --no-deps -e ~/tts-depency/MOSS-TTS
python -m pip check
```

清华源不可用时，可将 `--index-url` 替换为 `https://pypi.mirrors.ustc.edu.cn/simple` 或 `https://mirrors.aliyun.com/pypi/simple`。PyTorch 若需要专用 CUDA wheel，应按照本机 CUDA 驱动选择对应官方 wheel 源，不要无上限升级 Torch。

## 本地模型合成

```bash
conda activate moss-voiceGenerator
python /home/muyi086/github/scoring-for-TTS/modelScript/tts_local_moss-voiceGenerator.py \
  --model-path ~/hf-mirror/OpenMOSS-Team/MOSS-VoiceGenerator \
  --codec-path ~/hf-mirror/openmoss/MOSS-Audio-Tokenizer-v2 \
  --text "欢迎来到声音实验室，这是一次本地 MOSS VoiceGenerator 合成。" \
  --instruction "低沉、沉稳、成熟的中文男声，像深夜电台主持一样自然叙述。" \
  --local-files-only \
  --output-dir /tmp/moss-voiceGenerator-output
```

默认音频采样参数为 `temperature=1.5`、`top-p=0.6`、`top-k=50`、重复惩罚 `1.1`。长文本或显存不足时增加 `--max-chars-per-chunk 120`；默认 `0` 表示整段合成。

## 检查与提示

```bash
conda activate moss-voiceGenerator
python -c "import torch, torchaudio, transformers, numpy, soundfile; print('torch=', torch.__version__, 'torchaudio=', torchaudio.__version__, 'transformers=', transformers.__version__, 'cuda=', torch.cuda.is_available())"
python -m pip check
```

`flash_attention_2` 不可用时回退到 `sdpa` 的提示不影响当前实测生成。离线运行时必须确认模型目录和 tokenizer 目录是完整的本地快照。
