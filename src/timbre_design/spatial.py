"""High-value spatial audio scene taxonomy and placement defaults."""

from __future__ import annotations

from copy import deepcopy

from timbre_design.models import JsonDict, Voice

SPATIAL_SCENE_ORDER = (
    "asmr",
    "vehicle",
    "vr_ar",
    "theater",
    "battle",
    "adventure",
    "game",
)

SPATIAL_SCENE_KEYWORDS: dict[str, set[str]] = {
    "asmr": {"ASMR", "asmr", "近耳", "耳语", "低语", "私语", "助眠", "睡前"},
    "vehicle": {"车载", "座舱", "车机", "导航", "驾驶", "司机", "路况"},
    "vr_ar": {"VR", "vr", "AR", "ar", "头显", "虚拟现实", "增强现实", "空间引导"},
    "theater": {"沉浸式剧场", "剧场", "舞台", "群演", "现场"},
    "battle": {"战场", "无线电", "通讯", "战术", "火线", "battle", "radio"},
    "adventure": {"探险", "冒险", "野外", "洞穴", "追踪", "逃亡", "field"},
    "game": {"游戏", "互动", "任务", "关卡", "分支", "game"},
}

SPATIAL_SCENE_TAGS: dict[str, set[str]] = {
    "asmr": {"asmr", "bedtime", "near_ear", "binaural_close", "inner_monologue"},
    "vehicle": {
        "vehicle_cabin",
        "navigation",
        "route_prompt",
        "front_center",
        "driver",
        "roadside",
        "dispatch",
    },
    "vr_ar": {"vr", "ar", "headset", "interactive_guide", "spatial_anchor"},
    "theater": {"immersive_theater", "stage", "front_stage", "ceremony", "crowd", "side_stage"},
    "battle": {"battlefield", "radio", "war", "offscreen", "distance"},
    "adventure": {"adventure", "exploration", "outdoor", "moving_source"},
    "game": {"interactive_audio", "game", "mission", "choice_prompt"},
}

SPATIAL_ROLE_TAGS = frozenset(SPATIAL_SCENE_ORDER)

SPATIAL_PLACEMENT_PRESETS: dict[str, JsonDict] = {
    "asmr": {
        "mode": "binaural_close",
        "azimuth_deg": -25,
        "elevation_deg": 0,
        "distance_m": 0.18,
        "width": "narrow",
        "motion": "static",
    },
    "vehicle": {
        "mode": "cabin_front",
        "azimuth_deg": 0,
        "elevation_deg": 0,
        "distance_m": 1.0,
        "width": "narrow",
        "motion": "static",
    },
    "vr_ar": {
        "mode": "head_locked_ui",
        "azimuth_deg": 0,
        "elevation_deg": 8,
        "distance_m": 0.7,
        "width": "narrow",
        "motion": "head_locked",
    },
    "theater": {
        "mode": "stage_front",
        "azimuth_deg": 0,
        "elevation_deg": 0,
        "distance_m": 3.0,
        "width": "medium",
        "motion": "static",
    },
    "battle": {
        "mode": "offscreen_radio",
        "azimuth_deg": -55,
        "elevation_deg": 0,
        "distance_m": 7.0,
        "width": "narrow",
        "motion": "static",
    },
    "adventure": {
        "mode": "moving_companion",
        "azimuth_deg": 35,
        "elevation_deg": 0,
        "distance_m": 1.6,
        "width": "medium",
        "motion": "moving",
    },
    "game": {
        "mode": "center_prompt",
        "azimuth_deg": 0,
        "elevation_deg": 5,
        "distance_m": 0.9,
        "width": "narrow",
        "motion": "static",
    },
}


def voice_scene_tags(voice: Voice) -> set[str]:
    """Return normalized scene tags from a voice entry."""

    value = voice.style_tags.get("scene_tags", [])
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def scene_matches_voice(scene: str, voice: Voice) -> bool:
    """Check whether a spatial scene is explicitly covered by a voice."""

    tags = voice_scene_tags(voice)
    scene_tags = SPATIAL_SCENE_TAGS.get(scene, set())
    if tags & scene_tags:
        return True
    fit_text = " ".join(voice.fit_roles).lower()
    return scene.lower() in fit_text


def voice_primary_spatial_scene(voice: Voice) -> str | None:
    """Return the first high-value spatial scene covered by the voice."""

    if voice.group != "spatial":
        return None
    for scene in SPATIAL_SCENE_ORDER:
        if scene_matches_voice(scene, voice):
            return scene
    return None


def spatial_scene_score(scenes: set[str], voice: Voice) -> float:
    """Score how well a spatial voice covers requested high-value scenes."""

    requested = scenes & SPATIAL_ROLE_TAGS
    if voice.group != "spatial" or not requested:
        return 0.0
    matched = sum(1 for scene in requested if scene_matches_voice(scene, voice))
    return matched / len(requested)


def default_spatial_placement_for_voice(voice: Voice) -> JsonDict | None:
    """Return downstream placement hints for selected spatial voices."""

    scene = voice_primary_spatial_scene(voice)
    if scene is None:
        return None
    placement = deepcopy(SPATIAL_PLACEMENT_PRESETS[scene])
    tags = voice_scene_tags(voice)
    if scene == "asmr" and voice.profile.gender == "male":
        placement["azimuth_deg"] = 25
    if scene == "vehicle" and tags & {"driver", "roadside", "dispatch"}:
        placement["mode"] = "cabin_side"
        placement["azimuth_deg"] = -35
        placement["distance_m"] = 1.2
    if scene == "theater" and tags & {"side_stage", "crowd"}:
        placement["mode"] = "stage_side"
        placement["azimuth_deg"] = 45
        placement["distance_m"] = 2.2
    placement["scene"] = scene
    placement["source_mode"] = "dry_voice_stem"
    placement["post_process"] = "spatialize_after_tts"
    return placement
