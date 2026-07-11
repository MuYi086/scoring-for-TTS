#!/usr/bin/env python3
"""通过各模型原生本地 CLI 执行三角色声音克隆测试。

本模块不启动 HTTP 服务，也不导入任何 TTS 运行时。调用方须先通过对应的
conda 环境启动本模块；每个角色由一个独立子进程执行原生模型脚本，子进程退出
时操作系统会回收模型对象与 CUDA 显存。
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from _clone_test_support import CASES, OUTPUT_ROOT, REPO_ROOT, CloneCase, selected_cases


@dataclass(frozen=True)
class LocalModelSpec:
    """一个可由 modelScript 原生 CLI 运行的本地模型配置。"""

    slug: str
    model_name: str
    conda_env: str
    source_script: Path
    model_path: Path
    extra_args: tuple[str, ...] = ()
    required_paths: tuple[Path, ...] = ()
    supports_exact_output: bool = False
    reference_text_option: str | None = None


MODEL_SPECS = {
    "dots_tts_base": LocalModelSpec(
        slug="dots_tts_base",
        model_name="dots.tts-base",
        conda_env="dots_tts",
        source_script=REPO_ROOT / "modelScript/tts_local_dots_tts_base.py",
        model_path=Path("/home/muyi086/hf-mirror/rednote-hilab/dots.tts-base"),
        extra_args=("--local-files-only",),
        reference_text_option="--prompt-text",
    ),
    "qwen3_tts_12hz_1_7b_base": LocalModelSpec(
        slug="qwen3_tts_12hz_1_7b_base",
        model_name="Qwen3-TTS-12Hz-1.7B-Base",
        conda_env="qwen3-tts",
        source_script=REPO_ROOT / "modelScript/tts_local_qwen3_tts_12hz_1_7b_base.py",
        model_path=Path("/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base"),
        extra_args=("--attn-implementation", "sdpa", "--local-files-only"),
        reference_text_option="--ref-text",
    ),
    "voxcpm2": LocalModelSpec(
        slug="voxcpm2",
        model_name="VoxCPM2",
        conda_env="voxcpm2",
        source_script=REPO_ROOT / "modelScript/tts_local_voxcpm2.py",
        model_path=Path("/home/muyi086/hf-mirror/openbmb/VoxCPM2"),
        extra_args=("--style-prompt", "", "--local-files-only"),
        reference_text_option="--prompt-text",
    ),
    "moss_tts_local_transformer": LocalModelSpec(
        slug="moss_tts_local_transformer",
        model_name="MOSS-TTS-Local-Transformer-v1.5",
        conda_env="moss-tts-py310",
        source_script=REPO_ROOT / "modelScript/tts_local_moss_tts_local_transformer.py",
        model_path=Path("/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5"),
        extra_args=(
            "--codec-path",
            "/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer-v2",
            "--local-files-only",
        ),
        required_paths=(Path("/home/muyi086/hf-mirror/OpenMOSS-Team/MOSS-Audio-Tokenizer-v2"),),
    ),
    "longcat_audiodit_1b": LocalModelSpec(
        slug="longcat_audiodit_1b",
        model_name="LongCat-AudioDiT-1B",
        conda_env="longcat_audiodit",
        source_script=REPO_ROOT / "modelScript/tts_local_longcat_audiodit_1b.py",
        model_path=Path("/home/muyi086/hf-mirror/meituan-longcat/LongCat-AudioDiT-1B"),
        extra_args=(
            "--repo-path",
            "/home/muyi086/github/TTS-and-VoiceDesign/api/vendor/LongCat-AudioDiT",
            "--tokenizer-path",
            "/home/muyi086/hf-mirror/google/umt5-base",
            "--local-files-only",
        ),
        required_paths=(
            Path("/home/muyi086/github/TTS-and-VoiceDesign/api/vendor/LongCat-AudioDiT"),
            Path("/home/muyi086/hf-mirror/google/umt5-base"),
        ),
        reference_text_option="--prompt-text",
    ),
    "omnivoice": LocalModelSpec(
        slug="omnivoice",
        model_name="OmniVoice",
        conda_env="omnivoice",
        source_script=REPO_ROOT / "modelScript/tts_local_omnivoice.py",
        model_path=Path("/home/muyi086/hf-mirror/k2-fsa/OmniVoice"),
        extra_args=("--local-files-only",),
        supports_exact_output=True,
        reference_text_option="--ref-text",
    ),
}


def parse_args(spec: LocalModelSpec) -> argparse.Namespace:
    """解析每个模型测试脚本共享的选择与安全参数。"""

    parser = argparse.ArgumentParser(description=f"{spec.model_name} 三角色本地克隆测试")
    parser.add_argument("--model-path", type=Path, default=spec.model_path, help="本地模型目录")
    parser.add_argument(
        "--character",
        choices=[case.character for case in CASES],
        action="append",
        help="只测试指定角色；可重复传入。默认测试全部。",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅校验本地资产并显示执行计划")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖同名的既有输出 WAV")
    return parser.parse_args()


def require_paths(spec: LocalModelSpec, model_path: Path, cases: tuple[CloneCase, ...]) -> None:
    """在启动子进程前检查所有本地输入，避免半途加载大模型后失败。"""

    required = [spec.source_script, model_path, *spec.required_paths]
    required.extend(case.reference_audio for case in cases)
    missing = [str(path) for path in required if not path.is_file() and not path.is_dir()]
    if missing:
        raise FileNotFoundError("本地资产不存在：" + "；".join(missing))


def output_path(spec: LocalModelSpec, case: CloneCase) -> Path:
    """返回项目约定的模型加人物输出文件名。"""

    return OUTPUT_ROOT / f"{spec.model_name}_{case.character}.wav"


def command_for_case(
    spec: LocalModelSpec,
    model_path: Path,
    case: CloneCase,
    text_path: Path,
    staging_dir: Path,
) -> list[str]:
    """构造原生模型 CLI 命令，不经任何中间服务。"""

    command = [
        sys.executable,
        str(spec.source_script),
        "--model-path",
        str(model_path),
        "--text-file",
        str(text_path),
        "--ref-audio",
        str(case.reference_audio),
        *spec.extra_args,
    ]
    if spec.reference_text_option is not None:
        command.extend((spec.reference_text_option, case.reference_text))
    if spec.supports_exact_output:
        command.extend(("--output", str(staging_dir / "generated.wav")))
        if spec.slug == "omnivoice":
            command.extend(("--runtime-cache-dir", str(OUTPUT_ROOT / spec.slug / ".runtime_cache")))
    else:
        command.extend(("--output-dir", str(staging_dir)))
    return command


def generated_wav(staging_dir: Path) -> Path:
    """取得原生脚本在独立暂存目录生成的唯一 WAV 文件。"""

    candidates = sorted(path for path in staging_dir.rglob("*.wav") if path.stat().st_size > 0)
    if len(candidates) != 1:
        raise RuntimeError(f"期望生成 1 个有效 WAV，实际为 {len(candidates)} 个：{candidates}")
    return candidates[0]


def run(spec: LocalModelSpec) -> int:
    """执行一个本地模型的三角色集中克隆。"""

    args = parse_args(spec)
    cases = selected_cases(args.character)
    model_path = args.model_path.expanduser().resolve()
    try:
        require_paths(spec, model_path, cases)
        destinations = [output_path(spec, case) for case in cases]
        if not args.overwrite:
            existing = [str(path) for path in destinations if path.exists()]
            if existing:
                raise FileExistsError("输出已存在；如需重测请传入 --overwrite：" + "；".join(existing))

        if args.dry_run:
            for case, destination in zip(cases, destinations, strict=True):
                print(
                    f"计划：{spec.model_name} | {case.character} | 参考={case.reference_audio} | "
                    f"输出={destination} | conda={spec.conda_env}"
                )
            return 0

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        temporary_root = OUTPUT_ROOT / spec.slug / ".tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        for case, destination in zip(cases, destinations, strict=True):
            with tempfile.TemporaryDirectory(prefix=f"{case.character}-", dir=temporary_root) as temporary:
                staging_dir = Path(temporary)
                text_path = staging_dir / "text.txt"
                text_path.write_text(case.text + "\n", encoding="utf-8")
                command = command_for_case(spec, model_path, case, text_path, staging_dir)
                print(f"开始：{spec.model_name} / {case.character}")
                print(f"命令：{shlex.join(command)}")
                subprocess.run(command, cwd=REPO_ROOT, check=True)
                source = generated_wav(staging_dir)
                source.replace(destination)
                print(f"完成：{destination}")
        print(f"{spec.model_name} 全部角色已完成；每个角色的模型子进程均已退出并释放显存。")
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
