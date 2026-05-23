from __future__ import annotations

from timbre_design.library import load_voice_library
from timbre_design.spatial import SPATIAL_ROLE_TAGS, voice_primary_spatial_scene


def test_bundled_library_validates() -> None:
    library = load_voice_library()

    assert library.validate() == []
    assert library.summary()["total_voices"] == 106
    assert library.get("v_zh_narr_001").profile.gender == "male"


def test_search_finds_robot_voice() -> None:
    library = load_voice_library()

    results = library.search("robot service", limit=3)

    assert results
    assert any(voice.profile.species == "robot" for voice in results)


def test_spatial_group_covers_vehicle_and_asmr_search_terms() -> None:
    library = load_voice_library()

    spatial_voices = library.filter(group="spatial")
    vehicle_results = library.search("车载 座舱 导航", limit=5)
    asmr_results = library.search("ASMR 近耳 助眠", limit=5)

    assert len(spatial_voices) == 10
    assert any("vehicle_cabin_host_female" in voice.fit_roles for voice in vehicle_results)
    assert any("asmr_close_whisper_female" in voice.fit_roles for voice in asmr_results)


def test_spatial_group_covers_only_high_value_scene_taxonomy() -> None:
    library = load_voice_library()
    spatial_voices = library.filter(group="spatial")

    covered = {voice_primary_spatial_scene(voice) for voice in spatial_voices}

    assert None not in covered
    assert covered == set(SPATIAL_ROLE_TAGS)
