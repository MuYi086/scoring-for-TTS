#!/usr/bin/env python3
"""Task 6 V6 第一阶段：仅用 IndexTTS2 与 VoxCPM2 合成长音频成品。"""

from __future__ import annotations

import sys
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
TASK8_DIR = PROJECT_ROOT / "task-runner" / "task8"
if str(TASK8_DIR) not in sys.path:
    sys.path.insert(0, str(TASK8_DIR))

import run_task8_synthesis as engine  # noqa: E402


def configure_engine() -> None:
    """把共享分段、逐段证据合成器绑定到 V6 的冻结输入。"""
    engine.TASK_ID = "task6"
    engine.TASK_LABEL = "Task 6"
    engine.DEFAULT_TASK_DIR = PROJECT_ROOT / "longAudioTestV6"
    engine.DEFAULT_PLAN = engine.DEFAULT_TASK_DIR / ".task6-synthesis-plan.json"
    engine.PLAN_SCHEMA_VERSION = "task6-synthesis-plan-v2"
    engine.VERSION = "V6"
    engine.TEXT_PATH = "longAudioTestV6/text.md"
    engine.REFERENCE_AUDIO_PATH = "longAudioTestV6/mimo_旁白_v6.wav"
    engine.REFERENCE_TRANSCRIPT = "夜色中，两路人马各怀心思，表面客套，暗藏机锋，彼此试探周旋。"
    engine.VOICE_DESCRIPTION = (
        "男性，中年，音域中低，声线厚实略带磁性，明亮而不刺耳，音色沉稳平和中蕴含细微的叙述张力。"
        "咬字清晰干脆，语速中等偏慢，节奏均匀从容，语气平稳理性，自带一种冷眼旁观、洞察世事的气质。"
    )


def main() -> int:
    configure_engine()
    return engine.main()


if __name__ == "__main__":
    raise SystemExit(main())
