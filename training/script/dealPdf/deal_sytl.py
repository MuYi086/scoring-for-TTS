#!/usr/bin/env python3
"""用 MinerU 将《岁月推理》PDF 批量转换为同名 Markdown。"""

from __future__ import annotations

from pathlib import Path
import sys

if __package__:
    from .deal_nsnsjb import main_for_collection
else:
    from deal_nsnsjb import main_for_collection


WINDOWS_SOURCE_DIR = Path(r"C:\Downloads\岁月推理")
WSL_SOURCE_DIR = Path("/mnt/c/Downloads/岁月推理")
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[3] / "training" / "原始资源" / "岁月推理"
)


def main(argv: list[str] | None = None) -> int:
    """运行《岁月推理》批量转换入口。"""
    return main_for_collection(
        argv,
        collection_name="《岁月推理》",
        windows_source_dir=WINDOWS_SOURCE_DIR,
        wsl_source_dir=WSL_SOURCE_DIR,
        default_output_dir=DEFAULT_OUTPUT_DIR,
    )


if __name__ == "__main__":
    sys.exit(main())
