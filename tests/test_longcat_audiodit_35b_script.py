"""LongCat-AudioDiT-3.5B 接入脚本的无模型单元测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "modelScript/tts_local_LongCat_AudioDit_3.5B_bf16.py"


def load_script():
    spec = importlib.util.spec_from_file_location("longcat_audiodit_35b_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_markdown_text_is_normalized_and_chunked_without_loss(tmp_path: Path) -> None:
    script = load_script()
    text_path = tmp_path / "text.md"
    text_path.write_text("# 标题\n第一句。\n- 第二句！", encoding="utf-8")
    text = script.normalize_text(script.read_text(text_path))

    chunks = script.split_text(text, 4)

    assert "标题" in "".join(chunks)
    assert "第一句。" in "".join(chunks)
    assert "第二句！" in "".join(chunks)
    assert all(len(chunk) <= 4 for chunk in chunks)


def test_duration_estimate_never_exceeds_60_second_model_limit() -> None:
    script = load_script()

    duration = script.estimate_duration_frames(
        gen_text="甲" * 1000,
        prompt_text="参考音频",
        prompt_frames=100,
        sample_rate=24000,
        full_hop=2048,
        max_duration=60.0,
        duration_scale=2.0,
        np=__import__("numpy"),
    )

    assert duration <= int(60 * 24000 // 2048)
    assert duration > 100


def test_output_helpers_keep_mono_audio_and_insert_requested_pause() -> None:
    script = load_script()
    import numpy as np

    result = script.join_waveforms(
        [np.asarray([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32), np.asarray([0.5], dtype=np.float32)],
        sample_rate=10,
        pause_ms=100,
        np=np,
    )

    assert np.allclose(result, [0.2, 0.3, 0.0, 0.5])


def test_default_dependency_repository_matches_task103_location() -> None:
    script = load_script()

    assert script.DEFAULT_REPO_CANDIDATES[0] == (
        Path.home() / "tts-depency/LongCat-AudioDiT"
    )
