#!/usr/bin/env python3
"""在 omnivoice conda 环境中直接执行 OmniVoice 三角色克隆。"""

from pathlib import Path
import sys


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))

from _direct_local_clone_runner import MODEL_SPECS, run


if __name__ == "__main__":
    raise SystemExit(run(MODEL_SPECS["omnivoice"]))
