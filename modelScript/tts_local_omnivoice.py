"""Use local OmniVoice to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/OmniVoice_${t}_${k}khz.wav

Usage:
  python modelScript/tts_local_omnivoice.py --local-files-only

OmniVoice creates one reusable voice-clone prompt from the reference audio,
then generates each text chunk with that prompt.
"""

from __future__ import annotations

import argparse
import gc
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "OMNIVOICE_MODEL_PATH",
        os.environ.get("OMNIVOICE_MODEL_DIR", "/path/to/OmniVoice"),
    )
)
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
RUNTIME_CACHE_DIR = REPO_ROOT / "work" / "runtime_cache" / "omnivoice"


def parse_args() -> argparse.Namespace:
    """Parse standalone OmniVoice synthesis options."""
    parser = argparse.ArgumentParser(description="Local OmniVoice voice-clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="OmniVoice model directory")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--ref-text", default=None, help="Exact transcript of the reference audio")
    parser.add_argument("--ref-text-file", type=Path, default=None, help="File containing the reference transcript")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory used when --output is omitted")
    parser.add_argument("--output", type=Path, default=None, help="Exact output WAV path")
    parser.add_argument("--language", default="Chinese", help="Language passed to OmniVoice; use none to disable")
    parser.add_argument("--device-map", default="cuda:0", help="Device map passed to OmniVoice.from_pretrained")
    parser.add_argument(
        "--dtype",
        choices=("auto", "float32", "float16", "bfloat16"),
        default="float16",
        help="Model inference dtype",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed; use -1 to disable explicit seeding")
    parser.add_argument("--num-step", type=int, default=32, help="Generation denoising steps")
    parser.add_argument("--guidance-scale", type=float, default=2.0, help="Classifier-free guidance scale")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier")
    parser.add_argument("--duration", type=float, default=None, help="Optional target duration in seconds")
    parser.add_argument("--t-shift", type=float, default=0.1, help="Flow-matching time-shift value")
    parser.add_argument("--instruction", default=None, help="Optional generation instruction")
    parser.add_argument(
        "--denoise",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable OmniVoice denoising",
    )
    parser.add_argument(
        "--preprocess-prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preprocess reference audio before creating the voice-clone prompt",
    )
    parser.add_argument(
        "--postprocess-output",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable OmniVoice output postprocessing",
    )
    parser.add_argument("--layer-penalty-factor", type=float, default=5.0)
    parser.add_argument("--position-temperature", type=float, default=5.0)
    parser.add_argument("--class-temperature", type=float, default=0.0)
    parser.add_argument("--audio-chunk-duration", type=float, default=15.0)
    parser.add_argument("--audio-chunk-threshold", type=float, default=30.0)
    parser.add_argument("--pad-duration", type=float, default=0.1)
    parser.add_argument("--fade-duration", type=float, default=0.1)
    parser.add_argument("--max-chars-per-chunk", type=int, default=120, help="0 disables text chunking")
    parser.add_argument("--pause-ms", type=int, default=250, help="Silence inserted between text chunks")
    parser.add_argument(
        "--local-files-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use local Hugging Face files only (default: enabled)",
    )
    parser.add_argument(
        "--runtime-cache-dir",
        type=Path,
        default=RUNTIME_CACHE_DIR,
        help="Writable cache directory for Hugging Face and audio libraries",
    )
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    """Resolve and validate a required file or directory."""
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label}不存在：{resolved}")
    return resolved


def read_text(path: Path) -> str:
    """Read Markdown text while removing markers that should not be spoken."""
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def split_long_sentence(text: str, max_chars: int) -> list[str]:
    """Split an overlong sentence on Chinese-friendly punctuation."""
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
            chunks.extend(part[index : index + max_chars] for index in range(0, len(part), max_chars))
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
    """Keep sentences intact where possible while bounding generation length."""
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


