#!/usr/bin/env python3
"""完整合成脚本：使用 CosyVoice3 和 Qwen3-TTS 合成第一章全文"""

import sys
import os
import torch
import torchaudio
import soundfile as sf
import time

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'CosyVoice'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'CosyVoice/third_party/Matcha-TTS'))

# === 配置 ===
OUTPUT_DIR = "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
SAMPLE_WAV = os.path.join(OUTPUT_DIR, "sample.wav")
TEXT_FILE = os.path.join(OUTPUT_DIR, "第一章.md")
COSYVOICE3_MODEL = "/persistent/home/muyi086/hf-mirror/Fun-CosyVoice3-0.5B-2512"
QWEN3_MODEL = "/persistent/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base"
QWEN3_OUTPUT = os.path.join(OUTPUT_DIR, "Qwen3-TTS_第一章.wav")
COSYVOICE3_OUTPUT = os.path.join(OUTPUT_DIR, "CosyVoice3_第一章.wav")

# sample.wav 的参考文本 (whisper 转录)
REF_TEXT = "您好，很高兴能为您提供配音服务，选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"

# CosyVoice3 的 prompt_text (需要 <|endofprompt|> 标记)
PROMPT_TEXT = "You are a helpful assistant.<|endofprompt|>希望您以后能够做得比我还好。"


def read_text(filepath):
    """读取第一章 md 文件，清理格式"""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    # 移除标题行（## 开头的和 # 开头的）
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳过空行和标题行（但保留纯段落）
        cleaned.append(line)
    return '\n'.join(cleaned)


