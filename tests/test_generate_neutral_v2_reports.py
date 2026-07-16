"""V2 报告派生逻辑测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tts-bench/scripts/generate_neutral_v2_reports.py"


def load_script():
    spec = importlib.util.spec_from_file_location("generate_neutral_v2_reports", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dense_ranks_keep_ties_and_metric_direction() -> None:
    script = load_script()
    values = {"a": 0.1, "b": 0.2, "c": 0.1}

    assert script.dense_ranks(values, higher_is_better=False) == {
        "a": 1,
        "b": 2,
        "c": 1,
    }
    assert script.dense_ranks(values, higher_is_better=True) == {
        "a": 2,
        "b": 1,
        "c": 2,
    }


def test_current_complete_results_render_all_requested_reports() -> None:
    script = load_script()
    reports = script.build_reports(ROOT / "tts-bench/reports/task3-2026-07-16-v2")

    assert set(reports) == {"cer", "sim", "quality"}
    assert "不把二者平均成一个总分" in reports["cer"]
    assert "校准对照" in reports["sim"]
    assert "5 次裁剪" in reports["quality"]


def test_custom_results_link_is_used_for_evidence_links() -> None:
    script = load_script()
    reports = script.build_reports(
        ROOT / "tts-bench/reports/task3-2026-07-16-v2",
        results_link="../raw/task3-v2",
    )

    assert "(../raw/task3-v2/per_audio.jsonl)" in reports["cer"]
    assert "(../raw/task3-v2/speaker_similarity.jsonl)" in reports["sim"]
