# TTS 引擎问题分析报告

## 一、环境信息

| 项目 | 详情 |
|------|------|
| 操作系统 | Deepin 23 (Linux 6.6.138-amd64-desktop-hwe) |
| GPU | RTX 4070 Ti SUPER, 16GB VRAM |
| CUDA | 13.0 (Driver 580.119.02) |
| Python | 3.12.3 (anaconda py312_env) |
| PyTorch | 2.12.0+cu130 |
| transformers | 4.57.3 |
| flash-attn | **未安装** |

---

## 二、各引擎问题分析

### 1. CosyVoice3 - "叽里咕噜都不是中文"

**根本原因：安装了错误的 cosyvoice 包**

当前 pip 安装的是 `cosyvoice 0.0.8`，来自第三方 fork `lucasjinreal/CosyVoice`，而非官方 `FunAudioLLM/CosyVoice`。

**问题表现：**
- pip 包只包含 4 个 Python 文件，缺少 CosyVoice3 所需的所有核心模块
- 架构完全不匹配：v1 的 LLM 无法正确加载 v3 的权重
- 输出的 speech token 是乱码，转换成音频就是"叽里咕噜"

**其他问题：**
- 采样率不匹配：模型输出 24000Hz，但 pip 包硬编码保存为 22050Hz
- CosyVoice3 要求 `prompt_text` 中必须包含 `<|endofprompt|>` 特殊 token

**解决方案：**
```bash
# 1. 卸载错误的包
pip uninstall cosyvoice

# 2. 克隆官方仓库
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice && git submodule update --init --recursive

# 3. 安装依赖
pip install -r requirements.txt
export PYTHONPATH=$PWD/third_party/Matcha-TTS:$PYTHONPATH
```

---

### 2. Qwen3-TTS - "音频完全没有声音"

**根本原因：Base 模型需要参考音频**

`Qwen3-TTS-12Hz-1.7B-Base` 是一个 **voice clone** 模型，必须提供参考音频 (ref_audio) 和参考文本 (ref_text) 才能正常工作。

**可能的问题：**
1. **缺少 ref_audio**: 没有提供参考音频，模型退化到无 speaker conditioning 状态
2. **调用方法错误**: Base 模型必须用 `generate_voice_clone()`，不能用 `generate_custom_voice()`
3. **bf16 精度问题**: 在某些硬件下 bfloat16 可能导致数值异常
4. **codec tokens 全是 pad/eos**: prompt 构建错误导致生成无效 token

**诊断步骤：**
```python
# 1. 检查生成的 codec codes
print("codes shape:", talker_codes.shape)
print("unique codes:", torch.unique(talker_codes))

# 2. 检查输出波形统计
print(f"max abs: {abs(wavs[0]).max()}, mean: {wavs[0].mean()}")
# 如果 max_abs < 0.001，说明是静音输出

# 3. 尝试 float32 替代 bf16
model = Qwen3TTSModel.from_pretrained(
    "...", device_map="cuda:0", dtype=torch.float32,
    attn_implementation="sdpa",
)
```

**解决方案：**
- 确保提供 24kHz 的参考音频
- 使用 `generate_voice_clone()` 方法
- 检查 `prompt_text` 是否正确

---

### 3. MOSS-TTS - "完全跑不起来"

**根本原因：transformers 版本不兼容**

模型代码使用了 transformers 5.0+ 的特性，但当前安装的是 4.57.3。

**阻断性问题：**
1. `from transformers import initialization as init` - 该模块在 5.0+ 才存在
2. `processing_utils.MODALITY_TO_BASE_CLASS_MAPPING` - 该属性在 5.0+ 才存在

**显存问题：**
- 模型 8.5B 参数 (bfloat16)，仅权重需要 ~16 GB
- 加上音频 tokenizer (~8 GB)，总需求远超 16 GB
- **RTX 4070 Ti SUPER 的 16 GB 显存严重不足**

**解决方案：**
```bash
# 1. 升级 transformers（需要 5.0+）
pip install transformers>=5.0.0

# 2. 安装 flash-attn（可选但推荐）
pip install flash-attn

# 3. 考虑使用较小的模型
# MossTTSLocal-1.7B 版本可能更适合 16GB 显存
```

---

## 三、系统环境影响分析

### Deepin vs Ubuntu vs Windows

| 因素 | Deepin 23 | Ubuntu 24.04/26.04 | Windows 11 |
|------|-----------|-------------------|------------|
| CUDA 驱动支持 | ✅ 完全支持 | ✅ 完全支持 | ✅ 完全支持 |
| PyTorch 兼容性 | ✅ 无差异 | ✅ 无差异 | ✅ 无差异 |
| flash-attn 编译 | ⚠️ 可能需要手动编译 | ✅ 通常更顺利 | ❌ 需要 WSL2 或原生 Linux |
| 内核影响 | ❌ 无影响 | ❌ 无影响 | ❌ 无影响 |

**结论：Deepin 系统本身不是问题根源**

- PyTorch/CUDA 推理在用户空间进行，与发行版无关
- 关键限制是 flash-attn 的编译，这在所有 Linux 发版上都可能遇到
- Windows 原生不支持 CUDA/Linux 工具链，建议使用 WSL2

### 推荐方案

**最佳选择：保持 Deepin + 修复配置**
1. 升级 transformers 到 5.0+（解决 MOSS-TTS）
2. 安装官方 CosyVoice 代码（解决 CosyVoice3）
3. 正确使用 Qwen3-TTS 的 voice clone 功能

**次选：Ubuntu 24.04/26.04**
- 如果需要更稳定的开发环境
- flash-attn 编译可能更顺利
- 但核心问题（代码配置）仍然需要手动修复

**不推荐：Windows 11**
- 原生不支持 CUDA/Linux 工具链
- 需要 WSL2，增加了复杂度
- 性能可能有损失

---

## 四、总结

| 引擎 | 问题 | 修复难度 | 推荐操作 |
|------|------|----------|----------|
| CosyVoice3 | 安装了错误的包 | ⭐⭐ 中等 | 克隆官方仓库 |
| Qwen3-TTS | 使用方式错误 | ⭐ 简单 | 提供 ref_audio |
| MOSS-TTS | 版本不兼容 + 显存不足 | ⭐⭐⭐ 困难 | 升级 transformers + 考虑小模型 |

**建议优先级：**
1. 先修复 CosyVoice3（最容易，效果最明显）
2. 调试 Qwen3-TTS（需要提供参考音频）
3. 评估是否真的需要 MOSS-TTS（显存限制是硬伤）
