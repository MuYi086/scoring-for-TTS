"""Task 4 V3 集中克隆脚本的轻量回归测试。"""

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


def load_support_and_runner():
    load_module("_clone_test_support", CLONE_DATA / "_clone_test_support.py")
    support = load_module("_clone_test_support_v3", CLONE_DATA / "_clone_test_support_v3.py")
    runner = load_module("_direct_local_clone_runner", CLONE_DATA / "_direct_local_clone_runner.py")
    return support, runner


def test_v3_cases_freeze_references_transcripts_and_target_texts() -> None:
    support, _ = load_support_and_runner()
    cases = {case.character: case for case in support.CASES}

    assert set(cases) == {"旁白", "小公主", "辰南"}
    assert cases["旁白"].reference_audio == ROOT / "testData/mimo_旁白_v3.wav"
    assert cases["小公主"].text == "认识，当然认识。"
    assert cases["辰南"].text == "请公主殿下责罚。"
    assert cases["辰南"].reference_text.startswith("我是辰南，")
    assert all("声线校准测试" in case.reference_text for case in support.CASES)


def test_v3_generic_runner_uses_audio_v3_and_reference_text() -> None:
    support, runner = load_support_and_runner()
    case = support.CASES[0]
    spec = runner.MODEL_SPECS["qwen3_tts_12hz_1_7b_base"]
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        command = runner.command_for_case(
            spec,
            spec.model_path,
            case,
            staging / "text.txt",
            staging,
            support.OUTPUT_ROOT,
        )

    assert runner.output_path(spec, case, support.OUTPUT_ROOT) == (
        ROOT / "cloneData/audio_v3/Qwen3-TTS-12Hz-1.7B-Base_旁白.wav"
    )
    assert str(case.reference_audio) in command
    assert case.reference_text in command


def test_v3_indextts2_preserves_task_emotion_vectors() -> None:
    directory = CLONE_DATA / "indextts2"
    sys.path.insert(0, str(directory))
    try:
        script = load_module("clone_indextts2_v3", directory / "test_clone_indextts2_v3.py")
    finally:
        sys.path.remove(str(directory))

    cases = {case.character: case for case in script.CASES}
    assert cases["旁白"].emotion_vector == (0, 0, 0, 0, 0, 0, 0, 0.5)
    assert cases["小公主"].emotion_vector == (0, 0.5, 0, 0, 0, 0, 0, 0)
    assert cases["辰南"].emotion_vector == (0, 0, 0, 0, 0, 0.35, 0, 0)
    assert script.OUTPUT_ROOT == ROOT / "cloneData/audio_v3"


def test_all_eight_models_have_v3_test_scripts() -> None:
    scripts = sorted(CLONE_DATA.glob("*/test_clone_*_v3.py"))
    assert len(scripts) == 8
    assert {path.parent.name for path in scripts} == {
        "dots_tts_base",
        "indextts2",
        "longcat_audiodit_1b",
        "mimo",
        "moss_tts_local_transformer",
        "omnivoice",
        "qwen3_tts_12hz_1_7b_base",
        "voxcpm2",
    }
