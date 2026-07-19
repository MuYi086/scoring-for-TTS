#!/usr/bin/env python3
"""在 dots_tts conda 环境中执行 Task 3 V2 三角色克隆。"""

from pathlib import Path
import sys


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))

from _clone_test_support_v2 import CASES, OUTPUT_ROOT
from _direct_local_clone_runner import MODEL_SPECS, run


if __name__ == "__main__":
    raise SystemExit(run(MODEL_SPECS["dots_tts_base"], CASES, OUTPUT_ROOT))
