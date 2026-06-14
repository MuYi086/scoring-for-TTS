"""
Use local Qwen3-TTS-12Hz-1.7B-Base to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Qwen3-TTS-12Hz-1.7B-Base_${t}_${k}khz.wav

Usage:
  python scripts/tts_local_qwen3_tts_12hz_1_7b_base.py

The Base model supports higher-quality cloning when a reference transcript is
provided. If --ref-text/--ref-text-file is omitted, this script falls back to
x-vector-only cloning from the reference audio.
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
MODEL_PATH = Path("/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base")
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
DEFAULT_REF_TEXT = "您好，很高兴能为您提供配音服务。选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Qwen3-TTS Base voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="Qwen3-TTS Base model path")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--ref-text", default=DEFAULT_REF_TEXT, help="Transcript of the reference audio")
    parser.add_argument("--ref-text-file", type=Path, default=None, help="File containing the reference audio transcript")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument(
        "--language",
        default="Chinese",
        help="Language passed to Qwen3-TTS. Use Auto for automatic language adaptation.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=120,
        help="Maximum text characters per synthesis chunk. 0 disables chunking.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=250,
        help="Silence inserted between synthesized chunks.",
    )
    parser.add_argument(
        "--x-vector-only",
        action="store_true",
        help="Use only speaker embedding from ref audio. Enabled automatically when no ref text is provided.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=2048, help="Maximum generated codec tokens per chunk")
    parser.add_argument("--top-p", type=float, default=None, help="Optional generation top_p")
    parser.add_argument("--temperature", type=float, default=None, help="Optional generation temperature")
    parser.add_argument(
        "--attn-implementation",
        choices=("auto", "flash_attention_2", "sdpa", "eager"),
        default="auto",
        help="Attention backend for model loading",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float32", "float16", "bfloat16"),
        default="auto",
        help="Torch dtype. auto uses bfloat16 on CUDA.",
    )
    parser.add_argument("--device-map", default="cuda:0", help="Device map passed to Qwen3TTSModel.from_pretrained")
    parser.add_argument("--local-files-only", action="store_true", help="Do not download model files")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    # Keep Markdown prose, but remove common heading markers that TTS may read awkwardly.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    return text


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


def import_runtime():
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as exc:
        raise RuntimeError(
            "Qwen3-TTS runtime is not importable. Install qwen-tts in an isolated conda "
            "environment, then run this script from that environment. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return Qwen3TTSModel, np, sf, torch


def resolve_device(torch) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for Qwen3-TTS synthesis.")
    return "cuda"


def resolve_dtype(torch, dtype: str, device: str):
    if dtype == "auto":
        return torch.bfloat16 if device == "cuda" else torch.float32
    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[dtype]


def resolve_attn_implementation(torch, requested: str, device: str, dtype) -> str:
    if requested != "auto":
        return requested
    if (
        device == "cuda"
        and importlib.util.find_spec("flash_attn") is not None
        and dtype in {torch.float16, torch.bfloat16}
    ):
        major, _minor = torch.cuda.get_device_capability()
        if major >= 8:
            return "flash_attention_2"
    if device == "cuda":
        return "sdpa"
    return "eager"


def read_ref_text(args: argparse.Namespace) -> str | None:
    if args.ref_text_file is not None:
        return read_text(require_path(args.ref_text_file, "reference text file"))
    if args.ref_text is not None and args.ref_text.strip():
        return args.ref_text.strip()
    return None


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def to_mono_float32(waveform, np):
    audio = np.asarray(waveform, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio


def join_waveforms(waveforms: list, sample_rate: int, pause_ms: int, np):
    if not waveforms:
        raise RuntimeError("Qwen3-TTS returned no audio segments.")

    segments = [to_mono_float32(waveform, np) for waveform in waveforms]
    pause_samples = int(sample_rate * max(pause_ms, 0) / 1000)
    if pause_samples <= 0 or len(segments) == 1:
        return np.concatenate(segments)

    pause = np.zeros(pause_samples, dtype=np.float32)
    joined = []
    for index, segment in enumerate(segments):
        joined.append(segment)
        if index < len(segments) - 1:
            joined.append(pause)
    return np.concatenate(joined)


def build_generation_kwargs(args: argparse.Namespace) -> dict:
    kwargs = {"max_new_tokens": args.max_new_tokens}
    if args.top_p is not None:
        kwargs["top_p"] = args.top_p
    if args.temperature is not None:
        kwargs["temperature"] = args.temperature
    return kwargs


def synthesize(args: argparse.Namespace) -> Path:
    Qwen3TTSModel, np, sf, torch = import_runtime()

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    text = read_text(text_file)
    chunks = split_text(text, args.max_chars_per_chunk)
    ref_text = read_ref_text(args)
    x_vector_only = args.x_vector_only or ref_text is None
    device = resolve_device(torch)
    dtype = resolve_dtype(torch, args.dtype, device)
    attn_implementation = resolve_attn_implementation(torch, args.attn_implementation, device, dtype)

    print(f"model: {model_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(f"{index + 1}/{len(chunks)}:{len(chunk)} chars" for index, chunk in enumerate(chunks))
    )
    print(f"reference audio: {ref_audio}")
    print(f"reference text: {'provided' if ref_text else 'not provided; using x-vector-only mode'}")
    print(f"device: {device}")
    print(f"dtype: {dtype}")
    print(f"attn_implementation: {attn_implementation}")

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map=args.device_map,
        dtype=dtype,
        attn_implementation=attn_implementation,
        local_files_only=args.local_files_only,
    )
    voice_clone_prompt = model.create_voice_clone_prompt(
        ref_audio=str(ref_audio),
        ref_text=ref_text,
        x_vector_only_mode=x_vector_only,
    )

    generation_kwargs = build_generation_kwargs(args)
    wavs, sample_rate = model.generate_voice_clone(
        text=chunks if len(chunks) > 1 else chunks[0],
        language=[args.language] * len(chunks) if len(chunks) > 1 else args.language,
        voice_clone_prompt=voice_clone_prompt,
        **generation_kwargs,
    )
    waveform = join_waveforms(wavs, int(sample_rate), args.pause_ms, np)
    elapsed = time.perf_counter() - started

    output_name = f"{model_path.name}_{elapsed_label(elapsed)}_{khz_from_sample_rate(int(sample_rate))}khz.wav"
    output_path = output_dir / output_name
    sf.write(str(output_path), waveform, int(sample_rate))

    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample rate: {int(sample_rate)} Hz ({khz_from_sample_rate(int(sample_rate))} kHz)")
    print(f"output: {output_path}")
    return output_path


def main() -> int:
    args = parse_args()
    try:
        synthesize(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
