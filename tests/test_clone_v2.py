"""Task 3 V2 集中克隆脚本的轻量回归测试。"""

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
    support = load_module("_clone_test_support_v2", CLONE_DATA / "_clone_test_support_v2.py")
    runner = load_module("_direct_local_clone_runner", CLONE_DATA / "_direct_local_clone_runner.py")
    return support, runner


def test_v2_cases_freeze_references_transcripts_and_target_texts() -> None:
    support, _ = load_support_and_runner()
    cases = {case.character: case for case in support.CASES}

    assert list(cases) == ["旁白", "辰南", "小公主"]
    assert cases["旁白"].reference_audio == ROOT / "testData/mimo_旁白_v2.wav"
    assert cases["旁白"].text == (
        "看着小恶魔那甜甜的微笑，他感觉身体一阵颤栗，他想挣扎，却动弹不得，"
        "想大声呼喊，却发不出声音，眨眼间，冷汗浸透了他的衣衫。"
    )
    assert cases["辰南"].reference_audio == ROOT / "testData/mimo_辰南_v2.wav"
    assert cases["辰南"].text == (
        "人为刀俎，我为鱼肉。刚刚出来游历，便要遭受这番悲惨遭遇，"
        "老天你不会在和我开玩笑吧？"
    )
    assert cases["小公主"].reference_audio == ROOT / "testData/mimo_小公主_v2.wav"
    assert cases["小公主"].text.endswith("再也没有人会阻止我了，呵呵……")
    assert all(case.reference_text.startswith(f"我是{case.character}，") for case in support.CASES)


def test_v2_generic_runner_uses_audio_v2_and_reference_text() -> None:
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
        ROOT / "cloneData/audio_v2/Qwen3-TTS-12Hz-1.7B-Base_旁白.wav"
    )
    assert str(case.reference_audio) in command
    assert case.reference_text in command


def test_v2_indextts2_preserves_task_emotion_vectors() -> None:
    directory = CLONE_DATA / "indextts2"
    sys.path.insert(0, str(directory))
    try:
        script = load_module("clone_indextts2_v2", directory / "test_clone_indextts2_v2.py")
    finally:
        sys.path.remove(str(directory))

    cases = {case.character: case for case in script.CASES}
    assert cases["旁白"].emotion_vector == (0, 0, 0, 0, 0, 0, 0, 0.5)
    assert cases["辰南"].emotion_vector == (0, 0, 0, 1, 0, 0, 0, 0)
    assert cases["小公主"].emotion_vector == (0.75, 0, 0, 0, 0, 0, 0, 0)
    assert script.OUTPUT_ROOT == ROOT / "cloneData/audio_v2"


def test_all_eight_models_have_v2_test_scripts() -> None:
    scripts = sorted(CLONE_DATA.glob("*/test_clone_*_v2.py"))
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
