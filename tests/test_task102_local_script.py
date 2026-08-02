"""task102 本地 MOSS-Audio 接入脚本的轻量单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO_ROOT / "modelScript/tts_local_moss_audio_4b_thinking.py"
    spec = importlib.util.spec_from_file_location("task102_moss_audio", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strip_thinking_keeps_final_answer():
    module = load_module()
    assert module.strip_thinking("<think>内部推理</think>\n最终答案") == "最终答案"
    assert module.strip_thinking("没有推理标签") == "没有推理标签"


def test_build_generation_kwargs_is_deterministic_by_default():
    module = load_module()
    args = argparse.Namespace(
        max_new_tokens=128,
        do_sample=False,
        temperature=1.0,
        top_p=1.0,
        top_k=50,
    )
    assert module.build_generation_kwargs(args) == {
        "max_new_tokens": 128,
        "num_beams": 1,
        "use_cache": True,
        "do_sample": False,
    }


def test_require_path_reports_missing_directory(tmp_path):
    module = load_module()
    with pytest.raises(FileNotFoundError, match="依赖源码目录不存在"):
        module.require_path(tmp_path / "missing", "依赖源码", directory=True)
