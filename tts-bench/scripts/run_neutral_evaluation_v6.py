#!/usr/bin/env python3
"""Task 6 V6 公共评测受限入口。

仅执行音频交付原始测量、SenseVoice CER 与 Whisper-large-v3-turbo CER。
长音频 WavLM / ECAPA、UTMOSv2、NISQA 和自动综合排名已被公共任务排除。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from public_evaluation_v9 import PUBLIC_METRICS, run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v6.json",
        help="V6 公共评测冻结配置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="本次原始结果目录；正式评分必须传入尚不存在的新目录。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=PUBLIC_METRICS,
        default=list(PUBLIC_METRICS),
        help="仅可选择公共任务允许的后端；默认运行全部三个。",
    )
    parser.add_argument(
        "--model-id",
        required=True,
        help="本次唯一允许分析的模型；一次调用不得处理多条模型长音频。",
    )
    parser.add_argument("--resume", action="store_true", help="仅续跑同一次未完成的 V6 评测。")
    parser.add_argument("--strict", action="store_true", help="所选指标存在缺失或错误时返回非零状态。")
    return parser.parse_args()


def main() -> int:
    return run(parse_args(), expected_schema_version="6.0", version_label="V6")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"V6 公共评测失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
