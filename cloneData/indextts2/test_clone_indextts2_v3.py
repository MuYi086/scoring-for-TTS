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
        text="小公主恶狠狠的盯着他，其中的意思再明显不过，威胁兼恐吓让他配合。",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v3.wav",
        emotion_vector=(0, 0, 0, 0, 0.75, 0, 0, 0),
        text="他是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子你没想到会这么快见到我吧？",
    ),
    CloneCase(
        character="三皇子",
        reference_audio=REPO_ROOT / "testData/mimo_三皇子_v3.wav",
        emotion_vector=(0, 0, 0, 0, 0, 0, 0, 0.35),
        text="这个人在路上一直鬼鬼祟祟地跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？",
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_main(CASES, OUTPUT_ROOT))
