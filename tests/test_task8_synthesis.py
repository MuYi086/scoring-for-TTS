"""Task 8 V8 合成阶段的无模型测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "task-runner" / "task8"
RUNNER_PATH = TASK_DIR / "run_task8_synthesis.py"


def load_runner(name: str):
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(24000)
        writer.writeframes(b"\x00\x00" * 240)


def configure_task(monkeypatch, runner, tmp_path: Path) -> Path:
    task_dir = tmp_path / "longAudioTestV8"
    task_dir.mkdir()
    (task_dir / "text.md").write_text("用于 V8 合成的完整原文。", encoding="utf-8")
    write_wav(task_dir / "mimo_旁白_v8.wav")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "DEFAULT_TASK_DIR", task_dir)
    monkeypatch.setattr(runner, "DEFAULT_PLAN", task_dir / ".task8-synthesis-plan.json")
    return task_dir


def plan_for(runner, command: list[str], output_mode: str = "exact_path") -> dict:
    return {
        "schema_version": runner.PLAN_SCHEMA_VERSION,
        "version": runner.VERSION,
        "source": {
            "text_path": runner.TEXT_PATH,
            "reference_audio_path": runner.REFERENCE_AUDIO_PATH,
            "reference_transcript": runner.REFERENCE_TRANSCRIPT,
            "voice_description": runner.VOICE_DESCRIPTION,
        },
        "models": [
            {"model_id": "indextts2", "output_mode": output_mode, "command": command},
            {"model_id": "voxcpm2", "output_mode": output_mode, "command": command},
        ],
    }


def write_plan(path: Path, plan: dict) -> None:
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")


def fake_wav_command() -> list[str]:
    code = (
        "import sys,wave; path=sys.argv[1]; writer=wave.open(path, 'wb'); "
        "writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(24000); "
        "writer.writeframes(b'\\x00\\x00' * 240); writer.close()"
    )
    return [
        sys.executable,
        "-c",
        code,
        "{output_path}",
        "{text_file}",
        "{reference_audio}",
        "{segment_manifest}",
        "{segment_evidence_root}",
    ]


def test_plan_requires_v8_inputs_and_standard_output_placeholders(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_plan")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    invalid = plan_for(runner, [sys.executable, "-c", "pass", "{text_file}", "{reference_audio}"])
    write_plan(plan_path, invalid)

    try:
        runner.load_plan(plan_path)
    except ValueError as error:
        assert "{output_path}" in str(error)
    else:
        raise AssertionError("计划必须声明临时或标准输出占位符")


def test_plan_requires_shared_manifest_and_hash_bound_evidence_placeholders(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_evidence_plan")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    command = [item for item in fake_wav_command() if item != "{segment_evidence_root}"]
    write_plan(plan_path, plan_for(runner, command))

    try:
        runner.load_plan(plan_path)
    except ValueError as error:
        assert "{segment_evidence_root}" in str(error)
    else:
        raise AssertionError("V8 合成必须请求与成品哈希绑定的逐段证据")


def test_dry_run_uses_fixed_v8_inputs_without_creating_audio(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_dry_run")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    write_plan(plan_path, plan_for(runner, fake_wav_command()))

    result = runner.run(runner.parse_args(["--plan", str(plan_path), "--task-dir", str(task_dir), "--dry-run"]))

    assert result == 0
    assert not (task_dir / "audio_indextts2.wav").exists()
    assert not (task_dir / "audio_voxcpm2.wav").exists()


def test_synthesis_writes_standard_candidate_and_hash_bound_local_record(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_run")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    write_plan(plan_path, plan_for(runner, fake_wav_command()))
    evidence_manifest = task_dir / ".task8_synthesis_evidence" / "evidence.json"
    evidence_manifest.parent.mkdir(parents=True)
    evidence_manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_verified_synthesis_evidence",
        lambda **_kwargs: {
            "manifest_path": evidence_manifest,
            "full_audio_sha256": "a" * 64,
            "segments": [{"segment_id": "001"}],
        },
    )

    result = runner.run(
        runner.parse_args(["--plan", str(plan_path), "--task-dir", str(task_dir), "--models", "voxcpm2"])
    )

    output = task_dir / "audio_voxcpm2.wav"
    record_path = task_dir / ".task8_synthesis" / "voxcpm2" / "synthesis-record.json"
    assert result == 0
    runner.require_decodable_wav(output, "测试成品")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["model_id"] == "voxcpm2"
    assert record["output"]["sha256"] == runner.sha256_file(output)
    assert record["source"]["reference_transcript"] == runner.REFERENCE_TRANSCRIPT
    assert record["source"]["shared_segment_manifest_sha256"] == runner.sha256_file(
        task_dir / ".task8_segment_manifest.json"
    )
    assert record["segment_evidence"]["segment_count"] == 1


def test_existing_candidate_requires_explicit_overwrite(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_overwrite")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    write_plan(plan_path, plan_for(runner, fake_wav_command()))
    write_wav(task_dir / "audio_indextts2.wav")
    args = runner.parse_args(["--plan", str(plan_path), "--task-dir", str(task_dir), "--models", "indextts2"])

    try:
        runner.run(args)
    except FileExistsError as error:
        assert "--overwrite" in str(error)
    else:
        raise AssertionError("覆盖已有候选成品必须显式确认")


def test_plan_rejects_models_other_than_indextts2_and_voxcpm2(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_fixed_models")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    plan = plan_for(runner, fake_wav_command())
    plan["models"][1]["model_id"] = "qwen3-tts"
    write_plan(plan_path, plan)

    try:
        runner.load_plan(plan_path)
    except ValueError as error:
        assert "indextts2" in str(error)
        assert "voxcpm2" in str(error)
    else:
        raise AssertionError("Task 8 不得加入 Qwen3-TTS 或其他模型")


def test_voxcpm2_plan_rejects_a_style_prompt_that_would_be_read_as_text(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner("task8_synthesis_vox_style_prompt")
    task_dir = configure_task(monkeypatch, runner, tmp_path)
    plan_path = task_dir / ".task8-synthesis-plan.json"
    plan = plan_for(runner, fake_wav_command())
    plan["models"][1]["command"].extend(["--style-prompt", "{voice_description}"])
    write_plan(plan_path, plan)

    try:
        runner.load_plan(plan_path)
    except ValueError as error:
        assert "--style-prompt" in str(error)
        assert "朗读" in str(error)
    else:
        raise AssertionError("VoxCPM2 计划不得把音色说明拼入待朗读 text")
