#!/usr/bin/env python3
"""串行执行 Task 9 的 VoxCPM2 本地声音克隆。

该脚本只负责编排合成，固定使用 ``longAudioTestV9/text.md`` 作为成品文本源，
不会调用评测器。合成过程保留共享分段清单和逐段证据，避免 GPU 并发占用。
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

from text_segments import build_segment_plan, write_segment_plan


TASK_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_SCRIPT_DIR.parents[1]
DEFAULT_TASK_DIR = PROJECT_ROOT / "longAudioTestV9"
DEFAULT_REFERENCE_TEXT = "深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。"


@dataclass(frozen=True)
class TaskPaths:
    task_dir: Path
    text_file: Path
    reference_audio: Path
    voxcpm2_output: Path
    segment_manifest: Path
    segment_evidence_root: Path


@dataclass(frozen=True)
class Invocation:
    label: str
    output_path: Path
    command: tuple[str, ...]


def configured_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser() if value else None


def task_paths(task_dir: Path) -> TaskPaths:
    root = task_dir.expanduser().resolve()
    return TaskPaths(
        task_dir=root,
        text_file=root / "text.md",
        reference_audio=root / "mimo_旁白_v9.wav",
        voxcpm2_output=root / "audio_voxcpm2.wav",
        segment_manifest=root / ".task9_segment_manifest.json",
        segment_evidence_root=root / ".task9_synthesis_evidence",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR, help="V9 输入和输出目录")
    parser.add_argument(
        "--hf-mirror-root",
        type=Path,
        default=configured_path("HF_MIRROR_ROOT"),
        help="本地 hf-mirror 根目录；未显式传模型路径时必填",
    )
    parser.add_argument("--voxcpm2-model-path", type=Path, default=None, help="VoxCPM2 本地模型目录")
    parser.add_argument("--voxcpm2-conda-env", default="voxcpm2", help="VoxCPM2 Conda 环境名")
    parser.add_argument("--conda-executable", default="conda", help="Conda 可执行文件")
    parser.add_argument("--reference-text", default=DEFAULT_REFERENCE_TEXT, help="参考音频的准确文案")
    parser.add_argument("--segment-target-seconds", type=int, default=25, help="目标片段时长（秒）")
    parser.add_argument("--segment-max-seconds", type=int, default=35, help="最大片段时长（秒）")
    parser.add_argument("--overwrite", action="store_true", help="明确允许覆盖已有目标音频")
    parser.add_argument("--dry-run", action="store_true", help="只校验路径并打印命令，不启动模型")
    return parser.parse_args(argv)


def resolve_model_path(args: argparse.Namespace) -> Path:
    if args.voxcpm2_model_path is not None:
        return args.voxcpm2_model_path.expanduser().resolve()
    if args.hf_mirror_root is None:
        raise ValueError("必须设置 --hf-mirror-root，或显式传入 --voxcpm2-model-path。")
    return args.hf_mirror_root.expanduser().resolve() / "openbmb/VoxCPM2"


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在：{path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label}为空：{path}")


def require_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"{label}不存在：{path}")


def validate_preflight(args: argparse.Namespace, inputs: TaskPaths, model_path: Path) -> None:
    require_file(inputs.text_file, "合成原文 text.md")
    require_file(inputs.reference_audio, "旁白参考音频")
    if args.hf_mirror_root is not None:
        require_directory(args.hf_mirror_root.expanduser().resolve(), "hf-mirror 根目录")
    require_directory(model_path, "VoxCPM2 模型目录")
    if shutil.which(args.conda_executable) is None:
        raise FileNotFoundError(f"找不到 Conda 可执行文件：{args.conda_executable}")
    if not args.dry_run and not args.overwrite and inputs.voxcpm2_output.exists():
        raise FileExistsError(
            "目标音频已存在；如确认覆盖，请显式传入 --overwrite："
            + str(inputs.voxcpm2_output)
        )


def build_invocation(args: argparse.Namespace, inputs: TaskPaths, model_path: Path) -> Invocation:
    script = TASK_SCRIPT_DIR / "voxcpm2.py"
    command = (
        args.conda_executable,
        "run",
        "--no-capture-output",
        "-n",
        args.voxcpm2_conda_env,
        "python",
        str(script),
        "--model-path",
        str(model_path),
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
        "--segment-evidence-root",
        str(inputs.segment_evidence_root),
        "--model-id",
        "voxcpm2",
        "--local-files-only",
    )
    return Invocation("VoxCPM2", inputs.voxcpm2_output, command)


def print_plan(inputs: TaskPaths, invocation: Invocation, segment_plan: dict) -> None:
    policy = segment_plan["policy"]
    rate = segment_plan["reference_speech_rate"]
    print(f"文本源：{inputs.text_file}")
    print(f"参考音频：{inputs.reference_audio}")
    print(
        "共享分段："
        f"{len(segment_plan['segments'])} 段，参考语速 {rate['characters_per_second']:.3f} 字/秒，"
        f"目标 {policy['target_seconds']} 秒，最大 {policy['max_segment_seconds']} 秒"
    )
    print(f"共享清单：{inputs.segment_manifest}")
    print(f"逐段证据根目录：{inputs.segment_evidence_root}")
    print(f"\n[{invocation.label}] 目标：{invocation.output_path}")
    print(shlex.join(invocation.command))


def run(args: argparse.Namespace) -> int:
    inputs = task_paths(args.task_dir)
    model_path = resolve_model_path(args)
    validate_preflight(args, inputs, model_path)
    segment_plan = build_segment_plan(
        inputs.text_file.read_text(encoding="utf-8").strip(),
        inputs.reference_audio,
        args.reference_text,
        args.segment_target_seconds,
        args.segment_max_seconds,
    )
    invocation = build_invocation(args, inputs, model_path)
    print_plan(inputs, invocation, segment_plan)
    if args.dry_run:
        print("\n预检通过：未加载模型、未生成音频、未运行评测。")
        return 0

    write_segment_plan(inputs.segment_manifest, segment_plan)
    child_env = os.environ.copy()
    child_env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    if args.hf_mirror_root is not None:
        child_env["HF_HOME"] = str(args.hf_mirror_root.expanduser().resolve())
    print(f"\n开始合成：{invocation.label}", flush=True)
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
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(f"Task 9 合成编排失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
