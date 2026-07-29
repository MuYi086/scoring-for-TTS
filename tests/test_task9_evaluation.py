"""Task 9 受限公共评测入口与报告的无模型测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "task-runner" / "task9"
EVALUATOR_PATH = TASK_DIR / "run_task9_evaluation.py"
REPORTER_PATH = TASK_DIR / "generate_task9_reports.py"
CONTRACT_PATH = TASK_DIR / "evaluation-contract.json"


def load_module(name: str, path: Path):
    if str(TASK_DIR) not in sys.path:
        sys.path.insert(0, str(TASK_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def complete_record(model_id: str, display_name: str) -> dict:
    metric = {
        "status": "complete",
        "cer": 0.1,
        "character_errors": 1,
        "chunks": [{"index": 0, "start_seconds": 0.0, "end_seconds": 1.0, "transcription": "测试"}],
        "full_transcription": "测试",
        "error_locations": [
            {
                "operation": "substitution",
                "reference_index": 0,
                "reference_character": "测",
                "hypothesis_index": 0,
                "hypothesis_character": "试",
            }
        ],
    }
    return {
        "model_id": model_id,
        "display_name": display_name,
        "status": "complete",
        "audio_delivery": {
            "decode_status": "decoded",
            "sha256": "a" * 64,
            "format": "WAV",
            "subtype": "PCM_16",
            "sample_rate_hz": 24000,
            "channels": 1,
            "duration_seconds": 12.0,
            "clipping_ratio": 0.0,
            "max_sample_peak_dbfs": -1.0,
            "dc_offset": 0.0,
            "leading_silence_seconds": 0.0,
            "trailing_silence_seconds": 0.0,
            "long_silence_regions": [],
        },
        "metrics": {
            "sensevoice_cer": dict(metric),
            "whisper_large_v3_turbo_cer": dict(metric),
        },
    }


def test_contract_freezes_text_md_as_the_only_cer_reference() -> None:
    evaluator = load_module("task9_evaluator_contract", EVALUATOR_PATH)
    contract = evaluator.load_contract(CONTRACT_PATH)

    assert contract["source"]["text_path"] == "longAudioTestV9/text.md"
    assert contract["source"]["cer_reference"] == "text_md_actual_synthesis_order"
    assert contract["source"]["normalized_character_count"] == 1527
    assert [item["model_id"] for item in contract["models"]] == ["indextts2", "voxcpm2"]


def test_character_error_locations_are_reconstructable() -> None:
    evaluator = load_module("task9_evaluator_alignment", EVALUATOR_PATH)

    distance, locations = evaluator.levenshtein_alignment("甲乙", "甲丙")

    assert distance == 1
    assert locations == [
        {
            "operation": "substitution",
            "reference_index": 1,
            "reference_character": "乙",
            "hypothesis_index": 1,
            "hypothesis_character": "丙",
        }
    ]


def test_sensevoice_control_tags_do_not_count_as_spoken_text() -> None:
    evaluator = load_module("task9_evaluator_sensevoice_tags", EVALUATOR_PATH)

    assert evaluator.strip_sensevoice_control_tags(
        "<|zh|><|HAPPY|><|Speech|><|withitn|>实际台词"
    ) == "实际台词"


def test_reporter_writes_the_two_public_v9_reports(tmp_path: Path) -> None:
    reporter = load_module("task9_reporter", REPORTER_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    results = {
        "schema_version": "task9-v1",
        "version": "V9",
        "contract": contract,
        "inputs": {
            "segment_manifest_sha256": "b" * 64,
            "segment_manifest": {
                "reference_speech_rate": {"characters_per_second": 3.0},
                "policy": {
                    "target_seconds": 25,
                    "max_segment_seconds": 35,
                    "context_policy": "只记录相邻上下文。",
                },
                "segments": [{"segment_id": "001", "text": "测试"}],
            },
        },
        "models": {
            "indextts2": complete_record("indextts2", "IndexTTS2"),
            "voxcpm2": complete_record("voxcpm2", "VoxCPM2"),
        },
    }
    (tmp_path / "task9_evaluation_results.json").write_text(
        json.dumps(results, ensure_ascii=False), encoding="utf-8"
    )

    cer_path, automated_path = reporter.write_reports(tmp_path, tmp_path / "reports")

    assert cer_path.name == "SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md"
    assert automated_path.name == "音频交付与文本一致性_V9自动检查报告.md"
    assert "text.md" in cer_path.read_text(encoding="utf-8")
    assert "未配置冻结发音词典" in automated_path.read_text(encoding="utf-8")
