"""Task 6/7 两阶段、双模型逐段证据流程的无模型测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK8_DIR = ROOT / "task-runner" / "task8"
EVALUATOR_PATH = TASK8_DIR / "run_task8_evaluation.py"


def load_evaluator():
    if str(TASK8_DIR) not in sys.path:
        sys.path.insert(0, str(TASK8_DIR))
    spec = importlib.util.spec_from_file_location("evidenced_evaluator_for_v6_v7", EVALUATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_synthesis_wrapper(task_id: str):
    task_dir = ROOT / "task-runner" / task_id
    if str(task_dir) not in sys.path:
        sys.path.insert(0, str(task_dir))
    spec = importlib.util.spec_from_file_location(f"{task_id}_synthesis_wrapper", task_dir / f"run_{task_id}_synthesis.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v6_v7_contracts_freeze_their_own_text_and_exactly_two_evidenced_candidates() -> None:
    evaluator = load_evaluator()
    expected = {
        "task6": ("V6", "longAudioTestV6/text.md", 1826),
        "task7": ("V7", "longAudioTestV7/text.md", 2076),
    }
    for task_id, (version, text_path, character_count) in expected.items():
        contract = evaluator.load_contract(ROOT / "task-runner" / task_id / "evaluation-contract.json")
        assert contract["version"] == version
        assert contract["schema_version"] == f"{task_id}-v2"
        assert contract["source"]["text_path"] == text_path
        assert contract["source"]["normalized_character_count"] == character_count
        assert contract["source"]["segment_manifest_path"] == f"longAudioTest{version}/.{task_id}_segment_manifest.json"
        assert contract["asr_evaluation"]["mode"] == "synthesis_segment_evidence"
        assert contract["asr_evaluation"]["evidence_root"] == f"longAudioTest{version}/.{task_id}_synthesis_evidence"
        assert [model["model_id"] for model in contract["models"]] == ["indextts2", "voxcpm2"]
        assert evaluator.task_identity(contract) == (f"Task {task_id[-1]}", version)


def test_v6_v7_synthesis_templates_only_plan_the_two_required_models() -> None:
    for task_id, version in (("task6", "V6"), ("task7", "V7")):
        plan = json.loads((ROOT / "task-runner" / task_id / "synthesis-plan.example.json").read_text(encoding="utf-8"))
        assert plan["schema_version"] == f"{task_id}-synthesis-plan-v2"
        assert plan["version"] == version
        assert [model["model_id"] for model in plan["models"]] == ["indextts2", "voxcpm2"]
        index_command = plan["models"][0]["command"]
        vox_command = plan["models"][1]["command"]
        assert "task-runner/task9/indextts2.py" in index_command
        assert "task-runner/task9/voxcpm2.py" in vox_command
        for command in (index_command, vox_command):
            assert "{segment_manifest}" in command
            assert "{segment_evidence_root}" in command
        assert "--style-prompt" not in vox_command


def test_v6_v7_synthesis_wrappers_select_the_v2_evidence_plan_schema() -> None:
    for task_id, version in (("task6", "V6"), ("task7", "V7")):
        wrapper = load_synthesis_wrapper(task_id)
        wrapper.configure_engine()
        engine = sys.modules["run_task8_synthesis"]
        assert engine.TASK_ID == task_id
        assert engine.VERSION == version
        assert engine.PLAN_SCHEMA_VERSION == f"{task_id}-synthesis-plan-v2"


def test_versioned_results_must_stay_under_their_own_task_directory(monkeypatch, tmp_path: Path) -> None:
    evaluator = load_evaluator()
    monkeypatch.setattr(evaluator, "PROJECT_ROOT", tmp_path)
    contract = {"source": {"text_path": "longAudioTestV7/text.md"}}
    result_dir = tmp_path / "longAudioTestV7" / "评测结果" / "task-V7-test"

    resolved, result_file = evaluator.prepare_results_directory(result_dir, resume=False, contract=contract)

    assert resolved == result_dir
    assert result_file.name == "task8_evaluation_results.json"
    try:
        evaluator.prepare_results_directory(tmp_path / "longAudioTestV6" / "评测结果" / "wrong", resume=False, contract=contract)
    except ValueError as error:
        assert "必须位于" in str(error)
    else:
        raise AssertionError("Task 7 结果不得写入 V6 目录")


def test_task6_task7_docs_describe_synthesis_before_evaluation_and_exclude_qwen() -> None:
    for version in ("6", "7"):
        document = (ROOT / f"task{version}.md").read_text(encoding="utf-8")
        assert "两个阶段" in document
        assert "audio_*.wav` 是第一阶段的输出" in document
        assert "IndexTTS2" in document and "VoxCPM2" in document
        assert "Qwen3-TTS" in document
        assert f"longAudioTestV{version}/text.md" in document
        assert "逐段证据" in document
        assert "整条长音频一次送入 ASR" in document
