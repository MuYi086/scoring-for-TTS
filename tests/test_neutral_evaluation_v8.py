"""Task 9 V8 冻结输入、单模型入口与报告测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tts-bench" / "scripts"
ROLES = ["我", "旁白", "姐姐", "神秘声音"]
MODELS = [
    "dots.tts-base",
    "IndexTTS2",
    "LongCat-AudioDiT-1B",
    "MOSS-TTS-Local-Transformer-v1.5",
    "OmniVoice",
    "Qwen3-TTS-12Hz-1.7B-Base",
    "VoxCPM2",
]


def load_module(name: str, path: Path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_v8_config_freezes_all_inputs_and_role_references() -> None:
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v8.json").read_text(encoding="utf-8")
    )

    assert config["schema_version"] == "8.0"
    assert [item["model_id"] for item in config["models"]] == MODELS
    assert [item["role"] for item in config["references"]] == ROLES
    assert config["source"]["dialogue_count"] == 97
    assert config["source"]["normalized_character_count"] == 2513
    assert config["source"]["raw_text_normalized_character_count"] == 2537
    assert config["source"]["cer_reference"] == "ai_deal_dialogue_concatenation"
    assert config["alignment"]["fallback_min_exact_match_characters"] == 2
    assert config["quality_sampling"] == {
        "window_seconds": 12.0,
        "window_count": 8,
        "strategy": "non_overlapping_capacity_evenly_spaced",
    }


def test_v8_entry_accepts_only_one_model_and_uses_v8_paths(monkeypatch) -> None:
    script = load_module("run_neutral_evaluation_v8_test", SCRIPTS / "run_neutral_evaluation_v8.py")
    monkeypatch.setattr(sys, "argv", ["run_neutral_evaluation_v8.py", "--model-id", "OmniVoice"])

    args = script.parse_args()

    assert args.config == ROOT / "tts-bench/config/neutral-evaluation-v8.json"
    assert args.output_dir == ROOT / "longAudioTestV8/评测结果/task9-v8-raw"
    assert args.reports_dir == ROOT / "longAudioTestV8/评测结果"
    assert args.model_id == "OmniVoice"
    assert args.metrics == list(script.METRICS)


def test_shared_long_audio_runner_accepts_v8(monkeypatch, tmp_path: Path) -> None:
    runner = load_module("run_neutral_evaluation_v8_schema", SCRIPTS / "run_neutral_evaluation_v4.py")
    monkeypatch.setenv("HF_MIRROR_ROOT", str(tmp_path))
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v8.json").read_text(encoding="utf-8")
    )

    runner.validate_config(config)
    assert runner.evaluation_version(config) == "V8"
    assert len(ROLES) + len(list(combinations(ROLES, 2))) == 10


def write_complete_v8_results(directory: Path) -> None:
    audio_rows = []
    for index, role in enumerate(ROLES):
        audio_rows.append(
            {
                "schema_version": "8.0",
                "audio_id": f"reference:{role}",
                "kind": "reference",
                "model_id": "原始参考音频",
                "role": role,
                "audio": {"duration_seconds": 10.0},
                "metrics": {
                    "sensevoice_cer": {"cer": 0.01 + index / 1000},
                    "whisper_cer": {"cer": 0.02 + index / 1000},
                    "utmosv2": {"mean": 3.0, "min": 2.9, "std": 0.1, "count": 1},
                    "nisqa": {"mean": 4.0, "min": 3.9, "std": 0.1, "count": 1},
                },
                "errors": [],
            }
        )
    for index, model in enumerate(MODELS):
        audio_rows.append(
            {
                "schema_version": "8.0",
                "audio_id": f"synthesis:{model}",
                "kind": "synthesis",
                "model_id": model,
                "role": "完整有声书",
                "audio": {"duration_seconds": 600.0 + index},
                "metrics": {
                    "sensevoice_cer": {"cer": 0.10 + index / 10},
                    "whisper_cer": {
                        "cer": 0.11 + index / 10,
                        "alignment_summary": {
                            "exact_matched_characters": 2400,
                            "expected_characters": 2513,
                            "exact_alignment_ratio_to_expected": 2400 / 2513,
                        },
                    },
                    "utmosv2": {"mean": 4.0 - index / 10, "min": 3.5, "std": 0.1, "count": 8},
                    "nisqa": {"mean": 4.5 - index / 10, "min": 4.0, "std": 0.1, "count": 8},
                },
                "errors": [],
            }
        )

    similarity_rows = []
    for model_index, model in enumerate(MODELS):
        for role_index, role in enumerate(ROLES):
            similarity_rows.append(
                {
                    "schema_version": "8.0",
                    "model_id": model,
                    "role": role,
                    "alignment_excerpts": [{"start_seconds": 1.0, "end_seconds": 2.0}],
                    "metrics": {
                        "wavlm_sim": {"mean": 0.9 - model_index / 10 - role_index / 1000},
                        "speechbrain_ecapa_sim": {
                            "mean": 0.8 - model_index / 10 - role_index / 1000
                        },
                    },
                    "errors": [],
                }
            )

    calibration_rows = [
        {
            "schema_version": "8.0",
            "control_type": "same_speaker_split_half",
            "label": f"{role}同说话人",
            "metrics": {"wavlm_sim": 0.9, "speechbrain_ecapa_sim": 0.8},
            "errors": [],
        }
        for role in ROLES
    ]
    calibration_rows.extend(
        {
            "schema_version": "8.0",
            "control_type": "different_speaker_reference_pair",
            "label": f"{left}与{right}",
            "metrics": {"wavlm_sim": 0.4, "speechbrain_ecapa_sim": 0.3},
            "errors": [],
        }
        for left, right in combinations(ROLES, 2)
    )
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v8.json").read_text(encoding="utf-8")
    )
    metadata = {
        "schema_version": "8.0",
        "config": config,
        "coverage": {
            "sensevoice_cer": {"complete": 11, "expected": 11},
            "whisper_cer": {"complete": 11, "expected": 11},
            "wavlm_sim": {"complete": 38, "expected": 38},
            "speechbrain_ecapa_sim": {"complete": 38, "expected": 38},
            "utmosv2": {"complete": 11, "expected": 11},
            "nisqa": {"complete": 11, "expected": 11},
        },
    }
    write_jsonl(directory / "per_audio.jsonl", audio_rows)
    write_jsonl(directory / "speaker_similarity.jsonl", similarity_rows)
    write_jsonl(directory / "speaker_calibration.jsonl", calibration_rows)
    (directory / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )


def test_complete_v8_results_render_required_reports(tmp_path: Path) -> None:
    script = load_module(
        "generate_neutral_v8_reports_test", SCRIPTS / "generate_neutral_v8_reports.py"
    )
    write_complete_v8_results(tmp_path)

    reports = script.build_reports(tmp_path, results_link="raw-v8")
    model_report = script.build_model_report(tmp_path, MODELS[0], results_link="raw-v8")

    assert set(reports) == {"cer", "sim", "quality", "comprehensive"}
    assert "97 段台词、2513 个规范化字符" in reports["cer"]
    assert "longAudioTestV8/ai_deal.json" in reports["cer"]
    assert "4 角色宏平均" in reports["sim"]
    assert "不直接平均原始 MOS" in reports["quality"]
    assert "# 小说转有声 TTS V8 综合评价报告" in reports["comprehensive"]
    assert "raw-v8/run_metadata.json" in reports["comprehensive"]
    assert f"# {MODELS[0]} V8 独立评价报告" in model_report
    assert script.model_report_filename(MODELS[1]) == f"{MODELS[1]}_V8评价报告.md"
    assert script.REPORT_FILENAMES == {
        "cer": "SenseVoice_CER&Whisper_CER_V8评价报告.md",
        "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V8评价报告.md",
        "quality": "UTMOSv2&NISQA_V8评价报告.md",
        "comprehensive": "小说转有声TTS_V5综合评价报告.md",
    }
