"""Task 9 两模型本地合成编排器的无模型测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_SCRIPT_DIR = ROOT / "task-runner" / "task9"
RUNNER_PATH = TASK_SCRIPT_DIR / "run_task9_clone.py"
VOXCPM_SCRIPT_PATH = TASK_SCRIPT_DIR / "voxcpm2.py"
INDEXTTS_SCRIPT_PATH = TASK_SCRIPT_DIR / "indextts2.py"
SEGMENTS_PATH = TASK_SCRIPT_DIR / "text_segments.py"


def load_module(name: str, path: Path):
    if str(TASK_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(TASK_SCRIPT_DIR))
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
    assert "--segment-manifest" in invocations[0].command
    assert str(inputs.segment_manifest) in invocations[0].command
    assert "--segment-evidence-root" in invocations[0].command
    assert str(inputs.segment_evidence_root) in invocations[0].command
    assert "--prompt-text" in invocations[1].command
    assert runner.DEFAULT_REFERENCE_TEXT in invocations[1].command
    assert str(inputs.voxcpm2_output) in invocations[1].command
    assert str(inputs.segment_manifest) in invocations[1].command


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


def test_dry_run_allows_existing_audio_without_overwrite(tmp_path: Path) -> None:
    runner = load_module("task9_runner_dry_run_existing", RUNNER_PATH)
    task_dir, mirror, code_path, _ = create_task_inputs(tmp_path)
    (task_dir / "audio_indextts2.wav").write_bytes(b"existing")
    args = runner.parse_args(
        [
            "--task-dir",
            str(task_dir),
            "--hf-mirror-root",
            str(mirror),
            "--indextts-code-path",
            str(code_path),
            "--dry-run",
        ]
    )

    runner.validate_preflight(args, runner.task_paths(args.task_dir), runner.resolve_model_paths(args))


def test_preflight_ignores_completed_unselected_model_output(tmp_path: Path) -> None:
    runner = load_module("task9_runner_selected_overwrite", RUNNER_PATH)
    task_dir, mirror, code_path, _ = create_task_inputs(tmp_path)
    (task_dir / "audio_indextts2.wav").write_bytes(b"completed-index")
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
        ]
    )

    runner.validate_preflight(args, runner.task_paths(args.task_dir), runner.resolve_model_paths(args))


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
            "--segment-manifest",
            str(tmp_path / ".task9_segment_manifest.json"),
        ]
    )

    assert args.output == explicit


def test_runner_allows_explicit_model_paths_without_a_mirror_root(tmp_path: Path) -> None:
    runner = load_module("task9_runner_explicit_models", RUNNER_PATH)
    task_dir, mirror, code_path, index_model = create_task_inputs(tmp_path)
    vox_model = mirror / "openbmb/VoxCPM2"
    args = runner.parse_args(
        [
            "--task-dir",
            str(task_dir),
            "--indextts-model-path",
            str(index_model),
            "--voxcpm2-model-path",
            str(vox_model),
            "--indextts-code-path",
            str(code_path),
            "--dry-run",
        ]
    )

    paths = runner.resolve_model_paths(args)

    assert paths.hf_mirror_root is None
    assert paths.indextts_model == index_model
    assert paths.voxcpm2_model == vox_model


def test_indextts_defaults_keep_qwen_on_cpu_and_offload_conditioning(tmp_path: Path) -> None:
    script = load_module("task9_indextts_defaults", INDEXTTS_SCRIPT_PATH)
    args = script.parse_args(
        [
            "--model-path",
            str(tmp_path / "model"),
            "--code-path",
            str(tmp_path / "code"),
            "--text-file",
            str(tmp_path / "text.md"),
            "--ref-audio",
            str(tmp_path / "reference.wav"),
            "--output",
            str(tmp_path / "audio.wav"),
            "--segment-manifest",
            str(tmp_path / ".task9_segment_manifest.json"),
        ]
    )

    assert args.device is None
    assert args.qwen_emo_device == "cpu"
    assert args.offload_conditioning_models is True


def test_indextts_offloads_conditioning_models_after_reference_embedding() -> None:
    script = load_module("task9_indextts_offload", INDEXTTS_SCRIPT_PATH)

    class Moveable:
        def __init__(self) -> None:
            self.moves: list[str] = []

        def to(self, device: str):
            self.moves.append(device)
            return self

    class Model:
        device = "cuda"

        def __init__(self) -> None:
            self.semantic_model = Moveable()
            self.campplus_model = Moveable()
            self.calls = 0

        def get_emb(self) -> str:
            self.calls += 1
            return "embedding"

    class Torch:
        class cuda:
            empty_calls = 0

            @classmethod
            def empty_cache(cls) -> None:
                cls.empty_calls += 1

    model = Model()
    assert script.install_conditioning_model_offload(model, Torch) is True
    assert model.get_emb() == "embedding"
    assert model.semantic_model.moves == []
    assert model.get_emb() == "embedding"
    assert model.semantic_model.moves == ["cpu"]
    assert model.campplus_model.moves == ["cpu"]
    assert Torch.cuda.empty_calls == 1


def test_shared_segmenter_long_sentence_has_no_missing_characters() -> None:
    script = load_module("task9_shared_split", SEGMENTS_PATH)
    source = "甲" * 121

    chunks = script.split_synthesis_text(source, 40)

    assert "".join(chunks) == source
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_two_models_share_exactly_the_same_task9_text_segments(tmp_path: Path) -> None:
    runner = load_module("task9_runner_shared_manifest", RUNNER_PATH)
    task_dir, mirror, code_path, _ = create_task_inputs(tmp_path)
    inputs = runner.task_paths(task_dir)
    models = runner.ModelPaths(mirror, mirror / "IndexTeam/IndexTTS-2", code_path, mirror / "openbmb/VoxCPM2")
    args = runner.parse_args(["--hf-mirror-root", str(mirror), "--indextts-code-path", str(code_path)])
    invocations = runner.build_invocations(args, inputs, models)

    assert str(inputs.segment_manifest) in invocations[0].command
    assert str(inputs.segment_manifest) in invocations[1].command
    assert str(inputs.segment_evidence_root) in invocations[0].command
    assert str(inputs.segment_evidence_root) in invocations[1].command


def test_task9_original_text_has_a_complete_shared_80_character_segment_plan() -> None:
    segments_module = load_module("task9_actual_segments", SEGMENTS_PATH)
    source = (ROOT / "longAudioTestV9" / "text.md").read_text(encoding="utf-8").strip()
    reference = ROOT / "longAudioTestV9" / "mimo_旁白_v9.wav"

    plan = segments_module.build_segment_plan(
        source,
        reference,
        "深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。",
        25,
        35,
    )
    chunks = plan["segments"]

    assert plan["reference_speech_rate"]["characters_per_second"] > 0
    assert plan["source_normalized_character_count"] == 1527
    assert all(item["estimated_duration_seconds"] <= 35 for item in chunks)
    assert {item["pause_after_ms"] for item in chunks[:-1]} <= {250, 500, 750}
    assert "".join(segments_module.normalize_zh_v1(item["text"]) for item in chunks) == segments_module.normalize_zh_v1(source)
