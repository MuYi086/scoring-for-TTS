"""本地模型集中克隆编排器的轻量测试。"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLONE_DATA = ROOT / "cloneData"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_runner():
    support = load_module("_clone_test_support", CLONE_DATA / "_clone_test_support.py")
    runner = load_module("_direct_local_clone_runner", CLONE_DATA / "_direct_local_clone_runner.py")
    return support, runner


def test_local_models_have_a_direct_script_environment_and_local_model_path() -> None:
    _, runner = load_runner()
    expected = {
        "dots_tts_base": "dots_tts",
        "qwen3_tts_12hz_1_7b_base": "qwen3-tts",
        "voxcpm2": "voxcpm2",
        "moss_tts_local_transformer": "moss-tts-py310",
        "longcat_audiodit_1b": "longcat_audiodit",
        "omnivoice": "omnivoice",
    }
    assert {slug: spec.conda_env for slug, spec in runner.MODEL_SPECS.items()} == expected
    for spec in runner.MODEL_SPECS.values():
        assert spec.source_script.parent == ROOT / "modelScript"
        assert spec.model_path.is_absolute()


def test_local_command_uses_reference_and_staging_output_without_http() -> None:
    support, runner = load_runner()
    spec = runner.MODEL_SPECS["qwen3_tts_12hz_1_7b_base"]
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        text_path = staging / "text.txt"
        command = runner.command_for_case(spec, spec.model_path, support.CASES[0], text_path, staging)

    assert command[0] == sys.executable
    assert "--ref-audio" in command
    assert str(support.CASES[0].reference_audio) in command
    assert "--ref-text" in command
    assert support.CASES[0].reference_text in command
    assert "--output-dir" in command
    assert "http" not in " ".join(command).lower()


def test_output_names_use_model_and_character() -> None:
    support, runner = load_runner()
    spec = runner.MODEL_SPECS["voxcpm2"]
    assert runner.output_path(spec, support.CASES[1]) == ROOT / "cloneData/VoxCPM2_小公主.wav"
