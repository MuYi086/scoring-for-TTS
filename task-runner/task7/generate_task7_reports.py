#!/usr/bin/env python3
"""从 Task 7 V7 原始结果生成两份公共中文报告。"""

from __future__ import annotations

import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
TASK8_DIR = PROJECT_ROOT / "task-runner" / "task8"
if str(TASK8_DIR) not in sys.path:
    sys.path.insert(0, str(TASK8_DIR))

import generate_task8_reports as engine  # noqa: E402


DEFAULT_REPORTS_DIR = PROJECT_ROOT / "longAudioTestV7" / "评测结果"
RESULT_FILE_NAME = "task7_evaluation_results.json"
CER_REPORT_NAME = "SenseVoice_CER&Whisper-large-v3-turbo_CER_V7评价报告.md"
AUTOMATED_REPORT_NAME = "音频交付与文本一致性_V7自动检查报告.md"


def configure_engine() -> None:
    engine.DEFAULT_REPORTS_DIR = DEFAULT_REPORTS_DIR
    engine.RESULT_FILE_NAME = RESULT_FILE_NAME
    engine.CER_REPORT_NAME = CER_REPORT_NAME
    engine.AUTOMATED_REPORT_NAME = AUTOMATED_REPORT_NAME


def parse_args(argv: list[str] | None = None):
    configure_engine()
    return engine.parse_args(argv)


def write_reports(results_dir: Path, reports_dir: Path):
    configure_engine()
    return engine.write_reports(results_dir, reports_dir)


def main() -> int:
    args = parse_args()
    try:
        cer_path, automated_path = write_reports(args.results_dir, args.reports_dir)
    except ValueError as error:
        print(f"Task 7 报告生成失败：{error}", file=sys.stderr)
        return 2
    print(cer_path)
    print(automated_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
