"""Task 9 两模型本地合成编排器的无模型测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_SCRIPT_DIR = ROOT / "task-runner" / "task9"
RUNNER_PATH = TASK_SCRIPT_DIR / "run_task9_clone.py"
VOXCPM_SCRIPT_PATH = TASK_SCRIPT_DIR / "voxcpm2.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_task_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    task_dir = root / "longAudioTestV9"
    task_dir.mkdir()
    (task_dir / "text.md").write_text("用于测试的合成原文。", encoding="utf-8")
    (task_dir / "mimo_旁白_v9.wav").write_bytes(b"RIFF-test")
    mirror = root / "hf-mirror"
    (mirror / "IndexTeam/IndexTTS-2").mkdir(parents=True)
    (mirror / "openbmb/VoxCPM2").mkdir(parents=True)
    code_path = root / "index-tts"
    code_path.mkdir()
    return task_dir, mirror, code_path, mirror / "IndexTeam/IndexTTS-2"


def test_task_paths_have_the_two_fixed_output_names(tmp_path: Path) -> None:
    runner = load_module("task9_runner_paths", RUNNER_PATH)

    paths = runner.task_paths(tmp_path / "longAudioTestV9")

    assert paths.text_file.name == "text.md"
    assert paths.reference_audio.name == "mimo_旁白_v9.wav"
    assert paths.indextts_output.name == "audio_indextts2.wav"
    assert paths.voxcpm2_output.name == "audio_voxcpm2.wav"


def test_dry_run_plan_uses_text_reference_and_serial_model_order(tmp_path: Path) -> None:
    runner = load_module("task9_runner_plan", RUNNER_PATH)
    task_dir, mirror, code_path, _ = create_task_inputs(tmp_path)
    args = runner.parse_args(
        [
            "--task-dir",
            str(task_dir),
            "--hf-mirror-root",
            str(mirror),
            "--indextts-code-path",
            str(code_path),
            "--models",
            "voxcpm2",
            "indextts2",
            "--dry-run",
        ]
    )
    inputs = runner.task_paths(args.task_dir)
    models = runner.resolve_model_paths(args)
    runner.validate_preflight(args, inputs, models)
    invocations = runner.build_invocations(args, inputs, models)

    assert [item.model_key for item in invocations] == ["indextts2", "voxcpm2"]
    assert str(inputs.text_file) in invocations[0].command
    assert str(inputs.reference_audio) in invocations[0].command
    assert "--output" in invocations[0].command
    assert str(inputs.indextts_output) in invocations[0].command
    assert "--prompt-text" in invocations[1].command
    assert runner.DEFAULT_REFERENCE_TEXT in invocations[1].command
    assert str(inputs.voxcpm2_output) in invocations[1].command


def test_preflight_refuses_existing_audio_without_overwrite(tmp_path: Path) -> None:
    runner = load_module("task9_runner_overwrite", RUNNER_PATH)
    task_dir, mirror, code_path, _ = create_task_inputs(tmp_path)
    (task_dir / "audio_voxcpm2.wav").write_bytes(b"existing")
    args = runner.parse_args(
        [
            "--task-dir",
            str(task_dir),
            "--hf-mirror-root",
            str(mirror),
            "--indextts-code-path",
            str(code_path),
        ]
    )

    try:
        runner.validate_preflight(args, runner.task_paths(args.task_dir), runner.resolve_model_paths(args))
    except FileExistsError as error:
        assert "--overwrite" in str(error)
    else:
        raise AssertionError("已有目标音频时必须要求显式覆盖确认")


def test_task_specific_voxcpm_requires_an_explicit_output_path(tmp_path: Path) -> None:
    script = load_module("task9_voxcpm_output", VOXCPM_SCRIPT_PATH)
    explicit = tmp_path / "nested" / "audio_voxcpm2.wav"
    args = script.parse_args(
        [
            "--model-path",
            str(tmp_path / "model"),
            "--text-file",
            str(tmp_path / "text.md"),
            "--ref-audio",
            str(tmp_path / "reference.wav"),
            "--prompt-text",
            "准确参考文案",
            "--output",
            str(explicit),
        ]
    )

    assert args.output == explicit
