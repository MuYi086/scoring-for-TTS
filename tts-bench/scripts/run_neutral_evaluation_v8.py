#!/usr/bin/env python3
"""Task 9 V8 长音频六后端中立评测入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_neutral_evaluation_v4 import METRICS, run  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "longAudioTestV8" / "评测结果" / "task9-v8-raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v8.json",
        help="V8 长音频冻结配置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="本次原始结果目录；正式复测应使用一个尚不存在的新目录。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=METRICS,
        default=list(METRICS),
        help="只运行指定后端，用于排错或断点续跑。",
    )
    parser.add_argument(
        "--model-id",
        required=True,
        help="本次唯一允许分析的模型；一次调用不得处理多条模型长音频。",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=PROJECT_ROOT / "longAudioTestV8" / "评测结果",
        help="单模型六后端完成后写入独立评价报告的目录。",
    )
    parser.add_argument("--resume", action="store_true", help="续跑同一次未完成的 V8 评测。")
    parser.add_argument("--strict", action="store_true", help="所选后端存在任一缺失或错误时返回非零状态。")
    return parser.parse_args()


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"V8 长音频中立评测失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
