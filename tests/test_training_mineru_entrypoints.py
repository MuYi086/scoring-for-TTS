"""Task 12–17 MinerU 入口脚本的无网络配置测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "training" / "script"

ENTRYPOINTS = {
    "deal_bk.py": (
        "《怖客》",
        r"C:\Downloads\怖客2010-2018",
        "/mnt/c/Downloads/怖客2010-2018",
        "怖客",
    ),
    "deal_mgzzgs.py": (
        "《猛鬼杂志故事》",
        r"C:\Downloads\猛鬼杂志故事-56本",
        "/mnt/c/Downloads/猛鬼杂志故事-56本",
        "猛鬼杂志故事",
    ),
    "deal_mjgsdxg.py": (
        "《民间故事胆小鬼》",
        r"C:\Downloads\民间故事胆小鬼",
        "/mnt/c/Downloads/民间故事胆小鬼",
        "民间故事胆小鬼",
    ),
    "deal_sz.py": (
        "《悚族》",
        r"C:\Downloads\悚族-75本",
        "/mnt/c/Downloads/悚族-75本",
        "悚族",
    ),
    "deal_sytl.py": (
        "《岁月推理》",
        r"C:\Downloads\岁月推理",
        "/mnt/c/Downloads/岁月推理",
        "岁月推理",
    ),
    "deal_zmn.py": (
        "《啄木鸟》",
        r"C:\Downloads\啄木鸟",
        "/mnt/c/Downloads/啄木鸟",
        "啄木鸟",
    ),
}


def load_entrypoint(filename: str):
    """加载入口模块但不触发其 __main__ 分支。"""
    path = SCRIPT_DIR / filename
    module_name = f"test_{path.stem}_entrypoint"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPT_DIR))
    return module


class TrainingMinerUEntrypointTests(unittest.TestCase):
    def test_task12_through_task17_delegate_exact_collection_paths(self):
        for filename, expected in ENTRYPOINTS.items():
            with self.subTest(filename=filename):
                collection_name, windows_source, wsl_source, output_name = expected
                module = load_entrypoint(filename)
                with patch.object(module, "main_for_collection", return_value=17) as delegate:
                    exit_code = module.main(["--dry-run"])

                self.assertEqual(exit_code, 17)
                delegate.assert_called_once_with(
                    ["--dry-run"],
                    collection_name=collection_name,
                    windows_source_dir=Path(windows_source),
                    wsl_source_dir=Path(wsl_source),
                    default_output_dir=REPO_ROOT / "training" / output_name,
                )

    def test_shared_parser_uses_collection_specific_wsl_and_output_defaults(self):
        sys.path.insert(0, str(SCRIPT_DIR))
        try:
            import deal_nsnsjb
        finally:
            sys.path.remove(str(SCRIPT_DIR))

        parser = deal_nsnsjb.build_parser(
            collection_name="《测试刊物》",
            windows_source_dir=Path(r"Z:\definitely-missing\测试刊物"),
            wsl_source_dir=Path("/mnt/z/definitely-missing/测试刊物"),
            default_output_dir=REPO_ROOT / "training" / "测试刊物",
        )
        args = parser.parse_args([])

        self.assertEqual(args.source_dir, Path("/mnt/z/definitely-missing/测试刊物"))
        self.assertEqual(args.output_dir, REPO_ROOT / "training" / "测试刊物")
        self.assertEqual(args.batch_size, 50)
        self.assertEqual(args.upload_workers, 4)


if __name__ == "__main__":
    unittest.main()
