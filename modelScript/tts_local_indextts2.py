"""Use local IndexTTS2 for zero-shot voice-clone synthesis.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/IndexTTS-2_${timestamp}.wav

Usage:
  python modelScript/tts_local_indextts2.py --local-files-only

IndexTTS2 owns its own token-level long-text segmentation, so this script
passes the complete source text to the official infer_v2 runtime.
"""

from __future__ import annotations

import argparse
import gc
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "INDEXTTS_MODEL_PATH",
        os.environ.get("INDEXTTS_MODEL_DIR", "/path/to/IndexTTS-2"),
    )
)
CONFIG_PATH = os.environ.get("INDEXTTS_CONFIG_PATH")
CODE_PATH = os.environ.get("INDEXTTS_CODE_PATH", os.environ.get("INDEXTTS_CODE_DIR"))
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
RUNTIME_CACHE_DIR = REPO_ROOT / "work" / "runtime_cache" / "indextts2"
REQUIRED_MODEL_FILES = (
    "bpe.model",
    "wav2vec2bert_stats.pt",
    "gpt.pth",
    "s2mel.pth",
    "feat2.pt",
    "feat1.pt",
    "qwen0.6bemo4-merge/config.json",
    "qwen0.6bemo4-merge/model.safetensors",
    "qwen0.6bemo4-merge/tokenizer.json",
    "qwen0.6bemo4-merge/tokenizer_config.json",
)
REQUIRED_AUX_FILES = (
    "hf_cache/w2v-bert-2.0/config.json",
    "hf_cache/w2v-bert-2.0/preprocessor_config.json",
    "hf_cache/semantic_codec_model.safetensors",
    "hf_cache/campplus_cn_common.bin",
    "hf_cache/bigvgan/config.json",
    "hf_cache/bigvgan/bigvgan_generator.pt",
)


def parse_args() -> argparse.Namespace:
    """Parse standalone IndexTTS2 synthesis options."""
    parser = argparse.ArgumentParser(description="Local IndexTTS2 voice-clone synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="IndexTTS-2 checkpoint directory")
    parser.add_argument(
        "--config-path",
        type=Path,
        default=Path(CONFIG_PATH) if CONFIG_PATH else None,
        help="IndexTTS2 config.yaml; defaults to <model-path>/config.yaml",
    )
    parser.add_argument(
        "--code-path",
        type=Path,
        default=Path(CODE_PATH) if CODE_PATH else None,
        help="Optional index-tts source directory containing the indextts package",
    )
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Text/Markdown file to synthesize")
    parser.add_argument("--ref-audio", type=Path, default=REF_AUDIO, help="Speaker reference audio")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR, help="Directory used when --output is omitted")
    parser.add_argument("--output", type=Path, default=None, help="Exact output WAV path")
    parser.add_argument("--emo-audio", type=Path, default=None, help="Optional emotion reference audio")
    parser.add_argument("--emo-text", default=None, help="Optional emotion description text")
    parser.add_argument(
        "--emo-vector",
        default=None,
        help="Eight comma-separated emotion weights: happy, angry, sad, fearful, disgusted, melancholy, surprised, calm",
    )
    parser.add_argument("--emo-alpha", type=float, default=1.0, help="Emotion-reference blend strength")
    parser.add_argument("--num-beams", type=int, default=1, help="Autoregressive beam count")
    parser.add_argument("--interval-silence", type=int, default=200, help="Model-native segment silence in milliseconds")
    parser.add_argument(
        "--max-text-tokens-per-segment",
        type=int,
        default=120,
        help="Maximum text tokens handled by each native IndexTTS2 segment",
    )
    parser.add_argument("--device", default=None, help="Torch device; defaults to the IndexTTS2 runtime auto-selection")
    parser.add_argument(
        "--use-fp16",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use FP16 on CUDA (default: enabled)",
    )
    parser.add_argument(
        "--use-cuda-kernel",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable the optional BigVGAN fused CUDA kernel",
    )
    parser.add_argument("--use-deepspeed", action="store_true", help="Enable optional DeepSpeed acceleration")
    parser.add_argument("--use-accel", action="store_true", help="Enable the IndexTTS2 acceleration engine")
    parser.add_argument("--use-torch-compile", action="store_true", help="Enable torch.compile optimization")
    parser.add_argument(
        "--local-files-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require local checkpoints and auxiliary models (default: enabled)",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow very slow CPU inference when CUDA is unavailable",
    )
    parser.add_argument(
        "--runtime-cache-dir",
        type=Path,
        default=RUNTIME_CACHE_DIR,
        help="Writable cache directory for Hugging Face, Numba, and Matplotlib",
    )
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    """Resolve and validate a required file or directory."""
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label}不存在：{resolved}")
    return resolved


