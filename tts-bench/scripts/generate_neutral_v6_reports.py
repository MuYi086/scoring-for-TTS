#!/usr/bin/env python3
"""从 Task 7 V6 原始结果生成单模型、三维度和综合中文评价报告。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_neutral_v5_reports as shared  # noqa: E402


DEFAULT_RESULTS = PROJECT_ROOT / "longAudioTestV6" / "评测结果" / "task7-v6-raw"
DEFAULT_REPORTS = PROJECT_ROOT / "longAudioTestV6" / "评测结果"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper_CER_V6评价报告.md",
    "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V6评价报告.md",
    "quality": "UTMOSv2&NISQA_V6评价报告.md",
    # task7.md 明确指定该文件名；报告正文与数据版本仍为 V6。
    "comprehensive": "小说转有声TTS_V5综合评价报告.md",
}
ROLE_ORDER = {"旁白": 0, "三皇子": 1, "小公主": 2, "辰南": 3}


def configure_shared_renderer() -> None:
    """为复用的长音频报告渲染器注入 V6 冻结常量。"""

    shared.REPORT_VERSION = "V6"
    shared.SCHEMA_VERSION = "6.0"
    shared.SOURCE_DISPLAY_PATH = "longAudioTestV6/ai_deal.json"
    shared.CONFIG_DISPLAY_PATH = "tts-bench/config/neutral-evaluation-v6.json"
    shared.REPORT_FILENAMES = REPORT_FILENAMES
    shared.ROLE_ORDER = ROLE_ORDER


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--model-id",
        help="只生成一个已完成模型的独立报告；省略时要求全部模型完成并生成四份最终报告。",
    )
    return parser.parse_args()


def model_report_filename(model_id: str) -> str:
    configure_shared_renderer()
    return shared.model_report_filename(model_id)


def build_model_report(
    results_dir: Path, model_id: str, results_link: str | None = None
) -> str:
    configure_shared_renderer()
    return shared.build_model_report(results_dir, model_id, results_link)


def write_model_report(results_dir: Path, reports_dir: Path, model_id: str) -> Path:
    configure_shared_renderer()
    return shared.write_model_report(results_dir, reports_dir, model_id)


def build_reports(results_dir: Path, results_link: str | None = None) -> dict[str, str]:
    configure_shared_renderer()
    return shared.build_reports(results_dir, results_link)


def main() -> int:
    args = parse_args()
    if args.model_id:
        print(write_model_report(args.results_dir, args.reports_dir, args.model_id))
        return 0
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    results_link = Path(
        os.path.relpath(args.results_dir.resolve(), start=args.reports_dir.resolve())
    ).as_posix()
    for report_id, content in build_reports(args.results_dir, results_link).items():
        path = args.reports_dir / REPORT_FILENAMES[report_id]
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"V6 报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
