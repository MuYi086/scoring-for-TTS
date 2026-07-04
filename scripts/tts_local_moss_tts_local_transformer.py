"""
Use local MOSS-TTS-Local-Transformer to clone a reference voice and synthesize text.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer-v1.5_${t}_${k}khz.wav

Usage:
  python scripts/tts_local_moss_tts_local_transformer.py

If the audio tokenizer is stored locally:
  python scripts/tts_local_moss_tts_local_transformer.py --codec-path /path/to/MOSS-Audio-Tokenizer
"""

from __future__ import annotations

import argparse
import inspect
import importlib.util
import os
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path("/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5")
LOCAL_CODEC_PATH = Path("/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer-v2")
DEFAULT_CODEC_MODEL_ID = "OpenMOSS-Team/MOSS-Audio-Tokenizer-v2"
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local MOSS-TTS-Local-Transformer voice clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="MOSS-TTS-Local-Transformer model path")
    parser.add_argument(
        "--codec-path",
        default=str(LOCAL_CODEC_PATH if LOCAL_CODEC_PATH.exists() else DEFAULT_CODEC_MODEL_ID),
        help=(
            "MOSS audio tokenizer path or HF model id. "
            "Use a local path for fully offline runs; default follows the official processor."
        ),
    )
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Reference audio for voice cloning")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory for output wav")
    parser.add_argument("--language", default="Chinese", help="Language hint passed to the MOSS processor")
    parser.add_argument("--instruction", default=None, help="Optional style instruction passed to the MOSS processor")
    parser.add_argument("--quality", default=None, help="Optional quality hint passed to the MOSS processor")
    parser.add_argument("--tokens", type=int, default=None, help="Expected audio token count; 1s is about 12.5 tokens")
    parser.add_argument("--max-new-tokens", type=int, default=4096, help="Maximum generated audio tokens")
    parser.add_argument(
        "--n-vq-for-inference",
        type=int,
        default=None,
        help="RVQ depth. Defaults to the model config; MOSS-TTS-Local-Transformer-v1.5 requires 12.",
    )
    parser.add_argument("--audio-temperature", type=float, default=1.7, help="Audio token sampling temperature")
    parser.add_argument("--audio-top-p", type=float, default=0.8, help="Audio token nucleus sampling cutoff")
    parser.add_argument("--audio-top-k", type=int, default=25, help="Audio token top-k sampling cutoff")
    parser.add_argument("--audio-repetition-penalty", type=float, default=1.0, help="Audio repetition penalty")
    parser.add_argument("--text-temperature", type=float, default=None, help="Optional text layer sampling temperature")
    parser.add_argument("--text-top-p", type=float, default=None, help="Optional text layer nucleus sampling cutoff")
    parser.add_argument("--text-top-k", type=int, default=None, help="Optional text layer top-k sampling cutoff")
    parser.add_argument("--text-repetition-penalty", type=float, default=None, help="Optional text repetition penalty")
    parser.add_argument(
        "--attn-implementation",
        choices=("auto", "flash_attention_2", "sdpa", "eager"),
        default="auto",
        help="Attention backend for transformers model loading",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float32", "float16", "bfloat16"),
        default="auto",
        help="Torch dtype. auto uses bfloat16 on CUDA.",
    )
    parser.add_argument("--local-files-only", action="store_true", help="Do not download model or codec files")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    return text


def import_runtime():
    try:
        import torch
        import torchaudio
        import transformers
        import transformers.processing_utils as processing_utils
        from transformers import AutoModel, AutoProcessor
    except ImportError as exc:
        raise RuntimeError(
            "MOSS-TTS runtime is not importable. Install torch, torchaudio and transformers "
            "with the official OpenMOSS/MOSS-TTS dependencies. "
            f"Missing import: {exc.name or exc}"
        ) from exc

    if not hasattr(processing_utils, "MODALITY_TO_BASE_CLASS_MAPPING"):
        raise RuntimeError(
            "Installed transformers is too old for the local MOSS-TTS remote code. "
            f"Current transformers version: {transformers.__version__}. "
            "Install the official OpenMOSS/MOSS-TTS environment, or upgrade transformers "
            "to a version that provides processing_utils.MODALITY_TO_BASE_CLASS_MAPPING."
        )
    return AutoModel, AutoProcessor, torch, torchaudio


def resolve_device(torch) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for MOSS-TTS synthesis. Run outside the sandbox if GPU access is blocked.")
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
    torch.backends.cuda.enable_cudnn_sdp(False)
    torch.backends.cuda.enable_flash_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(True)

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


def patch_pad_sequence_padding_side(torch) -> None:
    original = torch.nn.utils.rnn.pad_sequence
    if "padding_side" in inspect.signature(original).parameters:
        return

    def pad_sequence_compat(sequences, batch_first=False, padding_value=0.0, padding_side="right"):
        if padding_side == "right":
            return original(sequences, batch_first=batch_first, padding_value=padding_value)
        if padding_side != "left":
            raise ValueError(f"padding_side must be 'right' or 'left', got {padding_side!r}")

        flipped = [sequence.flip(0) for sequence in sequences]
        padded = original(flipped, batch_first=batch_first, padding_value=padding_value)
        sequence_dim = 1 if batch_first else 0
        return padded.flip(sequence_dim)

    torch.nn.utils.rnn.pad_sequence = pad_sequence_compat


