"""Task 5 V4 长音频入口、对齐、采样与报告测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tts-bench" / "scripts"
ROLES = ["旁白", "辰南", "见习魔法师", "女侍卫", "侍卫", "小公主"]
MODELS = [f"model-{index}" for index in range(7)]


def load_module(name: str, path: Path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_v4_config_freezes_seven_models_six_roles_and_long_audio_policy() -> None:
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v4.json").read_text(encoding="utf-8")
    )

    assert config["schema_version"] == "4.0"
    assert config["expected_model_count"] == 7
    assert len(config["models"]) == 7
    assert {item["role"] for item in config["references"]} == set(ROLES)
    assert config["source"]["cer_reference"] == "ai_deal_dialogue_concatenation"
    assert config["source"]["dialogue_count"] == 148
    assert config["source"]["normalized_character_count"] == 5673
    assert config["quality_sampling"] == {
        "window_seconds": 12.0,
        "window_count": 8,
        "strategy": "non_overlapping_capacity_evenly_spaced",
    }
    assert config["sensevoice"]["long_audio_chunk_seconds"] == 30.0
    assert config["whisper"]["long_audio_chunk_seconds"] == 30.0
    assert (
        config["alignment"]["mixed_role_chunk_policy"]
        == "split_by_exact_character_run_linear_time"
    )


def test_v4_entry_defaults_target_long_audio_result_directory(monkeypatch) -> None:
    script = load_module("run_neutral_evaluation_v4_test", SCRIPTS / "run_neutral_evaluation_v4.py")
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_neutral_evaluation_v4.py", "--model-id", "dots.tts-base"],
    )

    args = script.parse_args()

    assert args.config == ROOT / "tts-bench/config/neutral-evaluation-v4.json"
    assert args.output_dir == ROOT / "longAudioTest/评测结果/task5-v4-raw"
    assert args.metrics == list(script.METRICS)
    assert args.model_id == "dots.tts-base"


def test_v4_single_model_scope_includes_shared_baselines_only_once() -> None:
    script = load_module("run_neutral_evaluation_v4_scope", SCRIPTS / "run_neutral_evaluation_v4.py")
    audio_rows = [
        *[
            {"kind": "reference", "model_id": "原始参考音频", "metrics": {}}
            for _ in ROLES
        ],
        *[{"kind": "synthesis", "model_id": model, "metrics": {}} for model in MODELS],
    ]
    similarity_rows = [
        {"model_id": model, "role": role, "metrics": {}}
        for model in MODELS
        for role in ROLES
    ]
    calibration_rows = [{"control_type": "same_speaker_split_half", "metrics": {}}]

    cer_scope = script.scoped_metric_rows(
        "sensevoice_cer",
        MODELS[0],
        audio_rows,
        similarity_rows,
        calibration_rows,
    )
    sim_scope = script.scoped_metric_rows(
        "wavlm_sim",
        MODELS[0],
        audio_rows,
        similarity_rows,
        calibration_rows,
    )

    assert len(cer_scope) == 7
    assert sum(row["kind"] == "synthesis" for row in cer_scope) == 1
    assert len(sim_scope) == 7
    assert {row.get("model_id") for row in sim_scope if "model_id" in row} == {MODELS[0]}


def test_v4_role_alignment_splits_mixed_chunk_at_role_boundary() -> None:
    script = load_module("run_neutral_evaluation_v4_alignment", SCRIPTS / "run_neutral_evaluation_v4.py")
    dialogues = [
        {"role_name": "旁白", "text_content": "甲乙丙丁"},
        {"role_name": "辰南", "text_content": "戊己庚辛"},
    ]
    chunks = [
        {"text": "甲乙丙", "start_seconds": 0.0, "end_seconds": 1.0},
        {"text": "丁戊", "start_seconds": 1.0, "end_seconds": 2.0},
        {"text": "己庚辛", "start_seconds": 2.0, "end_seconds": 3.0},
    ]
    config = {
        "alignment": {
            "max_excerpts_per_role": 5,
            "min_exact_match_characters": 2,
            "min_chunk_match_ratio": 0.5,
            "min_role_purity": 0.8,
            "max_merge_gap_seconds": 1.5,
            "min_excerpt_seconds": 0.5,
            "max_excerpt_seconds": 20.0,
        }
    }

    selected, summary = script.align_role_excerpts(dialogues, chunks, config)

    assert [item["asr_text"] for item in selected["旁白"]] == ["甲乙丙丁"]
    assert [item["asr_text"] for item in selected["辰南"]] == ["戊己庚辛"]
    assert summary["split_mixed_chunk_count"] == 1
    assert summary["rejected_chunk_counts"] == {}
    assert summary["exact_alignment_ratio_to_expected"] == 1.0


def test_v4_role_alignment_merges_word_timestamps_before_minimum_length() -> None:
    script = load_module(
        "run_neutral_evaluation_v4_word_alignment",
        SCRIPTS / "run_neutral_evaluation_v4.py",
    )
    dialogues = [{"role_name": "旁白", "text_content": "甲乙丙丁"}]
    chunks = [
        {
            "text": character,
            "start_seconds": index * 0.2,
            "end_seconds": (index + 1) * 0.2,
        }
        for index, character in enumerate("甲乙丙丁")
    ]
    config = {
        "alignment": {
            "max_excerpts_per_role": 5,
            "min_exact_match_characters": 4,
            "min_chunk_match_ratio": 0.5,
            "min_role_purity": 0.8,
            "max_merge_gap_seconds": 1.5,
            "min_excerpt_seconds": 0.5,
            "max_excerpt_seconds": 20.0,
        }
    }

    selected, _ = script.align_role_excerpts(dialogues, chunks, config)

    assert len(selected["旁白"]) == 1
    assert selected["旁白"][0]["asr_text"] == "甲乙丙丁"
    assert selected["旁白"][0]["chunk_end_index"] == 3


def test_v4_populates_alignment_only_for_active_model() -> None:
    script = load_module(
        "run_neutral_evaluation_v4_active_alignment",
        SCRIPTS / "run_neutral_evaluation_v4.py",
    )
    dialogues = [{"role_name": "旁白", "text_content": "甲乙丙丁"}]
    active_rows = [{"model_id": "active", "role": "旁白", "alignment_excerpts": []}]
    audio_rows = [
        {
            "kind": "synthesis",
            "model_id": "active",
            "metrics": {
                "whisper_cer": {
                    "chunks": [
                        {
                            "text": "甲乙丙丁",
                            "start_seconds": 0.0,
                            "end_seconds": 1.0,
                        }
                    ]
                }
            },
        },
        {"kind": "synthesis", "model_id": "not-run-yet", "metrics": {}},
    ]
    config = {
        "alignment": {
            "max_excerpts_per_role": 5,
            "min_exact_match_characters": 4,
            "min_chunk_match_ratio": 0.5,
            "min_role_purity": 0.8,
            "max_merge_gap_seconds": 1.5,
            "min_excerpt_seconds": 0.5,
            "max_excerpt_seconds": 20.0,
        }
    }

    script.populate_alignment_excerpts(active_rows, audio_rows, dialogues, config)

    assert len(active_rows[0]["alignment_excerpts"]) == 1


def test_v4_sensevoice_intervals_cover_long_audio_without_overlap() -> None:
    script = load_module(
        "run_neutral_evaluation_v4_sensevoice_chunks",
        SCRIPTS / "run_neutral_evaluation_v4.py",
    )

    assert script.sensevoice_intervals(15.0, 30.0) == [(0.0, 15.0)]
    assert script.sensevoice_intervals(65.0, 30.0) == [
        (0.0, 30.0),
        (30.0, 60.0),
        (60.0, 65.0),
    ]


def test_v4_whisper_timestamps_are_shifted_and_bounded() -> None:
    script = load_module(
        "run_neutral_evaluation_v4_whisper_timestamps",
        SCRIPTS / "run_neutral_evaluation_v4.py",
    )
    result = script.clean_whisper_result(
        {
            "text": "甲乙",
            "chunks": [
                {"text": "甲", "timestamp": (0.0, 0.4)},
                {"text": "乙", "timestamp": (0.4, 1.2)},
            ],
        },
        offset_seconds=30.0,
        segment_end_seconds=31.0,
        segment_index=1,
    )

    assert result == {
        "text": "甲乙",
        "chunks": [
            {
                "text": "甲",
                "start_seconds": 30.0,
                "end_seconds": 30.4,
                "segment_index": 1,
            },
            {
                "text": "乙",
                "start_seconds": 30.4,
                "end_seconds": 31.0,
                "segment_index": 1,
            },
        ],
    }


def test_v4_quality_intervals_are_bounded_and_evenly_spaced() -> None:
    script = load_module("run_neutral_evaluation_v4_windows", SCRIPTS / "run_neutral_evaluation_v4.py")

    assert script.quality_intervals(8.0, 12.0, 8) == [(0.0, 8.0)]
    assert script.quality_intervals(20.0, 12.0, 8) == [(4.0, 16.0)]
    intervals = script.quality_intervals(100.0, 12.0, 4)
    expected = [(0.0, 12.0), (88 / 3, 124 / 3), (176 / 3, 212 / 3), (88.0, 100.0)]
    assert len(intervals) == len(expected)
    for actual, frozen in zip(intervals, expected):
        assert actual == pytest.approx(frozen)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def synthetic_complete_results(directory: Path) -> None:
    audio_rows = []
    for index, role in enumerate(ROLES):
        audio_rows.append(
            {
                "kind": "reference",
                "model_id": "原始参考音频",
                "role": role,
                "audio": {"duration_seconds": 15.0},
                "metrics": {
                    "sensevoice_cer": {"cer": 0.01 + index / 1000},
                    "whisper_cer": {"cer": 0.02 + index / 1000},
                    "utmosv2": {"mean": 3.0, "min": 3.0, "std": 0.0, "count": 1},
                    "nisqa": {"mean": 4.0, "min": 4.0, "std": 0.0, "count": 1},
                },
                "errors": [],
            }
        )
    for index, model in enumerate(MODELS):
        audio_rows.append(
            {
                "kind": "synthesis",
                "model_id": model,
                "role": "完整有声书",
                "audio": {"duration_seconds": 1000.0 + index},
                "metrics": {
                    "sensevoice_cer": {"cer": 0.1 + index / 100},
                    "whisper_cer": {
                        "cer": 0.11 + index / 100,
                        "alignment_summary": {
                            "chunk_count": 100,
                            "exact_matched_characters": 5000,
                            "expected_characters": 5673,
                            "exact_alignment_ratio_to_expected": 5000 / 5673,
                        },
                    },
                    "utmosv2": {"mean": 3.0 + index / 10, "min": 2.5, "std": 0.1, "count": 8},
                    "nisqa": {"mean": 4.0 + index / 100, "min": 3.5, "std": 0.1, "count": 8},
                },
                "errors": [],
            }
        )

    similarity_rows = []
    for model_index, model in enumerate(MODELS):
        for role_index, role in enumerate(ROLES):
            similarity_rows.append(
                {
                    "model_id": model,
                    "role": role,
                    "alignment_excerpts": [{"start_seconds": 1.0, "end_seconds": 2.0}],
                    "metrics": {
                        "wavlm_sim": {"mean": 0.7 + model_index / 100 + role_index / 1000},
                        "speechbrain_ecapa_sim": {
                            "mean": 0.6 + model_index / 100 + role_index / 1000
                        },
                    },
                    "errors": [],
                }
            )

    calibration_rows = []
    for role in ROLES:
        calibration_rows.append(
            {
                "control_type": "same_speaker_split_half",
                "label": f"{role}同说话人",
                "metrics": {"wavlm_sim": 0.9, "speechbrain_ecapa_sim": 0.8},
                "errors": [],
            }
        )
    for left, right in combinations(ROLES, 2):
        calibration_rows.append(
            {
                "control_type": "different_speaker_reference_pair",
                "label": f"{left}与{right}",
                "metrics": {"wavlm_sim": 0.5, "speechbrain_ecapa_sim": 0.4},
                "errors": [],
            }
        )

    coverage = {
        "sensevoice_cer": {"complete": 13, "expected": 13},
        "whisper_cer": {"complete": 13, "expected": 13},
        "wavlm_sim": {"complete": 63, "expected": 63},
        "speechbrain_ecapa_sim": {"complete": 63, "expected": 63},
        "utmosv2": {"complete": 13, "expected": 13},
        "nisqa": {"complete": 13, "expected": 13},
    }
    metadata = {
        "coverage": coverage,
        "config": {
            "quality_sampling": {"window_count": 8, "window_seconds": 12.0},
            "utmosv2": {"inference_seed": 20260721, "num_repetitions": 5},
        },
    }
    write_jsonl(directory / "per_audio.jsonl", audio_rows)
    write_jsonl(directory / "speaker_similarity.jsonl", similarity_rows)
    write_jsonl(directory / "speaker_calibration.jsonl", calibration_rows)
    (directory / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )


def test_complete_v4_results_render_three_independent_reports(tmp_path: Path) -> None:
    script = load_module("generate_neutral_v4_reports_test", SCRIPTS / "generate_neutral_v4_reports.py")
    synthetic_complete_results(tmp_path)

    reports = script.build_reports(tmp_path, results_link="raw-v4")

    assert set(reports) == {"cer", "sim", "quality"}
    assert "不把两个 CER 简单平均为总分" in reports["cer"]
    assert "建议作为第一道生产硬门槛" in reports["cer"]
    assert "角色配音映射" in reports["sim"]
    assert "多角色作品的核心选型维度" in reports["sim"]
    assert "成品听感的体验门槛" in reports["quality"]
    assert "结合人工盲听决定最终生产方案" in reports["quality"]
    assert "7 模型 × 6 角色矩阵" not in reports["sim"]
    assert "21 个原始音频校准对" in reports["sim"]
    assert "不跨预测器加权" in reports["quality"]
    assert "raw-v4/per_audio.jsonl" in reports["cer"]
    assert script.REPORT_FILENAMES == {
        "cer": "SenseVoice_CER&Whisper_CER_V4评价报告.md",
        "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V4评价报告.md",
        "quality": "UTMOSv2&NISQA_V4评价报告.md",
    }


def test_complete_model_results_render_independent_report(tmp_path: Path) -> None:
    script = load_module("generate_neutral_v4_model_report", SCRIPTS / "generate_neutral_v4_reports.py")
    synthetic_complete_results(tmp_path)

    report = script.build_model_report(tmp_path, MODELS[0], results_link="raw-v4")

    assert f"# {MODELS[0]} V4 独立评价报告" in report
    assert "不计算跨后端加权总分" in report
    assert "WavLM SIM" in report
    assert "NISQA-TTS" in report
    assert "raw-v4/speaker_similarity.jsonl" in report
    assert script.model_report_filename("LongCat-AudioDiT-1B") == (
        "LongCat-AudioDiT-1B_V4评价报告.md"
    )
