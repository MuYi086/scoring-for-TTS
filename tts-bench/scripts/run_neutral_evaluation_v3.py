#!/usr/bin/env python3
"""Task 4 V3 六后端中立评测入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_neutral_evaluation_v2 import METRICS, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "runs-v3",
        help="Task 4 V3 的八个合成运行目录。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v3.json",
        help="V3 中立评测冻结配置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "reports" / "task4-2026-07-19-v3-r02",
        help="V3 原始评测结果目录。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=METRICS,
        default=list(METRICS),
        help="只运行指定后端，用于排错或断点续跑。",
    )
    parser.add_argument("--resume", action="store_true", help="续跑同一次未完成的 V3 评测。")
    parser.add_argument("--strict", action="store_true", help="所选后端存在任一缺失或错误时返回非零状态。")
    return parser.parse_args()


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"V3 中立评测失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
