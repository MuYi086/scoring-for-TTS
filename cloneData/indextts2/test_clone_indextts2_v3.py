#!/usr/bin/env python3
"""Task 4 V3 IndexTTS2 三角色克隆，保留任务指定的情感向量。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))


BASE_SCRIPT = Path(__file__).with_name("test_clone_indextts2.py")
BASE_SPEC = importlib.util.spec_from_file_location("_clone_indextts2_base", BASE_SCRIPT)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"无法加载 IndexTTS2 基础脚本：{BASE_SCRIPT}")
BASE_MODULE = importlib.util.module_from_spec(BASE_SPEC)
sys.modules[BASE_SPEC.name] = BASE_MODULE
BASE_SPEC.loader.exec_module(BASE_MODULE)

CloneCase = BASE_MODULE.CloneCase
REPO_ROOT = BASE_MODULE.REPO_ROOT
run_main = BASE_MODULE.main


OUTPUT_ROOT = REPO_ROOT / "cloneData" / "audio_v3"
CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白_v3.wav",
        emotion_vector=(0, 0, 0, 0, 0, 0, 0, 0.5),
        text="三皇子大吃一惊，对辰南的身份开始胡乱猜疑起来，他咳嗽了一声，",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v3.wav",
        emotion_vector=(0, 0.5, 0, 0, 0, 0, 0, 0),
        text="认识，当然认识。",
    ),
    CloneCase(
        character="辰南",
        reference_audio=REPO_ROOT / "testData/mimo_辰南_v3.wav",
        emotion_vector=(0, 0, 0, 0, 0, 0.35, 0, 0),
        text="请公主殿下责罚。",
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_main(CASES, OUTPUT_ROOT))
