#!/usr/bin/env python3
"""Task 9 专用的 IndexTTS2 离线旁白克隆脚本。"""

from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MODEL_FILES = (
    "config.yaml",
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
    "hf_cache/w2v-bert-2.0/config.json",
    "hf_cache/w2v-bert-2.0/preprocessor_config.json",
    "hf_cache/semantic_codec_model.safetensors",
    "hf_cache/campplus_cn_common.bin",
    "hf_cache/bigvgan/config.json",
    "hf_cache/bigvgan/bigvgan_generator.pt",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True, help="IndexTTS-2 本地模型目录")
    parser.add_argument("--code-path", type=Path, required=True, help="含 indextts 包的官方源码目录")
    parser.add_argument("--text-file", type=Path, required=True, help="要合成的 UTF-8 原文")
    parser.add_argument("--ref-audio", type=Path, required=True, help="旁白参考 WAV")
    parser.add_argument("--output", type=Path, required=True, help="精确目标 WAV 路径")
    parser.add_argument("--emo-text", default="", help="可选情感/风格描述")
    parser.add_argument("--device", default="cuda", help="推理设备，默认 cuda")
    parser.add_argument("--max-text-tokens-per-segment", type=int, default=80, help="原生单段最大 token 数")
    parser.add_argument("--max-mel-tokens", type=int, default=1200, help="单段最大 mel token 数")
    parser.add_argument("--no-fp16", action="store_true", help="关闭 CUDA FP16")
    parser.add_argument("--use-cuda-kernel", action="store_true", help="启用可选 BigVGAN CUDA 内核")
    parser.add_argument("--local-files-only", action="store_true", help="禁止 Hugging Face 联网下载")
    parser.add_argument(
        "--runtime-cache-dir",
        type=Path,
        default=PROJECT_ROOT / "work" / "runtime_cache" / "task9-indextts2",
        help="可写的运行时缓存目录",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label}不存在：{resolved}")
    if resolved.stat().st_size == 0:
        raise ValueError(f"{label}为空：{resolved}")
    return resolved


def require_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"{label}不存在：{resolved}")
    return resolved


def validate_model_assets(model_path: Path) -> None:
    missing = [relative for relative in REQUIRED_MODEL_FILES if not (model_path / relative).is_file()]
    if missing:
        raise FileNotFoundError("IndexTTS2 模型文件缺失：" + ", ".join(missing))


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"合成原文为空：{path}")
    return text


def auxiliary_paths(model_path: Path) -> dict[str, str]:
    cache_dir = model_path / "hf_cache"
    return {
        "w2v_bert": str(cache_dir / "w2v-bert-2.0"),
        "semantic_codec": str(cache_dir / "semantic_codec_model.safetensors"),
        "campplus": str(cache_dir / "campplus_cn_common.bin"),
        "bigvgan": str(cache_dir / "bigvgan"),
    }


def prepare_environment(args: argparse.Namespace) -> None:
    cache_dir = args.runtime_cache_dir.expanduser().resolve()
    for name, path in {
        "HF_MODULES_CACHE": cache_dir / "hf_modules",
        "NUMBA_CACHE_DIR": cache_dir / "numba",
        "MPLCONFIGDIR": cache_dir / "matplotlib",
        "XDG_CACHE_HOME": cache_dir / "xdg",
    }.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


def import_runtime(code_path: Path) -> tuple[Any, Any]:
    if str(code_path) not in sys.path:
        sys.path.insert(0, str(code_path))
    try:
        import torch
        from indextts.infer_v2 import IndexTTS2
    except ImportError as exc:
        raise RuntimeError(f"无法导入 IndexTTS2 运行时：{exc.name or exc}") from exc
    return IndexTTS2, torch


def clear_cuda_cache(torch: Any) -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def run(args: argparse.Namespace) -> Path:
    model_path = require_directory(args.model_path, "IndexTTS2 模型目录")
    code_path = require_directory(args.code_path, "IndexTTS2 源码目录")
    text_file = require_file(args.text_file, "合成原文")
    reference_audio = require_file(args.ref_audio, "参考音频")
    validate_model_assets(model_path)
    prepare_environment(args)
    IndexTTS2, torch = import_runtime(code_path)
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("IndexTTS2 要求 CUDA，但当前环境不可用。")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = None
    try:
        model = IndexTTS2(
            model_dir=str(model_path),
            cfg_path=str(model_path / "config.yaml"),
            aux_paths=auxiliary_paths(model_path),
            device=args.device,
            use_fp16=not args.no_fp16,
            use_cuda_kernel=args.use_cuda_kernel,
        )
        emo_text = args.emo_text.strip()
        with torch.inference_mode():
            model.infer(
                spk_audio_prompt=str(reference_audio),
                text=read_text(text_file),
                output_path=str(output),
                use_emo_text=bool(emo_text),
                emo_text=emo_text or None,
                max_text_tokens_per_segment=max(20, args.max_text_tokens_per_segment),
                max_mel_tokens=max(256, args.max_mel_tokens),
                num_beams=1,
                verbose=True,
            )
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"IndexTTS2 未生成有效音频：{output}")
        return output
    finally:
        del model
        clear_cuda_cache(torch)


def main() -> int:
    try:
        output = run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"IndexTTS2 Task 9 合成失败：{error}", file=sys.stderr)
        return 2
    print(f"IndexTTS2 合成完成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
