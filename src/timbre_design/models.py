"""Core data models for voice library entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

JsonDict: TypeAlias = dict[str, Any]


@dataclass(frozen=True)
class VoiceProfile:
    gender: str
    age_band: str
    species: str
    locale: str = "zh-CN"

    @classmethod
    def from_mapping(cls, data: JsonDict, *, locale: str = "zh-CN") -> "VoiceProfile":
        return cls(
            gender=str(data.get("gender", "neutral")),
            age_band=str(data.get("age_band", "ageless")),
            species=str(data.get("species", "human")),
            locale=str(data.get("locale", locale)),
        )

    def to_dict(self) -> JsonDict:
        return {
            "gender": self.gender,
            "age_band": self.age_band,
            "species": self.species,
            "locale": self.locale,
        }


@dataclass(frozen=True)
class Voice:
    voice_id: str
    group: str
    profile: VoiceProfile
    style_tags: JsonDict = field(default_factory=dict)
    fit_roles: tuple[str, ...] = ()
    constraints: JsonDict = field(default_factory=dict)
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: JsonDict, *, locale: str = "zh-CN") -> "Voice":
        voice_id = str(data.get("voice_id", "")).strip()
        if not voice_id:
            raise ValueError("voice_id 不能为空")
        group = str(data.get("group", "")).strip()
        if not group:
            raise ValueError(f"{voice_id} 缺少 group")
        profile_data = data.get("profile")
        if not isinstance(profile_data, dict):
            raise ValueError(f"{voice_id} 缺少 profile")
        fit_roles = data.get("fit_roles", [])
        if not isinstance(fit_roles, list):
            raise ValueError(f"{voice_id}.fit_roles 必须是数组")
        style_tags = data.get("style_tags", {})
        if not isinstance(style_tags, dict):
            raise ValueError(f"{voice_id}.style_tags 必须是对象")
        constraints = data.get("constraints", {})
        if not isinstance(constraints, dict):
            raise ValueError(f"{voice_id}.constraints 必须是对象")
        return cls(
            voice_id=voice_id,
            group=group,
            profile=VoiceProfile.from_mapping(profile_data, locale=locale),
            style_tags=style_tags,
            fit_roles=tuple(str(role) for role in fit_roles),
            constraints=constraints,
            raw=dict(data),
        )

    @property
    def timbre_tags(self) -> tuple[str, ...]:
        value = self.style_tags.get("timbre", [])
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        return ()

    @property
    def emotion_biases(self) -> tuple[str, ...]:
        value = self.style_tags.get("emotion_bias", [])
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        return ()

    @property
    def pace_default(self) -> str:
        return str(self.style_tags.get("pace_default", "medium"))

    @property
    def energy(self) -> str:
        return str(self.style_tags.get("energy", "medium"))

    def search_text(self) -> str:
        parts: list[str] = [
            self.voice_id,
            self.group,
            self.profile.gender,
            self.profile.age_band,
            self.profile.species,
            *_flatten_text(self.style_tags),
            *self.fit_roles,
            str(self.constraints.get("notes", "")),
        ]
        not_good_for = self.constraints.get("not_good_for", [])
        if isinstance(not_good_for, list):
            parts.extend(str(item) for item in not_good_for)
        return " ".join(part for part in parts if part)

    def to_dict(self) -> JsonDict:
        data = dict(self.raw)
        data["voice_id"] = self.voice_id
        data["group"] = self.group
        data["profile"] = self.profile.to_dict()
        data["style_tags"] = dict(self.style_tags)
        data["fit_roles"] = list(self.fit_roles)
        data["constraints"] = dict(self.constraints)
        return data


def _flatten_text(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(_flatten_text(item))
        return tuple(parts)
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.extend(_flatten_text(item))
        return tuple(parts)
    if value is None:
        return ()
    return (str(value),)


@dataclass(frozen=True)
class VoiceLibraryManifest:
    version: str
    locale: str
    total_voices: int
    naming_rule: str

    @classmethod
    def from_mapping(cls, data: JsonDict) -> "VoiceLibraryManifest":
        return cls(
            version=str(data.get("version", "0.0.0")),
            locale=str(data.get("locale", "zh-CN")),
            total_voices=int(data.get("total_voices", 0)),
            naming_rule=str(data.get("naming_rule", "")),
        )

    def to_dict(self) -> JsonDict:
        return {
            "version": self.version,
            "locale": self.locale,
            "total_voices": self.total_voices,
            "naming_rule": self.naming_rule,
        }
