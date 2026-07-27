#!/usr/bin/env python3
"""在加载 ASR 前检查 Task 9 V9 公共评测环境、输入与冻结哈希。"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_neutral_evaluation_setup import CheckReport, print_report  # noqa: E402
from public_evaluation_v9 import load_json, validate_config  # noqa: E402
from run_automated_evaluation import sha256_file  # noqa: E402
from public_evaluation_v9 import build_inputs, load_dialogues  # noqa: E402


REQUIRED_PACKAGES = {
    "torch": "2.12.0",
    "torchaudio": "2.11.0",
    "funasr": "1.3.9",
    "transformers": "5.12.0",
    "soundfile": "0.14.0",
    "scipy": "1.15.3",
    "jiwer": None,
    "zhconv": None,
    "zhon": "2.1.1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v9.json",
    )
    parser.add_argument("--strict-versions", action="store_true", help="版本漂移视为失败。")
    return parser.parse_args()


def check_package_versions(report: CheckReport, strict_versions: bool) -> None:
    if sys.version_info[:2] == (3, 10):
        report.passed.append(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        report.version_mismatch(
            f"Python 应为已验证的 3.10，实际为 {sys.version_info.major}.{sys.version_info.minor}",
            strict_versions,
        )
    for package, expected in REQUIRED_PACKAGES.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report.errors.append(f"缺少公共 V9 运行包：{package}")
            continue
        if expected is None or actual == expected:
            report.passed.append(f"{package}=={actual}")
        else:
            report.version_mismatch(
                f"{package} 应为 {expected}，实际为 {actual}", strict_versions
            )


def check_model(
    report: CheckReport,
    mirror_root: Path,
    section_name: str,
    section: dict[str, Any],
    marker: str,
    strict_versions: bool,
) -> None:
    model_id = str(section["model_id"])
    model_dir = mirror_root / model_id
    model_file = model_dir / marker
    if not model_file.is_file():
        report.errors.append(f"缺少 {section_name} 本地模型文件：{model_file}")
        return
    actual_hash = sha256_file(model_file)
    if actual_hash != section["model_sha256"]:
        report.errors.append(f"{section_name} 模型 SHA-256 不一致：{model_file}")
    else:
        report.passed.append(f"{section_name} 模型哈希已冻结：{model_id}")
    metadata_path = model_dir / ".cache" / "huggingface" / "download" / f"{marker}.metadata"
    revision = metadata_path.read_text(encoding="utf-8").splitlines()[0].strip() if metadata_path.is_file() else None
    if revision == section["revision"]:
        report.passed.append(f"{section_name} revision：{revision[:12]}")
    elif revision is None:
        report.version_mismatch(
            f"{section_name} 缺少 Hugging Face revision 元数据：{metadata_path}", strict_versions
        )
    else:
        report.version_mismatch(
            f"{section_name} revision 应为 {section['revision']}，实际为 {revision}", strict_versions
        )


def check_environment(report: CheckReport) -> Path | None:
    mirror_value = os.environ.get("HF_MIRROR_ROOT")
    if not mirror_value:
        report.errors.append("必须设置 HF_MIRROR_ROOT，公共 V9 评测不允许隐式联网下载")
        return None
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) == "1":
            report.passed.append(f"{name}=1")
        else:
            report.warnings.append(f"正式复测建议设置 {name}=1")
    try:
        import torch
    except ImportError:
        report.errors.append("缺少 torch，无法检查 CUDA")
    else:
        if torch.cuda.is_available():
            report.passed.append(f"CUDA 可用：{torch.cuda.get_device_name(0)}")
        else:
            report.errors.append("V9 配置要求 CUDA，但 torch.cuda.is_available() 为 False")
    return Path(mirror_value).expanduser()


def check_inputs(report: CheckReport, config: dict[str, Any]) -> None:
    try:
        dialogues = load_dialogues(config)
        references, syntheses = build_inputs(config, dialogues)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        report.errors.append(f"V9 输入或登记哈希检查失败：{exc}")
        return
    report.passed.append(f"V9 输入完整：{len(references)} 条角色参考音频、{len(syntheses)} 条模型长音频")
    report.passed.append(f"实际 CER 台词串：{len(dialogues)} 段、{config['source']['normalized_character_count']} 个规范化字符")


def main() -> int:
    args = parse_args()
    report = CheckReport()
    try:
        config = load_json(args.config)
        validate_config(config)
    except (KeyError, TypeError, ValueError) as exc:
        report.errors.append(str(exc))
        print_report(report)
        return 2
    check_package_versions(report, args.strict_versions)
    mirror_root = check_environment(report)
    if mirror_root is not None:
        check_model(report, mirror_root, "SenseVoice", config["sensevoice"], "model.pt", args.strict_versions)
        check_model(report, mirror_root, "Whisper-large-v3-turbo", config["whisper"], "model.safetensors", args.strict_versions)
        check_inputs(report, config)
    print_report(report)
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
