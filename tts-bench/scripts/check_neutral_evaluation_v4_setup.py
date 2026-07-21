#!/usr/bin/env python3
"""在加载评价模型前检查 Task 5 V4 环境、权重、长音频和冻结哈希。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_neutral_evaluation_setup import (  # noqa: E402
    CheckReport,
    check_assets,
    check_package_versions,
    print_report,
)
from run_automated_evaluation import load_json, normalize_zh_v1, project_path  # noqa: E402
from run_neutral_evaluation_v4 import (  # noqa: E402
    build_inputs,
    load_dialogues,
    validate_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v4.json",
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


def check_environment(report: CheckReport, config: dict[str, Any]) -> tuple[Path, Path] | None:
    try:
        validate_config(config)
    except (KeyError, TypeError, ValueError) as exc:
        report.errors.append(str(exc))
        return None

    mirror_root_value = os.environ.get("HF_MIRROR_ROOT")
    if not mirror_root_value:
        report.errors.append("必须设置 HF_MIRROR_ROOT，V4 评测不允许隐式联网下载")
        return None
    mirror_root = Path(mirror_root_value).expanduser()
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

    try:
        import torch
    except ImportError:
        report.errors.append("缺少 torch，无法检查 CUDA")
    else:
        if torch.cuda.is_available():
            report.passed.append(f"CUDA 可用：{torch.cuda.get_device_name(0)}")
        else:
            report.errors.append("V4 配置要求 CUDA，但 torch.cuda.is_available() 为 False")
    return mirror_root, hf_home


def check_inputs(report: CheckReport, config: dict[str, Any]) -> None:
    try:
        dialogues = load_dialogues(config)
        references, syntheses = build_inputs(config, dialogues)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        report.errors.append(f"V4 输入检查失败：{exc}")
        return

    role_counts: dict[str, int] = {}
    for row in dialogues:
        role = str(row["role_name"])
        role_counts[role] = role_counts.get(role, 0) + 1
    report.passed.append(
        f"V4 输入完整：{len(references)} 条角色参考音频、{len(syntheses)} 条模型长音频"
    )
    report.passed.append(
        f"角色台词完整：{len(dialogues)} 段，分布 "
        + "、".join(f"{role} {count}" for role, count in role_counts.items())
    )

    raw_text = project_path(config["source"]["raw_text_path"]).read_text(encoding="utf-8")
    dialogue_text = "".join(row["text_content"] for row in dialogues)
    if normalize_zh_v1(raw_text) == normalize_zh_v1(dialogue_text):
        report.errors.append("text.md 与 ai_deal.json 意外变为相同文本，需重新确认 V4 CER 参考")
    elif config["source"].get("raw_text_relation"):
        report.passed.append("已冻结 text.md 与 ai_deal.json 不同，并明确以 ai_deal.json 台词串计算 CER")
    else:
        report.errors.append("text.md 与 ai_deal.json 不同，但配置未说明 raw_text_relation")


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
        check_inputs(report, config)
    print_report(report)
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
