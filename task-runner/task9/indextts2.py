#!/usr/bin/env python3
"""Task 9 专用的 IndexTTS2 离线旁白克隆脚本。"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from text_segments import join_waveforms, load_segment_plan, read_synthesis_text


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True, help="IndexTTS-2 本地模型目录")
    parser.add_argument("--code-path", type=Path, required=True, help="含 indextts 包的官方源码目录")
    parser.add_argument("--text-file", type=Path, required=True, help="要合成的 UTF-8 原文")
    parser.add_argument("--ref-audio", type=Path, required=True, help="旁白参考 WAV")
    parser.add_argument("--output", type=Path, required=True, help="精确目标 WAV 路径")
    parser.add_argument("--emo-text", default="", help="可选情感/风格描述")
    parser.add_argument("--device", default=None, help="推理设备；默认由 IndexTTS2 自动选择")
    parser.add_argument("--max-text-tokens-per-segment", type=int, default=128, help="原生单段最大 token 数")
    parser.add_argument("--max-mel-tokens", type=int, default=1200, help="单段最大 mel token 数")
    parser.add_argument("--segment-manifest", type=Path, required=True, help="两个模型共用的冻结分段清单")
    parser.add_argument("--no-fp16", action="store_true", help="关闭 CUDA FP16")
    parser.add_argument("--use-cuda-kernel", action="store_true", help="启用可选 BigVGAN CUDA 内核")
    parser.add_argument(
        "--qwen-emo-device",
        default="cpu",
        choices=("cpu", "cuda"),
        help="情绪文本模型的加载设备；默认 CPU，以节约单卡显存",
    )
    parser.add_argument(
        "--offload-conditioning-models",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="提取参考音频条件后将语义与说话人模型卸载到 CPU（默认开启）",
    )
    parser.add_argument("--local-files-only", action="store_true", help="禁止 Hugging Face 联网下载")
    parser.add_argument(
        "--runtime-cache-dir",
        type=Path,
        default=PROJECT_ROOT / "work" / "runtime_cache" / "task9-indextts2",
        help="可写的运行时缓存目录",
    )
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


def validate_model_assets(model_path: Path) -> None:
    missing = [relative for relative in REQUIRED_MODEL_FILES if not (model_path / relative).is_file()]
    if missing:
        raise FileNotFoundError("IndexTTS2 模型文件缺失：" + ", ".join(missing))


def read_text(path: Path) -> str:
    return read_synthesis_text(path)


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


def import_runtime(code_path: Path) -> tuple[Any, Any, Any, Any]:
    if str(code_path) not in sys.path:
        sys.path.insert(0, str(code_path))
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from indextts.infer_v2 import IndexTTS2
    except ImportError as exc:
        raise RuntimeError(f"无法导入 IndexTTS2 运行时：{exc.name or exc}") from exc
    return IndexTTS2, np, sf, torch


@contextmanager
def lazy_qwen_emotion_on_cpu(IndexTTS2: Any, device: str):
    """让 IndexTTS2 的大语言情绪模型仅在需要时加载到 CPU。

    这与 Task 9 参考的本地 API worker 保持一致。语音主模型仍运行在 GPU，
    仅把文本情绪理解这一步移到 CPU，避免在 16GB 单卡上与声学模型争抢显存。
    """
    if device != "cpu":
        yield
        return

    runtime_module = sys.modules.get(IndexTTS2.__module__)
    if runtime_module is None or not hasattr(runtime_module, "QwenEmotion"):
        yield
        return

    original_qwen_emotion = runtime_module.QwenEmotion
    original_auto_model = runtime_module.AutoModelForCausalLM

    class LazyCpuQwenEmotion:
        def __init__(self, model_dir: str) -> None:
            self.model_dir = model_dir
            self.delegate: Any | None = None

        def inference(self, text_input: str) -> Any:
            if self.delegate is None:
                class CpuAutoModelForCausalLM:
                    @staticmethod
                    def from_pretrained(*args: Any, **kwargs: Any) -> Any:
                        kwargs["torch_dtype"] = "float32"
                        kwargs["device_map"] = "cpu"
                        return original_auto_model.from_pretrained(*args, **kwargs)

                runtime_module.AutoModelForCausalLM = CpuAutoModelForCausalLM
                try:
                    self.delegate = original_qwen_emotion(self.model_dir)
                finally:
                    runtime_module.AutoModelForCausalLM = original_auto_model
                print(">> Qwen emotion model loaded lazily on CPU")
            return self.delegate.inference(text_input)

    runtime_module.QwenEmotion = LazyCpuQwenEmotion
    try:
        yield
    finally:
        runtime_module.QwenEmotion = original_qwen_emotion


def install_conditioning_model_offload(model: Any, torch: Any) -> bool:
    """在参考音频条件提取后释放不再需要的 GPU 模型。"""
    if not str(getattr(model, "device", "")).startswith("cuda"):
        return False
    if not all(hasattr(model, name) for name in ("get_emb", "semantic_model", "campplus_model")):
        return False

    original_get_emb = model.get_emb
    call_count = 0
    offloaded = False

    def get_emb_and_offload(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count, offloaded
        result = original_get_emb(*args, **kwargs)
        call_count += 1
        if call_count >= 2 and not offloaded:
            model.semantic_model = model.semantic_model.to("cpu")
            model.campplus_model = model.campplus_model.to("cpu")
            torch.cuda.empty_cache()
            offloaded = True
            print(">> 已将参考条件模型卸载到 CPU")
        return result

    model.get_emb = get_emb_and_offload
    return True


def trim_leading_silence(waveform: Any, sample_rate: int, np: Any) -> tuple[Any, int]:
    """仅移除明显的前导静音，不改变正文节奏或尾部内容。"""
    mono = waveform.mean(axis=1) if waveform.ndim == 2 else waveform
    threshold = 10 ** (-60 / 20)
    active = np.flatnonzero(np.abs(mono) >= threshold)
    if not len(active):
        return waveform, 0
    leading_samples = int(active[0])
    # 保留 30ms 自然起音，避免在清辅音起始处切断。
    keep_samples = round(sample_rate * 0.03)
    trim_samples = max(0, leading_samples - keep_samples)
    return waveform[trim_samples:], trim_samples


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
    IndexTTS2, np, sf, torch = import_runtime(code_path)
    if args.device and args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("IndexTTS2 要求 CUDA，但当前环境不可用。")
    if args.device is None and not torch.cuda.is_available():
        raise RuntimeError("IndexTTS2 合成需要 CUDA，但当前环境不可用。")

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model = None
    try:
        with lazy_qwen_emotion_on_cpu(IndexTTS2, args.qwen_emo_device):
            model = IndexTTS2(
                model_dir=str(model_path),
                cfg_path=str(model_path / "config.yaml"),
                aux_paths=auxiliary_paths(model_path),
                device=args.device,
                use_fp16=not args.no_fp16,
                use_cuda_kernel=args.use_cuda_kernel,
            )
        if args.offload_conditioning_models:
            install_conditioning_model_offload(model, torch)
        segments = load_segment_plan(args.segment_manifest.expanduser().resolve(), read_text(text_file))
        emo_text = args.emo_text.strip()
        waveforms: list[Any] = []
        sample_rate: int | None = None
        with tempfile.TemporaryDirectory(prefix="task9-indextts2-", dir=output.parent) as temporary:
            temporary_dir = Path(temporary)
            with torch.inference_mode():
                for index, segment in enumerate(segments, start=1):
                    chunk = str(segment["text"])
                    chunk_output = temporary_dir / f"chunk-{index:03d}.wav"
                    print(f"IndexTTS2 合成片段 {index}/{len(segments)}（{len(chunk)} 字）", flush=True)
                    model.infer(
                        spk_audio_prompt=str(reference_audio),
                        text=chunk,
                        output_path=str(chunk_output),
                        use_emo_text=bool(emo_text),
                        emo_text=emo_text or None,
                        max_text_tokens_per_segment=max(20, args.max_text_tokens_per_segment),
                        max_mel_tokens=max(256, args.max_mel_tokens),
                        num_beams=1,
                        verbose=True,
                    )
                    if not chunk_output.is_file() or chunk_output.stat().st_size == 0:
                        raise RuntimeError(f"IndexTTS2 未生成有效片段：{chunk_output}")
                    waveform, chunk_sample_rate = sf.read(str(chunk_output), dtype="float32", always_2d=True)
                    if sample_rate is None:
                        sample_rate = chunk_sample_rate
                    elif sample_rate != chunk_sample_rate:
                        raise RuntimeError("IndexTTS2 各片段采样率不一致，拒绝拼接。")
                    waveforms.append(waveform)
        if sample_rate is None:
            raise RuntimeError("IndexTTS2 未返回任何可拼接的片段。")
        pauses = [int(item["pause_after_ms"]) for item in segments[:-1]]
        waveform = join_waveforms(waveforms, sample_rate, pauses, np)
        waveform, trimmed_samples = trim_leading_silence(waveform, sample_rate, np)
        if trimmed_samples:
            print(f"已裁掉前导静音 {trimmed_samples / sample_rate:.2f}s")
        sf.write(str(output), waveform, sample_rate, format="WAV")
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
