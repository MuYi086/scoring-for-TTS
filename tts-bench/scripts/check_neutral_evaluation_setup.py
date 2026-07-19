#!/usr/bin/env python3
"""在加载评价模型前检查 V2 环境、权重、音频矩阵和登记哈希。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_automated_evaluation import load_json, sha256_file  # noqa: E402
from run_neutral_evaluation_v2 import build_inputs, validate_config  # noqa: E402


KNOWN_GOOD_PYTHON = (3, 10)
KNOWN_GOOD_PACKAGES = {
    "torch": "2.12.0",
    "torchaudio": "2.11.0",
    "torchvision": "0.27.0",
    "transformers": "5.12.0",
    "funasr": "1.3.9",
    "speechbrain": "1.1.0",
    "utmosv2": "1.3.1.dev0",
    "librosa": "0.11.0",
    "soundfile": "0.14.0",
    "numpy": "1.26.4",
    "pandas": "2.3.3",
    "matplotlib": "3.10.9",
    "numba": "0.65.1",
    "huggingface-hub": "1.19.0",
}


@dataclass
class CheckReport:
    """预检消息集合。"""

    passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def version_mismatch(self, message: str, strict_versions: bool) -> None:
        (self.errors if strict_versions else self.warnings).append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "runs-v2",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v2.json",
    )
    parser.add_argument(
        "--assets",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "evaluation-assets-v2.json",
    )
    parser.add_argument(
        "--strict-versions",
        action="store_true",
        help="把 Python、包、模型 revision 不一致视为失败。",
    )
    return parser.parse_args()


def local_dir_metadata_revision(model_dir: Path, marker: str) -> str | None:
    metadata = model_dir / ".cache" / "huggingface" / "download" / f"{marker}.metadata"
    if not metadata.is_file():
        return None
    lines = metadata.read_text(encoding="utf-8").splitlines()
    return lines[0].strip() if lines else None


def huggingface_cache_dir(hf_home: Path, model_id: str, revision: str) -> Path:
    cache_name = "models--" + model_id.replace("/", "--")
    return hf_home / "hub" / cache_name / "snapshots" / revision


def check_package_versions(report: CheckReport, strict_versions: bool) -> None:
    if sys.version_info[:2] == KNOWN_GOOD_PYTHON:
        report.passed.append(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        report.version_mismatch(
            "Python 应为已验证的 3.10，实际为 "
            f"{sys.version_info.major}.{sys.version_info.minor}",
            strict_versions,
        )

    for package, expected in KNOWN_GOOD_PACKAGES.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report.errors.append(f"缺少 Python 包：{package}=={expected}")
            continue
        if actual == expected:
            report.passed.append(f"{package}=={actual}")
        else:
            report.version_mismatch(
                f"{package} 版本应为 {expected}，实际为 {actual}",
                strict_versions,
            )


def check_environment(report: CheckReport, config: dict[str, Any]) -> tuple[Path, Path] | None:
    try:
        validate_config(config)
    except ValueError as exc:
        report.errors.append(str(exc))
        return None

    mirror_root = Path(os.environ["HF_MIRROR_ROOT"]).expanduser()
    hf_home_value = os.environ.get("HF_HOME")
    if not hf_home_value:
        report.errors.append("必须设置 HF_HOME，UTMOSv2 的 Wav2Vec2 依赖从该缓存离线加载")
        return None
    hf_home = Path(hf_home_value).expanduser()

    for name in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"]:
        if os.environ.get(name) == "1":
            report.passed.append(f"{name}=1")
        else:
            report.warnings.append(f"建议在正式复测时设置 {name}=1")

    needs_cuda = any(
        str(section.get("device", "")).startswith("cuda")
        for section in config.values()
        if isinstance(section, dict)
    )
    if needs_cuda:
        try:
            import torch
        except ImportError:
            report.errors.append("缺少 torch，无法检查 CUDA")
        else:
            if torch.cuda.is_available():
                report.passed.append(f"CUDA 可用：{torch.cuda.get_device_name(0)}")
            else:
                report.errors.append("V2 配置要求 CUDA，但 torch.cuda.is_available() 为 False")
    return mirror_root, hf_home


def check_assets(
    report: CheckReport,
    assets: dict[str, Any],
    mirror_root: Path,
    hf_home: Path,
    strict_versions: bool,
) -> None:
    if assets.get("schema_version") != "1.0":
        report.errors.append("仅支持 schema_version=1.0 的评价资产清单")
        return

    for model in assets["local_models"]:
        model_dir = mirror_root / model["model_id"]
        marker = model_dir / model["marker"]
        if not marker.is_file():
            report.errors.append(f"缺少评价模型文件：{marker}")
            continue
        actual_revision = local_dir_metadata_revision(model_dir, model["marker"])
        if actual_revision == model["revision"]:
            report.passed.append(f"{model['model_id']}@{actual_revision[:12]}")
        elif actual_revision is None:
            report.version_mismatch(
                f"{model['model_id']} 文件存在，但缺少 Hugging Face revision 元数据",
                strict_versions,
            )
        else:
            report.version_mismatch(
                f"{model['model_id']} revision 应为 {model['revision']}，实际为 {actual_revision}",
                strict_versions,
            )

    for model in assets["cached_models"]:
        snapshot = huggingface_cache_dir(hf_home, model["model_id"], model["revision"])
        if snapshot.is_dir():
            report.passed.append(f"{model['model_id']}@{model['revision'][:12]} 缓存完整")
        else:
            report.errors.append(f"缺少 Hugging Face 缓存快照：{snapshot}")

    for item in assets["files"]:
        path = mirror_root / item["path"]
        if not path.is_file():
            report.errors.append(f"缺少评价资产：{path}")
        elif sha256_file(path) != item["sha256"]:
            report.errors.append(f"评价资产 SHA-256 不一致：{path}")
        else:
            report.passed.append(f"资产校验通过：{item['path']}")

    for repository in assets["git_repositories"]:
        path = mirror_root / repository["path"]
        try:
            revision = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            report.version_mismatch(
                f"无法确认本地 Git 仓库 revision：{path}",
                strict_versions,
            )
            continue
        if revision == repository["revision"]:
            report.passed.append(f"{repository['path']}@{revision[:12]}")
        else:
            report.version_mismatch(
                f"{repository['path']} revision 应为 {repository['revision']}，实际为 {revision}",
                strict_versions,
            )


def print_report(report: CheckReport) -> None:
    for label, messages in [
        ("通过", report.passed),
        ("警告", report.warnings),
        ("失败", report.errors),
    ]:
        for message in messages:
            print(f"[{label}] {message}")
    print(
        f"预检汇总：通过 {len(report.passed)}，警告 {len(report.warnings)}，失败 {len(report.errors)}"
    )


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    assets = load_json(args.assets)
    report = CheckReport()
    check_package_versions(report, args.strict_versions)
    roots = check_environment(report, config)
    if roots is not None:
        mirror_root, hf_home = roots
        check_assets(report, assets, mirror_root, hf_home, args.strict_versions)
        try:
            references, syntheses = build_inputs(args.runs_root, config)
        except (ValueError, OSError, KeyError) as exc:
            report.errors.append(f"输入矩阵检查失败：{exc}")
        else:
            report.passed.append(
                f"输入矩阵完整：{len(references)} 条参考音频、{len(syntheses)} 条克隆音频"
            )
    print_report(report)
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
