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
        "strict_character_cer": 0.1,
        "character_errors": 1,
        "phonetic_cer": 0.0,
        "phonetic_errors": 0,
        "chunks": [
            {
                "index": 0,
                "segment_id": "001",
                "start_seconds": 0.0,
                "end_seconds": 1.0,
                "transcription": "测试",
                "normalized_transcription": "测试",
                "asr_health": {"status": "healthy", "reasons": []},
            }
        ],
        "full_transcription": "测试",
        "asr_health": {"status": "healthy", "unreliable_segment_ids": [], "ranking_eligible": True},
        "error_locations": [
            {
                "operation": "substitution",
                "reference_index": 0,
                "reference_character": "测",
                "hypothesis_index": 0,
                "hypothesis_character": "试",
                "segment_id": "001",
                "classification": "different_pronunciation_substitution",
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
        "asr_consensus_health": {"status": "healthy", "unreliable_segment_ids": [], "segments": []},
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


def test_token_alignment_keeps_pinyin_tokens_intact() -> None:
    evaluator = load_module("task9_evaluator_token_alignment", EVALUATOR_PATH)

    distance, locations = evaluator.levenshtein_token_alignment(["gu3", "lan2", "jing1"], ["gu3", "lan2", "jing1"])

    assert distance == 0
    assert locations == []


def test_phonetic_metric_separates_same_pronunciation_substitution() -> None:
    evaluator = load_module("task9_evaluator_phonetic", EVALUATOR_PATH)
    phonetic = {"library": "pypinyin", "version": "0.55.0", "style": "tone3", "phrase_overrides": {}}
    health = {
        "minimum_hypothesis_to_reference_ratio": 0.5,
        "maximum_hypothesis_to_reference_ratio": 1.5,
        "maximum_consecutive_deletions": 20,
        "maximum_backend_disagreement_cer": 0.5,
        "ranking_requires_healthy_segments": True,
    }

    def fake_transcriber(audio_segments, _config, _model_dir):
        return "他", [{"index": 0, "segment_id": "001", "start_seconds": 0.0, "end_seconds": 1.0, "audio_sha256": "a" * 64, "transcription": "他"}]

    result = evaluator.evaluate_asr_backend(
        "fake",
        fake_transcriber,
        [{"segment_id": "001", "text": "她", "text_sha256": "b" * 64, "audio_path": Path("unused.wav"), "audio_sha256": "a" * 64, "start_seconds": 0.0, "end_seconds": 1.0}],
        {"model_id": "fake", "revision": "test"},
        Path("unused"),
        phonetic,
        health,
    )

    assert result["strict_character_cer"] == 1.0
    assert result["phonetic_cer"] == 0.0
    assert result["error_locations"][0]["classification"] == "same_pronunciation_substitution"


def test_asr_health_flags_a_long_contiguous_deletion() -> None:
    evaluator = load_module("task9_evaluator_health", EVALUATOR_PATH)
    health = {
        "minimum_hypothesis_to_reference_ratio": 0.5,
        "maximum_hypothesis_to_reference_ratio": 1.5,
        "maximum_consecutive_deletions": 3,
    }
    errors = [
        {"operation": "deletion", "reference_index": index, "reference_character": "甲", "hypothesis_index": 0, "hypothesis_character": ""}
        for index in range(4)
    ]

    result = evaluator.segment_health(10, 6, errors, health)

    assert result["status"] == "unreliable"
    assert "consecutive_deletion_too_long" in result["reasons"]


def test_cross_backend_disagreement_excludes_both_metrics_from_ranking() -> None:
    evaluator = load_module("task9_evaluator_cross_backend", EVALUATOR_PATH)
    chunk = {
        "segment_id": "001",
        "normalized_transcription": "甲乙丙丁",
        "asr_health": {"status": "healthy", "reasons": []},
    }
    record = {
        "metrics": {
            "sensevoice_cer": {"chunks": [dict(chunk)]},
            "whisper_large_v3_turbo_cer": {
                "chunks": [{**chunk, "normalized_transcription": "戊己庚辛", "asr_health": {"status": "healthy", "reasons": []}}]
            },
        }
    }

    consensus = evaluator.apply_cross_backend_health(
        record,
        {"maximum_backend_disagreement_cer": 0.5, "ranking_requires_healthy_segments": True},
    )

    assert consensus["status"] == "unreliable"
    for metric in record["metrics"].values():
        assert metric["asr_health"]["ranking_eligible"] is False
        assert "cross_backend_disagreement" in metric["chunks"][0]["asr_health"]["reasons"]


def test_sensevoice_control_tags_do_not_count_as_spoken_text() -> None:
    evaluator = load_module("task9_evaluator_sensevoice_tags", EVALUATOR_PATH)

    assert evaluator.strip_sensevoice_control_tags(
        "<|zh|><|HAPPY|><|Speech|><|withitn|>实际台词"
    ) == "实际台词"


def test_reporter_writes_the_two_public_v9_reports(tmp_path: Path) -> None:
    reporter = load_module("task9_reporter", REPORTER_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    results = {
        "schema_version": "task9-v2",
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
    assert "中高风险后续项" in automated_path.read_text(encoding="utf-8")
