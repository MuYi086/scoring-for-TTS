# Step-Audio-EditX 本地运行指南

本文对应 `modelScript/tts_local_Step_Audio_EditX.py`，用于参考音频零样本克隆和音频编辑。

## 路径与已验证配置

- Conda 环境：`Step-Audio-EditX`
- Python：3.12
- Step 模型：`~/hf-mirror/stepfun-ai/Step-Audio-EditX`
- tokenizer：`~/hf-mirror/stepfun-ai/Step-Audio-Tokenizer`
- 官方源码：`~/tts-depency/Step-Audio-EditX`
- 脚本：`/home/muyi086/github/scoring-for-TTS/modelScript/tts_local_Step_Audio_EditX.py`
- 当前核心版本：`torch 2.9.1+cu128`、`torchaudio 2.9.1+cu128`、`transformers 4.57.3`、`vllm 0.14.0rc2.dev125+gc826c72a9`
- `pip check`：通过；CUDA 可用
- 实测结果：参考音频克隆成功，生成 24 kHz、单声道 WAV

## 已配置环境检查

```bash
conda activate Step-Audio-EditX
python -c "import torch, torchaudio, transformers, vllm; print('torch=', torch.__version__, 'torchaudio=', torchaudio.__version__, 'transformers=', transformers.__version__, 'vllm=', vllm.__version__, 'cuda=', torch.cuda.is_available())"
python -m pip check
```

不要在这个环境中执行未锁版本的 `uv sync`、`deepspeed`、`llmcompressor`、`trl` 或其他训练/量化扩展安装命令；它们可能升级 Torch、Transformers 或 vLLM，破坏二进制匹配。

## 从零重建环境（仅在环境损坏时执行）

```bash
conda deactivate
conda env remove -n Step-Audio-EditX -y
conda create -n Step-Audio-EditX python=3.12 -y
conda activate Step-Audio-EditX

python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "torch==2.9.1" "torchaudio==2.9.1" "torchvision==0.24.1" \
  "triton==3.5.1" "numpy==2.2.6" "protobuf==5.29.3" \
  "transformers==4.57.3" "accelerate==1.10.1" "torchcodec==0.9.1"

python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "compressed-tensors==0.13.0" \
  "https://wheels.vllm.ai/c826c72a9633454679871fcb81fbc31fe03fb150/vllm-0.14.0rc2.dev125%2Bgc826c72a9-cp38-abi3-manylinux_2_31_x86_64.whl"

python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple --prefer-binary \
  "ffmpeg-python==0.2.0" "funasr>=1.3.0" "hdbscan>=0.8.41" \
  "hyperpyyaml>=1.2.3" "librosa>=0.11.0" "onnxruntime-gpu>=1.23.2" \
  "openai-whisper>=20250625" "pytorch-memlab>=0.3.0" \
  "rotary-embedding-torch>=0.8.9" "sox>=1.5.0" "torch-complex>=0.4.4" \
  soundfile scipy einops sentencepiece
```

清华源不可用时，将 PyPI 命令的 `--index-url` 替换为 `https://pypi.mirrors.ustc.edu.cn/simple` 或 `https://mirrors.aliyun.com/pypi/simple`。vLLM wheel 仍从其 URL 获取，不要改成源码构建。

## 参考音频克隆

```bash
conda activate Step-Audio-EditX
python /home/muyi086/github/scoring-for-TTS/modelScript/tts_local_Step_Audio_EditX.py \
  --code-path ~/tts-depency/Step-Audio-EditX \
  --model-path ~/hf-mirror/stepfun-ai/Step-Audio-EditX \
  --tokenizer-path ~/hf-mirror/stepfun-ai/Step-Audio-Tokenizer \
  --prompt-audio ~/tts-depency/Step-Audio-EditX/assets/test.wav \
  --prompt-text "这是一条测试音频，尝试各种功能是否正常运行。" \
  --generated-text "这是要生成的新文本。" \
  --output /tmp/Step-Audio-EditX-clone.wav \
  --gpu-memory-utilization 0.45 \
  --max-model-len 2048
```

正式使用时，`--prompt-text` 必须是参考音频的准确逐字稿，`--prompt-audio` 与 `--prompt-text` 必须对应同一段语音。默认 `--edit-type clone`；编辑任务可改为 `emotion`、`style`、`vad`、`denoise`、`paralinguistic` 或 `speed`，并配合 `--edit-info`。

## 已知的非阻断提示

- ONNXRuntime 可能提示 CUDA provider 缺少 `libcublasLt.so.13`，随后回退 CPU provider；本次生成仍成功。若希望消除提示，需要匹配的 ONNX/CUDA 运行库，不要因此重装整个 Torch/vLLM 栈。
- `VLLM_ATTENTION_BACKEND` 弃用提示、WSL `pin_memory` 提示和 NCCL 进程组销毁提示均不影响当前单卡短音频生成。
- 显存不足时先把 `--max-model-len` 降为 `1536` 或 `1024`，再把 `--gpu-memory-utilization` 调低；保持 `--max-num-seqs 1`。
