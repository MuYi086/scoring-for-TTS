from __future__ import annotations

from timbre_design.controls import default_controls_for_voice, render_voxcpm2_prompt
from timbre_design.library import load_voice_library


def test_render_voxcpm2_prompt_contains_voice_metadata() -> None:
    voice = load_voice_library().get("v_zh_narr_001")

    prompt = render_voxcpm2_prompt(voice)

    assert "VoxCPM2 音色设计" in prompt
    assert "voice_id=v_zh_narr_001" in prompt
    assert "结构化语音控制" in prompt
    assert "同一 voice_id 在整本书中保持音色稳定" in prompt


def test_default_controls_derive_narrator_style() -> None:
    voice = load_voice_library().get("v_zh_narr_003")

    controls = default_controls_for_voice(voice)

    assert controls.style == "audiobook_narration"
    assert controls.speed < 1.0
    assert controls.pause_profile == "long_form"


def test_spatial_prompt_keeps_tts_as_dry_source() -> None:
    voice = load_voice_library().get("v_zh_spatial_099")

    prompt = render_voxcpm2_prompt(voice)
    controls = default_controls_for_voice(voice)

    assert "空间音频源要求" in prompt
    assert "spatialize_after_tts" not in prompt
    assert controls.style == "system_voice"
    assert controls.pause_profile == "compact"