def patch_autocast_enabled_device_arg(torch) -> None:
    original = torch.is_autocast_enabled
    try:
        original("cuda")
    except TypeError:
        def is_autocast_enabled_compat(device_type=None):
            if device_type == "cpu" and hasattr(torch, "is_autocast_cpu_enabled"):
                return torch.is_autocast_cpu_enabled()
            return original()

        torch.is_autocast_enabled = is_autocast_enabled_compat

    if not hasattr(torch, "get_autocast_dtype"):
        def get_autocast_dtype_compat(device_type=None):
            if device_type == "cpu" and hasattr(torch, "get_autocast_cpu_dtype"):
                return torch.get_autocast_cpu_dtype()
            if hasattr(torch, "get_autocast_gpu_dtype"):
                return torch.get_autocast_gpu_dtype()
            return torch.float32

        torch.get_autocast_dtype = get_autocast_dtype_compat


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def collect_audio(decoded_messages, torch):
    waveforms = []
    channels = None
    for message in decoded_messages:
        if message is None:
            continue
        for audio in message.audio_codes_list:
            if isinstance(audio, torch.Tensor):
                waveform = audio.to(torch.float32).cpu()
                if waveform.ndim == 1:
                    waveform = waveform.unsqueeze(0)
                if waveform.ndim != 2:
                    raise RuntimeError(f"Decoded audio must be [samples] or [channels, samples], got {tuple(waveform.shape)}.")
                if channels is None:
                    channels = int(waveform.shape[0])
                elif int(waveform.shape[0]) != channels:
                    raise RuntimeError("MOSS-TTS returned decoded audio with inconsistent channel counts.")
                waveforms.append(waveform)

    if not waveforms:
        raise RuntimeError("MOSS-TTS returned no decoded audio.")

    return torch.cat(waveforms, dim=-1)


def synthesize(args: argparse.Namespace) -> Path:
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    AutoModel, AutoProcessor, torch, torchaudio = import_runtime()

    model_path = require_path(args.model_path, "model path")
    text_file = require_path(args.text_file, "text file")
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    text = read_text(text_file)
    device = resolve_device(torch)
    dtype = resolve_dtype(torch, args.dtype, device)
    attn_implementation = resolve_attn_implementation(torch, args.attn_implementation, device, dtype)
    patch_pad_sequence_padding_side(torch)
    patch_autocast_enabled_device_arg(torch)

    print(f"model: {model_path}")
    print(f"codec: {args.codec_path}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(f"reference audio: {ref_audio}")
    print(f"device: {device}")
    print(f"dtype: {dtype}")
    print(f"attn_implementation: {attn_implementation}")

    started = time.perf_counter()
    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    processor = AutoProcessor.from_pretrained(
        model_path,
        trust_remote_code=True,
        codec_path=args.codec_path,
    )
    processor.audio_tokenizer = processor.audio_tokenizer.to(device)

    conversation = [
        processor.build_user_message(
            text=text,
            reference=[str(ref_audio)],
            instruction=args.instruction,
            tokens=args.tokens,
            quality=args.quality,
            language=args.language,
        )
    ]
    batch = processor([conversation], mode="generation")

    model = AutoModel.from_pretrained(
        model_path,
        trust_remote_code=True,
        attn_implementation=attn_implementation,
        dtype=dtype,
        local_files_only=args.local_files_only,
    ).to(device)
    model.eval()

    input_ids = batch["input_ids"].to(device)
    attention_mask = batch["attention_mask"].to(device)
    generation_kwargs = {
        "max_new_tokens": args.max_new_tokens,
        "audio_temperature": args.audio_temperature,
        "audio_top_p": args.audio_top_p,
        "audio_top_k": args.audio_top_k,
        "audio_repetition_penalty": args.audio_repetition_penalty,
    }
    if args.n_vq_for_inference is not None:
        generation_kwargs["n_vq_for_inference"] = args.n_vq_for_inference
    if args.text_temperature is not None:
        generation_kwargs["text_temperature"] = args.text_temperature
    if args.text_top_p is not None:
        generation_kwargs["text_top_p"] = args.text_top_p
    if args.text_top_k is not None:
        generation_kwargs["text_top_k"] = args.text_top_k
    if args.text_repetition_penalty is not None:
        generation_kwargs["text_repetition_penalty"] = args.text_repetition_penalty

    with torch.no_grad():
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            **generation_kwargs,
        )
        waveform = collect_audio(processor.decode(outputs), torch)

    elapsed = time.perf_counter() - started
    sample_rate = int(processor.model_config.sampling_rate)
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
