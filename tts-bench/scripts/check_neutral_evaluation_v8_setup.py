#!/usr/bin/env python3
"""在加载 ASR 前检查 Task 8 V8 公共评测环境、输入与冻结哈希。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_neutral_evaluation_v9_setup import run_check  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v8.json",
    )
    parser.add_argument("--strict-versions", action="store_true", help="版本漂移视为失败。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_check(
        args.config,
        args.strict_versions,
        expected_schema_version="8.0",
        version_label="V8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