def split_into_chunks(text, max_chars=500):
    """将文本按段落切分成适合 TTS 的块"""
    # 按空行分段落
    paragraphs = []
    current = []
    for line in text.split('\n'):
        if line.strip() == '':
            if current:
                paragraphs.append('\n'.join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append('\n'.join(current))

    # 合并小段落为 chunk，同时确保每个 chunk 不过大
    chunks = []
    current_chunk = []
    current_len = 0
    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [para]
            current_len = para_len
        else:
            current_chunk.append(para)
            current_len += para_len
    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    print(f"  文本已分割为 {len(chunks)} 个 chunk, 每个约 {max_chars} 字符")
    for i, chunk in enumerate(chunks):
        print(f"    Chunk {i+1}: {len(chunk)} 字符")
    return chunks


def concat_audio(audio_segments, sample_rate):
    """拼接多个音频片段"""
    if len(audio_segments) == 0:
        return None
    if len(audio_segments) == 1:
        return audio_segments[0]

    if isinstance(audio_segments[0], torch.Tensor):
        return torch.cat(audio_segments, dim=1)
    elif isinstance(audio_segments[0], (list, tuple)):
        import numpy as np
        return np.concatenate(audio_segments, axis=0)


# ============================================================
# Part 1: CosyVoice3 合成
# ============================================================
def synthesize_cosyvoice3():
    print("\n" + "="*60)
    print("📢 CosyVoice3 合成开始")
    print("="*60)

    from cosyvoice.cli.cosyvoice import CosyVoice3

    text = read_text(TEXT_FILE)
    print(f"📄 文本长度: {len(text)} 字符")

    print("⏳ 加载模型...")
    start = time.time()
    model = CosyVoice3(COSYVOICE3_MODEL)
    print(f"✅ 模型加载完成 ({time.time()-start:.1f}s)")

    print("⏳ 开始推理...")
    start = time.time()

    # inference_zero_shot 会自动分割文本为多段处理
    segments = []
    for i, result in enumerate(model.inference_zero_shot(
        tts_text=text,
        prompt_text=PROMPT_TEXT,
        prompt_wav=SAMPLE_WAV,
        stream=False
    )):
        speech = result['tts_speech']
        duration = speech.shape[1] / model.sample_rate
        segments.append(speech)
        print(f"  ✅ 分段 {i+1}: {duration:.1f}s (shape: {list(speech.shape)})")

    # 拼接
    if segments:
        combined = torch.cat(segments, dim=1)
        torchaudio.save(COSYVOICE3_OUTPUT, combined, model.sample_rate)
        total_duration = combined.shape[1] / model.sample_rate
        print(f"\n✅ CosyVoice3 合成完成!")
        print(f"   输出: {COSYVOICE3_OUTPUT}")
        print(f"   总时长: {total_duration:.1f}s ({total_duration/60:.1f} 分钟)")
        print(f"   推理用时: {time.time()-start:.1f}s")
    else:
        print("❌ 没有生成任何音频段")


# ============================================================
# Part 2: Qwen3-TTS 合成
# ============================================================
def synthesize_qwen3_tts():
    print("\n" + "="*60)
    print("📢 Qwen3-TTS 合成开始")
    print("="*60)

    from qwen_tts import Qwen3TTSModel

    text = read_text(TEXT_FILE)
    print(f"📄 文本长度: {len(text)} 字符")

    # 分割文本
    chunks = split_into_chunks(text, max_chars=400)

    print("⏳ 加载模型...")
    start = time.time()
    model = Qwen3TTSModel.from_pretrained(
        QWEN3_MODEL,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    print(f"✅ 模型加载完成 ({time.time()-start:.1f}s)")

    # 预先构建 voice clone prompt（复用参考音频特征）
    print("⏳ 提取说话人特征...")
    prompt_start = time.time()
    voice_clone_prompt = model.create_voice_clone_prompt(
        ref_audio=SAMPLE_WAV,
        ref_text=REF_TEXT,
    )
    print(f"✅ 特征提取完成 ({time.time()-prompt_start:.1f}s)")

    print("⏳ 开始推理...")
    total_start = time.time()
    all_segments = []

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        chunk_start = time.time()
        try:
            wavs, sr = model.generate_voice_clone(
                text=chunk,
                language="Chinese",
                voice_clone_prompt=voice_clone_prompt,
            )
            duration = len(wavs[0]) / sr
            all_segments.append(wavs[0])
            print(f"  ✅ Chunk {i+1}/{len(chunks)}: {duration:.1f}s ({time.time()-chunk_start:.1f}s)")
        except Exception as e:
            print(f"  ❌ Chunk {i+1} 失败: {e}")
            # 失败后重新构建 prompt 重试一次
            try:
                print(f"    重试中...")
                voice_clone_prompt = model.create_voice_clone_prompt(
                    ref_audio=SAMPLE_WAV,
                    ref_text=REF_TEXT,
                )
                wavs, sr = model.generate_voice_clone(
                    text=chunk,
                    language="Chinese",
                    voice_clone_prompt=voice_clone_prompt,
                )
                duration = len(wavs[0]) / sr
                all_segments.append(wavs[0])
                print(f"  ✅ Chunk {i+1} (重试成功): {duration:.1f}s")
            except Exception as e2:
                print(f"  ❌ Chunk {i+1} 重试也失败: {e2}")

    # 拼接
    if all_segments:
        import numpy as np
        combined = np.concatenate(all_segments, axis=0)
        sf.write(QWEN3_OUTPUT, combined, sr)
        total_duration = len(combined) / sr
        print(f"\n✅ Qwen3-TTS 合成完成!")
        print(f"   输出: {QWEN3_OUTPUT}")
        print(f"   总时长: {total_duration:.1f}s ({total_duration/60:.1f} 分钟)")
        print(f"   推理用时: {time.time()-total_start:.1f}s")
    else:
        print("❌ 没有生成任何音频段")


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    print("🚀 开始完整 TTS 合成流程")
    print(f"   输出目录: {OUTPUT_DIR}")
    print(f"   参考音频: {SAMPLE_WAV}")

    # 1. CosyVoice3
    try:
        synthesize_cosyvoice3()
    except Exception as e:
        print(f"❌ CosyVoice3 合成失败: {e}")
        import traceback
        traceback.print_exc()

    # 2. Qwen3-TTS
    # Qwen3-TTS 需要重新创建模型实例，但避免 OOM 先释放
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    try:
        synthesize_qwen3_tts()
    except Exception as e:
        print(f"❌ Qwen3-TTS 合成失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("🎉 全部合成任务完成!")
    print("="*60)
