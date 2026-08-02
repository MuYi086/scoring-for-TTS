"""task101 本地接入脚本的轻量单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qwen_voice_design_direct_text_and_chunking():
    module = load_module("task101_qwen", "modelScript/tts_local_qwen3_voiceDesign.py")
    assert module.read_text(Path("/does/not/exist"), "直接文本") == "直接文本"
    chunks = module.split_text("第一句。第二句。第三句。", 5)
    assert len(chunks) >= 2
    assert "第一句。" in chunks


def test_moss_voice_generator_direct_text_and_chunking():
    module = load_module("task101_moss", "modelScript/tts_local_moss_voiceGenerator.py")
    assert module.read_text(Path("/does/not/exist"), "MOSS 文本") == "MOSS 文本"
    assert module.split_text("甲。乙。丙。", 2) == ["甲。", "乙。", "丙。"]


def test_higgs_client_reads_direct_text_and_file(tmp_path):
    module = load_module("task101_higgs", "modelScript/tts_local_higgs_audio_v3_tts_4b.py")
    text_file = tmp_path / "text.md"
    text_file.write_text("文件文本", encoding="utf-8")
    args = argparse.Namespace(text=None, text_file=text_file)
    assert module.read_input_text(args) == "文件文本"
    args.text = "直接文本"
    assert module.read_input_text(args) == "直接文本"


def test_step_code_preflight_has_actionable_error(tmp_path):
    module = load_module("task101_step", "modelScript/tts_local_Step_Audio_EditX.py")
    with pytest.raises(FileNotFoundError, match="源码目录不存在"):
        module.load_upstream(tmp_path / "missing")


def test_ming_instruction_serializes_voice_controls():
    module = load_module("task101_ming", "modelScript/tts_local_Ming_omni_tts.py")
    args = argparse.Namespace(
        instruction_json=None,
        style="轻柔耳语",
        emotion="平静",
        dialect=None,
        speed=None,
        pitch=None,
        volume=None,
    )
    instruction = module.build_instruction(args)
    assert instruction is not None
    assert "轻柔耳语" in instruction
    assert "平静" in instruction
