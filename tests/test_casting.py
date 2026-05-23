from __future__ import annotations

import json

from timbre_design.casting import LOW_FREQUENCY_GROUPS, build_voice_casting
from timbre_design.library import load_voice_library
from timbre_design.matcher import CharacterProfile


def test_build_voice_casting_is_audio3d_compatible_payload() -> None:
    library = load_voice_library()
    characters = [
        CharacterProfile(
            character_id="char_001",
            display_name="主角",
            gender_group="female",
            age_group="young",
            appearance_count=50,
            dialogue_count=30,
            frequency_class="high_frequency",
            personality_summary="果断勇敢，情绪外放但有分寸。",
            voice_style_hint="声音明亮有穿透力，句尾利落。",
        )
    ]

    casting = build_voice_casting(characters, library)

    assert casting["provider"] == "voxcpm2-local"
    assert casting["narrator_voice_slot"] == "v_zh_narr_001"
    assert set(casting["low_frequency_groups"]) == set(LOW_FREQUENCY_GROUPS)
    assert casting["high_frequency_slots"]["char_001"].startswith("v_zh_")
    voice_id = casting["high_frequency_slots"]["char_001"]
    assert voice_id in casting["voice_descriptions"]
    assert "VoxCPM2 音色设计" in casting["voice_descriptions"][voice_id]
    allowed_emotions = {
        "neutral",
        "calm",
        "warm",
        "bright",
        "sad",
        "happy",
        "angry",
        "fearful",
        "tense",
        "whispering",
        "serious",
    }
    assert {
        controls["emotion"] for controls in casting["voice_controls"].values()
    } <= allowed_emotions
    json.dumps(casting, ensure_ascii=False)


def test_build_voice_casting_exports_spatial_placement_for_high_value_scene() -> None:
    library = load_voice_library()
    characters = [
        CharacterProfile(
            character_id="vehicle_guide",
            display_name="车载座舱导航",
            gender_group="neutral",
            age_group="adult",
            species="human",
            appearance_count=80,
            dialogue_count=40,
            frequency_class="high_frequency",
            voice_style_hint="车载座舱导航，前方定位，低疲劳。",
        )
    ]

    casting = build_voice_casting(characters, library)
    voice_id = casting["high_frequency_slots"]["vehicle_guide"]

    assert voice_id in casting["spatial_placements"]
    assert casting["spatial_placements"][voice_id]["scene"] == "vehicle"
    assert casting["spatial_placements"][voice_id]["source_mode"] == "dry_voice_stem"
