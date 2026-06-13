# Fun-CosyVoice3-0.5B-2512 本地 TTS 环境安装指南

本文记录 `scripts/tts_local_cosyvoice3.py` 运行 `Fun-CosyVoice3-0.5B-2512` 所需的软件、安装过程和本机实测问题处理。

## 目标

- 模型路径：`/home/muyi086/hf-mirror/FunAudioLLM/Fun-CosyVoice3-0.5B-2512`
- 官方代码路径：`/home/muyi086/github/CosyVoice`
- conda 环境名：`cosyvoice`
- Python 版本：`3.10`
- 运行脚本：`scripts/tts_local_cosyvoice3.py`

## 1. 接受 Anaconda channel TOS

如果 `conda create` 报 `CondaToSNonInteractiveError`，先执行：

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

## 2. 创建 conda 环境

```bash
conda create -n cosyvoice -y python=3.10
conda activate cosyvoice
```

验证：

```bash
python --version
```

期望为 `Python 3.10.x`。

## 3. 克隆官方 CosyVoice 仓库

```bash
cd ~/github
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /home/muyi086/github/CosyVoice
```

确认 Matcha-TTS 子模块存在：

```bash
ls /home/muyi086/github/CosyVoice/third_party/Matcha-TTS
```

## 4. 安装基础构建工具

`pyworld` 需要 C++ 编译器。如果安装依赖时报 `error: command 'g++' failed: No such file or directory`，执行：

```bash
conda install -n cosyvoice -y gxx_linux-64
```

## 5. 安装 Python 依赖

先安装兼容版 `setuptools`，避免 `openai-whisper` 构建时报 `No module named 'pkg_resources'`：

```bash
conda run -n cosyvoice pip install 'setuptools<70' wheel
```

单独安装 `openai-whisper`，并关闭 build isolation：

```bash
conda run -n cosyvoice pip install --no-build-isolation openai-whisper==20231117
```

安装 CosyVoice3 本地推理所需核心依赖：

```bash
conda run -n cosyvoice pip install \
  conformer==0.3.2 \
  diffusers==0.29.0 \
  gdown==5.1.0 \
  grpcio==1.57.0 \
  grpcio-tools==1.57.0 \
  hydra-core==1.3.2 \
  HyperPyYAML==1.2.3 \
  inflect==7.3.1 \
  librosa==0.10.2 \
  lightning==2.2.4 \
  matplotlib==3.7.5 \
  modelscope==1.20.0 \
  networkx==3.1 \
  numpy==1.26.4 \
  omegaconf==2.3.0 \
  onnx==1.16.0 \
  onnxruntime-gpu==1.18.0 \
  protobuf==4.25 \
  pyarrow==18.1.0 \
  pydantic==2.7.0 \
  pyworld==0.3.4 \
  rich==13.7.1 \
  soundfile==0.12.1 \
  torchaudio==2.3.1 \
  transformers==4.51.3 \
  x-transformers==2.11.24 \
  wetext==0.0.4 \
  wget==3.2
```

说明：官方 `requirements.txt` 还包含 `deepspeed`、`tensorrt-cu12`、`fastapi`、`gradio` 等服务端或训练相关依赖。当前脚本只做本地 CosyVoice3 推理，上面的核心依赖已经足够跑通。

## 6. 验证环境导入

```bash
conda run -n cosyvoice python -c "import sys; sys.path[:0]=['/home/muyi086/github/CosyVoice/third_party/Matcha-TTS','/home/muyi086/github/CosyVoice']; import torch, torchaudio; from cosyvoice.cli.cosyvoice import AutoModel; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('torchaudio', torchaudio.__version__); print('AutoModel import ok')"
```

本机实测输出包括：

```text
torch 2.3.1+cu121 cuda True
torchaudio 2.3.1+cu121
AutoModel import ok
```

## 7. 验证模型初始化

```bash
conda run -n cosyvoice python -c "import sys; sys.path[:0]=['/home/muyi086/github/CosyVoice/third_party/Matcha-TTS','/home/muyi086/github/CosyVoice']; from cosyvoice.cli.cosyvoice import AutoModel; m=AutoModel(model_dir='/home/muyi086/hf-mirror/FunAudioLLM/Fun-CosyVoice3-0.5B-2512'); print('model sample_rate', m.sample_rate)"
```

本机实测成功输出：

```text
model sample_rate 24000
```

首次初始化会通过 `modelscope` 下载 `pengzhendong/wetext` 前端资源到：

```text
/home/muyi086/.cache/modelscope/hub/pengzhendong/wetext
```

## 8. 运行合成脚本

```bash
conda activate cosyvoice
cd ~/github/timbre-design
python scripts/tts_local_cosyvoice3.py --cosyvoice-repo ~/github/CosyVoice
```

脚本默认会按标点把长文本切成多个片段逐段合成，再拼接为一个 WAV。可通过下面两个参数调整：

```bash
python scripts/tts_local_cosyvoice3.py \
  --cosyvoice-repo ~/github/CosyVoice \
  --max-chars-per-chunk 80 \
  --pause-ms 300
```

说明：

- `--max-chars-per-chunk 80` 是当前样例对应的默认分块长度，能避免长文本单块输入导致漏读。
- `--pause-ms 300` 是当前样例对应的默认段间静音长度。

本机实测生成：

```text
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Fun-CosyVoice3-0.5B-2512_58.31s_24khz.wav
```

音频元数据：

```text
sample_rate: 24000 Hz
duration: 87.98s
channels: 1
format: WAV
size: 8.1M
```

## 9. 常见问题

### Missing import: torch

说明当前 Python 环境没有安装 `torch`，或没有使用 `cosyvoice` conda 环境。

处理：

```bash
conda activate cosyvoice
python -c "import torch; print(torch.__version__)"
```

