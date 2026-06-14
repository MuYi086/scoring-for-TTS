"""
Use local dots.tts-base to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-base_${t}_${k}khz.wav

Usage:
  python scripts/tts_local_dots_tts_base.py --local-files-only
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path("/home/muyi086/hf-mirror/rednote-hilab/dots.tts-base")
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
DEFAULT_PROMPT_TEXT = "您好，很高兴能为您提供配音服务。选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local dots.tts-base voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="dots.tts-base model path")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--prompt-text", default=DEFAULT_PROMPT_TEXT, help="Transcript of the reference audio")
    parser.add_argument("--prompt-text-file", type=Path, default=None, help="File containing the reference audio transcript")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument(
        "--language",
        default="chinese",
        help="Language tag passed to dots.tts. Use none to disable or auto_detect for detection.",
    )
    parser.add_argument(
        "--template-name",
        choices=("tts", "instruction_tts", "text_to_audio", "tts_interleave"),
        default=None,
        help="dots.tts runtime template. Default follows the runtime tts template.",
    )
    parser.add_argument("--precision", default="bfloat16", help="Inference precision")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for inference")
    parser.add_argument("--ode-method", default="euler", help="ODE solver method")
    parser.add_argument("--num-steps", type=int, default=10, help="Flow-matching sampling steps")
    parser.add_argument("--guidance-scale", type=float, default=1.2, help="Classifier-free guidance scale")
    parser.add_argument("--speaker-scale", type=float, default=1.5, help="Scale applied to the reference speaker embedding")
    parser.add_argument(
        "--max-generate-length",
        type=int,
        default=500,
        help="Maximum audio patch count for each chunk, including prompt audio patches.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=120,
        help="Maximum text characters per synthesis chunk. 0 disables chunking.",
    )
    parser.add_argument("--pause-ms", type=int, default=250, help="Silence inserted between synthesized chunks")
    parser.add_argument("--normalize-text", action="store_true", help="Enable dots.tts text normalization")
    parser.add_argument("--profile-inference", action="store_true", help="Collect dots.tts inference profiling")
    parser.add_argument("--local-files-only", action="store_true", help="Disable Hugging Face network access")
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


def read_prompt_text(args: argparse.Namespace) -> str | None:
    if args.prompt_text_file is not None:
        return read_text(require_path(args.prompt_text_file, "prompt text file"))
    if args.prompt_text is not None and args.prompt_text.strip():
        return args.prompt_text.strip()
    return None


def import_runtime():
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from dots_tts.runtime import DotsTtsRuntime
        from dots_tts.utils.logging import configure_logging
        from dots_tts.utils.util import seed_everything
    except ImportError as exc:
        raise RuntimeError(
            "dots.tts runtime is not importable. Install the official rednote-hilab/dots.tts "
            "package in an isolated conda environment, then run this script from that environment. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return DotsTtsRuntime, configure_logging, np, seed_everything, sf, torch


def require_cuda(torch) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for dots.tts synthesis.")


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def to_mono_float32(audio, np):
    waveform = np.asarray(audio, dtype=np.float32)
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0 if waveform.shape[0] <= 2 else 1)
    return waveform.reshape(-1)


def join_waveforms(waveforms: list, sample_rate: int, pause_ms: int, np):
    if not waveforms:
        raise RuntimeError("dots.tts returned no audio segments.")

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


def synthesize(args: argparse.Namespace) -> Path:
    DotsTtsRuntime, configure_logging, np, seed_everything, sf, torch = import_runtime()

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    require_cuda(torch)
    configure_logging()
    seed_everything(args.seed)

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    text = read_text(text_file)
    chunks = split_text(text, args.max_chars_per_chunk)
    prompt_text = read_prompt_text(args)
    language = None if args.language.strip().lower() == "none" else args.language

    print(f"model: {model_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(f"{index + 1}/{len(chunks)}:{len(chunk)} chars" for index, chunk in enumerate(chunks))
    )
    print(f"reference audio: {ref_audio}")
    print(f"prompt text: {'provided' if prompt_text else 'not provided'}")
    print("device: cuda")
    print(f"precision: {args.precision}")
    print(f"num_steps: {args.num_steps}")
    print(f"guidance_scale: {args.guidance_scale}")
    print(f"speaker_scale: {args.speaker_scale}")

    started = time.perf_counter()
    runtime = DotsTtsRuntime.from_pretrained(
        str(model_path),
        precision=args.precision,
        max_generate_length=args.max_generate_length,
    )

    waveforms = []
    for index, chunk in enumerate(chunks, start=1):
        print(f"synthesizing chunk {index}/{len(chunks)} ({len(chunk)} chars)")
        result = runtime.generate(
            text=chunk,
            prompt_audio_path=str(ref_audio),
            prompt_text=prompt_text,
            language=language,
            template_name=args.template_name,
            ode_method=args.ode_method,
            num_steps=args.num_steps,
            guidance_scale=args.guidance_scale,
            speaker_scale=args.speaker_scale,
            normalize_text=args.normalize_text,
            profile_inference=args.profile_inference,
        )
        waveforms.append(result["audio"].float().cpu().squeeze().numpy())

    sample_rate = int(runtime.sample_rate)
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
