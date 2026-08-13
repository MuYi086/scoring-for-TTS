"""task103 Stable Audio 3 Medium 本地接入脚本的轻量单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO_ROOT / "modelScript/tts_local_stable_audio_3_medium.py"
    spec = importlib.util.spec_from_file_location("task103_stable_audio_medium", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StableAudio3MediumLocalScriptTests(unittest.TestCase):
    def test_read_prompt_file_removes_markdown_markers(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            prompt_file = Path(directory) / "prompt.md"
            prompt_file.write_text("# 音效\n\n- train horn\n- station ambience\n", encoding="utf-8")
            self.assertEqual(
                module.read_prompt_file(prompt_file),
                "音效\n\ntrain horn\nstation ambience",
            )

    def test_require_model_path_reports_missing_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model"
            model_path.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "model_config.json"):
                module.require_model_path(model_path)

    def test_patch_local_text_encoder_path_uses_local_subdirectory(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory)
            config = {
                "model": {
                    "conditioning": {
                        "configs": [
                            {
                                "id": "prompt",
                                "config": {
                                    "repo_id": "stabilityai/stable-audio-3-medium",
                                    "subfolder": "t5gemma-b-b-ul2",
                                },
                            }
                        ]
                    }
                }
            }

            patched = module.patch_local_text_encoder_path(config, model_path)
            prompt_config = patched["model"]["conditioning"]["configs"][0]["config"]

            self.assertEqual(
                prompt_config["model_path"],
                str((model_path / "t5gemma-b-b-ul2").resolve()),
            )
            self.assertNotIn("repo_id", prompt_config)
            self.assertNotIn("subfolder", prompt_config)
            self.assertIn(
                "repo_id",
                config["model"]["conditioning"]["configs"][0]["config"],
            )

    def test_validate_args_rejects_conflicting_prompt_sources(self):
        module = load_module()
        args = argparse.Namespace(
            prompt="train",
            prompt_file=Path("prompt.txt"),
            duration=7.0,
            steps=8,
            cfg_scale=1.0,
        )

        with self.assertRaisesRegex(ValueError, "cannot be used together"):
            module.validate_args(args)