### `/path/to/CosyVoice` 不是有效路径

`/path/to/CosyVoice` 只是示例占位。实际运行应使用：

```bash
python scripts/tts_local_cosyvoice3.py --cosyvoice-repo ~/github/CosyVoice
```

### `No module named 'pkg_resources'`

`openai-whisper` 构建隔离环境缺少兼容的 setuptools。处理：

```bash
conda run -n cosyvoice pip install 'setuptools<70' wheel
conda run -n cosyvoice pip install --no-build-isolation openai-whisper==20231117
```

### `g++ failed: No such file or directory`

`pyworld` 编译需要 C++ 编译器。处理：

```bash
conda install -n cosyvoice -y gxx_linux-64
```

### `No module named 'matplotlib'`

Matcha-TTS 的导入链需要 `matplotlib`。处理：

```bash
conda run -n cosyvoice pip install matplotlib==3.7.5
```

### ONNX Runtime CUDA provider 警告

运行时可能出现：

```text
Failed to create CUDAExecutionProvider
libcublasLt.so.11: cannot open shared object file
```

本机实测该警告不会阻止合成，ONNX Runtime 会回退到可用 provider，最终仍成功生成 wav。

### 合成音频内容不完整

现象：

- `第一章.md` 明明包含完整文本，但生成音频只读到前面一部分。
- 本机旧产物 `Fun-CosyVoice3-0.5B-2512_30.22s_24khz.wav` 只读到“他熟练地撒上黑胡椒，关火，出锅，动作精确得像在做手术。”，后面的“三明治”“妹妹沈鸢”等内容缺失。
- 日志里能看到完整输入文本，容易误判为模型已经处理了全文。

原因：

- 旧版 `tts_local_cosyvoice3.py` 在 cross-lingual 模式下会把 `You are a helpful assistant.<|endofprompt|>` 和整章正文拼成一个长字符串。
- CosyVoice 前端 `text_normalize()` 检测到 `<|...|>` 特殊 token 后会关闭文本前端处理，直接返回 `[text]`，不会再走内置 `split_paragraph(... token_max_n=80 ...)` 分段逻辑。
- 结果是 400 字以上文本被当成单段请求交给 LLM speech token 生成。长段生成时模型可能提前输出 EOS 或达到内部稳定性边界，最终音频提前结束。

第一版修复：

- 脚本侧先按中文标点分块，再逐块调用 CosyVoice3 推理，最后拼接音频。
- 第一版修复曾使用 `--max-chars-per-chunk 180`，音频时长从 `46.68s` 增加到 `80.8s`，但第 2 段末尾仍漏了“妹妹沈鸢走了出来。沈行看向了妹妹的方向。”。
- 说明 `180` 字分块仍然偏长：缺失句处在第 2 段尾部，模型仍可能在单块尾端提前结束。
- 默认分块参数改为 `--max-chars-per-chunk 80` 后，漏读句成为独立短块，降低了尾部漏读概率。
- 当前样例会被拆成 8 段，其中第 6 段是“大概十多分钟后，次卧的门开了，妹妹沈鸢走了出来。沈行看向了妹妹的方向。”，缺失句成为独立短块，降低尾部漏读概率。

### 当前版本的已知问题：拼接处不自然

现象：

- 合成音频一会儿慢、一会儿快。
- 变化常出现在句号后。
- 句号后的衔接不够顺畅，并且和前一句的说话声相似度差一些。

原因：

- 当前脚本使用独立分块思路：每个文本块都单独调用一次 CosyVoice 推理，再手工拼接音频。
- 这种方式能降低长文本漏读，但每个块都会重新启动一轮声学生成。句号通常也是分块边界，所以模型容易在边界后重新采样出略有差异的语速、停顿和音色。
- 手工插入的 `--pause-ms` 静音只能控制间隔长度，不能保证下一段的韵律和上一段连续。

当前回退版本：

- 已回退到 `Fun-CosyVoice3-0.5B-2512_58.31s_24khz.wav` 对应的脚本行为。
- 该版本的优势是整体音色和内容完整性优于后续连续会话尝试。
- 该版本仍保留拼接处不自然的问题，后续优化应在这个版本基础上只处理拼接和语速一致性。

运行：

```bash
python scripts/tts_local_cosyvoice3.py \
  --cosyvoice-repo ~/github/CosyVoice \
  --max-chars-per-chunk 80 \
  --pause-ms 300
```

验证：

```bash
conda run -n cosyvoice python -c "import soundfile as sf; p='samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Fun-CosyVoice3-0.5B-2512_58.31s_24khz.wav'; info=sf.info(p); print(info.samplerate, round(info.duration, 2), info.channels)"
```

本机回退目标产物：

```text
Fun-CosyVoice3-0.5B-2512_58.31s_24khz.wav
sample_rate: 24000 Hz
duration: 87.98s
channels: 1
exact_zero_runs>=200ms: 7
```

对比旧产物和其他尝试产物：

```text
Fun-CosyVoice3-0.5B-2512_30.22s_24khz.wav
duration: 46.68s

Fun-CosyVoice3-0.5B-2512_50.55s_24khz.wav
duration: 80.8s

Fun-CosyVoice3-0.5B-2512_54.14s_24khz.wav
duration: 86.36s

Fun-CosyVoice3-0.5B-2512_58.31s_24khz.wav
duration: 87.98s
exact_zero_runs>=200ms: 7
```

## 10. 快速检查命令

```bash
conda env list
conda run -n cosyvoice python --version
conda run -n cosyvoice python -c "import torch, torchaudio, numpy, matplotlib; print(torch.__version__); print(torchaudio.__version__); print(numpy.__version__); print(matplotlib.__version__); print(torch.cuda.is_available())"
```
