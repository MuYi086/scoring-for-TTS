#!/usr/bin/env python3
"""在正式评测前只读检查 Task 8 V8 的音频、环境与本地 ASR 资产。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from run_task8_evaluation import DEFAULT_CONTRACT, check_preflight, discover_models, load_contract


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--hf-mirror-root", type=Path, default=os.getenv("HF_MIRROR_ROOT"))
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(args.contract.expanduser().resolve())
        models = discover_models(contract)
        root = args.hf_mirror_root.expanduser().resolve() if args.hf_mirror_root else None
        errors = check_preflight(contract, models, root)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Task 8 评测预检失败：{error}", file=sys.stderr)
        return 2
    if errors:
        print("Task 8 评测预检失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print(
        "Task 8 评测预检通过：text.md、共享分段清单、旁白参考音频、全部 audio_*.wav 及其哈希绑定逐段证据、"
        "本地 SenseVoiceSmall 与 Whisper-large-v3-turbo、pypinyin、CUDA 和 pip check 均可用。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
