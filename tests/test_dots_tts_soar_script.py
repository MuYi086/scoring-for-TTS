"""dots.tts-soar 本地接入脚本的无模型单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "modelScript/tts_local_dots_tts_soar.py"


def load_script():
    spec = importlib.util.spec_from_file_location("dots_tts_soar_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_markdown_text_is_normalized_and_chunked_without_loss(tmp_path: Path) -> None:
    script = load_script()
    text_path = tmp_path / "text.md"
    text_path.write_text("# 标题\n第一句。\n第二句！", encoding="utf-8")

    text = script.read_text(text_path)
    chunks = script.split_text(text, 4)

    assert "#" not in text
    assert "标题" in "".join(chunks)
    assert "第一句。" in "".join(chunks)
    assert "第二句！" in "".join(chunks)
    assert all(len(chunk) <= 4 for chunk in chunks)


def test_prompt_text_file_takes_precedence(tmp_path: Path) -> None:
    script = load_script()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("参考音频的准确转写。", encoding="utf-8")
    args = argparse.Namespace(prompt_text_file=prompt_path, prompt_text="不应使用")

    assert script.read_prompt_text(args) == "参考音频的准确转写。"


def test_output_helpers_keep_mono_audio_and_insert_requested_pause() -> None:
    script = load_script()

    result = script.join_waveforms(
        [
            np.asarray([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
            np.asarray([0.5], dtype=np.float32),
        ],
        sample_rate=10,
        pause_ms=100,
        np=np,
    )

    assert np.allclose(result, [0.2, 0.3, 0.0, 0.5])


def test_sample_rate_label_uses_khz() -> None:
    script = load_script()

    assert script.khz_from_sample_rate(48000) == "48"
    assert script.elapsed_label(1.234) == "1.23s"
