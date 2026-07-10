"""
Use local LongCat-AudioDiT-1B to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/LongCat-AudioDiT-1B_${t}_${k}khz.wav

Usage:
  PYTHONPATH=/path/to/LongCat-AudioDiT \
    python modelScript/tts_local_longcat_audiodit_1b.py --local-files-only

The official LongCat repository provides the audiodit package but does not need
to live inside this repository. Pass --repo-path or set PYTHONPATH so Python can
import audiodit.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.environ.get("LONGCAT_AUDIODIT_MODEL_PATH", "/path/to/LongCat-AudioDiT-1B"))
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
DEFAULT_PROMPT_TEXT = "您好，很高兴能为您提供配音服务。选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"
DEFAULT_REPO_CANDIDATES = (
    Path("/path/to/LongCat-AudioDiT"),
    Path("/tmp/LongCat-AudioDiT"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local LongCat-AudioDiT-1B voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="LongCat-AudioDiT-1B model path")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Official LongCat-AudioDiT repository path containing the audiodit package",
    )
    parser.add_argument(
        "--tokenizer-path",
        default=None,
        help="Tokenizer path or HF id. Default uses model.config.text_encoder_model, usually google/umt5-base",
    )
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--prompt-text", default=DEFAULT_PROMPT_TEXT, help="Transcript of the reference audio")
    parser.add_argument("--prompt-text-file", type=Path, default=None, help="File containing the reference audio transcript")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=90,
        help="Maximum text characters per synthesis chunk. 0 disables chunking.",
    )
    parser.add_argument("--pause-ms", type=int, default=250, help="Silence inserted between synthesized chunks")
    parser.add_argument("--nfe", type=int, default=16, help="Number of diffusion/ODE inference steps")
    parser.add_argument("--guidance-strength", type=float, default=4.0, help="CFG/APG guidance strength")
    parser.add_argument("--guidance-method", choices=("cfg", "apg"), default="apg", help="Guidance method")
    parser.add_argument("--seed", type=int, default=1024, help="Random seed")
    parser.add_argument(
        "--duration-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to estimated generated duration before converting to latent frames",
    )
    parser.add_argument(
        "--vae-dtype",
        choices=("float16", "float32"),
        default="float16",
        help="VAE precision. Official inference uses float16 for the VAE.",
    )
    parser.add_argument("--local-files-only", action="store_true", help="Do not download model or tokenizer files")
    return parser.parse_args()


def maybe_add_repo_path(repo_path: Path | None) -> None:
    candidates = [repo_path] if repo_path is not None else list(DEFAULT_REPO_CANDIDATES)
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if (resolved / "audiodit").is_dir() and str(resolved) not in sys.path:
            sys.path.insert(0, str(resolved))
            return


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    return text


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\"“”‘’]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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


def approx_duration_from_text(text: str, max_duration: float = 30.0) -> float:
    en_dur_per_char = 0.082
    zh_dur_per_char = 0.21
    text = re.sub(r"\s+", "", text)
    num_zh = num_en = num_other = 0

    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            num_zh += 1
        elif char.isalpha():
            num_en += 1
        else:
            num_other += 1

    if num_zh > num_en:
        num_zh += num_other
    else:
        num_en += num_other
    return min(max_duration, num_zh * zh_dur_per_char + num_en * en_dur_per_char)


def import_runtime():
    try:
        import librosa
        import numpy as np
        import soundfile as sf
        import torch
        import torch.nn.functional as F

        import audiodit  # noqa: F401  # auto-registers AudioDiTModel with transformers
        from audiodit import AudioDiTModel
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "LongCat-AudioDiT runtime is not importable. Clone the official repository, "
            "install its requirements in the longcat_audiodit conda environment, then "
            "set PYTHONPATH to that repository or pass --repo-path. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return AudioDiTModel, AutoTokenizer, F, librosa, np, sf, torch


def load_tokenizer(AutoTokenizer: Any, tokenizer_source: str, local_files_only: bool):
    kwargs = {"local_files_only": local_files_only, "fix_mistral_regex": True}
    try:
        return AutoTokenizer.from_pretrained(tokenizer_source, **kwargs)
    except TypeError:
        kwargs.pop("fix_mistral_regex")
        return AutoTokenizer.from_pretrained(tokenizer_source, **kwargs)


def require_cuda(torch: Any) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for LongCat-AudioDiT synthesis.")
    return "cuda"


def set_seed(torch: Any, seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)


def apply_vae_dtype(model: Any, torch: Any, dtype: str) -> None:
    if dtype == "float16" and hasattr(model.vae, "to_half"):
        model.vae.to_half()
        return
    target_dtype = {
        "float16": torch.float16,
        "float32": torch.float32,
    }[dtype]
    model.vae.to(target_dtype)


def load_prompt_audio(path: Path, sample_rate: int, librosa: Any, torch: Any):
    audio, _ = librosa.load(str(path), sr=sample_rate, mono=True)
    return torch.from_numpy(audio).float().unsqueeze(0).unsqueeze(0)


def prompt_latent_frames(model: Any, prompt_audio: Any, full_hop: int, device: str, F: Any, torch: Any) -> int:
    off = 3
    prompt = prompt_audio.squeeze(0)
    if prompt.shape[-1] % full_hop != 0:
        prompt = F.pad(prompt, (0, full_hop - prompt.shape[-1] % full_hop))
    prompt = F.pad(prompt, (0, full_hop * off))

    vae_dtype = next(model.vae.parameters()).dtype
    with torch.inference_mode():
        latents = model.vae.encode(prompt.unsqueeze(0).to(device=device, dtype=vae_dtype))
    if off:
        latents = latents[..., :-off]
    return int(latents.shape[-1])


def estimate_duration_frames(
    gen_text: str,
    prompt_text: str | None,
    prompt_frames: int,
    sample_rate: int,
    full_hop: int,
    max_duration: float,
    duration_scale: float,
    np: Any,
) -> int:
    prompt_time = prompt_frames * full_hop / sample_rate
    available_duration = max(max_duration - prompt_time, full_hop / sample_rate)
    gen_duration = approx_duration_from_text(gen_text, max_duration=available_duration)

    if prompt_text:
        approx_prompt_duration = approx_duration_from_text(prompt_text, max_duration=max_duration)
        if approx_prompt_duration > 0:
            ratio = float(np.clip(prompt_time / approx_prompt_duration, 1.0, 1.5))
            gen_duration *= ratio

    gen_duration *= max(duration_scale, 0.1)
    gen_frames = max(1, int(gen_duration * sample_rate // full_hop))
    max_frames = max(1, int(max_duration * sample_rate // full_hop))
    return min(prompt_frames + gen_frames, max_frames)


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def to_mono_float32(waveform: Any, np: Any):
    audio = np.asarray(waveform, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=0 if audio.shape[0] <= 2 else 1)
    return audio.reshape(-1)


def join_waveforms(waveforms: list[Any], sample_rate: int, pause_ms: int, np: Any):
    if not waveforms:
        raise RuntimeError("LongCat-AudioDiT returned no audio segments.")

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
    maybe_add_repo_path(args.repo_path)
    AudioDiTModel, AutoTokenizer, F, librosa, np, sf, torch = import_runtime()

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    device = require_cuda(torch)
    torch.backends.cudnn.benchmark = False
    set_seed(torch, args.seed)

    text = normalize_text(read_text(text_file))
    chunks = split_text(text, args.max_chars_per_chunk)
    prompt_text = read_prompt_text(args)
    prompt_text = normalize_text(prompt_text) if prompt_text else None

    print(f"model: {model_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(f"{index + 1}/{len(chunks)}:{len(chunk)} chars" for index, chunk in enumerate(chunks))
    )
    print(f"reference audio: {ref_audio}")
    print(f"prompt text: {'provided' if prompt_text else 'not provided'}")
    print(f"device: {device}")
    print(f"nfe: {args.nfe}")
    print(f"guidance_method: {args.guidance_method}")
    print(f"guidance_strength: {args.guidance_strength}")
    print(f"vae_dtype: {args.vae_dtype}")

    started = time.perf_counter()
    model = AudioDiTModel.from_pretrained(str(model_path), local_files_only=args.local_files_only).to(device)
    apply_vae_dtype(model, torch, args.vae_dtype)
    model.eval()

    tokenizer_source = args.tokenizer_path or model.config.text_encoder_model
    tokenizer = load_tokenizer(AutoTokenizer, tokenizer_source, args.local_files_only)

    sample_rate = int(model.config.sampling_rate)
    full_hop = int(model.config.latent_hop)
    max_duration = float(model.config.max_wav_duration)
    prompt_audio = load_prompt_audio(ref_audio, sample_rate, librosa, torch)
    prompt_frames = prompt_latent_frames(model, prompt_audio, full_hop, device, F, torch)
    prompt_time = prompt_frames * full_hop / sample_rate
    print(f"sample_rate: {sample_rate} Hz")
    print(f"prompt_duration: {prompt_time:.2f}s ({prompt_frames} latent frames)")

    waveforms = []
    with torch.inference_mode():
        for index, chunk in enumerate(chunks, start=1):
            set_seed(torch, args.seed + index - 1)
            full_text = f"{prompt_text} {chunk}" if prompt_text else chunk
            inputs = tokenizer([full_text], padding="longest", return_tensors="pt")
            duration = estimate_duration_frames(
                gen_text=chunk,
                prompt_text=prompt_text,
                prompt_frames=prompt_frames,
                sample_rate=sample_rate,
                full_hop=full_hop,
                max_duration=max_duration,
                duration_scale=args.duration_scale,
                np=np,
            )
            print(
                f"synthesizing chunk {index}/{len(chunks)} "
                f"({len(chunk)} chars, duration={duration} latent frames)"
            )
            output = model(
                input_ids=inputs.input_ids.to(device),
                attention_mask=inputs.attention_mask.to(device),
                prompt_audio=prompt_audio,
                duration=duration,
                steps=args.nfe,
                cfg_strength=args.guidance_strength,
                guidance_method=args.guidance_method,
            )
            waveforms.append(output.waveform.squeeze().detach().cpu().numpy())

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
