# Ming-omni-tts-0.5B 本地运行指南

本文对应 `modelScript/tts_local_Ming_omni_tts.py`，支持文字音色设计、参考音频零样本克隆和文本转语音。

## 路径与已验证配置

- Conda 环境：`Ming-omni-tts-0.5B`
- Python：3.12
- 模型：`~/hf-mirror/inclusionAI/Ming-omni-tts-0.5B`
- 官方源码：`~/tts-depency/Ming-omni-tts`
- 脚本：`/home/muyi086/github/scoring-for-TTS/modelScript/tts_local_Ming_omni_tts.py`
- 当前核心版本：`torch 2.6.0`、`torchaudio 2.6.0`、`transformers 4.52.4`、`flash-attn 2.7.4.post1`
- `pip check`：通过；CUDA 可用
- 实测结果：已能生成 44.1 kHz、单声道 WAV

## 已配置环境检查

```bash
conda activate Ming-omni-tts-0.5B
python -c "import torch, transformers, flash_attn; print('torch=', torch.__version__, 'transformers=', transformers.__version__, 'flash_attn=', flash_attn.__file__, 'cuda=', torch.cuda.is_available())"
python -m pip check
```

不要在当前环境中执行不带版本约束的 Torch、Transformers 或 FlashAttention 升级命令。`grouped_gemm` 和 `decord` 不是当前 0.5B 本地推理脚本的必需依赖。

## 从零重建环境（仅在环境损坏时执行）

```bash
conda create -n Ming-omni-tts-0.5B python=3.12 -y
conda activate Ming-omni-tts-0.5B
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "torch==2.6.0" "torchaudio==2.6.0" "torchvision==0.21.0" \
  "tokenizers==0.21.4" "transformers==4.52.4" "accelerate==1.3.0" \
  "soundfile==0.12.1"
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "peft==0.17.1" "diffusers==0.33.0" "hyperpyyaml==1.2.2" \
  "x_transformers==2.9.2" "torchdiffeq" "torchtune==0.6.1" \
  "torchao==0.13.0" ipynbname "jiwer==3.1.0" rich loguru PyYAML \
  onnxruntime inflect pypinyin packaging psutil ninja
MAX_JOBS=4 python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --no-build-isolation "flash-attn==2.7.4.post1"
```

清华源不可用时，将 PyPI 命令的 `--index-url` 替换为 `https://pypi.mirrors.ustc.edu.cn/simple` 或 `https://mirrors.aliyun.com/pypi/simple`。编译 FlashAttention 前确认 `nvcc --version` 与 PyTorch CUDA 版本匹配。

## 文字音色设计

```bash
conda activate Ming-omni-tts-0.5B
python /home/muyi086/github/scoring-for-TTS/modelScript/tts_local_Ming_omni_tts.py \
  --code-path ~/tts-depency/Ming-omni-tts \
  --model-path ~/hf-mirror/inclusionAI/Ming-omni-tts-0.5B \
  --text "欢迎来到声音实验室，这是一次本地 Ming-omni-tts 合成。" \
  --style "温柔、清晰、成熟的中文女声，语速舒缓。" \
  --local-files-only \
  --output /tmp/Ming-omni-tts-0.5B-design.wav
```

## 参考音频零样本克隆

```bash
conda activate Ming-omni-tts-0.5B
python /home/muyi086/github/scoring-for-TTS/modelScript/tts_local_Ming_omni_tts.py \
  --code-path ~/tts-depency/Ming-omni-tts \
  --model-path ~/hf-mirror/inclusionAI/Ming-omni-tts-0.5B \
  --ref-audio /path/to/reference.wav \
  --ref-text "这里填写参考音频的准确逐字稿" \
  --text "这是需要使用参考音色生成的新文本。" \
  --local-files-only \
  --output /tmp/Ming-omni-tts-0.5B-clone.wav
```

也可以用 `--text-file` 读取长文本；`--style`、`--emotion`、`--dialect`、`--speed`、`--pitch`、`--volume` 可用于控制生成属性。

## 常见提示

- 首次导入可能出现模型类型映射或 `GenerationMixin` 警告；本次实测不影响加载和生成。
- 离线运行必须保留 `--local-files-only`，并确认模型目录是完整快照。
- 如果 `flash_attn` 导入失败，先检查当前环境的 Torch、CUDA、Python 版本，再重新编译匹配版本，不要直接安装最新 wheel。
