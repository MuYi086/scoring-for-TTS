#!/usr/bin/env python3
"""Task 9 专用的 VoxCPM2 离线旁白克隆脚本。"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path
from typing import Any

from text_segments import join_waveforms, load_segment_plan, read_synthesis_text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True, help="VoxCPM2 本地模型目录")
    parser.add_argument("--text-file", type=Path, required=True, help="要合成的 UTF-8 原文")
    parser.add_argument("--ref-audio", type=Path, required=True, help="旁白参考 WAV")
    parser.add_argument("--prompt-text", required=True, help="参考音频的准确文案")
    parser.add_argument("--output", type=Path, required=True, help="精确目标 WAV 路径")
    parser.add_argument("--style-prompt", default="", help="可选风格前缀；默认空值为纯克隆")
    parser.add_argument("--segment-manifest", type=Path, required=True, help="两个模型共用的冻结分段清单")
    parser.add_argument("--cfg-value", type=float, default=2.0, help="分类器自由引导强度")
    parser.add_argument("--inference-timesteps", type=int, default=10, help="扩散推理步数")
    parser.add_argument("--seed", type=int, default=20260614, help="固定采样随机种子")
    parser.add_argument("--local-files-only", action="store_true", help="禁止 Hugging Face 联网下载")
    return parser.parse_args(argv)


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


def read_text(path: Path) -> str:
    return read_synthesis_text(path)


def import_runtime() -> tuple[Any, Any, Any, Any]:
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from voxcpm import VoxCPM
    except ImportError as exc:
        raise RuntimeError(f"无法导入 VoxCPM2 运行时：{exc.name or exc}") from exc
    return VoxCPM, np, sf, torch


def set_seed(seed: int, np: Any, torch: Any) -> None:
    if seed < 0:
        return
    import random

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def from_pretrained_kwargs(VoxCPM: Any) -> dict[str, Any]:
    signature = inspect.signature(VoxCPM.from_pretrained)
    supported = signature.parameters
    values = {"load_denoiser": False, "local_files_only": True, "optimize": False}
    if any(item.kind == inspect.Parameter.VAR_KEYWORD for item in supported.values()):
        return values
    return {name: value for name, value in values.items() if name in supported}


def generate_kwargs(model: Any, args: argparse.Namespace, text: str, reference_audio: Path) -> dict[str, Any]:
    style_prefix = args.style_prompt.strip()
    target_text = f"({style_prefix}){text}" if style_prefix else text
    values: dict[str, Any] = {
        "text": target_text,
        "reference_wav_path": str(reference_audio),
        "prompt_wav_path": str(reference_audio),
        "prompt_text": args.prompt_text.strip(),
        "cfg_value": args.cfg_value,
        "inference_timesteps": args.inference_timesteps,
    }
    signature = inspect.signature(model.generate)
    if any(item.kind == inspect.Parameter.VAR_KEYWORD for item in signature.parameters.values()):
        return values
    return {name: value for name, value in values.items() if name in signature.parameters}


def run(args: argparse.Namespace) -> Path:
    model_path = require_directory(args.model_path, "VoxCPM2 模型目录")
    text_file = require_file(args.text_file, "合成原文")
    reference_audio = require_file(args.ref_audio, "参考音频")
    if not args.prompt_text.strip():
        raise ValueError("参考音频文案不能为空。")
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    VoxCPM, np, sf, torch = import_runtime()
    if not torch.cuda.is_available():
        raise RuntimeError("VoxCPM2 合成需要 CUDA GPU。")
    set_seed(args.seed, np, torch)
    model = VoxCPM.from_pretrained(str(model_path), device="cuda", **from_pretrained_kwargs(VoxCPM))
    sample_rate = int(model.tts_model.sample_rate)
    try:
        with torch.inference_mode():
            segments = load_segment_plan(args.segment_manifest.expanduser().resolve(), read_text(text_file))
            waveforms = []
            for index, segment in enumerate(segments, start=1):
                chunk = str(segment["text"])
                print(f"VoxCPM2 合成片段 {index}/{len(segments)}（{len(chunk)} 字）", flush=True)
                waveforms.append(model.generate(**generate_kwargs(model, args, chunk, reference_audio)))
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        pauses = [int(item["pause_after_ms"]) for item in segments[:-1]]
        sf.write(str(output), join_waveforms(waveforms, sample_rate, pauses, np), sample_rate)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"VoxCPM2 未生成有效音频：{output}")
        return output
    finally:
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def main() -> int:
    try:
        output = run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"VoxCPM2 Task 9 合成失败：{error}", file=sys.stderr)
        return 2
    print(f"VoxCPM2 合成完成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
