#!/usr/bin/env python3
"""在 voxcpm2 conda 环境中执行 Task 4 V3 三角色克隆。"""

from pathlib import Path
import sys


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))

from _clone_test_support_v3 import CASES, OUTPUT_ROOT
from _direct_local_clone_runner import MODEL_SPECS, run


if __name__ == "__main__":
    raise SystemExit(run(MODEL_SPECS["voxcpm2"], CASES, OUTPUT_ROOT))