def resolve_optional_text(value: str | None) -> str | None:
    """Normalize optional command-line text values."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def resolve_dtype(torch: Any, dtype_name: str) -> Any:
    """Translate a portable CLI dtype name to the runtime value."""
    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
        "auto": "auto",
    }
    return mapping[dtype_name]


def seed_everything(torch: Any, np: Any, seed: int) -> None:
    """Seed every local random generator used by the inference stack."""
    if seed < 0:
        return
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def to_mono_float32(audio: Any, np: Any) -> Any:
    """Normalize generated audio to a one-dimensional float32 waveform."""
    waveform = np.asarray(audio, dtype=np.float32)
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0 if waveform.shape[0] <= 2 else 1)
    return waveform.reshape(-1)


def join_waveforms(waveforms: list[Any], sample_rate: int, pause_ms: int, np: Any) -> Any:
    """Join generated chunks with optional silence while preserving sample rate."""
    if not waveforms:
        raise RuntimeError("OmniVoice未返回音频片段。")
    segments = [to_mono_float32(waveform, np) for waveform in waveforms]
    pause_samples = int(sample_rate * max(pause_ms, 0) / 1000)
    if pause_samples <= 0 or len(segments) == 1:
        return np.concatenate(segments)
    pause = np.zeros(pause_samples, dtype=np.float32)
    joined: list[Any] = []
    for index, segment in enumerate(segments):
        joined.append(segment)
        if index < len(segments) - 1:
            joined.append(pause)
    return np.concatenate(joined)


def prepare_environment(args: argparse.Namespace) -> None:
    """Set per-project writable caches before importing model libraries."""
    cache_dir = args.runtime_cache_dir.expanduser().resolve()
    cache_paths = {
        "HF_MODULES_CACHE": cache_dir / "hf_modules",
        "NUMBA_CACHE_DIR": cache_dir / "numba",
        "MPLCONFIGDIR": cache_dir / "matplotlib",
        "XDG_CACHE_HOME": cache_dir / "xdg",
    }
    for name, path in cache_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True,max_split_size_mb:128")
    os.environ.setdefault("CUDA_MODULE_LOADING", "LAZY")
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)


def import_runtime() -> tuple[Any, Any, Any, Any]:
    """Import optional inference dependencies only when synthesis starts."""
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from omnivoice import OmniVoice
    except ImportError as exc:
        raise RuntimeError(
            "OmniVoice运行时不可导入。请在独立环境安装 omnivoice、torch、numpy 和 soundfile。"
            f"缺失导入：{exc.name or exc}"
        ) from exc
    return OmniVoice, np, sf, torch


def build_generation_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    """Build the public OmniVoice generation controls from CLI options."""
    return {
        "num_step": args.num_step,
        "guidance_scale": args.guidance_scale,
        "speed": args.speed,
        "duration": args.duration,
        "t_shift": args.t_shift,
        "denoise": args.denoise,
        "postprocess_output": args.postprocess_output,
        "layer_penalty_factor": args.layer_penalty_factor,
        "position_temperature": args.position_temperature,
        "class_temperature": args.class_temperature,
        "audio_chunk_duration": args.audio_chunk_duration,
        "audio_chunk_threshold": args.audio_chunk_threshold,
        "pad_duration": args.pad_duration,
        "fade_duration": args.fade_duration,
    }


def resolve_ref_text(args: argparse.Namespace) -> str | None:
    """Prefer an explicit transcript file over an inline transcript."""
    if args.ref_text_file is not None:
        return read_text(require_path(args.ref_text_file, "参考文本文件"))
    return resolve_optional_text(args.ref_text)


def output_path(args: argparse.Namespace, sample_rate: int, elapsed: float) -> Path:
    """Choose the caller-provided output path or construct the standard name."""
    if args.output is not None:
        return args.output.expanduser().resolve()
    khz = sample_rate / 1000
    return args.output_dir.expanduser().resolve() / f"OmniVoice_{elapsed:.2f}s_{khz:g}khz.wav"


def clear_cuda_cache(torch: Any) -> None:
    """Release model references and cached CUDA memory after synthesis."""
    gc.collect()
    if not torch.cuda.is_available():
        return
    try:
        torch.cuda.synchronize()
    except Exception:
        pass
    try:
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
    except Exception:
        pass


def synthesize(args: argparse.Namespace) -> Path:
    """Create a reference prompt once, generate all chunks, and write one WAV."""
    prepare_environment(args)
    OmniVoice, np, sf, torch = import_runtime()
    model_path = require_path(args.model_path, "模型目录")
    ref_audio = require_path(args.ref_audio, "参考音频")
    text = read_text(require_path(args.text_file, "合成文本"))
    ref_text = resolve_ref_text(args)
    if not torch.cuda.is_available():
        raise RuntimeError("OmniVoice合成需要可用的CUDA GPU。")

    seed_everything(torch, np, args.seed)
    chunks = split_text(text, args.max_chars_per_chunk)
    model = None
    voice_clone_prompt = None
    started = time.perf_counter()
    try:
        model = OmniVoice.from_pretrained(
            str(model_path),
            device_map=args.device_map,
            dtype=resolve_dtype(torch, args.dtype),
            local_files_only=args.local_files_only,
        )
        sample_rate = int(getattr(model, "sampling_rate", 24000))
        voice_clone_prompt = model.create_voice_clone_prompt(
            ref_audio=str(ref_audio),
            ref_text=ref_text,
            preprocess_prompt=args.preprocess_prompt,
        )
        waveforms: list[Any] = []
        generation_kwargs = build_generation_kwargs(args)
        for index, chunk in enumerate(chunks, start=1):
            print(f"合成第 {index}/{len(chunks)} 段（{len(chunk)} 字）")
            generated = model.generate(
                text=chunk,
                language=resolve_optional_text(args.language),
                voice_clone_prompt=voice_clone_prompt,
                instruct=resolve_optional_text(args.instruction),
                **generation_kwargs,
            )
            if not generated:
                raise RuntimeError("OmniVoice未返回音频片段。")
            waveforms.append(generated[0])
        waveform = join_waveforms(waveforms, sample_rate, args.pause_ms, np)
        elapsed = time.perf_counter() - started
        destination = output_path(args, sample_rate, elapsed)
        destination.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(destination), waveform, sample_rate)
        print(f"完成：{destination}（{sample_rate} Hz，耗时 {elapsed:.2f}s）")
        return destination
    finally:
        del voice_clone_prompt
        del model
        clear_cuda_cache(torch)


def main() -> int:
    """Run the command-line entry point."""
    try:
        synthesize(parse_args())
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
