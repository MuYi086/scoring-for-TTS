# Qwen3-TTS VoiceDesign 本地运行指南

本文对应 `modelScript/tts_local_qwen3_voiceDesign.py`，用于通过文字描述设计音色并合成语音；不需要参考音频。

## 已验证配置

- Conda 环境：`qwen3-voiceDesign`
- Python：3.12
- 模型：`~/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- 脚本：`/home/muyi086/github/scoring-for-TTS/modelScript/tts_local_qwen3_voiceDesign.py`
- 当前环境：`torch 2.12.0`、`transformers 4.57.3`、`qwen-tts 0.1.1`
- `pip check`：通过
- 实测输出：24 kHz、单声道 WAV

## 已配置环境的快速检查

```bash
conda activate qwen3-voiceDesign
python -c "import torch, transformers; from qwen_tts import Qwen3TTSModel; print('torch=', torch.__version__, 'transformers=', transformers.__version__, 'cuda=', torch.cuda.is_available())"
python -m pip check
```

如果只是使用现有环境，不要重复执行安装命令。需要重建环境时，使用清华源安装最小运行依赖：

```bash
conda create -n qwen3-voiceDesign python=3.12 -y
conda activate qwen3-voiceDesign
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "qwen-tts==0.1.1" "transformers==4.57.3" soundfile
```

清华源不可用时，可将 `--index-url` 替换为 `https://pypi.mirrors.ustc.edu.cn/simple` 或 `https://mirrors.aliyun.com/pypi/simple`。

## 音色设计合成

建议使用绝对脚本路径和 `--local-files-only`，这样不会因为当前终端目录或网络状态改变结果：

```bash
conda activate qwen3-voiceDesign
python /home/muyi086/github/scoring-for-TTS/modelScript/tts_local_qwen3_voiceDesign.py \
  --model-path ~/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
  --text "欢迎来到声音实验室，这是一次本地 Qwen3-TTS VoiceDesign 合成。" \
  --instruct "清晰、自然、沉稳的中文男声，像纪录片旁白一样平稳。" \
  --local-files-only \
  --output-dir /tmp/qwen3-voiceDesign-output
```

长文本可增加 `--max-chars-per-chunk 120` 分块合成；默认 `0` 表示整段合成，通常更有利于保持音色一致。支持 `--language Chinese|English|Auto`、`--dtype auto|float16|bfloat16|float32` 和 `--attn-implementation auto|flash_attention_2|sdpa|eager`。

## 常见提示

- `flash_attention_2` 未安装时，脚本会回退到 `sdpa`，不影响当前推理。
- `sox` 缺失只会产生可选音频工具提示，不是本脚本当前合成路径的硬依赖。
- 离线加载失败时，确认模型目录包含 `config.json`、权重、tokenizer 和 `speech_tokenizer/`，并确认没有把模型目录写成压缩包路径。
