"""
使用本地 Stable Audio 3 Small-SFX 模型根据文字提示生成音效。

默认模型目录：~/hf-mirror/stabilityai/stable-audio-3-small-sfx
默认输出目录：samples/stable-audio-3-small-sfx

最小运行示例：
  python modelScript/tts_local_stable_audio_3_small_sfx.py \
    --prompt "A steam train entering a station and blowing its horn" \
    --duration 7 \
    --local-files-only

Stable Audio 3 Small-SFX 是 text-to-audio（文字生成音频）模型，不是语音合成或声音克隆模型。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "STABLE_AUDIO_3_SMALL_SFX_MODEL_PATH",
        str(Path.home() / "hf-mirror/stabilityai/stable-audio-3-small-sfx"),
    )
).expanduser()
UPSTREAM_PATH = Path(
    os.environ.get(
        "STABLE_AUDIO_3_REPO_PATH",
        str(Path.home() / "tts-depency/stable-audio-3"),
    )
).expanduser()
OUTPUT_DIR = REPO_ROOT / "samples/stable-audio-3-small-sfx"
MAX_DURATION_SECONDS = 120.0
DEFAULT_PROMPT = "A short, clean cinematic sound effect of a steam train entering a station and blowing its horn."
REQUIRED_MODEL_FILES = (
    "model_config.json",
    "model.safetensors",
    "t5gemma-b-b-ul2/config.json",
    "t5gemma-b-b-ul2/model.safetensors",
    "t5gemma-b-b-ul2/tokenizer.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local Stable Audio 3 Small-SFX text-to-audio generation"
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=MODEL_PATH,
        help="Local Stable Audio 3 Small-SFX model directory",
    )
    parser.add_argument(
        "--upstream-path",
        type=Path,
        default=UPSTREAM_PATH,
        help="Official stable-audio-3 source directory containing the stable_audio_3 package",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="English sound-effect description; cannot be combined with --prompt-file",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=None,
        help="UTF-8 text or Markdown file containing the sound-effect description",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=7.0,
        help="Generated audio duration in seconds; Small-SFX supports up to 120 seconds",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=8,
        help="Diffusion sampling steps; 8 is the official post-trained default",
    )
    parser.add_argument(
        "--cfg-scale",
        type=float,
        default=1.0,
        help="Classifier-free guidance scale; 1.0 is the official post-trained default",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="Random seed; use -1 for a new random result on every run",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Inference device; auto selects CUDA when available, otherwise CPU",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "float32"),
        default="auto",
        help="Model precision; auto uses float16 on CUDA and float32 on CPU",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for the generated WAV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Exact output path; when omitted a timestamped WAV name is created in --output-dir",
    )
    parser.add_argument(
        "--subtype",
        choices=("FLOAT", "PCM_16"),
        default="FLOAT",
        help="WAV sample subtype; FLOAT preserves the model's 32-bit waveform",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Disable Hugging Face network access and require all model files to be local",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.prompt is not None and args.prompt_file is not None:
        raise ValueError("--prompt and --prompt-file cannot be used together")
    if args.duration <= 0 or args.duration > MAX_DURATION_SECONDS:
        raise ValueError(f"--duration must be > 0 and <= {MAX_DURATION_SECONDS:g} seconds")
    if args.steps < 1:
        raise ValueError("--steps must be >= 1")
    if args.cfg_scale < 0:
        raise ValueError("--cfg-scale must be >= 0")


def require_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    return resolved


def require_model_path(path: Path) -> Path:
    model_path = require_path(path, "model path")
    if not model_path.is_dir():
        raise NotADirectoryError(f"model path is not a directory: {model_path}")

    missing = [name for name in REQUIRED_MODEL_FILES if not (model_path / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "model path is missing required file(s): "
            + ", ".join(missing)
            + f"; path={model_path}"
        )
    return model_path


def read_prompt_file(path: Path) -> str:
    prompt = require_path(path, "prompt file").read_text(encoding="utf-8")
    # Markdown 标题和列表符号不是音效提示词内容，移除常见格式标记。
    prompt = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*", "", prompt)
    prompt = re.sub(r"(?m)^[ \t]*[-*+][ \t]+", "", prompt)
    return prompt.strip()


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file is not None:
        prompt = read_prompt_file(args.prompt_file)
    elif args.prompt is not None:
        prompt = args.prompt.strip()
    else:
        prompt = DEFAULT_PROMPT
    if not prompt:
        raise ValueError("sound-effect prompt is empty")
    return prompt


def resolve_device(requested: str, torch) -> str:
    cuda_available = bool(torch.cuda.is_available())
    if requested == "cuda" and not cuda_available:
        raise RuntimeError("--device cuda was requested, but torch.cuda.is_available() is False")
    if requested == "auto":
        return "cuda" if cuda_available else "cpu"
    return requested


def resolve_model_half(dtype: str, device: str) -> bool:
    if dtype == "float16" and device != "cuda":
        raise ValueError("--dtype float16 requires --device cuda")
    if dtype == "float32":
        return False
    return device == "cuda"


def maybe_add_upstream_path(upstream_path: Path | None) -> None:
    if upstream_path is None:
        return
    candidate = upstream_path.expanduser().resolve()
    if (candidate / "stable_audio_3").is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def import_runtime(upstream_path: Path | None = None):
    maybe_add_upstream_path(upstream_path)
    try:
        import soundfile as sf
        import torch
        from stable_audio_3.loading_utils import load_diffusion_cond
        from stable_audio_3.model import StableAudioModel
    except ImportError as exc:
        raise RuntimeError(
            "Stable Audio 3 runtime is not importable. Install the official stable-audio-3 "
            "dependencies in the stable_audio_3_small_sfx conda environment. "
            f"Missing import: {exc.name or exc}"
        ) from exc
    return StableAudioModel, load_diffusion_cond, sf, torch


def patch_local_text_encoder_path(model_config: dict[str, Any], model_path: Path) -> dict[str, Any]:
    """让官方库从本地模型目录读取 T5Gemma，而不是访问远程仓库。"""
    local_config = copy.deepcopy(model_config)
    conditioning = local_config.get("model", {}).get("conditioning", {})
    prompt_configs = [item for item in conditioning.get("configs", []) if item.get("id") == "prompt"]
    if not prompt_configs:
        raise ValueError("model_config.json does not contain a prompt conditioner")

    local_text_encoder = (model_path / "t5gemma-b-b-ul2").resolve()
    for item in prompt_configs:
        config = item.setdefault("config", {})
        # stable-audio-3 的 T5GemmaConditioner 支持 model_path；删除 subfolder
        # 可以兼容直接传本地子目录的 transformers 加载方式。
        config["model_path"] = str(local_text_encoder)
        config.pop("repo_id", None)
        config.pop("subfolder", None)
    return local_config


def load_local_model(model_path: Path, upstream_path: Path, device: str, model_half: bool):
    StableAudioModel, load_diffusion_cond, _, _ = import_runtime(upstream_path)
    config_path = model_path / "model_config.json"
    checkpoint_path = model_path / "model.safetensors"
    model_config = json.loads(config_path.read_text(encoding="utf-8"))
    model_config = patch_local_text_encoder_path(model_config, model_path)

    diffusion_model = load_diffusion_cond(
        model_config,
        str(checkpoint_path),
        device=device,
        model_half=model_half,
    )
    diffusion_model.use_lora = False
    diffusion_model.lora_names = []
    return StableAudioModel(diffusion_model, model_config, device, model_half)


def model_sample_rate(model) -> int:
    sample_rate = model.model_config.get("sample_rate")
    if sample_rate is None:
        sample_rate = getattr(model.model, "sample_rate", None)
    if sample_rate is None:
        raise RuntimeError("could not resolve Stable Audio 3 sample rate")
    return int(sample_rate)


def audio_to_numpy(audio, torch):
    waveform = audio.detach().to(torch.float32).cpu().numpy()
    if waveform.ndim == 3:
        if waveform.shape[0] != 1:
            raise RuntimeError(f"expected batch size 1, got waveform shape {waveform.shape}")
        waveform = waveform[0]
    if waveform.ndim == 1:
        waveform = waveform[:, None]
    elif waveform.ndim == 2:
        # Stable Audio 3 returns (channels, samples); soundfile expects (samples, channels).
        if waveform.shape[0] <= 8:
            waveform = waveform.T
    else:
        raise RuntimeError(f"unexpected generated waveform shape: {waveform.shape}")
    return waveform


def output_path(args: argparse.Namespace, model_path: Path, elapsed: float, sample_rate: int) -> Path:
    if args.output is not None:
        target = args.output.expanduser().resolve()
    else:
        target = (
            args.output_dir.expanduser().resolve()
            / f"{model_path.name}_{elapsed:.2f}s_{sample_rate / 1000:g}khz.wav"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def synthesize(args: argparse.Namespace) -> Path:
    validate_args(args)
    model_path = require_model_path(args.model_path)
    prompt = read_prompt(args)

    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    _, _, sf, torch = import_runtime(args.upstream_path)
    device = resolve_device(args.device, torch)
    model_half = resolve_model_half(args.dtype, device)

    print(f"model: {model_path}")
    print(f"prompt: {prompt}")
    print(f"duration: {args.duration:g}s")
    print(f"device: {device}")
    print(f"precision: {'float16' if model_half else 'float32'}")
    print(f"steps: {args.steps}; cfg_scale: {args.cfg_scale:g}; seed: {args.seed}")

    started = time.perf_counter()
    model = load_local_model(model_path, args.upstream_path, device, model_half)
    with torch.inference_mode():
        audio = model.generate(
            prompt=prompt,
            duration=args.duration,
            steps=args.steps,
            cfg_scale=args.cfg_scale,
            seed=args.seed,
            batch_size=1,
        )

    sample_rate = model_sample_rate(model)
    waveform = audio_to_numpy(audio, torch)
    elapsed = time.perf_counter() - started
    target = output_path(args, model_path, elapsed, sample_rate)
    sf.write(str(target), waveform, sample_rate, subtype=args.subtype)

    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample rate: {sample_rate} Hz ({sample_rate / 1000:g} kHz)")
    print(f"channels: {waveform.shape[1]}")
    print(f"duration: {waveform.shape[0] / sample_rate:.2f}s")
    print(f"output: {target}")
    return target


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
