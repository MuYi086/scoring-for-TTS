from __future__ import annotations

import json

from timbre_design.assets import write_voice_asset_bundle
from timbre_design.cli import main
from timbre_design.library import load_voice_library


def test_write_voice_asset_bundle_uses_one_directory_per_voice(tmp_path) -> None:
    voice = load_voice_library().get("v_zh_narr_001")

    bundle = write_voice_asset_bundle(voice, tmp_path, sample_text="试听文本。")

    assert bundle.directory == tmp_path / "v_zh_narr_001"
    assert bundle.paths.voice_json.is_file()
    assert bundle.paths.sample_text.read_text(encoding="utf-8") == "试听文本。\n"
    assert bundle.paths.prompt_text.is_file()
    assert bundle.paths.controls_json.is_file()
    assert bundle.paths.readme.is_file()

    voice_payload = json.loads(bundle.paths.voice_json.read_text(encoding="utf-8"))
    controls_payload = json.loads(bundle.paths.controls_json.read_text(encoding="utf-8"))
    readme = bundle.paths.readme.read_text(encoding="utf-8")

    assert voice_payload["voice_id"] == "v_zh_narr_001"
    assert controls_payload["style"] == "audiobook_narration"
    assert "sample.wav" in readme
    assert "sample.mp3" in readme
    assert "VoxCPM2 控制提示" in readme


def test_assets_cli_writes_selected_voice(tmp_path) -> None:
    main(
        [
            "assets",
            "--voice-id",
            "v_zh_narr_001",
            "--output-dir",
            str(tmp_path),
        ]
    )

    voice_dir = tmp_path / "v_zh_narr_001"
    assert (voice_dir / "voice.json").is_file()
    assert (voice_dir / "README.md").is_file()
