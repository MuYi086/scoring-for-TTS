from __future__ import annotations

from timbre_design.library import load_voice_library
from timbre_design.matcher import CharacterProfile, match_voice


def test_match_young_female_character_prefers_human_female() -> None:
    library = load_voice_library()
    character = CharacterProfile(
        character_id="char_001",
        display_name="女主角",
        gender_group="female",
        age_group="young",
        personality_summary="清冷、聪慧、敏感",
        voice_style_hint="清晰、略冷、诗性",
        frequency_class="high_frequency",
    )

    result = match_voice(character, library, top_k=1)[0]

    assert result.voice.profile.gender == "female"
    assert result.voice.profile.species == "human"
    assert result.score > 0.5


def test_match_robot_character_prefers_robot_voice() -> None:
    library = load_voice_library()
    character = CharacterProfile(
        character_id="ai",
        display_name="中控AI",
        gender_group="neutral",
        age_group="ageless",
        species="robot",
        voice_style_hint="高智能 AI，冷静清晰，系统提示",
        frequency_class="high_frequency",
    )

    result = match_voice(character, library, top_k=1)[0]

    assert result.voice.profile.species == "robot"


def test_match_vehicle_scene_prefers_spatial_voice() -> None:
    library = load_voice_library()
    character = CharacterProfile(
        character_id="vehicle_guide",
        display_name="车载座舱导航",
        gender_group="neutral",
        age_group="adult",
        species="human",
        voice_style_hint="车载座舱导航，低疲劳、清晰、前方定位",
        frequency_class="high_frequency",
    )

    result = match_voice(character, library, top_k=1)[0]

    assert result.voice.group == "spatial"
    assert any("vehicle" in role for role in result.voice.fit_roles)


def test_match_generic_character_does_not_use_spatial_voice() -> None:
    library = load_voice_library()
    character = CharacterProfile(
        character_id="char_generic",
        display_name="普通青年",
        gender_group="male",
        age_group="young",
        species="human",
        voice_style_hint="自然、清晰、适合普通对白",
        frequency_class="high_frequency",
    )

    result = match_voice(character, library, top_k=1)[0]

    assert result.voice.group != "spatial"


def test_match_vr_scene_can_use_spatial_robot_even_with_human_default() -> None:
    library = load_voice_library()
    character = CharacterProfile(
        character_id="vr_guide",
        display_name="头显空间引导",
        gender_group="neutral",
        age_group="unknown",
        species="human",
        voice_style_hint="VR 头显空间引导，短句、清晰、方向提示",
        frequency_class="high_frequency",
    )

    result = match_voice(character, library, top_k=1)[0]

    assert result.voice.voice_id == "v_zh_spatial_101"
    assert "spatial_scene" in result.reasons
