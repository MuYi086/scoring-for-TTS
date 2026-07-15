#!/usr/bin/env python3
"""在 IndexTTS2 的 conda 环境内直接完成三位角色的集中克隆测试。

本脚本不经过任何 HTTP 后端，也不会启动常驻服务。它只直接加载一次
IndexTTS2，顺序克隆三个角色，并在 finally 中删除模型、同步 CUDA、清空
缓存与 IPC 缓存。请通过同目录的 run_clone_indextts2.sh 进入正确 conda 环境。
"""

from __future__ import annotations

import argparse
import gc
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "cloneData"
DEFAULT_HF_MIRROR_ROOT = Path(
    os.environ.get("HF_MIRROR_ROOT", Path.home() / "hf-mirror")
).expanduser()
DEFAULT_TTS_VENDOR_ROOT = Path(
    os.environ.get("TTS_VENDOR_ROOT", REPO_ROOT.parent / "TTS-and-VoiceDesign/api/vendor")
).expanduser()
DEFAULT_MODEL_PATH = Path(
    os.environ.get("INDEXTTS_MODEL_PATH", DEFAULT_HF_MIRROR_ROOT / "IndexTeam/IndexTTS-2")
)
DEFAULT_CODE_PATH = Path(
    os.environ.get("INDEXTTS_CODE_PATH", DEFAULT_TTS_VENDOR_ROOT / "index-tts")
)
DEFAULT_RUNTIME_CACHE_DIR = REPO_ROOT / "cloneData" / "indextts2" / ".runtime_cache"
REQUIRED_MODEL_FILES = (
    "bpe.model",
    "wav2vec2bert_stats.pt",
    "gpt.pth",
    "s2mel.pth",
    "feat1.pt",
    "feat2.pt",
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


@dataclass(frozen=True)
class CloneCase:
    """一条固定的本地 IndexTTS2 角色克隆测试。"""

    character: str
    reference_audio: Path
    emotion_vector: tuple[float, float, float, float, float, float, float, float]
    text: str

    @property
    def output_name(self) -> str:
        return f"indextts2_{self.character}.wav"


CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白.wav",
        emotion_vector=(0, 0, 0, 0, 0, 0, 0, 0.5),
        text="小公主手下的侍卫紧张无比，其中一个见习魔法师道：",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主.wav",
        emotion_vector=(0, 0.35, 0, 0, 0, 0, 0, 0),
        text="当然有，你们是不是害怕了？",
    ),
    CloneCase(
        character="见习魔法师",
        reference_audio=REPO_ROOT / "testData/mimo_见习魔法师.wav",
        emotion_vector=(0, 0, 0, 0.5, 0, 0, 0, 0),
        text="公主殿下，火山口真的有烈火仙莲吗？",
    ),
)


