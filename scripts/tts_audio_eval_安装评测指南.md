# TTS 音频完整评测环境安装与运行指南

## 目标

本指南记录 `task4.md` 对应的完整评测环境搭建和运行过程。评测环境独立命名为 `audio_eval`，用于生成 `模型合成音频完整评测.md`，覆盖内容准确率、神经 MOS（平均意见分）预测和说话人相似度指标。

## 评测范围

输入目录：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/
```

参与评测的合成音频：

```text
dots.tts-base_232.67s_48khz.wav
MOSS-TTS-Local-Transformer_178.47s_24khz.wav
Qwen3-TTS-12Hz-1.7B-Base_40.75s_24khz.wav
VoxCPM2_72.45s_48khz.wav
```

参考音频：

```text
sample.wav
```

合成文本：

```text
第一章.md
```

## 环境创建

```bash
conda create -n audio_eval python=3.10 -y
conda install -n audio_eval -c conda-forge ffmpeg sox -y
conda install -n audio_eval -c conda-forge libgomp -y
```

`libgomp` 用于修复 SoX 启动时报 `libgomp.so.1` 缺失的问题。

## Python 依赖

```bash
conda run -n audio_eval python -m pip install --upgrade \
  pip setuptools wheel \
  numpy scipy pandas soundfile librosa jiwer editdistance tqdm pyyaml \
  onnxruntime speechbrain transformers accelerate datasets huggingface_hub \
  funasr matplotlib
```

其中：

- `funasr`：调用 SenseVoiceSmall 做中文 ASR（自动语音识别）。
- `speechbrain`：调用 ECAPA-TDNN 做说话人相似度。
- `onnxruntime`：运行 DNSMOS 的 ONNX 权重。
- `librosa`、`soundfile`：音频读取、重采样和分段。
- `matplotlib`：NISQA 脚本的隐式依赖。

## 下载的评测工具和模型

GitHub 工具仓库：

```bash
mkdir -p /home/muyi086/github/audio-eval-tools
git clone https://github.com/gabrielmittag/NISQA.git /home/muyi086/github/audio-eval-tools/NISQA
git clone https://github.com/microsoft/DNS-Challenge.git /home/muyi086/github/audio-eval-tools/DNS-Challenge
```

Hugging Face 模型：

```bash
mkdir -p /home/muyi086/hf-mirror/FunAudioLLM
mkdir -p /home/muyi086/hf-mirror/speechbrain

conda run -n audio_eval hf download FunAudioLLM/SenseVoiceSmall \
  --local-dir /home/muyi086/hf-mirror/FunAudioLLM/SenseVoiceSmall

conda run -n audio_eval hf download speechbrain/spkrec-ecapa-voxceleb \
  --local-dir /home/muyi086/hf-mirror/speechbrain/spkrec-ecapa-voxceleb
```

实际使用的本地路径：

```text
/home/muyi086/hf-mirror/FunAudioLLM/SenseVoiceSmall
/home/muyi086/hf-mirror/speechbrain/spkrec-ecapa-voxceleb
/home/muyi086/github/audio-eval-tools/NISQA
/home/muyi086/github/audio-eval-tools/DNS-Challenge/DNSMOS
```

## GPU 要求

完整评测脚本强制使用 GPU。脚本启动时会执行 CUDA 检查：

```python
torch.cuda.is_available()
torch.zeros(1, device="cuda")
```

如果 GPU 不可用，脚本会直接失败，不降级为 CPU。当前可用 GPU：

```text
NVIDIA GeForce RTX 4070 Ti SUPER
```

注意：普通沙箱命令可能看不到 CUDA 设备；实际运行使用已授权的：

```bash
conda run -n audio_eval python scripts/evaluate_tts_model_audio_full.py
```

## 评测脚本

新增脚本：

```text
scripts/evaluate_tts_model_audio_full.py
```

该脚本会执行：

- SenseVoiceSmall ASR 转写并计算 CER（字符错误率）。
- NISQA-TTS 自然度评分。
- NISQA v2 质量维度评分。
- DNSMOS OVRL/SIG/BAK/P808 评分。
- SpeechBrain ECAPA-TDNN 说话人 embedding（嵌入向量）相似度。
- 既有信号健康度指标。

NISQA 对长音频有窗口长度限制，脚本会先把每个模型音频切成 25 秒片段，再对片段得分取平均。

DNSMOS 官方脚本与当前 `librosa` 版本的 `resample` 调用不兼容，因此完整评测脚本直接复用其 ONNX 权重并用兼容新版 `librosa` 的本地实现计算。

## 复现命令

```bash
conda run -n audio_eval python scripts/evaluate_tts_model_audio_full.py
```

输出文件：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/模型合成音频完整评测.md
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/quality_scores.csv
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_transcripts/
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_diffs/
```

## 本次评测结果

完整评测排序：

| 排名 | 模型 | 总分 |
| ---: | --- | ---: |
| 1 | dots.tts-base | 77.5 |
| 2 | Qwen3-TTS-12Hz-1.7B-Base | 76.7 |
| 3 | MOSS-TTS-Local-Transformer | 73.2 |
| 4 | VoxCPM2 | 69.2 |

评分构成：

- 内容准确率：35 分，基于 SenseVoiceSmall CER。
- 神经质量：30 分，基于 NISQA-TTS、NISQA v2 和 DNSMOS。
- 说话人相似度：20 分，基于 SpeechBrain ECAPA cosine similarity（余弦相似度）。
- 信号健康度：15 分，沿用本地 WAV 客观指标。

人工盲听已经作为前置筛选完成，不参与本次局限补全评分。

## 验证命令

```bash
python -m compileall scripts/evaluate_tts_model_audio_full.py
conda run -n audio_eval ffmpeg -version
conda run -n audio_eval sox --version
conda run -n audio_eval python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

本次实际验证：

- `compileall` 通过。
- FFmpeg 可运行。
- SoX 可运行。
- 使用非沙箱 GPU 权限时，`audio_eval` 可见 CUDA，并能分配 CUDA tensor。
