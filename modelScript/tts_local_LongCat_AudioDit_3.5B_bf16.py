"""
使用本地 LongCat-AudioDiT-3.5B-bf16 模型进行参考音频声音克隆与文本转语音。

默认输出文件名：
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/LongCat-AudioDiT-3.5B-bf16_${t}_${k}khz.wav

最小运行示例：
  PYTHONPATH=~/tts-depency/LongCat-AudioDiT \
    python modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py \
    --repo-path ~/tts-depency/LongCat-AudioDiT \
    --tokenizer-path ~/hf-mirror/google/umt5-base \
    --ref-audio ~/tts-depency/LongCat-AudioDiT/assets/prompt.wav \
    --prompt-text "参考音频对应的准确文本" \
    --text "要合成的文本" \
    --model-path ~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16 \
    --local-files-only

官方 LongCat-AudioDiT 源码目录不需要放在本仓库内；默认会发现
~/tts-depency/LongCat-AudioDiT，也可通过 --repo-path、LONGCAT_AUDIODIT_REPO_PATH
或 PYTHONPATH 提供其中的 audiodit 包。
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
MODEL_PATH = Path(
    os.environ.get(
        "LONGCAT_AUDIODIT_35B_BF16_MODEL_PATH",
        str(Path.home() / "hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16"),
    )
).expanduser()
TOKENIZER_PATH = Path(
    os.environ.get(
        "LONGCAT_AUDIODIT_TOKENIZER_PATH",
        str(Path.home() / "hf-mirror/google/umt5-base"),
    )
).expanduser()
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
DEFAULT_PROMPT_TEXT = "您好，很高兴能为您提供配音服务。选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。"
DEFAULT_REPO_PATH = Path(
    os.environ.get(
        "LONGCAT_AUDIODIT_REPO_PATH",
        str(Path.home() / "tts-depency/LongCat-AudioDiT"),
    )
).expanduser()
DEFAULT_REPO_CANDIDATES = (
    DEFAULT_REPO_PATH,
    Path.home() / "LongCat-AudioDiT",
    Path("/tmp/LongCat-AudioDiT"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local LongCat-AudioDiT-3.5B-bf16 voice clone synthesis"
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=MODEL_PATH,
        help="LongCat-AudioDiT-3.5B-bf16 model directory",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help=(
            "Official LongCat-AudioDiT repository containing the audiodit package; "
            f"default discovery starts at {DEFAULT_REPO_PATH}"
        ),
    )
    parser.add_argument(
        "--tokenizer-path",
        type=Path,
        default=None,
        help=(
            "Local google/umt5-base tokenizer directory. If omitted, use "
            f"{TOKENIZER_PATH} when it exists, otherwise model.config.text_encoder_model."
        ),
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        default=TEXT_FILE,
        help="Text/Markdown file to synthesize; ignored when --text is provided",
    )
    parser.add_argument("--text", default=None, help="Text to synthesize directly")
    parser.add_argument(
        "--ref-audio",
        type=Path,
        default=REF_AUDIO,
        help="Reference audio for zero-shot voice cloning",
    )
    parser.add_argument(
        "--prompt-text",
        default=DEFAULT_PROMPT_TEXT,
        help="Accurate transcript of the reference audio",
    )
    parser.add_argument(
        "--prompt-text-file",
        type=Path,
        default=None,
        help="File containing the accurate reference-audio transcript",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SAMPLE_DIR,
        help="Directory for the generated WAV file",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=180,
        help="Maximum text characters per synthesis chunk; 0 disables chunking",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=250,
        help="Silence inserted between synthesized chunks",
    )
    parser.add_argument("--nfe", type=int, default=16, help="Number of ODE inference steps")
    parser.add_argument(
        "--guidance-strength",
        type=float,
        default=4.0,
        help="CFG/APG guidance strength",
    )
    parser.add_argument(
        "--guidance-method",
        choices=("cfg", "apg"),
        default="apg",
        help="Guidance method; APG is the official voice-cloning default",
    )
    parser.add_argument("--seed", type=int, default=20260614, help="Random seed; -1 disables seeding")
    parser.add_argument(
        "--duration-scale",
        type=float,
        default=1.0,
        help="Multiplier applied to estimated generated duration",
    )
    parser.add_argument(
        "--vae-dtype",
        choices=("float16", "float32"),
        default="float16",
        help="VAE precision; float16 matches the official inference example",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Disable remote Hugging Face access and require local model/tokenizer files",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.max_chars_per_chunk < 0:
        raise ValueError("--max-chars-per-chunk must be >= 0")
    if args.pause_ms < 0:
        raise ValueError("--pause-ms must be >= 0")
    if args.nfe < 2:
        raise ValueError("--nfe must be >= 2")
    if args.guidance_strength < 0:
        raise ValueError("--guidance-strength must be >= 0")
    if args.duration_scale <= 0:
        raise ValueError("--duration-scale must be > 0")


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
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    return resolved


def require_model_path(path: Path) -> Path:
    model_path = require_path(path, "model path")
    if not model_path.is_dir():
        raise NotADirectoryError(f"model path is not a directory: {model_path}")
    required = ("config.json", "model.safetensors")
    missing = [name for name in required if not (model_path / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"model path is missing required file(s): {', '.join(missing)}; path={model_path}"
        )
    return model_path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    # Markdown 标题和列表符号不是要朗读的正文，先移除常见格式标记。
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    return text.strip()


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'["“”‘’]', " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_generation_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.text is not None and args.text.strip():
        return normalize_text(args.text), "--text"
    text_path = require_path(args.text_file, "text file")
    return normalize_text(read_text(text_path)), str(text_path)


def split_text(text: str, max_chars: int) -> list[str]:
    if not text:
        raise ValueError("synthesis text is empty")
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


def read_prompt_text(args: argparse.Namespace) -> str | None:
    if args.prompt_text_file is not None:
        prompt_text = read_text(require_path(args.prompt_text_file, "prompt text file"))
        return normalize_text(prompt_text) or None
    if args.prompt_text is not None and args.prompt_text.strip():
        return normalize_text(args.prompt_text)
    return None


def approx_duration_from_text(text: str, max_duration: float = 30.0) -> float:
    en_dur_per_char = 0.082
    zh_dur_per_char = 0.21
    compact_text = re.sub(r"\s+", "", text)
    num_zh = 0
    num_en = 0
    num_other = 0

    for char in compact_text:
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

        import audiodit  # noqa: F401  # 注册 AudioDiTConfig/AudioDiTModel
        from audiodit import AudioDiTModel
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "LongCat-AudioDiT runtime is not importable. Install the official requirements "
            "in the LongCat-AudioDiT-3.5B-bf16 conda environment, ensure the dependency "
            "repository is available at ~/tts-depency/LongCat-AudioDiT or provide --repo-path, "
            f"and retry. Missing import: {exc.name or exc}"
        ) from exc
    return AudioDiTModel, AutoTokenizer, F, librosa, np, sf, torch


def load_tokenizer(AutoTokenizer: Any, tokenizer_source: str, local_files_only: bool):
    kwargs = {"local_files_only": local_files_only, "fix_mistral_regex": True}
    try:
        return AutoTokenizer.from_pretrained(tokenizer_source, **kwargs)
    except TypeError:
        # 兼容较旧版本 transformers 不认识 fix_mistral_regex 的情况。
        kwargs.pop("fix_mistral_regex")
        return AutoTokenizer.from_pretrained(tokenizer_source, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"无法加载 UMT5 tokenizer: {tokenizer_source}。请准备 tokenizer.json、"
            f"spiece.model 和 tokenizer_config.json；原始错误：{exc}"
        ) from exc


def resolve_tokenizer_source(args: argparse.Namespace, model: Any) -> str:
    if args.tokenizer_path is not None:
        return str(require_path(args.tokenizer_path, "tokenizer path"))
    if TOKENIZER_PATH.exists():
        return str(TOKENIZER_PATH.resolve())
    return str(model.config.text_encoder_model)


def require_cuda(torch: Any) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for LongCat-AudioDiT-3.5B-bf16 synthesis.")
    return "cuda"


def set_seed(torch: Any, seed: int) -> None:
    if seed < 0:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def apply_vae_dtype(model: Any, torch: Any, dtype: str) -> None:
    if dtype == "float16" and hasattr(model.vae, "to_half"):
        model.vae.to_half()
        return
    target_dtype = {"float16": torch.float16, "float32": torch.float32}[dtype]
    model.vae.to(target_dtype)


def load_prompt_audio(path: Path, sample_rate: int, librosa: Any, torch: Any):
    audio, _ = librosa.load(str(path), sr=sample_rate, mono=True)
    return torch.from_numpy(audio).float().unsqueeze(0).unsqueeze(0)


def prompt_latent_frames(
    model: Any,
    prompt_audio: Any,
    full_hop: int,
    device: str,
    F: Any,
    torch: Any,
) -> int:
    off = 3
    prompt = prompt_audio.squeeze(0)
    if prompt.shape[-1] % full_hop != 0:
        prompt = F.pad(prompt, (0, full_hop - prompt.shape[-1] % full_hop))
    prompt = F.pad(prompt, (0, full_hop * off))

    with torch.inference_mode():
        latents = model.vae.encode(prompt.unsqueeze(0).to(device=device))
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

    gen_duration *= duration_scale
    gen_frames = max(1, int(gen_duration * sample_rate // full_hop))
    max_frames = max(1, int(max_duration * sample_rate // full_hop))
    return min(prompt_frames + gen_frames, max_frames)


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


def model_dtype_summary(model: Any) -> str:
    dtypes = sorted({str(parameter.dtype) for parameter in model.parameters()})
    return ", ".join(dtypes)


def synthesize(args: argparse.Namespace) -> Path:
    validate_args(args)
    maybe_add_repo_path(args.repo_path)
    AudioDiTModel, AutoTokenizer, F, librosa, np, sf, torch = import_runtime()

    model_path = require_model_path(args.model_path)
    ref_audio = require_path(args.ref_audio, "reference audio")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.local_files_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    device = require_cuda(torch)
    torch.backends.cudnn.benchmark = False
    set_seed(torch, args.seed)

    text, text_source = read_generation_text(args)
    chunks = split_text(text, args.max_chars_per_chunk)
    prompt_text = read_prompt_text(args)

    print(f"model: {model_path}")
    print(f"text source: {text_source} ({len(text)} chars)")
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
    model = AudioDiTModel.from_pretrained(
        str(model_path),
        local_files_only=args.local_files_only,
    ).to(device)
    apply_vae_dtype(model, torch, args.vae_dtype)
    model.eval()
    print(f"model parameter dtypes: {model_dtype_summary(model)}")

    tokenizer_source = resolve_tokenizer_source(args, model)
    tokenizer = load_tokenizer(AutoTokenizer, tokenizer_source, args.local_files_only)
    print(f"tokenizer: {tokenizer_source}")

    sample_rate = int(model.config.sampling_rate)
    full_hop = int(model.config.latent_hop)
    max_duration = float(model.config.max_wav_duration)
    prompt_audio = load_prompt_audio(ref_audio, sample_rate, librosa, torch)
    prompt_frames = prompt_latent_frames(model, prompt_audio, full_hop, device, F, torch)
    prompt_time = prompt_frames * full_hop / sample_rate
    if prompt_time >= max_duration:
        raise ValueError(
            f"reference audio is too long for model max_wav_duration={max_duration}s: "
            f"{prompt_time:.2f}s"
        )
    print(f"sample_rate: {sample_rate} Hz")
    print(f"prompt_duration: {prompt_time:.2f}s ({prompt_frames} latent frames)")

    waveforms = []
    with torch.inference_mode():
        for index, chunk in enumerate(chunks, start=1):
            if args.seed >= 0:
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
                prompt_audio=prompt_audio.to(device),
                duration=duration,
                steps=args.nfe,
                cfg_strength=args.guidance_strength,
                guidance_method=args.guidance_method,
            )
            waveforms.append(output.waveform.squeeze().detach().cpu().numpy())

    waveform = join_waveforms(waveforms, sample_rate, args.pause_ms, np)
    elapsed = time.perf_counter() - started
    output_name = f"{model_path.name}_{elapsed:.2f}s_{sample_rate / 1000:g}khz.wav"
    output_path = output_dir / output_name
    sf.write(str(output_path), waveform, sample_rate)

    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample rate: {sample_rate} Hz ({sample_rate / 1000:g} kHz)")
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
