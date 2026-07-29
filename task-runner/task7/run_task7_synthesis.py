#!/usr/bin/env python3
"""Task 7 V7 第一阶段：仅用 IndexTTS2 与 VoxCPM2 合成长音频成品。"""

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
    """把共享分段、逐段证据合成器绑定到 V7 的冻结输入。"""
    engine.TASK_ID = "task7"
    engine.TASK_LABEL = "Task 7"
    engine.DEFAULT_TASK_DIR = PROJECT_ROOT / "longAudioTestV7"
    engine.DEFAULT_PLAN = engine.DEFAULT_TASK_DIR / ".task7-synthesis-plan.json"
    engine.PLAN_SCHEMA_VERSION = "task7-synthesis-plan-v2"
    engine.VERSION = "V7"
    engine.TEXT_PATH = "longAudioTestV7/text.md"
    engine.REFERENCE_AUDIO_PATH = "longAudioTestV7/mimo_旁白_v7.wav"
    engine.REFERENCE_TRANSCRIPT = "夜夜如此，我听见头顶传来三声闷响，不像老鼠，更像精准的敲击。"
    engine.VOICE_DESCRIPTION = (
        "成年女性，中频偏暗，音色略带沙哑与气声，声线薄透但不过分尖锐，共鸣自然，发声力度适中偏轻柔。"
        "咬字清晰利落，语速中等偏慢，节奏均匀，停顿自然沉稳，默认情绪基调为冷静克制的叙述，"
        "隐含一丝不安但波动极小，整体气质内敛而耐听。"
    )


def main() -> int:
    configure_engine()
    return engine.main()


if __name__ == "__main__":
    raise SystemExit(main())
