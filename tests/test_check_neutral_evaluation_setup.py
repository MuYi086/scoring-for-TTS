"""V2 跨电脑复测预检脚本的轻量测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tts-bench/scripts/check_neutral_evaluation_setup.py"


def load_script():
    spec = importlib.util.spec_from_file_location("check_neutral_evaluation_setup", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_local_dir_metadata_revision_reads_first_line(tmp_path: Path) -> None:
    script = load_script()
    model_dir = tmp_path / "model"
    metadata = model_dir / ".cache/huggingface/download/model.bin.metadata"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("abc123\nblob-hash\ntimestamp\n", encoding="utf-8")

    assert script.local_dir_metadata_revision(model_dir, "model.bin") == "abc123"
    assert script.local_dir_metadata_revision(model_dir, "missing.bin") is None


def test_huggingface_cache_dir_uses_hub_snapshot_layout(tmp_path: Path) -> None:
    script = load_script()

    actual = script.huggingface_cache_dir(tmp_path, "facebook/wav2vec2-base", "revision")

    assert actual == (
        tmp_path / "hub/models--facebook--wav2vec2-base/snapshots/revision"
    )


def test_version_mismatch_can_be_warning_or_error() -> None:
    script = load_script()
    report = script.CheckReport()

    report.version_mismatch("宽松", strict_versions=False)
    report.version_mismatch("严格", strict_versions=True)

    assert report.warnings == ["宽松"]
    assert report.errors == ["严格"]
