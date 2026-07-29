"""Task 9 逐段合成音频证据的无模型测试。"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "task-runner" / "task9"
EVIDENCE_PATH = TASK_DIR / "synthesis_evidence.py"


def load_module(name: str):
    if str(TASK_DIR) not in sys.path:
        sys.path.insert(0, str(TASK_DIR))
    spec = importlib.util.spec_from_file_location(name, EVIDENCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_synthesis_evidence_round_trip_binds_segments_to_final_audio(tmp_path: Path) -> None:
    import numpy as np
    import soundfile as sf

    evidence = load_module("task9_synthesis_evidence")
    output = tmp_path / "audio.wav"
    segment_manifest = tmp_path / "segments.json"
    segment_manifest.write_text("{}", encoding="utf-8")
    waveforms = [np.asarray([0.1, 0.2], dtype=np.float32), np.asarray([0.3], dtype=np.float32)]
    sf.write(str(output), np.asarray([0.1, 0.2, 0.0, 0.3], dtype=np.float32), 10, format="WAV")
    source_segments = [
        {"segment_id": "001", "text_sha256": text_hash("甲"), "normalized_character_count": 1},
        {"segment_id": "002", "text_sha256": text_hash("乙"), "normalized_character_count": 1},
    ]

    manifest = evidence.write_synthesis_evidence(
        evidence_root=tmp_path / "evidence",
        model_id="demo",
        output_audio=output,
        segment_manifest=segment_manifest,
        segments=source_segments,
        waveforms=waveforms,
        sample_rate=10,
        pauses_ms=[100],
        first_segment_trimmed_samples=0,
        np=np,
        sf=sf,
    )
    loaded = evidence.load_verified_synthesis_evidence(
        evidence_root=tmp_path / "evidence",
        model_id="demo",
        output_audio=output,
        source_segment_manifest=segment_manifest,
        source_segments=source_segments,
    )

    assert manifest == loaded["manifest_path"]
    assert [item["segment_id"] for item in loaded["segments"]] == ["001", "002"]
    assert loaded["segments"][1]["start_frame"] == 3

    # 成品任何字节变化都必须使证据失效，防止对外部后处理后的 WAV 误用旧片段。
    output.write_bytes(output.read_bytes() + b"changed")
    with pytest.raises(FileNotFoundError, match="哈希绑定"):
        evidence.load_verified_synthesis_evidence(
            evidence_root=tmp_path / "evidence",
            model_id="demo",
            output_audio=output,
            source_segment_manifest=segment_manifest,
            source_segments=source_segments,
        )
