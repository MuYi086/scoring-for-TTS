"""V2 双后端评测入口的轻量逻辑测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tts-bench/scripts/run_neutral_evaluation_v2.py"


def load_script():
    spec = importlib.util.spec_from_file_location("run_neutral_evaluation_v2", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_audio(script, audio_id: str, case_id: str, role: str):
    return script.AudioInput(
        audio_id=audio_id,
        kind="reference",
        model_id="原始参考音频",
        run_id=None,
        case_id=case_id,
        role=role,
        path=ROOT / f"{case_id}.wav",
        sha256="0" * 64,
        expected_text="测试文本",
    )


def test_calibration_contains_three_positive_and_three_negative_pairs() -> None:
    script = load_script()
    references = [
        make_audio(script, "reference:a", "a", "旁白"),
        make_audio(script, "reference:b", "b", "小公主"),
        make_audio(script, "reference:c", "c", "见习魔法师"),
    ]

    rows = script.build_calibration_records(references)

    assert len(rows) == 6
    assert sum(row["control_type"] == "same_speaker_split_half" for row in rows) == 3
    assert sum(row["control_type"] == "different_speaker_reference_pair" for row in rows) == 3


def test_asr_metric_keeps_raw_transcript_and_uses_shared_cer_normalization() -> None:
    script = load_script()
    audio = make_audio(script, "reference:a", "a", "旁白")
    row = script.base_audio_record(audio)

    class FakeEvaluator:
        def transcribe(self, path: Path) -> str:
            assert path == audio.path
            return "测，试 文本！"

    script.apply_asr_metric(
        "sensevoice_cer",
        FakeEvaluator,
        {audio.audio_id: audio},
        [row],
    )

    metric = row["metrics"]["sensevoice_cer"]
    assert metric["hypothesis_raw"] == "测，试 文本！"
    assert metric["reference_normalized"] == "测试文本"
    assert metric["hypothesis_normalized"] == "测试文本"
    assert metric["cer"] == 0.0
    assert row["errors"] == []


def test_metric_coverage_counts_audio_and_similarity_backends_separately() -> None:
    script = load_script()
    audio_rows = [
        {"metrics": {"sensevoice_cer": {}, "whisper_cer": {}, "utmosv2": {}, "nisqa": {}}},
        {"metrics": {"sensevoice_cer": {}, "whisper_cer": {}, "utmosv2": {}}},
    ]
    similarity_rows = [{"metrics": {"wavlm_sim": 0.8, "speechbrain_ecapa_sim": 0.7}}]
    calibration_rows = [{"metrics": {"wavlm_sim": 0.5}}]

    coverage = script.metric_coverage(audio_rows, similarity_rows, calibration_rows)

    assert coverage["sensevoice_cer"] == {"complete": 2, "expected": 2}
    assert coverage["nisqa"] == {"complete": 1, "expected": 2}
    assert coverage["wavlm_sim"] == {"complete": 2, "expected": 2}
    assert coverage["speechbrain_ecapa_sim"] == {"complete": 1, "expected": 2}


def test_speechbrain_uses_local_override_instead_of_remote_pretrainer(monkeypatch) -> None:
    script = load_script()
    captured: dict[str, object] = {}

    fake_torch = ModuleType("torch")
    fake_torch.cuda = type("FakeCuda", (), {"is_available": staticmethod(lambda: True)})()
    fake_speechbrain = ModuleType("speechbrain")
    fake_inference = ModuleType("speechbrain.inference")
    fake_speaker = ModuleType("speechbrain.inference.speaker")

    class FakeEncoderClassifier:
        @staticmethod
        def from_hparams(**kwargs):
            captured.update(kwargs)
            return object()

    fake_speaker.EncoderClassifier = FakeEncoderClassifier
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "speechbrain", fake_speechbrain)
    monkeypatch.setitem(sys.modules, "speechbrain.inference", fake_inference)
    monkeypatch.setitem(sys.modules, "speechbrain.inference.speaker", fake_speaker)
    monkeypatch.delenv("HF_MIRROR_ROOT", raising=False)

    script.SpeechBrainEcapaEvaluator(
        {
            "model_id": "speechbrain/spkrec-ecapa-voxceleb",
            "device": "cuda",
            "sample_rate_hz": 16000,
        }
    )

    assert captured["source"] == "speechbrain/spkrec-ecapa-voxceleb"
    assert captured["overrides"] == {
        "pretrained_path": "speechbrain/spkrec-ecapa-voxceleb"
    }
    assert captured["run_opts"] == {"device": "cuda:0"}
