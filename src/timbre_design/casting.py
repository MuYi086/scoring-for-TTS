"""Build audio-3d-sdd compatible voice-casting payloads."""

from __future__ import annotations

from timbre_design.controls import default_controls_for_voice, render_voxcpm2_prompt
from timbre_design.library import VoiceLibrary
from timbre_design.matcher import CharacterProfile, match_voice
from timbre_design.models import JsonDict, Voice
from timbre_design.spatial import default_spatial_placement_for_voice

LOW_FREQUENCY_GROUPS = (
    "青年男",
    "中年男",
    "老年男",
    "青年女",
    "中年女",
    "老年女",
    "儿童",
    "群像",
)

LOW_GROUP_CHARACTERS = {
    "青年男": CharacterProfile("group_young_male", "低频青年男", "male", "young", "human"),
    "中年男": CharacterProfile("group_middle_male", "低频中年男", "male", "middle", "human"),
    "老年男": CharacterProfile("group_old_male", "低频老年男", "male", "old", "human"),
    "青年女": CharacterProfile("group_young_female", "低频青年女", "female", "young", "human"),
    "中年女": CharacterProfile("group_middle_female", "低频中年女", "female", "middle", "human"),
    "老年女": CharacterProfile("group_old_female", "低频老年女", "female", "old", "human"),
    "儿童": CharacterProfile("group_child", "低频儿童", "neutral", "child", "human"),
    "群像": CharacterProfile("group_crowd", "低频群像", "neutral", "unknown", "human"),
}


def build_voice_casting(
    characters: list[CharacterProfile],
    library: VoiceLibrary,
    *,
    provider: str = "voxcpm2-local",
    dedicated_limit: int = 12,
    min_score: float = 0.45,
) -> JsonDict:
    used: set[str] = set()
    degradation_notes: list[str] = []

    narrator = _pick_fixed_or_match(
        library,
        preferred_id="v_zh_narr_001",
        character=CharacterProfile("narrator", "旁白", "neutral", "adult", "human", ("narrator",)),
        used=used,
    )
    used.add(narrator.voice_id)

    low_frequency_groups: dict[str, str] = {}
    selected_voices: dict[str, Voice] = {narrator.voice_id: narrator}
    for group in LOW_FREQUENCY_GROUPS:
        result = match_voice(LOW_GROUP_CHARACTERS[group], library, exclude_voice_ids=used, top_k=1)
        voice = result[0].voice if result else narrator
        low_frequency_groups[group] = voice.voice_id
        selected_voices[voice.voice_id] = voice
        used.add(voice.voice_id)

    high_frequency_slots: dict[str, str] = {}
    high_frequency = _dedicated_characters(characters)
    for character in high_frequency[:dedicated_limit]:
        result = match_voice(character, library, exclude_voice_ids=used, top_k=1)
        if not result:
            degradation_notes.append(f"{character.display_name} 未找到可用独立音色，降级为低频分组。")
            continue
        match = result[0]
        if match.score < min_score:
            degradation_notes.append(
                f"{character.display_name} 独立音色匹配置信度偏低："
                f"{match.voice.voice_id} score={match.score:.2f}。"
            )
        high_frequency_slots[character.character_id] = match.voice.voice_id
        selected_voices[match.voice.voice_id] = match.voice
        used.add(match.voice.voice_id)
    for character in high_frequency[dedicated_limit:]:
        degradation_notes.append(
            f"{character.display_name} 超过独立音色上限 {dedicated_limit}，降级为低频分组。"
        )

    fallback_slots = {
        "未识别男声": low_frequency_groups["青年男"],
        "未识别女声": low_frequency_groups["青年女"],
        "旁白": narrator.voice_id,
    }
    voice_descriptions = {
        voice_id: render_voxcpm2_prompt(voice)
        for voice_id, voice in sorted(selected_voices.items())
    }
    voice_controls = {
        voice_id: default_controls_for_voice(voice).to_dict()
        for voice_id, voice in sorted(selected_voices.items())
    }
    spatial_placements: dict[str, JsonDict] = {}
    for voice_id, voice in sorted(selected_voices.items()):
        placement = default_spatial_placement_for_voice(voice)
        if placement is not None:
            spatial_placements[voice_id] = placement
    return {
        "schema_version": "1.3-timbre-design",
        "provider": provider,
        "narrator_voice_slot": narrator.voice_id,
        "high_frequency_slots": high_frequency_slots,
        "low_frequency_groups": low_frequency_groups,
        "fallback_slots": fallback_slots,
        "voice_descriptions": voice_descriptions,
        "voice_controls": voice_controls,
        "spatial_placements": spatial_placements,
        "provider_voice_ids": {voice_id: voice_id for voice_id in sorted(selected_voices)},
        "degradation_notes": degradation_notes,
    }


def low_frequency_group(gender_group: str, age_group: str) -> str:
    if age_group in {"child", "teen", "儿童", "少年", "少女"}:
        return "儿童"
    if gender_group in {"male", "男", "男性"}:
        if age_group in {"old", "senior", "老年"}:
            return "老年男"
        if age_group in {"middle", "middle_aged", "中年"}:
            return "中年男"
        return "青年男"
    if gender_group in {"female", "女", "女性"}:
        if age_group in {"old", "senior", "老年"}:
            return "老年女"
        if age_group in {"middle", "middle_aged", "中年"}:
            return "中年女"
        return "青年女"
    return "群像"


def fallback_speaker_slot(
    confidence: float,
    gender_hint: str | None,
    threshold: float = 0.6,
) -> str | None:
    if confidence >= threshold:
        return None
    if gender_hint == "male":
        return "未识别男声"
    if gender_hint == "female":
        return "未识别女声"
    return "旁白"


def _dedicated_characters(characters: list[CharacterProfile]) -> list[CharacterProfile]:
    candidates = [
        character
        for character in characters
        if character.frequency_class == "high_frequency"
        or character.dialogue_count >= 20
        or character.appearance_count >= 30
    ]
    return sorted(
        candidates,
        key=lambda character: (
            -character.appearance_count,
            -character.dialogue_count,
            character.character_id,
        ),
    )


def _pick_fixed_or_match(
    library: VoiceLibrary,
    *,
    preferred_id: str,
    character: CharacterProfile,
    used: set[str],
) -> Voice:
    try:
        voice = library.get(preferred_id)
        if preferred_id not in used:
            return voice
    except KeyError:
        pass
    result = match_voice(character, library, exclude_voice_ids=used, top_k=1)
    if not result:
        raise ValueError(f"无法为 {character.display_name} 匹配音色")
    return result[0].voice
