#!/usr/bin/env python3
"""串行执行 Task 9 的 IndexTTS2 与 VoxCPM2 本地声音克隆。

该脚本只负责编排合成。它固定使用 ``longAudioTestV9/text.md`` 作为两条
成品的文本源，分别写入 ``audio_indextts2.wav`` 与 ``audio_voxcpm2.wav``；
不会调用任何评测器。两个模型始终串行运行，避免同时占用同一张 GPU。
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from text_segments import build_segment_plan, write_segment_plan


TASK_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_SCRIPT_DIR.parents[1]
DEFAULT_TASK_DIR = PROJECT_ROOT / "longAudioTestV9"
DEFAULT_REFERENCE_TEXT = "深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。"
DEFAULT_VOICE_DESCRIPTION = (
    "女声，20-30岁，中音区略偏低，音色沉静而敏锐，略带暖意，不沙哑或气声过度。"
    "咬字清晰但不刻板，语速中等偏慢，有自然的停顿；默认气质冷静而克制，"
    "像深夜播讲都市传说中的悬念播客主，不动声色地铺垫紧张氛围。"
)
MODEL_ORDER = ("indextts2", "voxcpm2")


@dataclass(frozen=True)
class TaskPaths:
    """Task 9 的固定输入与目标输出路径。"""

    task_dir: Path
    text_file: Path
    reference_audio: Path
    indextts_output: Path
    voxcpm2_output: Path
    segment_manifest: Path


@dataclass(frozen=True)
class ModelPaths:
    """两个模型及其运行源码的本地目录。"""

    hf_mirror_root: Path | None
    indextts_model: Path
    indextts_code: Path
    voxcpm2_model: Path


@dataclass(frozen=True)
class Invocation:
    """一次可审阅、可执行的本地合成调用。"""

    model_key: str
    label: str
    output_path: Path
    command: tuple[str, ...]


def configured_path(*names: str) -> Path | None:
    """从首个非空环境变量解析路径，避免把机器目录写死进仓库。"""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return Path(value).expanduser()
    return None


def task_paths(task_dir: Path) -> TaskPaths:
    """由任务目录构造所有 V9 输入和固定输出名。"""
    root = task_dir.expanduser().resolve()
    return TaskPaths(
        task_dir=root,
        text_file=root / "text.md",
        reference_audio=root / "mimo_旁白_v9.wav",
        indextts_output=root / "audio_indextts2.wav",
        voxcpm2_output=root / "audio_voxcpm2.wav",
        segment_manifest=root / ".task9_segment_manifest.json",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析不含任何机器专属默认路径的 Task 9 参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR, help="V9 输入和输出目录")
    parser.add_argument(
        "--hf-mirror-root",
        type=Path,
        default=configured_path("HF_MIRROR_ROOT"),
        help="本地 hf-mirror 根目录；未显式传模型路径时必填",
    )
    parser.add_argument("--indextts-model-path", type=Path, default=None, help="IndexTTS-2 本地模型目录")
    parser.add_argument(
        "--indextts-code-path",
        type=Path,
        default=configured_path("INDEXTTS_CODE_PATH", "INDEXTTS_CODE_DIR"),
        help="含 indextts 包的官方 index-tts 源码目录",
    )
    parser.add_argument("--voxcpm2-model-path", type=Path, default=None, help="VoxCPM2 本地模型目录")
    parser.add_argument("--indextts-conda-env", default="unitale-tts-local", help="IndexTTS2 Conda 环境名")
    parser.add_argument("--voxcpm2-conda-env", default="voxcpm2", help="VoxCPM2 Conda 环境名")
    parser.add_argument("--conda-executable", default="conda", help="Conda 可执行文件")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=MODEL_ORDER,
        default=list(MODEL_ORDER),
        help="要执行的模型；始终按 IndexTTS2、VoxCPM2 的固定顺序串行运行",
    )
    parser.add_argument("--reference-text", default=DEFAULT_REFERENCE_TEXT, help="参考音频的准确文案")
    parser.add_argument("--voice-description", default=DEFAULT_VOICE_DESCRIPTION, help="旁白音色和风格描述")
    parser.add_argument(
        "--index-emo-text",
        default=None,
        help="传给 IndexTTS2 的情感描述；默认使用 --voice-description",
    )
    parser.add_argument(
        "--index-max-text-tokens-per-segment",
        type=int,
        default=128,
        help="IndexTTS2 单个共同文本片段的原生 token 上限，默认 128，覆盖清单的 35 秒上限",
    )
    parser.add_argument(
        "--segment-target-seconds",
        type=int,
        default=25,
        help="根据旁白参考语速估算的目标片段时长（秒）",
    )
    parser.add_argument(
        "--segment-max-seconds",
        type=int,
        default=35,
        help="根据旁白参考语速估算的最大片段时长（秒）",
    )
    parser.add_argument("--overwrite", action="store_true", help="明确允许覆盖已有目标音频")
    parser.add_argument("--dry-run", action="store_true", help="只校验路径并打印命令，不启动模型")
    return parser.parse_args(argv)


def resolve_model_path(
    explicit_path: Path | None, mirror_root: Path | None, relative_path: str, label: str
) -> Path:
    """解析显式模型路径或 hf-mirror 中的标准相对位置。"""
    if explicit_path is not None:
        return explicit_path.expanduser().resolve()
    if mirror_root is None:
        raise ValueError(f"缺少 {label} 模型目录：请传入对应 --*-model-path 或 --hf-mirror-root。")
    return mirror_root.expanduser().resolve() / relative_path


def resolve_model_paths(args: argparse.Namespace) -> ModelPaths:
    """解析两个模型路径并要求 IndexTTS2 的源码目录明确可追溯。"""
    mirror_root = args.hf_mirror_root.expanduser().resolve() if args.hf_mirror_root else None
    if mirror_root is None and (
        args.indextts_model_path is None or args.voxcpm2_model_path is None
    ):
        raise ValueError("必须设置 --hf-mirror-root，或显式传入两个模型路径。")
    if args.indextts_code_path is None:
        raise ValueError("缺少 --indextts-code-path（或 INDEXTTS_CODE_PATH 环境变量）。")
    return ModelPaths(
        hf_mirror_root=mirror_root,
        indextts_model=resolve_model_path(
            args.indextts_model_path, mirror_root, "IndexTeam/IndexTTS-2", "IndexTTS2"
        ),
        indextts_code=args.indextts_code_path.expanduser().resolve(),
        voxcpm2_model=resolve_model_path(
            args.voxcpm2_model_path, mirror_root, "openbmb/VoxCPM2", "VoxCPM2"
        ),
    )


def require_file(path: Path, label: str) -> None:
    """在启动任何子进程前拒绝缺失或空的输入文件。"""
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在：{path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label}为空：{path}")


def require_directory(path: Path, label: str) -> None:
    """在启动任何子进程前拒绝缺失模型或源码目录。"""
    if not path.is_dir():
        raise FileNotFoundError(f"{label}不存在：{path}")


def validate_preflight(args: argparse.Namespace, inputs: TaskPaths, models: ModelPaths) -> None:
    """执行无模型加载的本地路径和覆盖保护校验。"""
    require_file(inputs.text_file, "合成原文 text.md")
    require_file(inputs.reference_audio, "旁白参考音频")
    if models.hf_mirror_root is not None:
        require_directory(models.hf_mirror_root, "hf-mirror 根目录")
    require_directory(models.indextts_model, "IndexTTS2 模型目录")
    require_directory(models.indextts_code, "IndexTTS2 源码目录")
    require_directory(models.voxcpm2_model, "VoxCPM2 模型目录")
    if shutil.which(args.conda_executable) is None:
        raise FileNotFoundError(f"找不到 Conda 可执行文件：{args.conda_executable}")
    if not args.overwrite:
        outputs = {
            "indextts2": inputs.indextts_output,
            "voxcpm2": inputs.voxcpm2_output,
        }
        existing = [outputs[model] for model in selected_models(args.models) if outputs[model].exists()]
        if existing:
            raise FileExistsError("目标音频已存在；如确认覆盖，请显式传入 --overwrite：" + ", ".join(map(str, existing)))


def selected_models(values: Iterable[str]) -> tuple[str, ...]:
    """忽略调用者传入的顺序，始终保障单 GPU 的固定串行顺序。"""
    requested = set(values)
    return tuple(model for model in MODEL_ORDER if model in requested)


def build_invocations(args: argparse.Namespace, inputs: TaskPaths, models: ModelPaths) -> tuple[Invocation, ...]:
    """构建两个本地脚本的无网络 Conda 调用，不执行它们。"""
    selected = selected_models(args.models)
    if not selected:
        raise ValueError("至少选择一个模型。")
    index_script = TASK_SCRIPT_DIR / "indextts2.py"
    voxcpm_script = TASK_SCRIPT_DIR / "voxcpm2.py"
    index_emo_text = args.index_emo_text if args.index_emo_text is not None else args.voice_description
    invocations: dict[str, Invocation] = {
        "indextts2": Invocation(
            model_key="indextts2",
            label="IndexTTS2",
            output_path=inputs.indextts_output,
            command=(
                args.conda_executable,
                "run",
                "--no-capture-output",
                "-n",
                args.indextts_conda_env,
                "python",
                str(index_script),
                "--model-path",
                str(models.indextts_model),
                "--code-path",
                str(models.indextts_code),
                "--text-file",
                str(inputs.text_file),
                "--ref-audio",
                str(inputs.reference_audio),
                "--output",
                str(inputs.indextts_output),
                "--emo-text",
                index_emo_text,
                "--max-text-tokens-per-segment",
                str(args.index_max_text_tokens_per_segment),
                "--segment-manifest",
                str(inputs.segment_manifest),
                "--local-files-only",
            ),
        ),
        "voxcpm2": Invocation(
            model_key="voxcpm2",
            label="VoxCPM2",
            output_path=inputs.voxcpm2_output,
            command=(
                args.conda_executable,
                "run",
                "--no-capture-output",
                "-n",
                args.voxcpm2_conda_env,
                "python",
                str(voxcpm_script),
                "--model-path",
                str(models.voxcpm2_model),
                "--text-file",
                str(inputs.text_file),
                "--ref-audio",
                str(inputs.reference_audio),
                "--output",
                str(inputs.voxcpm2_output),
                "--prompt-text",
                args.reference_text,
                "--segment-manifest",
                str(inputs.segment_manifest),
                "--local-files-only",
            ),
        ),
    }
    return tuple(invocations[model] for model in selected)


def print_plan(inputs: TaskPaths, invocations: Iterable[Invocation], segment_plan: dict) -> None:
    """输出所有实际输入、固定输出名和即将执行的命令。"""
    print(f"文本源：{inputs.text_file}")
    print(f"参考音频：{inputs.reference_audio}")
    policy = segment_plan["policy"]
    rate = segment_plan["reference_speech_rate"]
    print(
        "共享分段："
        f"{len(segment_plan['segments'])} 段，参考语速 {rate['characters_per_second']:.3f} 字/秒，"
        f"目标 {policy['target_seconds']} 秒，最大 {policy['max_segment_seconds']} 秒"
    )
    print(f"共享清单：{inputs.segment_manifest}")
    for invocation in invocations:
        print(f"\n[{invocation.label}] 目标：{invocation.output_path}")
        print(shlex.join(invocation.command))


def run(args: argparse.Namespace) -> int:
    """预检、展示计划，并在非 dry-run 时严格串行地启动两个模型。"""
    inputs = task_paths(args.task_dir)
    models = resolve_model_paths(args)
    validate_preflight(args, inputs, models)
    segment_plan = build_segment_plan(
        inputs.text_file.read_text(encoding="utf-8").strip(),
        inputs.reference_audio,
        args.reference_text,
        args.segment_target_seconds,
        args.segment_max_seconds,
    )
    invocations = build_invocations(args, inputs, models)
    print_plan(inputs, invocations, segment_plan)
    if args.dry_run:
        print("\n预检通过：未加载模型、未生成音频、未运行评测。")
        return 0

    write_segment_plan(inputs.segment_manifest, segment_plan)

    child_env = os.environ.copy()
    child_env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    if models.hf_mirror_root is not None:
        child_env["HF_HOME"] = str(models.hf_mirror_root)
    for invocation in invocations:
        print(f"\n开始串行合成：{invocation.label}", flush=True)
        completed = subprocess.run(invocation.command, env=child_env, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{invocation.label} 合成失败，退出码={completed.returncode}")
        if not invocation.output_path.is_file() or invocation.output_path.stat().st_size == 0:
            raise RuntimeError(f"{invocation.label} 未生成有效音频：{invocation.output_path}")
        print(f"{invocation.label} 合成完成：{invocation.output_path}", flush=True)
    return 0


def main() -> int:
    try:
        return run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Task 9 合成编排失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
