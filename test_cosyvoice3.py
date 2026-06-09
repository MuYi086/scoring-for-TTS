#!/usr/bin/env python3
"""CosyVoice3 验证脚本：加载模型并进行 zero-shot 推理测试"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'CosyVoice'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'CosyVoice/third_party/Matcha-TTS'))

import torch
import torchaudio

# 检查 CUDA
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
print(f"CUDA devices: {torch.cuda.device_count()}")

# 加载模型
from cosyvoice.cli.cosyvoice import CosyVoice3

MODEL_DIR = "/persistent/home/muyi086/hf-mirror/Fun-CosyVoice3-0.5B-2512"
SAMPLE_WAV = "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav"
OUTPUT_DIR = "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"

print("\n=== 开始加载 CosyVoice3 模型 ===")
cosyvoice = CosyVoice3(MODEL_DIR)
print("✅ 模型加载成功!")
print(f"   采样率: {cosyvoice.sample_rate}Hz")

# 验证 zero-shot 推理
print("\n=== 测试 zero-shot 推理 ===")
# prompt_text 需要包含 <|endofprompt|> 标记
prompt_text = "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。"
tts_text = "尊敬的各位听众朋友，大家好。欢迎收听今天的节目。"

for i, result in enumerate(cosyvoice.inference_zero_shot(
    tts_text=tts_text,
    prompt_text=prompt_text,
    prompt_wav=SAMPLE_WAV,
    stream=False
)):
    output_path = os.path.join(OUTPUT_DIR, f"test_cosyvoice3.wav")
    torchaudio.save(output_path, result['tts_speech'], cosyvoice.sample_rate)
    speech_len = result['tts_speech'].shape[1] / cosyvoice.sample_rate
    print(f"✅ 推理成功! 输出: {output_path}")
    print(f"   音频长度: {speech_len:.2f}s")
    print(f"   音频 shape: {result['tts_speech'].shape}")
    print(f"   音频范围: [{result['tts_speech'].min().item():.4f}, {result['tts_speech'].max().item():.4f}]")

print("\n🎉 CosyVoice3 验证全部通过!")
