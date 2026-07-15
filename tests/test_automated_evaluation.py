"""自动评估入口的轻量兼容性测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tts-bench/scripts/run_automated_evaluation.py"


def load_script():
    spec = importlib.util.spec_from_file_location("run_automated_evaluation", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_whisper_pipeline_receives_local_files_only_as_top_level_option(monkeypatch) -> None:
    script = load_script()
    captured: dict[str, object] = {}

    fake_torch = ModuleType("torch")
    fake_torch.cuda = type("FakeCuda", (), {"is_available": staticmethod(lambda: False)})()
    fake_transformers = ModuleType("transformers")

    def fake_pipeline(task: str, **kwargs):
        captured["task"] = task
        captured.update(kwargs)
        return object()

    fake_transformers.pipeline = fake_pipeline
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    script.WhisperAsrEvaluator(
        {
            "model_id": "openai/whisper-large-v3-turbo",
            "device": "cpu",
            "language": "zh",
            "task": "transcribe",
        },
        allow_model_download=False,
    )

    assert captured["task"] == "automatic-speech-recognition"
    assert captured["local_files_only"] is True
    assert "model_kwargs" not in captured


def test_mirror_root_resolves_local_models_and_rejects_missing(monkeypatch, tmp_path: Path) -> None:
    script = load_script()
    model_dir = tmp_path / "microsoft/wavlm-base-sv"
    model_dir.mkdir(parents=True)
    monkeypatch.setenv("HF_MIRROR_ROOT", str(tmp_path))

    assert script.resolve_mirrored_model("microsoft/wavlm-base-sv") == str(model_dir)

    try:
        script.resolve_mirrored_model("openai/whisper-large-v3-turbo")
    except RuntimeError as exc:
        assert "HF_MIRROR_ROOT 中找不到评价模型" in str(exc)
    else:
        raise AssertionError("镜像根目录已设置时不得回退到远端模型 ID")


def test_utmosv2_uses_the_mirrored_checkpoint(monkeypatch, tmp_path: Path) -> None:
    script = load_script()
    checkpoint = tmp_path / "sarulab-speech/UTMOSv2/fold0_s42_best_model.pth"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.touch()
    monkeypatch.setenv("HF_MIRROR_ROOT", str(tmp_path))
    captured: dict[str, object] = {}

    fake_utmosv2 = ModuleType("utmosv2")

    def fake_create_model(**kwargs):
        captured.update(kwargs)
        return object()

    fake_utmosv2.create_model = fake_create_model
    monkeypatch.setitem(sys.modules, "utmosv2", fake_utmosv2)

    script.UtmosV2Evaluator(
        {"checkpoint_id": "sarulab-speech/UTMOSv2/fold0_s42_best_model.pth"}
    )

    assert captured == {"pretrained": True, "checkpoint_path": str(checkpoint)}


def test_sensevoice_uses_mirror_and_removes_control_tags(monkeypatch, tmp_path: Path) -> None:
    script = load_script()
    model_dir = tmp_path / "FunAudioLLM/SenseVoiceSmall"
    model_dir.mkdir(parents=True)
    monkeypatch.setenv("HF_MIRROR_ROOT", str(tmp_path))
    captured: dict[str, object] = {}

    class FakeModel:
        def generate(self, **kwargs):
            captured["generate"] = kwargs
            return [{"text": "<|zh|><|HAPPY|><|Speech|><|withitn|>当然有，你们是不是害怕了？"}]

    fake_funasr = ModuleType("funasr")

    def fake_auto_model(**kwargs):
        captured["init"] = kwargs
        return FakeModel()

    fake_funasr.AutoModel = fake_auto_model
    monkeypatch.setitem(sys.modules, "funasr", fake_funasr)

    evaluator = script.SenseVoiceAsrEvaluator(
        {"model_id": "FunAudioLLM/SenseVoiceSmall", "device": "cuda", "language": "zh"}
    )
    transcript = evaluator.transcribe(tmp_path / "sample.wav")

    assert captured["init"] == {
        "model": str(model_dir),
        "disable_update": True,
        "device": "cuda",
    }
    assert transcript == "当然有，你们是不是害怕了？"
    assert captured["generate"]["language"] == "zh"


def test_fixed_windows_uses_a_full_overlapping_tail_window() -> None:
    script = load_script()
    waveform = list(range(529))

    windows = script.fixed_windows(waveform, 500)

    assert [len(window) for window in windows] == [500, 500]
    assert windows[0][0] == 0
    assert windows[1][0] == 29
    assert windows[1][-1] == 528
