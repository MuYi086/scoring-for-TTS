"""task103 Stable Audio 3 Small-SFX 本地接入脚本的轻量单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO_ROOT / "modelScript/tts_local_stable_audio_3_small_sfx.py"
    spec = importlib.util.spec_from_file_location("task103_stable_audio", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_prompt_file_removes_markdown_markers(tmp_path):
    module = load_module()
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("# 音效\n\n- train horn\n- station ambience\n", encoding="utf-8")

    assert module.read_prompt_file(prompt_file) == "音效\n\ntrain horn\nstation ambience"


def test_require_model_path_reports_missing_files(tmp_path):
    module = load_module()
    model_path = tmp_path / "model"
    model_path.mkdir()

    with pytest.raises(FileNotFoundError, match="model_config.json"):
        module.require_model_path(model_path)


def test_patch_local_text_encoder_path_uses_local_subdirectory(tmp_path):
    module = load_module()
    config = {
        "model": {
            "conditioning": {
                "configs": [
                    {
                        "id": "prompt",
                        "config": {
                            "repo_id": "stabilityai/stable-audio-3-small-sfx",
                            "subfolder": "t5gemma-b-b-ul2",
                        },
                    }
                ]
            }
        }
    }

    patched = module.patch_local_text_encoder_path(config, tmp_path)
    prompt_config = patched["model"]["conditioning"]["configs"][0]["config"]

    assert prompt_config["model_path"] == str((tmp_path / "t5gemma-b-b-ul2").resolve())
    assert "repo_id" not in prompt_config
    assert "subfolder" not in prompt_config
    assert config["model"]["conditioning"]["configs"][0]["config"]["repo_id"]


def test_validate_args_rejects_conflicting_prompt_sources():
    module = load_module()
    args = argparse.Namespace(
        prompt="train",
        prompt_file=Path("prompt.txt"),
        duration=7.0,
        steps=8,
        cfg_scale=1.0,
    )

    with pytest.raises(ValueError, match="cannot be used together"):
        module.validate_args(args)
