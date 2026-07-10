"""
Use local VoxCPM2 to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_${t}_${k}khz.wav

Usage:
  python modelScript/tts_local_voxcpm2.py --local-files-only
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.environ.get("VOXCPM2_MODEL_PATH", "/path/to/VoxCPM2"))
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local VoxCPM2 voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="VoxCPM2 model path")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument(
        "--style-prompt",
        default="低沉、沉稳、沉浸式，像电台主持一样自然叙述。",
        help="Optional style control text prepended in parentheses for each chunk.",
    )
    parser.add_argument(
        "--prompt-text",
        default=None,
        help="Exact transcript of the reference audio. Enables ultimate cloning when provided.",
    )
    parser.add_argument(
        "--prompt-text-file",
        type=Path,
        default=None,
        help="File containing the exact transcript of the reference audio.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=0,
        help="Maximum text characters per synthesis chunk. Default 0 disables chunking for voice consistency.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=250,
        help="Silence inserted between synthesized chunks.",
    )
    parser.add_argument("--cfg-value", type=float, default=2.0, help="Classifier-free guidance value")
    parser.add_argument("--inference-timesteps", type=int, default=10, help="Diffusion inference timesteps")
    parser.add_argument(
        "--load-denoiser",
        action="store_true",
        help="Load optional denoiser if supported by the installed voxcpm package.",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Enable VoxCPM torch.compile/Triton optimization. Requires a working C compiler.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Prefer offline local model loading and disable remote Hugging Face access.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260614,
        help="Random seed for reproducible sampling. Use -1 to disable explicit seeding.",
    )
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
        from voxcpm import VoxCPM
    except ImportError as exc:
        raise RuntimeError(
            "VoxCPM2 runtime is not importable. Install voxcpm in an isolated conda "
            "environment, then run this script from that environment. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return VoxCPM, np, sf, torch


def resolve_device(torch) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for VoxCPM2 synthesis.")
    return "cuda"


def read_prompt_text(args: argparse.Namespace) -> str | None:
    if args.prompt_text_file is not None:
        return read_text(require_path(args.prompt_text_file, "prompt text file"))
    if args.prompt_text is not None and args.prompt_text.strip():
        return args.prompt_text.strip()
    return None


def set_seed(seed: int, np, torch) -> None:
    if seed < 0:
        return
    import random

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def prepare_text(chunk: str, style_prompt: str) -> str:
    style_prompt = style_prompt.strip()
    if not style_prompt:
        return chunk
    return f"({style_prompt}){chunk}"


def from_pretrained_kwargs(VoxCPM, args: argparse.Namespace) -> dict:
    kwargs = {}
    signature = inspect.signature(VoxCPM.from_pretrained)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return {
            "load_denoiser": args.load_denoiser,
            "local_files_only": args.local_files_only,
            "optimize": args.optimize,
        }
    if "load_denoiser" in signature.parameters:
        kwargs["load_denoiser"] = args.load_denoiser
    if "local_files_only" in signature.parameters:
        kwargs["local_files_only"] = args.local_files_only
    if "optimize" in signature.parameters:
        kwargs["optimize"] = args.optimize
    return kwargs


def generate_kwargs(model, args: argparse.Namespace, chunk: str, ref_audio: Path, prompt_text: str | None) -> dict:
    kwargs = {
        "text": prepare_text(chunk, args.style_prompt),
        "reference_wav_path": str(ref_audio),
        "cfg_value": args.cfg_value,
        "inference_timesteps": args.inference_timesteps,
    }

    signature = inspect.signature(model.generate)
    if prompt_text is not None and "prompt_text" in signature.parameters:
        kwargs["prompt_text"] = prompt_text
    if prompt_text is not None and "prompt_wav_path" in signature.parameters:
        kwargs["prompt_wav_path"] = str(ref_audio)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        if prompt_text is not None:
            kwargs["prompt_text"] = prompt_text
            kwargs["prompt_wav_path"] = str(ref_audio)
        return kwargs
    return {key: value for key, value in kwargs.items() if key in signature.parameters}


def to_mono_float32(waveform, np):
    audio = np.asarray(waveform, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio


def join_waveforms(waveforms: list, sample_rate: int, pause_ms: int, np):
    if not waveforms:
        raise RuntimeError("VoxCPM2 returned no audio segments.")

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


def resolve_sample_rate(model) -> int:
    tts_model = getattr(model, "tts_model", None)
    sample_rate = getattr(tts_model, "sample_rate", None)
    if sample_rate is None:
        raise RuntimeError("Could not resolve VoxCPM2 sample rate from model.tts_model.sample_rate.")
    return int(sample_rate)


def synthesize(args: argparse.Namespace) -> Path:
    VoxCPM, np, sf, torch = import_runtime()
    set_seed(args.seed, np, torch)

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    text = read_text(text_file)
    chunks = split_text(text, args.max_chars_per_chunk)
    prompt_text = read_prompt_text(args)
    device = resolve_device(torch)

    print(f"model: {model_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(f"{index + 1}/{len(chunks)}:{len(chunk)} chars" for index, chunk in enumerate(chunks))
    )
    print(f"reference audio: {ref_audio}")
    print(f"prompt text: {'provided' if prompt_text else 'not provided; using controllable cloning mode'}")
    print(f"device: {device}")
    print(f"style prompt: {args.style_prompt or 'none'}")

    started = time.perf_counter()
    model = VoxCPM.from_pretrained(str(model_path), **from_pretrained_kwargs(VoxCPM, args))
    sample_rate = resolve_sample_rate(model)

    waveforms = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"synthesizing chunk {index}/{len(chunks)} ({len(chunk)} chars)")
        with torch.inference_mode():
            waveforms.append(model.generate(**generate_kwargs(model, args, chunk, ref_audio, prompt_text)))

    waveform = join_waveforms(waveforms, sample_rate, args.pause_ms, np)
    elapsed = time.perf_counter() - started

    output_name = f"{model_path.name}_{elapsed_label(elapsed)}_{khz_from_sample_rate(sample_rate)}khz.wav"
    output_path = output_dir / output_name
    sf.write(str(output_path), waveform, sample_rate)

    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample rate: {sample_rate} Hz ({khz_from_sample_rate(sample_rate)} kHz)")
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
