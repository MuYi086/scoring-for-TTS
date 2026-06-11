"""
MiMo TTS v2.5 - 使用 voiceclone 模型合成音频
用法: python scripts/tts_mimo.py --api-key YOUR_KEY
"""
import argparse
import base64
import os
import sys

from openai import OpenAI


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def encode_audio(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg"}
    mime = mime_map.get(ext, "audio/wav")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def synthesize(
    api_key: str,
    text: str,
    ref_audio_path: str,
    output_path: str,
    user_instruction: str = "",
    model: str = "mimo-v2.5-tts-voiceclone",
):
    client = OpenAI(
        api_key="sk-c9d60a0qmbqcspsr45kdtvbioiddr6ohd87m0sa8y5d69w0i",
        base_url="https://api.xiaomimimo.com/v1",
    )

    voice_b64 = encode_audio(ref_audio_path)
    print(f"参考音频已编码: {len(voice_b64) // 1024}KB")

    messages = [
        {"role": "user", "content": user_instruction},
        {"role": "assistant", "content": text},
    ]

    print(f"模型: {model}")
    print(f"文本长度: {len(text)} 字符")
    print("正在合成，请稍候...")

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        audio={
            "format": "wav",
            "voice": voice_b64,
        },
    )

    message = completion.choices[0].message
    audio_bytes = base64.b64decode(message.audio.data)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    print(f"合成完成! 输出: {output_path} ({len(audio_bytes) // 1024}KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="MiMo TTS v2.5 Voice Clone")
    parser.add_argument("--api-key", required=True, help="MiMo API Key")
    parser.add_argument(
        "--model",
        default="mimo-v2.5-tts-voiceclone",
        choices=["mimo-v2.5-tts", "mimo-v2.5-tts-voiceclone"],
        help="模型选择 (default: mimo-v2.5-tts-voiceclone)",
    )
    parser.add_argument(
        "--text-file",
        default="samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md",
        help="要合成的文本文件路径",
    )
    parser.add_argument(
        "--ref-audio",
        default="samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav",
        help="参考音频文件路径",
    )
    parser.add_argument(
        "--output",
        default="samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.wav",
        help="输出音频文件路径",
    )
    parser.add_argument(
        "--instruction",
        default="",
        help="user message 中的风格指令 (voiceclone 模型可选)",
    )
    args = parser.parse_args()

    text = read_text(args.text_file)
    synthesize(
        api_key=args.api_key,
        text=text,
        ref_audio_path=args.ref_audio,
        output_path=args.output,
        user_instruction=args.instruction,
        model=args.model,
    )


if __name__ == "__main__":
    main()
