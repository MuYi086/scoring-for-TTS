"""Task 4 V3 评测入口与报告派生逻辑测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tts-bench/scripts"


def load_module(name: str, path: Path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_v3_config_freezes_eight_models_and_three_requested_roles() -> None:
    config = json.loads((ROOT / "tts-bench/config/neutral-evaluation-v3.json").read_text(encoding="utf-8"))

    assert config["expected_model_count"] == 8
    assert set(config["case_labels"].values()) == {"旁白", "小公主", "辰南"}
    assert config["manifest_path"] == "tts-bench/manifests/task4-2026-07-19-v3.jsonl"
    assert config["utmosv2"]["num_repetitions"] == 5


def test_v3_entry_defaults_are_isolated_from_v2(monkeypatch) -> None:
    script = load_module("run_neutral_evaluation_v3_test", SCRIPTS / "run_neutral_evaluation_v3.py")
    monkeypatch.setattr(sys, "argv", ["run_neutral_evaluation_v3.py"])

    args = script.parse_args()

    assert args.runs_root == ROOT / "tts-bench/runs-v3"
    assert args.config == ROOT / "tts-bench/config/neutral-evaluation-v3.json"
    assert args.output_dir == ROOT / "tts-bench/reports/task4-2026-07-19-v3"


def test_v3_report_names_and_role_order_are_frozen() -> None:
    script = load_module("generate_neutral_v3_reports_test", SCRIPTS / "generate_neutral_v3_reports.py")

    assert script.REPORT_FILENAMES == {
        "cer": "SenseVoice_CER&Whisper_CER_V3评价报告.md",
        "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V3评价报告.md",
        "quality": "UTMOSv2&NISQA_V3评价报告.md",
    }
    assert script.ROLE_ORDER == {"旁白": 0, "小公主": 1, "辰南": 2}


def test_v3_rank_correlation_uses_both_independent_rankings() -> None:
    script = load_module("generate_neutral_v3_reports_rank", SCRIPTS / "generate_neutral_v3_reports.py")

    assert script.rank_correlation({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2, "c": 3}) == 1.0
    assert script.rank_correlation({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1}) == -1.0


def test_complete_v3_results_render_three_reports_without_cross_metric_score() -> None:
    script = load_module("generate_neutral_v3_reports_complete", SCRIPTS / "generate_neutral_v3_reports.py")

    reports = script.build_reports(ROOT / "tts-bench/reports/task4-2026-07-19-v3")

    assert set(reports) == {"cer", "sim", "quality"}
    assert "不将 CER 简单平均为总分" in reports["cer"]
    assert "原始音频校准对照" in reports["sim"]
    assert "不跨量纲加权" in reports["quality"]
    assert "辰南" in reports["cer"] and "辰南" in reports["sim"] and "辰南" in reports["quality"]
