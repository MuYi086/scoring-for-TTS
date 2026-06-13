"""
Use local Fun-CosyVoice3 to clone a reference voice and synthesize the sample text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Fun-CosyVoice3-0.5B-2512_${t}_${k}khz.wav

Usage:
  python scripts/tts_local_cosyvoice3.py

If the official CosyVoice repository is not installed as an importable package:
  python scripts/tts_local_cosyvoice3.py --cosyvoice-repo /path/to/CosyVoice
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path("/home/muyi086/hf-mirror/FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Fun-CosyVoice3 voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="CosyVoice3 model path")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for cloning")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument(
        "--cosyvoice-repo",
        type=Path,
        default=None,
        help="Official FunAudioLLM/CosyVoice repo path; adds repo and third_party/Matcha-TTS to sys.path",
    )
    parser.add_argument(
        "--mode",
        choices=("cross-lingual", "zero-shot", "instruct"),
        default="cross-lingual",
        help="Inference mode for each synthesized chunk.",
    )
    parser.add_argument(
        "--prompt-text",
        default="",
        help="Prompt transcript for zero-shot mode. '<|endofprompt|>' is appended if missing.",
    )
    parser.add_argument(
        "--instruction",
        default="You are a helpful assistant.<|endofprompt|>",
        help="Instruction prefix for cross-lingual/instruct mode.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=80,
        help="Maximum text characters per synthesis chunk. Prevents long-form truncation.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=300,
        help="Silence inserted between synthesized chunks.",
    )
    parser.add_argument("--stream", action="store_true", help="Enable streaming inference")
    return parser.parse_args()


def add_cosyvoice_repo(cosyvoice_repo: Path | None) -> None:
    if cosyvoice_repo is None:
        return

    repo = cosyvoice_repo.expanduser().resolve()
    matcha = repo / "third_party" / "Matcha-TTS"
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(matcha))


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


def ensure_endofprompt(text: str) -> str:
    text = text.strip()
    if "<|endofprompt|>" not in text:
        text += "<|endofprompt|>"
    return text


def import_runtime():
    try:
        import torch
        import torchaudio
        from cosyvoice.cli.cosyvoice import AutoModel
    except ImportError as exc:
        raise RuntimeError(
            "CosyVoice3 runtime is not importable. Install the official FunAudioLLM/CosyVoice "
            "repository dependencies, then rerun with --cosyvoice-repo /path/to/CosyVoice if needed. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return AutoModel, torch, torchaudio


def collect_audio_segments(result_iter, torch):
    segments = []
    for result in result_iter:
        speech = result["tts_speech"]
        if speech.dim() == 1:
            speech = speech.unsqueeze(0)
        segments.append(speech.cpu())

    if not segments:
        raise RuntimeError("CosyVoice returned no audio segments.")

    return torch.cat(segments, dim=-1)


def synthesize_chunk(cosyvoice, args: argparse.Namespace, text: str, ref_audio: Path, torch):
    if args.mode == "zero-shot":
        if not args.prompt_text.strip():
            raise ValueError("--prompt-text is required when --mode zero-shot")
        result_iter = cosyvoice.inference_zero_shot(
            text,
            ensure_endofprompt(args.prompt_text),
            str(ref_audio),
            stream=args.stream,
        )
    elif args.mode == "instruct":
        result_iter = cosyvoice.inference_instruct2(
            text,
            ensure_endofprompt(args.instruction),
            str(ref_audio),
            stream=args.stream,
        )
    else:
        synthesis_text = ensure_endofprompt(args.instruction) + "\n" + text
        result_iter = cosyvoice.inference_cross_lingual(
            synthesis_text,
            str(ref_audio),
            stream=args.stream,
        )

    return collect_audio_segments(result_iter, torch)


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def synthesize(args: argparse.Namespace) -> Path:
    add_cosyvoice_repo(args.cosyvoice_repo)
    AutoModel, torch, torchaudio = import_runtime()

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    text = read_text(text_file)
    chunks = split_text(text, args.max_chars_per_chunk)
    print(f"model: {model_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(f"{index + 1}/{len(chunks)}:{len(chunk)} chars" for index, chunk in enumerate(chunks))
    )
    print(f"reference audio: {ref_audio}")

    started = time.perf_counter()
    cosyvoice = AutoModel(model_dir=str(model_path))

    waveforms = []
    pause_samples = int(cosyvoice.sample_rate * max(args.pause_ms, 0) / 1000)
    pause = torch.zeros(1, pause_samples) if pause_samples > 0 else None
    for index, chunk in enumerate(chunks, start=1):
        print(f"synthesizing chunk {index}/{len(chunks)} ({len(chunk)} chars)")
        waveforms.append(synthesize_chunk(cosyvoice, args, chunk, ref_audio, torch))
        if pause is not None and index < len(chunks):
            waveforms.append(pause)
    waveform = torch.cat(waveforms, dim=-1)
    elapsed = time.perf_counter() - started

    sample_rate = int(cosyvoice.sample_rate)
    output_name = f"{model_path.name}_{elapsed_label(elapsed)}_{khz_from_sample_rate(sample_rate)}khz.wav"
    output_path = output_dir / output_name
    torchaudio.save(str(output_path), waveform, sample_rate)

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
