#!/usr/bin/env python3
"""直接调用 MiMo 官方云端 voiceclone 接口的三角色克隆测试。

MiMo 没有本地 conda 推理运行时。本脚本直接调用仓库中的官方接口 CLI，
不经过任何本地 HTTP 后端；真实请求前须设置 MIMO_API_KEY。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


CLONE_DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLONE_DATA))

from _clone_test_support import CASES, OUTPUT_ROOT, REPO_ROOT, selected_cases


SOURCE_SCRIPT = REPO_ROOT / "modelScript/tts_cloud_mimo.py"
MODEL_NAME = "mimo-v2.5-tts-voiceclone"


def parse_args() -> argparse.Namespace:
    """解析 MiMo 三角色测试选项。"""

    parser = argparse.ArgumentParser(description="MiMo-V2.5-TTS voiceclone 三角色测试")
    parser.add_argument("--character", choices=[case.character for case in CASES], action="append")
    parser.add_argument("--dry-run", action="store_true", help="校验并显示请求摘要，不调用云端接口")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖同名的既有输出 WAV")
    return parser.parse_args()


def output_path(character: str) -> Path:
    """返回模型加人物命名的固定输出路径。"""

    return OUTPUT_ROOT / f"{MODEL_NAME}_{character}.wav"


def preflight(cases, overwrite: bool) -> None:
    """在发送任何云端请求前检查脚本、参考音频与覆盖策略。"""

    required = [SOURCE_SCRIPT, *(case.reference_audio for case in cases)]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("本地资产不存在：" + "；".join(missing))
    if not overwrite:
        existing = [str(output_path(case.character)) for case in cases if output_path(case.character).exists()]
        if existing:
            raise FileExistsError("输出已存在；如需重测请传入 --overwrite：" + "；".join(existing))


def command_for_case(case, text_path: Path, destination: Path, dry_run: bool) -> list[str]:
    """构造 MiMo 官方 CLI 的单角色请求命令。"""

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
    """逐一提交三位角色的原生 MiMo voiceclone 请求。"""

    args = parse_args()
    cases = selected_cases(args.character)
    try:
        preflight(cases, args.overwrite)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        temporary_root = OUTPUT_ROOT / "mimo" / ".tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        for case in cases:
            with tempfile.TemporaryDirectory(prefix="mimo-", dir=temporary_root) as temporary:
                text_path = Path(temporary) / "text.txt"
                text_path.write_text(case.text + "\n", encoding="utf-8")
                destination = output_path(case.character)
                print(f"开始：{MODEL_NAME} / {case.character}")
                subprocess.run(command_for_case(case, text_path, destination, args.dry_run), cwd=REPO_ROOT, check=True)
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
