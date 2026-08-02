"""使用本地 Qwen3-TTS VoiceDesign 模型按文字描述设计音色并合成语音。

默认输入：samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md
默认输出：samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Qwen3-TTS-12Hz-1.7B-VoiceDesign_${t}_${k}hz.wav
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "QWEN3_VOICEDESIGN_MODEL_PATH",
        "~/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    )
)
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Qwen3-TTS VoiceDesign synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE)
    parser.add_argument("--text", default=None, help="直接传入文本；传入后优先于 --text-file")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR)
    parser.add_argument("--language", default="Chinese", help="Chinese、English 或 Auto")
    parser.add_argument(
        "--instruct",
        default="低沉、沉稳、成熟的中文男声，像深夜电台主持一样自然、克制地叙述。",
        help="自然语言音色/情绪描述",
    )
    parser.add_argument("--max-chars-per-chunk", type=int, default=0, help="0 表示整段生成")
    parser.add_argument("--pause-ms", type=int, default=250)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--dtype", choices=("auto", "float16", "bfloat16", "float32"), default="auto")
    parser.add_argument("--attn-implementation", choices=("auto", "flash_attention_2", "sdpa", "eager"), default="auto")
    parser.add_argument("--device-map", default="cuda:0")
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label}不存在：{path}")
    return path


def read_text(path: Path, direct_text: str | None = None) -> str:
    if direct_text is not None and direct_text.strip():
        return direct_text.strip()
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def split_long_sentence(text: str, max_chars: int) -> list[str]:
    parts = re.findall(r".+?[，,、：:]|.+$", text, flags=re.S)
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(part[i : i + max_chars] for i in range(0, len(part), max_chars))
            continue
        candidate = current + part
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = part
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    sentences = re.findall(r".+?[。！？；;!?]|.+$", text, flags=re.S)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_sentence(sentence, max_chars))
            continue
        candidate = current + sentence
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def import_runtime():
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as exc:
        raise RuntimeError(f"Qwen3-TTS 运行时不可导入，缺失：{exc.name or exc}") from exc
    return Qwen3TTSModel, np, sf, torch


def resolve_dtype(torch, requested: str):
    if requested == "auto":
        return torch.bfloat16
    return {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}[requested]


def resolve_attention(torch, requested: str, dtype) -> str:
    if requested != "auto":
        return requested
    if importlib.util.find_spec("flash_attn") is not None and dtype in {torch.float16, torch.bfloat16}:
        major, _minor = torch.cuda.get_device_capability()
        if major >= 8:
            return "flash_attention_2"
    return "sdpa"


def join_waveforms(waveforms: list, sample_rate: int, pause_ms: int, np):
    if not waveforms:
        raise RuntimeError("Qwen3-TTS 未返回音频。")
    segments = []
    for waveform in waveforms:
        audio = np.asarray(waveform, dtype=np.float32)
        if audio.ndim == 2:
            audio = audio.mean(axis=0 if audio.shape[0] <= 2 else 1)
        segments.append(audio.reshape(-1))
    pause = np.zeros(int(sample_rate * max(pause_ms, 0) / 1000), dtype=np.float32)
    joined: list = []
    for index, segment in enumerate(segments):
        joined.append(segment)
        if index + 1 < len(segments) and len(pause):
            joined.append(pause)
    return np.concatenate(joined)


def synthesize(args: argparse.Namespace) -> Path:
    Qwen3TTSModel, np, sf, torch = import_runtime()
    model_path = require_path(args.model_path, "模型目录")
    text_file = None if args.text is not None and args.text.strip() else require_path(args.text_file, "文本文件")
    if not torch.cuda.is_available():
        raise RuntimeError("Qwen3-TTS VoiceDesign 需要 CUDA GPU。")
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    text_chunks = split_text(read_text(text_file, args.text), args.max_chars_per_chunk)
    dtype = resolve_dtype(torch, args.dtype)
    attention = resolve_attention(torch, args.attn_implementation, dtype)
    print(f"model: {model_path}")
    print(f"chunks: {len(text_chunks)}; language: {args.language}; attention: {attention}; dtype: {dtype}")
    started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map=args.device_map,
        dtype=dtype,
        attn_implementation=attention,
        local_files_only=args.local_files_only,
    )
    generation_kwargs = {"max_new_tokens": args.max_new_tokens}
    if args.top_p is not None:
        generation_kwargs["top_p"] = args.top_p
    if args.temperature is not None:
        generation_kwargs["temperature"] = args.temperature
    wavs, sample_rate = model.generate_voice_design(
        text=text_chunks if len(text_chunks) > 1 else text_chunks[0],
        instruct=[args.instruct] * len(text_chunks) if len(text_chunks) > 1 else args.instruct,
        language=[args.language] * len(text_chunks) if len(text_chunks) > 1 else args.language,
        non_streaming_mode=True,
        **generation_kwargs,
    )
    waveform = join_waveforms(wavs, int(sample_rate), args.pause_ms, np)
    elapsed = time.perf_counter() - started
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{model_path.name}_{elapsed:.2f}s_{int(sample_rate / 1000):g}khz.wav"
    sf.write(str(output_path), waveform, int(sample_rate))
    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample_rate: {sample_rate} Hz")
    print(f"output: {output_path}")
    return output_path


def main() -> int:
    try:
        synthesize(parse_args())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
