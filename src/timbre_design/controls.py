"""Provider-neutral controls and VoxCPM2 prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from timbre_design.models import JsonDict, Voice
from timbre_design.spatial import default_spatial_placement_for_voice, voice_primary_spatial_scene


@dataclass(frozen=True)
class VoiceControls:
    speed: float = 1.0
    pitch_semitones: float = 0.0
    volume_gain_db: float = 0.0
    emotion: str = "neutral"
    emotion_intensity: float = 1.0
    style: str = "character_dialogue"
    style_degree: float = 1.0
    rhythm: str = "natural"
    pause_profile: str = "normal"
    stability: float = 0.88
    similarity_boost: float = 0.78
    style_exaggeration: float = 0.12
    use_speaker_boost: bool = True
    provider_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "speed": self.speed,
            "pitch_semitones": self.pitch_semitones,
            "volume_gain_db": self.volume_gain_db,
            "emotion": self.emotion,
            "emotion_intensity": self.emotion_intensity,
            "style": self.style,
            "style_degree": self.style_degree,
            "rhythm": self.rhythm,
            "pause_profile": self.pause_profile,
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style_exaggeration": self.style_exaggeration,
            "use_speaker_boost": self.use_speaker_boost,
            "provider_overrides": self.provider_overrides,
        }


EMOTION_LABELS_ZH = {
    "neutral": "中性",
    "calm": "平静",
    "warm": "温暖",
    "bright": "明亮",
    "happy": "愉悦",
    "sad": "悲伤",
    "angry": "愤怒",
    "fearful": "恐惧",
    "tense": "紧张",
    "whispering": "低声耳语",
    "serious": "严肃",
}

RHYTHM_LABELS_ZH = {
    "steady": "稳定均匀",
    "natural": "自然口语",
    "expressive": "表现力更强",
    "dramatic": "戏剧化",
}

PAUSE_LABELS_ZH = {
    "compact": "紧凑停顿",
    "normal": "自然停顿",
    "long_form": "长篇听书停顿",
    "dramatic": "戏剧化停顿",
}

STYLE_LABELS_ZH = {
    "audiobook_narration": "有声书旁白",
    "character_dialogue": "角色对白",
    "supporting_dialogue": "配角对白",
    "system_voice": "系统提示音",
    "special_effect_voice": "特殊效果角色音",
}

PACE_SPEED = {
    "slow": 0.88,
    "medium_slow": 0.94,
    "slow_medium": 0.94,
    "medium": 1.0,
    "fast_medium": 1.04,
    "medium_fast": 1.04,
    "fast": 1.08,
}

EMOTION_MAP = {
    "calm": "calm",
    "kind": "warm",
    "gentle": "warm",
    "warm": "warm",
    "bright": "bright",
    "energetic": "bright",
    "lively": "happy",
    "cheerful": "happy",
    "playful": "happy",
    "serious": "serious",
    "authoritative": "serious",
    "strict": "serious",
    "severe": "serious",
    "cold": "serious",
    "mysterious": "tense",
    "suspense": "tense",
    "eerie": "tense",
    "threatening": "tense",
    "ominous": "tense",
    "intimate": "whispering",
    "soothing": "calm",
    "guiding": "calm",
    "focused": "serious",
    "immersive": "serious",
    "alert": "tense",
    "urgent": "tense",
    "tactical": "tense",
    "brisk": "bright",
    "weak": "sad",
    "fragile": "sad",
}


def default_controls_for_voice(voice: Voice) -> VoiceControls:
    speed = PACE_SPEED.get(voice.pace_default, 1.0)
    pitch = _default_pitch(voice)
    emotion = _default_emotion(voice)
    style = _default_style(voice)
    rhythm = "steady" if speed < 0.96 else "natural"
    pause = "long_form" if voice.group == "narrator" or speed < 0.92 else "normal"
    stability = 0.92 if voice.group == "narrator" else 0.86
    exaggeration = 0.08 if voice.group == "narrator" else 0.14
    if voice.profile.species in {"robot", "human_fx"}:
        style = "system_voice"
        rhythm = "steady"
    elif voice.group == "special":
        style = "special_effect_voice"
        rhythm = "dramatic"
    if voice.group == "spatial":
        style, rhythm, pause, stability, exaggeration = _spatial_control_defaults(voice)
    if voice.profile.species not in {"human", "human_fx"} and voice.group != "spatial":
        exaggeration = 0.18
    return VoiceControls(
        speed=speed,
        pitch_semitones=pitch,
        emotion=emotion,
        emotion_intensity=0.55 if voice.group == "narrator" else 0.75,
        style=style,
        rhythm=rhythm,
        pause_profile=pause,
        stability=stability,
        similarity_boost=0.8,
        style_exaggeration=exaggeration,
    )


def _spatial_control_defaults(voice: Voice) -> tuple[str, str, str, float, float]:
    scene = voice_primary_spatial_scene(voice)
    if scene == "asmr":
        return "character_dialogue", "steady", "long_form", 0.9, 0.06
    if scene in {"vehicle", "vr_ar", "game"}:
        return "system_voice", "steady", "compact", 0.9, 0.08
    if scene == "theater":
        return "supporting_dialogue", "dramatic", "dramatic", 0.86, 0.13
    if scene == "battle":
        return "special_effect_voice", "dramatic", "compact", 0.84, 0.18
    if scene == "adventure":
        return "supporting_dialogue", "natural", "normal", 0.86, 0.12
    return "special_effect_voice", "dramatic", "normal", 0.86, 0.14


def render_voxcpm2_prompt(
    voice: Voice,
    controls: VoiceControls | None = None,
    *,
    extra_context: str = "",
) -> str:
    controls = controls or default_controls_for_voice(voice)
    profile = voice.profile
    timbre = "、".join(voice.timbre_tags) or "自然清晰"
    emotion = "、".join(voice.emotion_biases) or "中性"
    roles = "、".join(voice.fit_roles) or "通用角色"
    notes = str(voice.constraints.get("notes", "")).strip()
    not_good_for = voice.constraints.get("not_good_for", [])
    if isinstance(not_good_for, list) and not_good_for:
        constraints = "避免用于：" + "、".join(str(item) for item in not_good_for) + "。"
    else:
        constraints = ""
    context_part = f"角色上下文：{extra_context.strip()} " if extra_context.strip() else ""
    parts = [
        f"VoxCPM2 音色设计，voice_id={voice.voice_id}。",
        (
            f"基础定位：{profile.locale}，{profile.gender}，{profile.age_band}，"
            f"{profile.species}，分组 {voice.group}。"
        ),
        f"声音质感：{timbre}；默认语气：{emotion}；适配角色：{roles}。",
        context_part + "要求普通话发音清晰，近场干净录音，无背景音乐，无明显房间混响。",
        _render_spatial_source_sentence(voice),
        _render_control_sentence(controls),
    ]
    if constraints:
        parts.append(constraints)
    if notes:
        parts.append(f"禁忌说明：{notes}")
    parts.append("同一 voice_id 在整本书中保持音色稳定，避免漂移。")
    return " ".join(part for part in parts if part)


def _render_spatial_source_sentence(voice: Voice) -> str:
    placement = default_spatial_placement_for_voice(voice)
    if placement is None:
        return ""
    return (
        "空间音频源要求：只合成干净人声干声，不把声像、距离、移动、混响、无线电"
        "或车厢空间感烘焙进 TTS；这些由后处理完成。"
        f"建议场景={placement['scene']}，mode={placement['mode']}，"
        f"azimuth={placement['azimuth_deg']}deg，distance={placement['distance_m']}m。"
    )


def _render_control_sentence(controls: VoiceControls) -> str:
    style = STYLE_LABELS_ZH.get(controls.style, controls.style.replace("_", " "))
    emotion = EMOTION_LABELS_ZH.get(controls.emotion, controls.emotion)
    rhythm = RHYTHM_LABELS_ZH.get(controls.rhythm, controls.rhythm)
    pause = PAUSE_LABELS_ZH.get(controls.pause_profile, controls.pause_profile)
    parts = [
        "结构化语音控制："
        f"语速约 {controls.speed:.2f}x；"
        f"情绪/语气为{emotion}，强度 {controls.emotion_intensity:.1f}/2；"
        f"表达风格{style}，风格强度 {controls.style_degree:.1f}/2；"
        f"节奏{rhythm}；停顿采用{pause}。"
    ]
    if controls.pitch_semitones:
        direction = "提高" if controls.pitch_semitones > 0 else "降低"
        parts.append(f"音高相对默认{direction}约 {abs(controls.pitch_semitones):.1f} 个半音。")
    if controls.volume_gain_db:
        direction = "提高" if controls.volume_gain_db > 0 else "降低"
        parts.append(f"音量相对默认{direction}约 {abs(controls.volume_gain_db):.1f} dB。")
    parts.append(
        f"长文本一致性目标 {controls.stability:.2f}，"
        f"音色相似度目标 {controls.similarity_boost:.2f}，"
        f"风格夸张度 {controls.style_exaggeration:.2f}。"
    )
    return " ".join(parts)


def _default_pitch(voice: Voice) -> float:
    gender = voice.profile.gender
    age = voice.profile.age_band
    species = voice.profile.species
    timbre_text = " ".join(voice.timbre_tags)
    if species == "creature" and any(tag in timbre_text for tag in ("thick", "low_monster")):
        return -2.0
    if species == "robot":
        return -0.3 if gender == "male_coded" else 0.0
    if age in {"child", "teen"}:
        return 2.0 if gender in {"female", "neutral"} else 1.5
    if age == "senior":
        return -0.7
    if gender == "female":
        return 0.5
    if gender in {"male", "male_coded"} and ("low" in timbre_text or age == "middle_aged"):
        return -0.6
    return 0.0


def _default_emotion(voice: Voice) -> str:
    for bias in voice.emotion_biases:
        mapped = EMOTION_MAP.get(bias)
        if mapped:
            return mapped
    if voice.group == "narrator":
        return "calm"
    if voice.profile.species in {"spirit", "creature", "nonhuman"}:
        return "tense"
    return "neutral"


def _default_style(voice: Voice) -> str:
    if voice.group == "narrator" or any("narrator" in role for role in voice.fit_roles):
        return "audiobook_narration"
    if voice.group == "functional":
        return "supporting_dialogue"
    return "character_dialogue"
