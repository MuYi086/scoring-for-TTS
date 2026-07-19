#!/usr/bin/env python3
"""Task 3 V2 IndexTTS2 三角色克隆，保留任务指定的情感向量。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))


BASE_SCRIPT = Path(__file__).with_name("test_clone_indextts2.py")
BASE_SPEC = importlib.util.spec_from_file_location("_clone_indextts2_base_v2", BASE_SCRIPT)
if BASE_SPEC is None or BASE_SPEC.loader is None:
    raise RuntimeError(f"无法加载 IndexTTS2 基础脚本：{BASE_SCRIPT}")
BASE_MODULE = importlib.util.module_from_spec(BASE_SPEC)
sys.modules[BASE_SPEC.name] = BASE_MODULE
BASE_SPEC.loader.exec_module(BASE_MODULE)

CloneCase = BASE_MODULE.CloneCase
REPO_ROOT = BASE_MODULE.REPO_ROOT
run_main = BASE_MODULE.main


OUTPUT_ROOT = REPO_ROOT / "cloneData" / "audio_v2"
CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白_v2.wav",
        emotion_vector=(0, 0, 0, 0, 0, 0, 0, 0.5),
        text="看着小恶魔那甜甜的微笑，他感觉身体一阵颤栗，他想挣扎，却动弹不得，想大声呼喊，却发不出声音，眨眼间，冷汗浸透了他的衣衫。",
    ),
    CloneCase(
        character="辰南",
        reference_audio=REPO_ROOT / "testData/mimo_辰南_v2.wav",
        emotion_vector=(0, 0, 0, 1, 0, 0, 0, 0),
        text="人为刀俎，我为鱼肉。刚刚出来游历，便要遭受这番悲惨遭遇，老天你不会在和我开玩笑吧？",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v2.wav",
        emotion_vector=(0.75, 0, 0, 0, 0, 0, 0, 0),
        text="你们说，当我把烈火仙莲献给我父皇之后，他会是什么表情？嗯，我猜他一定会笑的合不拢嘴，允许我以后自由出入皇城。呵呵，真是太好了，以后我想到哪里玩，就到哪里玩，再也没有人会阻止我了，呵呵……",
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_main(CASES, OUTPUT_ROOT))
