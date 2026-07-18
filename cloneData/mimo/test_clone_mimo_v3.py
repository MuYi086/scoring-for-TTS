#!/usr/bin/env python3
"""Task 4 V3：直接调用 MiMo 官方云端 voiceclone 接口。"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))

from _clone_test_support import REPO_ROOT
from _clone_test_support_v3 import CASES, OUTPUT_ROOT


SOURCE_SCRIPT = REPO_ROOT / "modelScript/tts_cloud_mimo.py"
MODEL_NAME = "mimo-v2.5-tts-voiceclone"


def parse_args() -> argparse.Namespace:
    """解析 V3 角色选择与覆盖策略。"""

    parser = argparse.ArgumentParser(description="MiMo-V2.5-TTS V3 三角色克隆")
    parser.add_argument("--character", choices=[case.character for case in CASES], action="append")
    parser.add_argument("--dry-run", action="store_true", help="只校验并显示请求摘要")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖同名 WAV")
    return parser.parse_args()


def selected_cases(characters: list[str] | None):
    """按声明顺序返回指定角色。"""

    if not characters:
        return CASES
    requested = set(characters)
    return tuple(case for case in CASES if case.character in requested)


def output_path(character: str) -> Path:
    """返回 V3 的固定输出路径。"""

    return OUTPUT_ROOT / f"{MODEL_NAME}_{character}.wav"


def command_for_case(case, text_path: Path, destination: Path, dry_run: bool) -> list[str]:
    """构造单角色 MiMo 官方 CLI 请求。"""

    command = [
        sys.executable,
        str(SOURCE_SCRIPT),
        "--model",
        MODEL_NAME,
        "--text-file",
        str(text_path),
        "--ref-audio",
        str(case.reference_audio),
        "--instruction",
        "",
        "--output",
        str(destination),
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def main() -> int:
    """逐角色执行 V3 MiMo 声音克隆。"""

    args = parse_args()
    cases = selected_cases(args.character)
    try:
        missing = [str(path) for path in [SOURCE_SCRIPT, *(case.reference_audio for case in cases)] if not path.is_file()]
        if missing:
            raise FileNotFoundError("本地资产不存在：" + "；".join(missing))
        if not args.overwrite:
            existing = [str(output_path(case.character)) for case in cases if output_path(case.character).exists()]
            if existing:
                raise FileExistsError("输出已存在；如需重测请传入 --overwrite：" + "；".join(existing))

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        temporary_root = OUTPUT_ROOT / ".tmp" / "mimo"
        temporary_root.mkdir(parents=True, exist_ok=True)
        for case in cases:
            with tempfile.TemporaryDirectory(prefix="mimo-", dir=temporary_root) as temporary:
                text_path = Path(temporary) / "text.txt"
                text_path.write_text(case.text + "\n", encoding="utf-8")
                destination = output_path(case.character)
                print(f"开始：{MODEL_NAME} / {case.character}")
                subprocess.run(
                    command_for_case(case, text_path, destination, args.dry_run),
                    cwd=REPO_ROOT,
                    check=True,
                )
                if not args.dry_run and (not destination.is_file() or destination.stat().st_size == 0):
                    raise RuntimeError(f"MiMo 未生成有效 WAV：{destination}")
                if not args.dry_run:
                    print(f"完成：{destination}")
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
