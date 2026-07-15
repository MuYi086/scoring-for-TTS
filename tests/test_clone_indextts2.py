"""IndexTTS2 集中克隆脚本的无网络测试。"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "cloneData/indextts2/test_clone_indextts2.py"


def load_script():
    spec = importlib.util.spec_from_file_location("clone_indextts2", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixed_cases_preserve_task_text_vectors_and_output_names() -> None:
    script = load_script()

    cases = {case.character: case for case in script.CASES}
    assert set(cases) == {"旁白", "小公主", "见习魔法师"}
    assert cases["旁白"].emotion_vector == (0, 0, 0, 0, 0, 0, 0, 0.5)
    assert cases["小公主"].emotion_vector == (0, 0.35, 0, 0, 0, 0, 0, 0)
    assert cases["见习魔法师"].emotion_vector == (0, 0, 0, 0.5, 0, 0, 0, 0)
    assert [case.output_name for case in script.CASES] == [
        "indextts2_旁白.wav",
        "indextts2_小公主.wav",
        "indextts2_见习魔法师.wav",
    ]


def test_model_and_source_roots_are_configurable(monkeypatch, tmp_path: Path) -> None:
    mirror_root = tmp_path / "hf-mirror"
    vendor_root = tmp_path / "vendor"
    monkeypatch.setenv("HF_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("TTS_VENDOR_ROOT", str(vendor_root))

    script = load_script()

    assert script.DEFAULT_MODEL_PATH == mirror_root / "IndexTeam/IndexTTS-2"
    assert script.DEFAULT_CODE_PATH == vendor_root / "index-tts"
    assert [case.reference_audio.as_posix() for case in script.CASES] == [
        (ROOT / "testData/mimo_旁白.wav").as_posix(),
        (ROOT / "testData/mimo_小公主.wav").as_posix(),
        (ROOT / "testData/mimo_见习魔法师.wav").as_posix(),
    ]


def test_selected_cases_preserve_the_declared_order() -> None:
    script = load_script()
    assert [case.character for case in script.selected_cases(["见习魔法师", "旁白"])] == [
        "旁白",
        "见习魔法师",
    ]


def test_infer_arguments_directly_map_to_the_official_runtime() -> None:
    script = load_script()
    case = script.CASES[0]
    args = type("Args", (), {"emo_alpha": 0.6, "num_beams": 1})()
    arguments = script.infer_arguments(case, Path("/tmp/indextts2_旁白.wav"), args)

    assert arguments["spk_audio_prompt"] == str(ROOT / "testData/mimo_旁白.wav")
    assert arguments["output_path"] == "/tmp/indextts2_旁白.wav"
    assert arguments["emo_vector"] == list(case.emotion_vector)
    assert arguments["emo_alpha"] == 0.6
    assert arguments["use_emo_text"] is False
    assert arguments["num_beams"] == 1


def test_preflight_checks_the_local_assets_without_importing_the_model() -> None:
    script = load_script()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        reference = root / "reference.wav"
        reference.touch()
        model_path = root / "IndexTTS-2"
        for relative in ("config.yaml", *script.REQUIRED_MODEL_FILES):
            path = model_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        code_path = root / "index-tts"
        code_path.mkdir()
        case = script.CloneCase("测试角色", reference, (0, 0, 0, 0, 0, 0, 0, 0), "测试文本")
        args = SimpleNamespace(model_path=model_path, config_path=None, code_path=code_path)

        resolved_model, resolved_config = script.preflight(args, (case,))

        assert resolved_model == model_path.resolve()
        assert resolved_config == (model_path / "config.yaml").resolve()


def test_runtime_options_require_explicit_cpu_opt_in() -> None:
    script = load_script()

    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return False

    fake_torch = type("FakeTorch", (), {"cuda": FakeCuda()})()
    cpu_args = SimpleNamespace(device=None, allow_cpu=True)
    assert script.resolve_runtime_options(fake_torch, cpu_args) == ("cpu", False)

    cuda_args = SimpleNamespace(device="cuda:0", allow_cpu=True)
    try:
        script.resolve_runtime_options(fake_torch, cuda_args)
    except RuntimeError as exc:
        assert "未检测到 CUDA" in str(exc)
    else:
        raise AssertionError("显式 CUDA 请求在无 CUDA 环境中必须失败")
