"""Voice library loading, validation, and lookup."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from timbre_design.models import JsonDict, Voice, VoiceLibraryManifest
from timbre_design.spatial import SPATIAL_ROLE_TAGS, voice_primary_spatial_scene

BUNDLED_LIBRARY = "voices_v2_106.json"


class VoiceLibrary:
    """In-memory voice library with deterministic validation and lookup."""

    def __init__(self, manifest: VoiceLibraryManifest, voices: Iterable[Voice]) -> None:
        self.manifest = manifest
        self.voices = list(voices)
        self._by_id = {voice.voice_id: voice for voice in self.voices}

    @classmethod
    def from_mapping(cls, data: JsonDict) -> "VoiceLibrary":
        manifest = VoiceLibraryManifest.from_mapping(data)
        voices_data = data.get("voices", [])
        if not isinstance(voices_data, list):
            raise ValueError("voices 必须是数组")
        voices = [Voice.from_mapping(item, locale=manifest.locale) for item in voices_data]
        return cls(manifest=manifest, voices=voices)

    @classmethod
    def from_path(cls, path: Path) -> "VoiceLibrary":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("音色库根节点必须是对象")
        return cls.from_mapping(data)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.manifest.total_voices != len(self.voices):
            errors.append(
                f"total_voices={self.manifest.total_voices} 与实际数量 {len(self.voices)} 不一致"
            )
        seen: set[str] = set()
        for voice in self.voices:
            if voice.voice_id in seen:
                errors.append(f"voice_id 重复：{voice.voice_id}")
            seen.add(voice.voice_id)
            if not voice.voice_id.startswith("v_zh_"):
                errors.append(f"voice_id 不符合 v_zh_ 前缀：{voice.voice_id}")
            if not voice.fit_roles:
                errors.append(f"{voice.voice_id} 缺少 fit_roles")
            if not voice.timbre_tags:
                errors.append(f"{voice.voice_id} 缺少 style_tags.timbre")
        spatial_voices = [voice for voice in self.voices if voice.group == "spatial"]
        if spatial_voices:
            covered = {
                scene
                for voice in spatial_voices
                if (scene := voice_primary_spatial_scene(voice)) is not None
            }
            invalid = [
                voice.voice_id
                for voice in spatial_voices
                if voice_primary_spatial_scene(voice) is None
            ]
            if invalid:
                errors.append("spatial 音色缺少高价值场景标签：" + "、".join(invalid))
            missing = sorted(SPATIAL_ROLE_TAGS - covered)
            if missing:
                errors.append("spatial 音色未覆盖高价值场景：" + "、".join(missing))
        return errors

    def require_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise ValueError("音色库校验失败：\n" + "\n".join(f"- {error}" for error in errors))

    def get(self, voice_id: str) -> Voice:
        try:
            return self._by_id[voice_id]
        except KeyError as exc:
            raise KeyError(f"未知 voice_id：{voice_id}") from exc

    def filter(
        self,
        *,
        group: str | None = None,
        species: str | None = None,
        gender: str | None = None,
    ) -> list[Voice]:
        voices = self.voices
        if group:
            voices = [voice for voice in voices if voice.group == group]
        if species:
            voices = [voice for voice in voices if voice.profile.species == species]
        if gender:
            voices = [voice for voice in voices if voice.profile.gender == gender]
        return voices

    def search(self, query: str, *, limit: int = 10) -> list[Voice]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return self.voices[:limit]

        def score(voice: Voice) -> tuple[int, str]:
            text = voice.search_text().lower()
            return (sum(1 for term in terms if term in text), voice.voice_id)

        ranked = sorted(self.voices, key=score, reverse=True)
        return [voice for voice in ranked if score(voice)[0] > 0][:limit]

    def summary(self) -> JsonDict:
        groups: dict[str, int] = {}
        species: dict[str, int] = {}
        for voice in self.voices:
            groups[voice.group] = groups.get(voice.group, 0) + 1
            species[voice.profile.species] = species.get(voice.profile.species, 0) + 1
        return {
            "version": self.manifest.version,
            "locale": self.manifest.locale,
            "total_voices": len(self.voices),
            "groups": dict(sorted(groups.items())),
            "species": dict(sorted(species.items())),
        }

    def to_dict(self) -> JsonDict:
        data = self.manifest.to_dict()
        data["voices"] = [voice.to_dict() for voice in self.voices]
        return data


def bundled_library_path() -> Path:
    return Path(str(files("timbre_design.data").joinpath(BUNDLED_LIBRARY)))


def load_voice_library(path: str | Path | None = None) -> VoiceLibrary:
    library_path = Path(path) if path else bundled_library_path()
    return VoiceLibrary.from_path(library_path)
