#!/usr/bin/env python3
"""从 Task 7 V7 受限公共评测原始结果生成中文报告。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_neutral_v9_reports import build_reports as build_shared_reports  # noqa: E402


DEFAULT_REPORTS = PROJECT_ROOT / "longAudioTestV7" / "评测结果"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper-large-v3-turbo_CER_V7评价报告.md",
    "delivery": "音频交付与文本一致性_V7自动检查报告.md",
}
ROLE_ORDER = {"旁白": 0, "我": 1, "警察": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True, help="已完成的公共 V7 原始结果目录。")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    return parser.parse_args()


def build_reports(results_dir: Path, results_link: str | None = None) -> dict[str, str]:
    """以 V7 冻结角色和版本标识渲染两份公共报告。"""

    return build_shared_reports(
        results_dir,
        results_link,
        schema_version="7.0",
        version_label="V7",
        role_order=ROLE_ORDER,
    )


def main() -> int:
    args = parse_args()
    reports = build_reports(args.results_dir)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    link = Path(os.path.relpath(args.results_dir.resolve(), start=args.reports_dir.resolve())).as_posix()
    reports = build_reports(args.results_dir, link)
    for report_id, content in reports.items():
        path = args.reports_dir / REPORT_FILENAMES[report_id]
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"V7 公共报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
