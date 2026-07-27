"""Task 9 V9 公共受限入口、冻结输入和报告测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tts-bench" / "scripts"
ROLES = ["旁白", "布罗迪", "我", "布罗迪姐姐", "教授"]
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
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def test_v9_config_freezes_only_public_long_audio_metrics() -> None:
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v9.json").read_text(encoding="utf-8")
    )

    assert config["schema_version"] == "9.0"
    assert config["evaluation_profile"] == "public-task-restricted"
    assert [item["model_id"] for item in config["models"]] == MODELS
    assert [item["role"] for item in config["references"]] == ROLES
    assert config["source"]["dialogue_count"] == 77
    assert config["source"]["normalized_character_count"] == 1505
    assert config["policy"]["long_audio_metrics"] == [
        "audio_delivery",
        "sensevoice_cer",
        "whisper_cer",
    ]
    assert {"wavlm_sim", "speechbrain_ecapa_sim", "utmosv2", "nisqa"} <= set(
        config["policy"]["prohibited_long_audio_metrics"]
    )
    assert "wavlm" not in config and "utmosv2" not in config and "nisqa" not in config
    assert "seed_tts_benchmark" not in config


def test_v9_entry_requires_new_output_and_only_public_metrics(monkeypatch, tmp_path: Path) -> None:
    script = load_module("run_neutral_evaluation_v9_public_test", SCRIPTS / "run_neutral_evaluation_v9.py")
    output = tmp_path / "new-run"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_neutral_evaluation_v9.py",
            "--model-id",
            "OmniVoice",
            "--output-dir",
            str(output),
        ],
    )

    args = script.parse_args()

    assert args.output_dir == output
    assert args.model_id == "OmniVoice"
    assert args.metrics == ["audio_delivery", "sensevoice_cer", "whisper_cer"]
    assert "wavlm_sim" not in script.PUBLIC_METRICS


def test_v9_validator_rejects_any_non_public_metric() -> None:
    module = load_module("public_evaluation_v9_validator_test", SCRIPTS / "public_evaluation_v9.py")
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v9.json").read_text(encoding="utf-8")
    )
    config["policy"]["long_audio_metrics"].append("utmosv2")

    with pytest.raises(ValueError, match="长音频指标"):
        module.validate_config(config)


def complete_rows() -> list[dict]:
    rows: list[dict] = []
    for index, role in enumerate(ROLES):
        rows.append(
            {
                "schema_version": "9.0",
                "audio_id": f"reference:{role}",
                "kind": "reference",
                "model_id": "原始参考音频",
                "role": role,
                "expected_text": "参考文本",
                "audio": {"path": f"reference-{index}.wav", "sha256": "ref"},
                "metrics": {
                    "audio_delivery": delivery(10.0),
                    "sensevoice_cer": asr(0.01 + index / 1000),
                    "whisper_cer": asr(0.02 + index / 1000),
                },
                "errors": [],
            }
        )
    for index, model in enumerate(MODELS):
        rows.append(
            {
                "schema_version": "9.0",
                "audio_id": f"synthesis:{model}",
                "kind": "synthesis",
                "model_id": model,
                "role": "完整有声书",
                "expected_text": "甲乙",
                "audio": {"path": f"{model}.wav", "sha256": "synth"},
                "metrics": {
                    "audio_delivery": delivery(600.0 + index),
                    "sensevoice_cer": asr(0.10 + index / 100),
                    "whisper_cer": asr(0.11 + index / 100),
                },
                "errors": [],
            }
        )
    return rows


def asr(value: float) -> dict:
    return {
        "cer": value,
        "reference_normalized": "甲乙",
        "hypothesis_normalized": "甲乙",
        "hypothesis_raw": "甲乙",
        "segments": [],
    }


def delivery(duration: float) -> dict:
    return {
        "decode_status": "decoded",
        "file_bytes": 10,
        "format": {
            "sample_rate_hz": 44100,
            "channels": 2,
            "subtype": "PCM_16",
            "frames": int(duration * 44100),
            "duration_seconds": duration,
        },
        "sample_peak_dbfs": -1.0,
        "dc_offset": 0.0,
        "clipping": {"measurement_threshold": 0.999, "sample_count_at_or_above_threshold": 0, "ratio": 0.0},
        "silence": {
            "measurement_window_seconds": 0.1,
            "threshold_dbfs": -60.0,
            "reported_minimum_seconds": 0.5,
            "leading_seconds": 0.0,
            "trailing_seconds": 0.0,
            "runs": [],
        },
        "format_contract": {"status": "not_frozen"},
        "loudness_and_true_peak": {"status": "not_executed"},
    }


def write_complete_results(directory: Path) -> None:
    config = json.loads(
        (ROOT / "tts-bench/config/neutral-evaluation-v9.json").read_text(encoding="utf-8")
    )
    rows = complete_rows()
    coverage = {
        metric: {"complete": len(rows), "expected": len(rows)}
        for metric in ("audio_delivery", "sensevoice_cer", "whisper_cer")
    }
    metadata = {
        "schema_version": "9.0",
        "evaluation_profile": "public-task-restricted",
        "long_audio_metrics": ["audio_delivery", "sensevoice_cer", "whisper_cer"],
        "cross_metric_weighted_score": False,
        "coverage": coverage,
        "unexecuted_checks": config["checks"],
        "config": config,
    }
    write_jsonl(directory / "per_audio.jsonl", rows)
    (directory / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )


def test_complete_public_v9_results_render_only_required_reports(tmp_path: Path) -> None:
    script = load_module(
        "generate_neutral_v9_public_test", SCRIPTS / "generate_neutral_v9_reports.py"
    )
    write_complete_results(tmp_path)

    reports = script.build_reports(tmp_path, results_link="raw-v9")

    assert set(reports) == {"cer", "delivery"}
    assert "Whisper-large-v3-turbo" in reports["cer"]
    assert "77 段" in reports["cer"]
    assert "不判定通过、失败或优劣" in reports["delivery"]
    assert "强制对齐与读法合规：**未执行**" in reports["delivery"]
    assert "综合" not in "\n".join(reports.values())
    assert script.REPORT_FILENAMES == {
        "cer": "SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md",
        "delivery": "音频交付与文本一致性_V9自动检查报告.md",
    }