def read_text(path: Path) -> str:
    """Read source prose while removing Markdown markers from speech input."""
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def parse_emo_vector(value: str | None) -> list[float] | None:
    """Parse and validate the eight-dimensional IndexTTS2 emotion vector."""
    if value is None or not value.strip():
        return None
    try:
        vector = [float(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise ValueError("--emo-vector 必须是八个以逗号分隔的数字。") from exc
    if len(vector) != 8:
        raise ValueError("--emo-vector 必须包含八个值。")
    if not all(math.isfinite(item) and 0.0 <= item <= 1.0 for item in vector):
        raise ValueError("--emo-vector 的每个值必须位于 0.0 到 1.0 之间。")
    return vector


def missing_relative_files(base_dir: Path, relative_paths: tuple[str, ...]) -> list[str]:
    """Return model artifacts that are missing from a checkpoint directory."""
    return [relative for relative in relative_paths if not (base_dir / relative).is_file()]


def model_file_status(model_path: Path, config_path: Path) -> dict[str, list[str]]:
    """Inspect all required IndexTTS2 main and auxiliary local artifacts."""
    main_missing = missing_relative_files(model_path, REQUIRED_MODEL_FILES)
    aux_missing = missing_relative_files(model_path, REQUIRED_AUX_FILES)
    config_missing = [] if config_path.is_file() else [str(config_path)]
    return {
        "main_missing": main_missing,
        "aux_missing": aux_missing,
        "config_missing": config_missing,
    }


def require_model_assets(model_path: Path, config_path: Path) -> None:
    """Fail before loading when the offline model bundle is incomplete."""
    if not model_path.is_dir():
        raise FileNotFoundError(f"模型目录不存在：{model_path}")
    status = model_file_status(model_path, config_path)
    problems = []
    if status["config_missing"]:
        problems.append("配置文件缺失：" + ", ".join(status["config_missing"]))
    if status["main_missing"]:
        problems.append("主模型文件缺失：" + ", ".join(status["main_missing"]))
    if status["aux_missing"]:
        problems.append("辅助模型文件缺失：" + ", ".join(status["aux_missing"]))
    if problems:
        raise FileNotFoundError("；".join(problems))


def resolve_aux_paths(model_path: Path) -> dict[str, str]:
    """Map the official IndexTTS2 auxiliary artifacts to infer_v2 arguments."""
    aux_dir = model_path / "hf_cache"
    return {
        "w2v_bert": str(aux_dir / "w2v-bert-2.0"),
        "semantic_codec": str(aux_dir / "semantic_codec_model.safetensors"),
        "campplus": str(aux_dir / "campplus_cn_common.bin"),
        "bigvgan": str(aux_dir / "bigvgan"),
    }


def add_code_path(code_path: Path | None) -> None:
    """Expose a locally cloned official source tree without installing it globally."""
    if code_path is None:
        return
    resolved = require_path(code_path, "IndexTTS源码目录")
    if not resolved.is_dir():
        raise NotADirectoryError(f"IndexTTS源码目录不是目录：{resolved}")
    if str(resolved) not in sys.path:
        sys.path.insert(0, str(resolved))


def prepare_environment(args: argparse.Namespace) -> None:
    """Set per-project writable caches before importing IndexTTS2 dependencies."""
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
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)


def import_runtime() -> tuple[Any, Any]:
    """Import IndexTTS2 only after all local paths and caches are ready."""
    try:
        import torch
        from indextts.infer_v2 import IndexTTS2
    except ImportError as exc:
        raise RuntimeError(
            "IndexTTS2运行时不可导入。请使用 index-tts 的 uv 环境运行，或传入 --code-path。"
            f"缺失导入：{exc.name or exc}"
        ) from exc
    return IndexTTS2, torch


def output_path(args: argparse.Namespace) -> Path:
    """Choose the caller-provided output path or build a collision-safe default."""
    if args.output is not None:
        return args.output.expanduser().resolve()
    return args.output_dir.expanduser().resolve() / f"IndexTTS-2_{time.time_ns()}.wav"


def clear_cuda_cache(torch: Any) -> None:
    """Release cached CUDA memory after the model object is discarded."""
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
    """Load IndexTTS2, synthesize once with its native text segmentation, then unload."""
    prepare_environment(args)
    model_path = require_path(args.model_path, "模型目录")
    config_path = (args.config_path or model_path / "config.yaml").expanduser().resolve()
    require_model_assets(model_path, config_path)
    text_file = require_path(args.text_file, "合成文本")
    ref_audio = require_path(args.ref_audio, "参考音频")
    emo_audio = require_path(args.emo_audio, "情感参考音频") if args.emo_audio is not None else None
    add_code_path(args.code_path)
    IndexTTS2, torch = import_runtime()
    if not torch.cuda.is_available() and not args.allow_cpu and args.device != "cpu":
        raise RuntimeError("IndexTTS2默认需要CUDA GPU；仅在明确接受缓慢推理时使用 --allow-cpu。")

    destination = output_path(args)
    destination.parent.mkdir(parents=True, exist_ok=True)
    model = None
    started = time.perf_counter()
    try:
        model = IndexTTS2(
            model_dir=str(model_path),
            cfg_path=str(config_path),
            aux_paths=resolve_aux_paths(model_path),
            device=args.device,
            use_fp16=args.use_fp16,
            use_cuda_kernel=args.use_cuda_kernel,
            use_deepspeed=args.use_deepspeed,
            use_accel=args.use_accel,
            use_torch_compile=args.use_torch_compile,
        )
        model.infer(
            spk_audio_prompt=str(ref_audio),
            text=read_text(text_file),
            output_path=str(destination),
            emo_audio_prompt=str(emo_audio) if emo_audio is not None else None,
            emo_alpha=args.emo_alpha,
            emo_vector=parse_emo_vector(args.emo_vector),
            use_emo_text=bool(args.emo_text and args.emo_text.strip()),
            emo_text=args.emo_text.strip() if args.emo_text and args.emo_text.strip() else None,
            interval_silence=args.interval_silence,
            max_text_tokens_per_segment=args.max_text_tokens_per_segment,
            num_beams=args.num_beams,
            verbose=True,
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("IndexTTS2未生成有效的WAV文件。")
        elapsed = time.perf_counter() - started
        print(f"完成：{destination}（耗时 {elapsed:.2f}s）")
        return destination
    finally:
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