def parse_args() -> argparse.Namespace:
    """解析直接推理的模型与输出参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH, help="IndexTTS-2 本地权重目录")
    parser.add_argument("--code-path", type=Path, default=DEFAULT_CODE_PATH, help="index-tts 官方源码目录")
    parser.add_argument("--config-path", type=Path, default=None, help="默认使用 <model-path>/config.yaml")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录，默认 cloneData/")
    parser.add_argument("--runtime-cache-dir", type=Path, default=DEFAULT_RUNTIME_CACHE_DIR)
    parser.add_argument("--device", default=os.environ.get("INDEXTTS_DEVICE") or None)
    parser.add_argument("--emo-alpha", type=float, default=0.6, help="情感向量混合强度，沿用原服务的 0.6")
    parser.add_argument("--num-beams", type=int, default=1, help="自回归 beam 数，沿用原服务的 1")
    parser.add_argument("--use-cuda-kernel", action="store_true", help="启用可选 BigVGAN CUDA 融合核")
    parser.add_argument("--allow-cpu", action="store_true", help="明确允许极慢 CPU 推理")
    parser.add_argument(
        "--character",
        choices=[case.character for case in CASES],
        action="append",
        help="只克隆指定角色；重复传入可选择多个。默认全部。",
    )
    parser.add_argument("--dry-run", action="store_true", help="只验证路径与打印计划，不加载模型")
    return parser.parse_args()


def selected_cases(characters: list[str] | None) -> tuple[CloneCase, ...]:
    """按固定声明顺序过滤角色。"""

    if not characters:
        return CASES
    requested = set(characters)
    return tuple(case for case in CASES if case.character in requested)


def prepare_environment(runtime_cache_dir: Path) -> None:
    """将运行时缓存限制在项目目录，并禁止推理中隐式联网。"""

    cache_dir = runtime_cache_dir.expanduser().resolve()
    paths = {
        "HF_MODULES_CACHE": cache_dir / "hf_modules",
        "NUMBA_CACHE_DIR": cache_dir / "numba",
        "MPLCONFIGDIR": cache_dir / "matplotlib",
        "XDG_CACHE_HOME": cache_dir / "xdg",
    }
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def require_model_assets(model_path: Path, config_path: Path) -> None:
    """在加载大模型前检查本地权重和辅助文件是否完整。"""

    missing = []
    if not model_path.is_dir():
        missing.append(f"模型目录不存在：{model_path}")
    if not config_path.is_file():
        missing.append(f"配置文件不存在：{config_path}")
    missing.extend(str(model_path / relative) for relative in REQUIRED_MODEL_FILES if not (model_path / relative).is_file())
    if missing:
        raise FileNotFoundError("IndexTTS2 本地资产缺失：" + "；".join(missing))


def add_code_path(code_path: Path) -> None:
    """仅为当前进程添加官方 index-tts 源码，不污染其他 conda 环境。"""

    resolved = code_path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"IndexTTS2 官方源码目录不存在：{resolved}")
    if str(resolved) not in sys.path:
        sys.path.insert(0, str(resolved))


def import_runtime(code_path: Path) -> tuple[Any, Any]:
    """在指定 conda 环境中直接导入官方 IndexTTS2 运行时。"""

    add_code_path(code_path)
    try:
        import torch
        from indextts.infer_v2 import IndexTTS2
    except ImportError as exc:
        raise RuntimeError(
            "当前 Python 环境无法导入 IndexTTS2。请通过 run_clone_indextts2.sh 使用 "
            "unitale-tts-local conda 环境运行。"
        ) from exc
    return IndexTTS2, torch


def auxiliary_paths(model_path: Path) -> dict[str, str]:
    """构造 IndexTTS2 官方构造器需要的本地辅助模型路径。"""

    auxiliary_dir = model_path / "hf_cache"
    return {
        "w2v_bert": str(auxiliary_dir / "w2v-bert-2.0"),
        "semantic_codec": str(auxiliary_dir / "semantic_codec_model.safetensors"),
        "campplus": str(auxiliary_dir / "campplus_cn_common.bin"),
        "bigvgan": str(auxiliary_dir / "bigvgan"),
    }


def infer_arguments(case: CloneCase, output_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    """把任务指定的参考音频、文本和情感向量映射为官方 infer 参数。"""

    return {
        "spk_audio_prompt": str(case.reference_audio),
        "text": case.text,
        "output_path": str(output_path),
        "emo_audio_prompt": None,
        "emo_alpha": args.emo_alpha,
        "emo_vector": list(case.emotion_vector),
        "use_emo_text": False,
        "emo_text": None,
        "interval_silence": 200,
        "max_text_tokens_per_segment": 120,
        "num_beams": args.num_beams,
        "verbose": True,
    }


def clear_cuda_cache(torch: Any) -> None:
    """在模型对象删除后尽可能释放本进程持有的显存。"""

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


def resolve_runtime_options(torch: Any, args: argparse.Namespace) -> tuple[str | None, bool]:
    """根据 CUDA 可用性确定设备与精度，拒绝未明确同意的 CPU 推理。"""

    requested_device = args.device.lower() if args.device else None
    cuda_available = torch.cuda.is_available()
    if requested_device == "cpu":
        return "cpu", False
    if cuda_available:
        return args.device, True
    if requested_device and requested_device.startswith("cuda"):
        raise RuntimeError("已指定 CUDA 设备，但当前环境未检测到 CUDA。")
    if args.allow_cpu:
        return "cpu", False
    raise RuntimeError("IndexTTS2 默认要求 CUDA；当前环境未检测到 CUDA，拒绝隐式 CPU 推理。")


def validate_case_inputs(cases: tuple[CloneCase, ...]) -> None:
    """在加载模型前一次性列出缺失参考音频。"""

    missing = [str(case.reference_audio) for case in cases if not case.reference_audio.is_file()]
    if missing:
        raise FileNotFoundError("参考音频不存在：" + "；".join(missing))


def preflight(args: argparse.Namespace, cases: tuple[CloneCase, ...]) -> tuple[Path, Path]:
    """校验任务输入、离线权重和官方源码，但不导入或加载模型。"""

    validate_case_inputs(cases)
    model_path = args.model_path.expanduser().resolve()
    config_path = (args.config_path or model_path / "config.yaml").expanduser().resolve()
    require_model_assets(model_path, config_path)
    if not args.code_path.expanduser().resolve().is_dir():
        raise FileNotFoundError(f"IndexTTS2 官方源码目录不存在：{args.code_path.expanduser().resolve()}")
    return model_path, config_path


def run_cases(args: argparse.Namespace, cases: tuple[CloneCase, ...]) -> int:
    """一次加载模型并串行执行所有角色，最终无条件释放显存。"""

    model_path, config_path = preflight(args, cases)
    prepare_environment(args.runtime_cache_dir)
    IndexTTS2, torch = import_runtime(args.code_path)
    device, use_fp16 = resolve_runtime_options(torch, args)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model = None
    failures = 0
    try:
        model = IndexTTS2(
            model_dir=str(model_path),
            cfg_path=str(config_path),
            aux_paths=auxiliary_paths(model_path),
            device=device,
            use_fp16=use_fp16,
            use_cuda_kernel=args.use_cuda_kernel,
        )
        for case in cases:
            output_path = output_dir / case.output_name
            started = time.perf_counter()
            try:
                print(f"开始：{case.character}")
                model.infer(**infer_arguments(case, output_path, args))
                if not output_path.is_file() or output_path.stat().st_size == 0:
                    raise RuntimeError("模型未生成有效 WAV 文件")
                print(f"完成：{output_path}（耗时 {time.perf_counter() - started:.2f}s）")
            except Exception as exc:
                failures += 1
                print(f"错误：{case.character} 克隆失败：{exc}", file=sys.stderr)
        return 1 if failures else 0
    finally:
        del model
        clear_cuda_cache(torch)
        print("IndexTTS2 已卸载，已请求释放 CUDA 缓存。")


def main() -> int:
    """运行命令行入口。"""

    args = parse_args()
    cases = selected_cases(args.character)
    try:
        if args.dry_run:
            preflight(args, cases)
            for case in cases:
                print(
                    f"计划：{case.character} | 参考={case.reference_audio} | "
                    f"输出={args.output_dir / case.output_name} | emo_vector={list(case.emotion_vector)}"
                )
            return 0
        return run_cases(args, cases)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
