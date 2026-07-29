#!/usr/bin/env python3
"""Task 6 V6 第二阶段：哈希绑定逐段证据双 ASR 公共评测入口。"""

from __future__ import annotations

import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
TASK8_DIR = PROJECT_ROOT / "task-runner" / "task8"
if str(TASK8_DIR) not in sys.path:
    sys.path.insert(0, str(TASK8_DIR))

import run_task8_evaluation as engine  # noqa: E402


DEFAULT_CONTRACT = TASK_DIR / "evaluation-contract.json"
RESULT_FILE_NAME = "task6_evaluation_results.json"


def configure_engine() -> None:
    engine.DEFAULT_CONTRACT = DEFAULT_CONTRACT
    engine.RESULT_FILE_NAME = RESULT_FILE_NAME


def parse_args(argv: list[str] | None = None):
    configure_engine()
    return engine.parse_args(argv)


def load_contract(path: Path):
    return engine.load_contract(path)


discover_models = engine.discover_models
check_preflight = engine.check_preflight


def run(args) -> int:
    configure_engine()
    return engine.run(args)


def main() -> int:
    try:
        return run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Task 6 公共评测失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
