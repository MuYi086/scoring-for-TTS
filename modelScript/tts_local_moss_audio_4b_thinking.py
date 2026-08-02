"""使用本地 MOSS-Audio-4B-Thinking 模型进行音频理解或转写。

虽然文件名沿用项目中的 ``tts_local_*`` 命名习惯，MOSS-Audio 本身是音频理解
模型，不会生成新的语音波形。本脚本读取音频，向模型提问，并将模型返回的文本
打印到终端；如指定 ``--output-path``，同时保存为 UTF-8 文本文件。

最小用法：

    python modelScript/tts_local_moss_audio_4b_thinking.py \
        --model-path ~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking \
        --audio-path ~/tts-depency/MOSS-Audio/test/test_zh.mp3 \
        --local-files-only
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = Path(
    os.environ.get(
        "MOSS_AUDIO_MODEL_PATH",
        "~/hf-mirror/OpenMOSS-Team/MOSS-Audio-4B-Thinking",
    )
).expanduser()
DEFAULT_DEPENDENCY_PATH = Path(
    os.environ.get("MOSS_AUDIO_DEPENDENCY_PATH", "~/tts-depency/MOSS-Audio")
).expanduser()
DEFAULT_AUDIO_PATH = Path(
    os.environ.get(
        "MOSS_AUDIO_AUDIO_PATH",
        "~/tts-depency/MOSS-Audio/test/test_zh.mp3",
    )
).expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用本地 MOSS-Audio-4B-Thinking 进行音频理解或转写"
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="本地 MOSS-Audio-4B-Thinking 模型目录",
    )
    parser.add_argument(
        "--dependency-path",
        type=Path,
        default=DEFAULT_DEPENDENCY_PATH,
        help="本地 MOSS-Audio 源码目录，至少包含 src/",
    )
    parser.add_argument(
        "--audio-path",
        type=Path,
        default=DEFAULT_AUDIO_PATH,
        help="待理解或转写的音频文件",
    )
    parser.add_argument(
        "--prompt",
        "--question",
        dest="prompt",
        default="请准确转写这段音频，仅输出转写文本。",
        help="向模型提出的问题或任务指令",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="可选的 UTF-8 文本输出路径；不指定时只打印到终端",
    )
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="模型设备映射，默认 cuda:0；4B 模型建议使用 CUDA",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "bfloat16", "float16"),
        default="auto",
        help="模型加载精度，auto 会遵循模型配置",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=1024,
        help="最多生成的文本 token 数",
    )
    parser.add_argument(
        "--do-sample",
        action="store_true",
        help="启用采样；默认关闭以便转写结果更稳定",
    )
    parser.add_argument("--temperature", type=float, default=1.0, help="采样温度")
    parser.add_argument("--top-p", type=float, default=1.0, help="采样 top-p")
    parser.add_argument("--top-k", type=int, default=50, help="采样 top-k")
    parser.add_argument(
        "--no-time-marker",
        action="store_false",
        dest="enable_time_marker",
        default=True,
        help="关闭处理器中的时间标记 token",
    )
    parser.add_argument(
        "--strip-thinking",
        action="store_true",
        help="去除 Thinking 模型返回的 <think>...</think> 推理段，只保留最终答案",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="只从本地模型与 tokenizer 文件加载，并设置 Hugging Face 离线变量",
    )
    return parser.parse_args()


def require_path(path: Path, label: str, *, directory: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    exists_as_expected = resolved.is_dir() if directory else resolved.is_file()
    if not exists_as_expected:
        kind = "目录" if directory else "文件"
        raise FileNotFoundError(f"{label}{kind}不存在: {resolved}")
    return resolved


def load_runtime(dependency_path: Path):
    """从指定的 MOSS-Audio 源码目录导入运行时，避免依赖机器当前工作目录。"""

    dependency_path = require_path(dependency_path, "MOSS-Audio 依赖源码", directory=True)
    source_path = dependency_path / "src"
    if not source_path.is_dir():
        raise FileNotFoundError(f"MOSS-Audio 依赖源码目录不存在: {source_path}")

    dependency_string = str(dependency_path)
    if dependency_string not in sys.path:
        sys.path.insert(0, dependency_string)

    try:
        import torch
        from src.audio_io import load_audio
        from src.modeling_moss_audio import MossAudioModel
        from src.processing_moss_audio import MossAudioProcessor
    except ImportError as exc:
        raise RuntimeError(
            "MOSS-Audio 运行时导入失败，请在 moss-audio-4b-thinking 环境中安装 "
            "torch、torchaudio、transformers、accelerate、soundfile 等依赖。"
            f"缺少或无法导入: {exc}"
        ) from exc
    return torch, load_audio, MossAudioModel, MossAudioProcessor


def resolve_device(torch, device: str) -> str:
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA 不可用，MOSS-Audio-4B-Thinking 默认要求 GPU。"
            "请检查 NVIDIA 驱动和 CUDA 版 PyTorch，或显式传入 --device cpu 进行兼容性排查。"
        )
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("请求使用 MPS，但当前 PyTorch 未检测到可用的 MPS 设备。")
    return device


def set_offline_mode() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def build_generation_kwargs(args: argparse.Namespace) -> dict:
    kwargs = {
        "max_new_tokens": args.max_new_tokens,
        "num_beams": 1,
        "use_cache": True,
        "do_sample": args.do_sample,
    }
    if args.do_sample:
        kwargs.update(
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
        )
    return kwargs


def load_audio_compat(load_audio, audio_path: Path, sample_rate: int):
    """调用 MOSS 官方加载器，并在 TorchCodec 不可用时回退到 ffmpeg。"""

    try:
        return load_audio(str(audio_path), sample_rate=sample_rate)
    except (ImportError, RuntimeError) as exc:
        message = str(exc).lower()
        if "torchcodec" not in message:
            raise

    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("ffmpeg 回退需要 numpy，但当前环境无法导入 numpy。") from exc

    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "f32le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "torchaudio 需要 TorchCodec，且系统中找不到 ffmpeg 回退工具。"
            "请安装 torchcodec==0.9.* 或在 PATH 中安装 ffmpeg。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg 无法读取音频 {audio_path}: {detail}") from exc

    audio = np.frombuffer(completed.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise RuntimeError(f"ffmpeg 未输出音频采样: {audio_path}")
    print("notice: TorchCodec 不可用，已使用 ffmpeg 音频加载回退。")
    return audio


def strip_thinking(text: str) -> str:
    """提取 ``</think>`` 后的最终回答；没有完整推理段时原样返回。"""

    match = re.search(r"</think>\s*(.*)", text, flags=re.DOTALL | re.IGNORECASE)
    if match is None:
        return text.strip()
    return match.group(1).strip()


def write_output(path: Path, text: str) -> Path:
    output_path = path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return output_path


def run_inference(args: argparse.Namespace) -> str:
    if args.local_files_only:
        set_offline_mode()

    model_path = require_path(args.model_path, "模型", directory=True)
    audio_path = require_path(args.audio_path, "音频")
    torch, load_audio, MossAudioModel, MossAudioProcessor = load_runtime(
        args.dependency_path
    )
    device = resolve_device(torch, args.device)

    print(f"model: {model_path}")
    print(f"audio: {audio_path}")
    print(f"device: {device}")
    print(f"prompt: {args.prompt}")

    started = time.perf_counter()
    model = MossAudioModel.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        dtype=args.dtype,
        device_map=device,
        local_files_only=args.local_files_only,
    )
    model.eval()
    processor = MossAudioProcessor.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        enable_time_marker=args.enable_time_marker,
        local_files_only=args.local_files_only,
    )

    raw_audio = load_audio_compat(load_audio, audio_path, processor.config.mel_sr)
    inputs = processor(text=args.prompt, audios=[raw_audio], return_tensors="pt")
    inputs = inputs.to(model.device)
    if inputs.get("audio_data") is not None:
        inputs["audio_data"] = inputs["audio_data"].to(model.dtype)
    inputs["audio_input_mask"] = inputs["input_ids"] == processor.audio_token_id

    with torch.inference_mode():
        generated_ids = model.generate(**inputs, **build_generation_kwargs(args))

    input_len = inputs["input_ids"].shape[1]
    answer = processor.decode(generated_ids[0, input_len:], skip_special_tokens=True).strip()
    if args.strip_thinking:
        answer = strip_thinking(answer)

    elapsed = time.perf_counter() - started
    print(f"elapsed: {elapsed:.2f}s")
    print("result:")
    print(answer)
    if args.output_path is not None:
        output_path = write_output(args.output_path, answer)
        print(f"output: {output_path}")
    return answer


def main() -> int:
    args = parse_args()
    try:
        run_inference(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
