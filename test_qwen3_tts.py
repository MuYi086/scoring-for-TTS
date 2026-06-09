#!/usr/bin/env python3
"""Qwen3-TTS 验证脚本：加载 Base 模型并进行 voice clone 推理测试"""

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel
import os

# 检查 CUDA
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")

# 路径配置
MODEL_DIR = "/persistent/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base"
SAMPLE_WAV = "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav"
OUTPUT_DIR = "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"

# 参考文本 (从 sample.wav 转录)
REF_TEXT = "您好，很高兴能为您提供配音服务，选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"

print("\n=== 开始加载 Qwen3-TTS 模型 ===")
model = Qwen3TTSModel.from_pretrained(
    MODEL_DIR,
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation="sdpa",
)
print("✅ 模型加载成功!")

# 验证 voice clone 推理
print("\n=== 测试 voice clone 推理 ===")
tts_text = "尊敬的各位听众朋友，大家好。欢迎收听今天的节目。"

try:
    wavs, sr = model.generate_voice_clone(
        text=tts_text,
        language="Chinese",
        ref_audio=SAMPLE_WAV,
        ref_text=REF_TEXT,
    )
    output_path = os.path.join(OUTPUT_DIR, "test_qwen3_tts.wav")
    sf.write(output_path, wavs[0], sr)
    print(f"✅ 推理成功! 输出: {output_path}")
    print(f"   音频长度: {len(wavs[0]) / sr:.2f}s")
    print(f"   采样率: {sr}Hz")
    print(f"   音频 range: [{wavs[0].min():.4f}, {wavs[0].max():.4f}]")
    print("\n🎉 Qwen3-TTS 验证全部通过!")
except Exception as e:
    print(f"❌ 推理失败: {e}")
    import traceback
    traceback.print_exc()
