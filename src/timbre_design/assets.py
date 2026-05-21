"""Voice asset directory generation."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from timbre_design.controls import VoiceControls, default_controls_for_voice, render_voxcpm2_prompt
from timbre_design.models import JsonDict, Voice
from timbre_design.voxcpm import synthesize_with_voxcpm2

DEFAULT_ASSET_ROOT = Path("samples/generated")
DEFAULT_SAMPLE_TEXT = (
    "这是一个用于锁定音色的试听片段。请保持普通话清晰自然，情绪稳定，"
    "并在长文本中保持同一 voice_id 的声音一致。"
)


@dataclass(frozen=True)
class VoiceAssetPaths:
    """Conventional files for one voice asset directory."""

    root: Path
    voice_id: str

    @property
    def directory(self) -> Path:
        return self.root / self.voice_id

    @property
    def voice_json(self) -> Path:
        return self.directory / "voice.json"

    @property
    def readme(self) -> Path:
        return self.directory / "README.md"

    @property
    def sample_text(self) -> Path:
        return self.directory / "sample.txt"

    @property
    def prompt_text(self) -> Path:
        return self.directory / "sample.voice.txt"

    @property
    def controls_json(self) -> Path:
        return self.directory / "sample.controls.json"

    @property
    def wav(self) -> Path:
        return self.directory / "sample.wav"

    @property
    def mp3(self) -> Path:
        return self.directory / "sample.mp3"

    def metadata_files(self) -> tuple[Path, ...]:
        return (
            self.voice_json,
            self.readme,
            self.sample_text,
            self.prompt_text,
            self.controls_json,
        )


@dataclass(frozen=True)
class VoiceAssetBundle:
    voice_id: str
    paths: VoiceAssetPaths
    files: tuple[Path, ...]

    @property
    def directory(self) -> Path:
        return self.paths.directory

    def to_dict(self) -> JsonDict:
        return {
            "voice_id": self.voice_id,
            "directory": str(self.directory),
            "files": [str(path) for path in self.files],
        }


def voice_asset_paths(root: str | Path, voice_id: str) -> VoiceAssetPaths:
    _validate_voice_id_for_path(voice_id)
    return VoiceAssetPaths(root=Path(root), voice_id=voice_id)


def write_voice_asset_bundle(
    voice: Voice,
    root: str | Path = DEFAULT_ASSET_ROOT,
    *,
    sample_text: str | None = None,
    controls: VoiceControls | None = None,
    overwrite: bool = True,
) -> VoiceAssetBundle:
    """Write deterministic metadata files for a single voice directory."""

    paths = voice_asset_paths(root, voice.voice_id)
    paths.directory.mkdir(parents=True, exist_ok=True)
    resolved_controls = controls or default_controls_for_voice(voice)
    text = sample_text or DEFAULT_SAMPLE_TEXT
    prompt = render_voxcpm2_prompt(voice, resolved_controls)
    files = [
        _write_text(
            paths.voice_json,
            json.dumps(voice.to_dict(), ensure_ascii=False, indent=2) + "\n",
            overwrite=overwrite,
        ),
        _write_text(paths.sample_text, text.rstrip() + "\n", overwrite=overwrite),
        _write_text(paths.prompt_text, prompt.rstrip() + "\n", overwrite=overwrite),
        _write_text(
            paths.controls_json,
            json.dumps(resolved_controls.to_dict(), ensure_ascii=False, indent=2) + "\n",
            overwrite=overwrite,
        ),
        _write_text(
            paths.readme,
            render_voice_asset_readme(voice, prompt=prompt, controls=resolved_controls),
            overwrite=overwrite,
        ),
    ]
    return VoiceAssetBundle(voice_id=voice.voice_id, paths=paths, files=tuple(files))


def synthesize_voice_asset(
    voice: Voice,
    root: str | Path = DEFAULT_ASSET_ROOT,
    *,
    sample_text: str | None = None,
    controls: VoiceControls | None = None,
    command: str | None = None,
    make_mp3: bool = False,
    mp3_command: str | None = None,
    overwrite: bool = True,
) -> VoiceAssetBundle:
    """Write the asset directory, synthesize sample.wav, and optionally make sample.mp3."""

    bundle = write_voice_asset_bundle(
        voice,
        root,
        sample_text=sample_text,
        controls=controls,
        overwrite=overwrite,
    )
    text = sample_text or DEFAULT_SAMPLE_TEXT
    synthesize_with_voxcpm2(
        command=command,
        text=text,
        voice=voice,
        output_wav=bundle.paths.wav,
        controls=controls,
    )
    files = list(bundle.files)
    files.append(bundle.paths.wav)
    if make_mp3:
        convert_wav_to_mp3(
            bundle.paths.wav,
            bundle.paths.mp3,
            command=mp3_command,
            voice_id=voice.voice_id,
        )
        files.append(bundle.paths.mp3)
    return VoiceAssetBundle(voice_id=voice.voice_id, paths=bundle.paths, files=tuple(files))


def convert_wav_to_mp3(
    input_wav: str | Path,
    output_mp3: str | Path,
    *,
    command: str | None = None,
    voice_id: str = "",
) -> Path:
    input_path = Path(input_wav)
    output_path = Path(output_mp3)
    if not input_path.is_file():
        raise RuntimeError(f"找不到待转换 WAV：{input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = _audio_convert_args(
        command or os.environ.get("TIMBRE_AUDIO_CONVERT_COMMAND"),
        input_wav=input_path,
        output_mp3=output_path,
        voice_id=voice_id,
    )
    try:
        subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"音频转换命令不存在：{args[0]}。") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "无 stderr"
        raise RuntimeError(f"音频转换失败：{stderr}") from exc
    if not output_path.is_file():
        raise RuntimeError(f"音频转换未生成目标 MP3：{output_path}。")
    return output_path


def render_voice_asset_readme(
    voice: Voice,
    *,
    prompt: str | None = None,
    controls: VoiceControls | None = None,
) -> str:
    resolved_controls = controls or default_controls_for_voice(voice)
    rendered_prompt = prompt or render_voxcpm2_prompt(voice, resolved_controls)
    constraints = voice.constraints
    not_good_for = constraints.get("not_good_for", [])
    if isinstance(not_good_for, list) and not_good_for:
        not_good_for_text = "、".join(str(item) for item in not_good_for)
    else:
        not_good_for_text = "无"
    notes = str(constraints.get("notes", "")).strip() or "无"
    return (
        f"# {voice.voice_id}\n\n"
        "## 音色定位\n\n"
        f"- 分组：{voice.group}\n"
        f"- 档案：{voice.profile.gender} / {voice.profile.age_band} / "
        f"{voice.profile.species} / {voice.profile.locale}\n"
        f"- 声音质感：{_join_values(voice.timbre_tags)}\n"
        f"- 默认语气：{_join_values(voice.emotion_biases)}\n"
        f"- 适配角色：{_join_values(voice.fit_roles)}\n"
        f"- 不推荐场景：{not_good_for_text}\n"
        f"- 备注：{notes}\n\n"
        "## 文件约定\n\n"
        "- `voice.json`：从音色库导出的锁定元数据。\n"
        "- `sample.txt`：试听合成文本。\n"
        "- `sample.voice.txt`：VoxCPM2 音色控制提示。\n"
        "- `sample.controls.json`：结构化控制参数。\n"
        "- `sample.wav`：VoxCPM2 生成的无损试听音频。\n"
        "- `sample.mp3`：由 WAV 转出的便携试听音频。\n\n"
        "## VoxCPM2 控制提示\n\n"
        f"{rendered_prompt}\n"
    )


def _audio_convert_args(
    command: str | None,
    *,
    input_wav: Path,
    output_mp3: Path,
    voice_id: str,
) -> list[str]:
    if command:
        values = {
            "input_wav": str(input_wav),
            "output_mp3": str(output_mp3),
            "voice_id": voice_id,
        }
        return [part.format(**values) for part in shlex.split(command, posix=os.name != "nt")]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "未找到 ffmpeg。请安装 ffmpeg，或设置 TIMBRE_AUDIO_CONVERT_COMMAND，"
            "模板可使用 {input_wav}、{output_mp3}、{voice_id}。"
        )
    return [
        ffmpeg,
        "-y",
        "-i",
        str(input_wav),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_mp3),
    ]


def _write_text(path: Path, content: str, *, overwrite: bool) -> Path:
    if path.exists() and not overwrite:
        return path
    path.write_text(content, encoding="utf-8")
    return path


def _join_values(values: tuple[str, ...]) -> str:
    return "、".join(values) if values else "无"


def _validate_voice_id_for_path(voice_id: str) -> None:
    if not voice_id or voice_id in {".", ".."}:
        raise ValueError("voice_id 不能为空或相对目录")
    if any(separator in voice_id for separator in ("/", "\\")):
        raise ValueError(f"voice_id 不能包含路径分隔符：{voice_id}")
