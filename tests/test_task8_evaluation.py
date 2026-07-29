"""Task 8 公共评测入口的无模型测试。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "task-runner" / "task8"
EVALUATOR_PATH = TASK_DIR / "run_task8_evaluation.py"
REPORTER_PATH = TASK_DIR / "generate_task8_reports.py"
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


def complete_record(model_id: str) -> dict:
    metric = {
        "status": "complete",
        "strict_character_cer": 0.1,
        "character_errors": 1,
        "phonetic_cer": 0.0,
        "phonetic_errors": 0,
        "full_transcription": "测试",
        "chunks": [{"segment_id": "001", "raw_transcription": "<|zh|>测试"}],
        "error_locations": [],
        "asr_health": {"status": "healthy", "unreliable_segment_ids": [], "ranking_eligible": True},
    }
    return {
        "model_id": model_id,
        "display_name": model_id,
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


def test_contract_freezes_v8_text_md_as_the_only_cer_reference() -> None:
    evaluator = load_module("task8_evaluator_contract", EVALUATOR_PATH)

    contract = evaluator.load_contract(CONTRACT_PATH)

    assert contract["source"]["text_path"] == "longAudioTestV8/text.md"
    assert contract["source"]["cer_reference"] == "text_md_actual_synthesis_order"
    assert contract["source"]["normalized_character_count"] == 2537
    assert contract["asr_evaluation"]["mode"] == "synthesis_segment_evidence"
    assert contract["source"]["segment_manifest_path"] == "longAudioTestV8/.task8_segment_manifest.json"
    assert [item["model_id"] for item in contract["models"]] == ["indextts2", "voxcpm2"]


def test_discover_models_uses_the_frozen_candidate_registry(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_module("task8_evaluator_discovery", EVALUATOR_PATH)
    audio_dir = tmp_path / "longAudioTestV8"
    audio_dir.mkdir()
    (audio_dir / "audio_indextts2.wav").write_bytes(b"first")
    (audio_dir / "audio_voxcpm2.wav").write_bytes(b"second")
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    contract = {
        "models": [
            {"model_id": "indextts2", "display_name": "IndexTTS2", "audio_path": "longAudioTestV8/audio_indextts2.wav"},
            {"model_id": "voxcpm2", "display_name": "VoxCPM2", "audio_path": "longAudioTestV8/audio_voxcpm2.wav"},
        ]
    }

    models = evaluator.discover_models(contract)

    assert [item["model_id"] for item in models] == ["indextts2", "voxcpm2"]
    assert models[0]["audio_sha256"] == hashlib.sha256(b"first").hexdigest()


def test_v8_evaluation_delegates_to_task9_hash_bound_segment_evidence(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_module("task8_evaluator_unit", EVALUATOR_PATH)
    task_root = tmp_path / "longAudioTestV8"
    task_root.mkdir()
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    calls: list[tuple[dict, dict, Path, Path]] = []

    def fake_evaluate(contract, model, mirror_root, output_dir):
        calls.append((contract, model, mirror_root, output_dir))
        return {"status": "complete", "model_id": model["model_id"]}

    monkeypatch.setattr(evaluator, "evaluate_evidenced_model", fake_evaluate)
    contract = {
        "models": [{"model_id": "demo", "display_name": "Demo", "audio_path": "longAudioTestV8/audio_demo.wav"}],
    }

    record = evaluator.evaluate_model(
        contract,
        {"model_id": "demo", "display_name": "Demo", "audio_path": str(task_root / "audio_demo.wav")},
        tmp_path / "hf-mirror",
    )

    assert record["status"] == "complete"
    assert calls == [(contract, contract["models"][0], tmp_path / "hf-mirror", tmp_path)]


def test_preflight_delegates_to_evidence_preflight_and_checks_frozen_text_hash(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_module("task8_evaluator_evidence_preflight", EVALUATOR_PATH)
    task_root = tmp_path / "longAudioTestV8"
    task_root.mkdir()
    text_path = task_root / "text.md"
    text_path.write_text("测试台词", encoding="utf-8")
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    calls: list[tuple[dict, Path | None]] = []
    monkeypatch.setattr(evaluator, "check_evidence_preflight", lambda contract, root: calls.append((contract, root)) or [])
    contract = {
        "source": {
            "text_path": "longAudioTestV8/text.md",
            "text_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
        }
    }
    mirror_root = tmp_path / "hf-mirror"
    models = []

    assert evaluator.check_preflight(contract, models, mirror_root) == []
    assert calls == [(contract, mirror_root)]


def test_resume_rejects_a_changed_frozen_reference_audio(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_module("task8_evaluator_resume_inputs", EVALUATOR_PATH)
    task_root = tmp_path / "longAudioTestV8"
    task_root.mkdir()
    text_path = task_root / "text.md"
    text_path.write_text("测试台词", encoding="utf-8")
    reference_path = task_root / "mimo_旁白_v8.wav"
    reference_path.write_bytes(b"first-reference")
    candidate_path = task_root / "audio_demo.wav"
    candidate_path.write_bytes(b"candidate")
    segment_manifest_path = task_root / ".task8_segment_manifest.json"
    segment_manifest_path.write_text("{}", encoding="utf-8")
    contract_path = tmp_path / "evaluation-contract.json"
    contract_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    contract = {
        "schema_version": "task8-v2",
        "version": "V8",
        "source": {"text_path": "longAudioTestV8/text.md", "segment_manifest_path": "longAudioTestV8/.task8_segment_manifest.json"},
        "reference": {"audio_path": "longAudioTestV8/mimo_旁白_v8.wav"},
        "asr_evaluation": {"mode": "synthesis_segment_evidence", "evidence_note": "逐段证据。"},
    }
    models = [{
        "model_id": "demo",
        "display_name": "demo",
        "audio_path": str(candidate_path),
        "audio_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    }]
    result_path = tmp_path / "results.json"
    results = evaluator.load_or_create_results(result_path, contract, contract_path, tmp_path / "hf-mirror", models)
    assert results["inputs"]["source_text"] == "测试台词"
    assert results["inputs"]["normalized_source_text"] == "测试台词"
    evaluator.write_json_atomic(result_path, results)
    reference_path.write_bytes(b"changed-reference")

    try:
        evaluator.load_or_create_results(result_path, contract, contract_path, tmp_path / "hf-mirror", models)
    except ValueError as error:
        assert "reference_audio_sha256 已变化" in str(error)
    else:
        raise AssertionError("续跑必须拒绝变化后的参考音频")


def test_results_directory_must_be_a_new_v8_batch_subdirectory(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_module("task8_evaluator_results_directory", EVALUATOR_PATH)
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    root = tmp_path / "longAudioTestV8" / "评测结果"

    try:
        evaluator.prepare_results_directory(tmp_path / "outside", resume=False)
    except ValueError as error:
        assert "必须位于" in str(error)
    else:
        raise AssertionError("结果目录不能离开 V8 固定输出目录")
    try:
        evaluator.prepare_results_directory(root, resume=False)
    except ValueError as error:
        assert "批次目录" in str(error)
    else:
        raise AssertionError("报告目录本身不能充当原始结果批次目录")


def test_reporter_writes_the_two_public_v8_reports(tmp_path: Path) -> None:
    reporter = load_module("task8_reporter", REPORTER_PATH)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    results = {
        "schema_version": "task8-v2",
        "version": "V8",
        "contract": contract,
        "inputs": {
            "evaluation_unit": "synthesis_segment_evidence",
            "evaluation_unit_note": "逐段证据。",
            "segment_manifest": {"policy": {"target_seconds": 25, "max_segment_seconds": 35}, "segments": [{"segment_id": "001"}]},
        },
        "candidate_models": [{"model_id": "demo"}],
        "models": {"demo": complete_record("demo")},
    }
    (tmp_path / "task8_evaluation_results.json").write_text(
        json.dumps(results, ensure_ascii=False), encoding="utf-8"
    )

    cer_path, automated_path = reporter.write_reports(tmp_path, tmp_path / "reports")

    assert cer_path.name == "SenseVoice_CER&Whisper-large-v3-turbo_CER_V8评价报告.md"
    assert automated_path.name == "音频交付与文本一致性_V8自动检查报告.md"
    cer_report = cer_path.read_text(encoding="utf-8")
    assert "已删除的 `ai_deal.json`" in cer_report
    assert "原始转写（仅移除 SenseVoice 控制标记后才计算 CER；此处保留以供复核）" in cer_report
    assert "synthesis_segment_evidence" in automated_path.read_text(encoding="utf-8")
