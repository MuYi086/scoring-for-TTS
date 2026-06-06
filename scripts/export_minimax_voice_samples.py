"""从 MiniMax 中英音色 JSON 生成一音色一目录的试听资产。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_INPUT = Path("音色/中英音色.json")
DEFAULT_OUTPUT_DIR = Path("samples")
DEFAULT_EN_START_INDEX = 77
DEFAULT_ZH_START_INDEX = 1
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class VoiceAsset:
    voice: dict[str, Any]
    asset_id: str
    language: str
    language_code: str
    sequence: int
    directory: Path


def main() -> int:
    args = parse_args()
    voices = load_voices(args.input)
    assets = build_voice_assets(
        voices,
        args.output_dir,
        en_start_index=args.en_start_index,
        zh_start_index=args.zh_start_index,
        limit=args.limit,
    )

    failures: list[str] = []
    for asset in assets:
        write_voice_asset(asset)
        if args.skip_download:
            continue
        try:
            download_sample_audio_with_retries(
                str(asset.voice.get("sample_audio") or ""),
                asset.directory / "sample.wav",
                overwrite=args.overwrite_audio,
                timeout=args.timeout,
                keep_source=args.keep_source,
                retries=args.retries,
            )
        except Exception as exc:  # noqa: BLE001 - 需要继续处理其余音色并汇总失败项。
            failures.append(f"{asset.asset_id}: {exc}")

    print(f"已生成 {len(assets)} 个音色目录：{args.output_dir}")
    if args.skip_download:
        print("已跳过试听音频下载。")
    elif failures:
        print(f"试听音频下载失败 {len(failures)} 个：")
        for item in failures:
            print(f"- {item}")
        return 1
    else:
        print("试听音频已全部写入 sample.wav。")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="遍历 音色/中英音色.json，在 samples 下生成每个音色的目录、描述和 sample.wav。"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="输入音色 JSON。")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录。")
    parser.add_argument("--en-start-index", type=int, default=DEFAULT_EN_START_INDEX)
    parser.add_argument("--zh-start-index", type=int, default=DEFAULT_ZH_START_INDEX)
    parser.add_argument("--timeout", type=float, default=60.0, help="单个试听音频下载超时时间，单位秒。")
    parser.add_argument("--retries", type=int, default=3, help="单个试听音频下载/转码失败后的重试次数。")
    parser.add_argument("--overwrite-audio", action="store_true", help="已存在 sample.wav 时重新下载并覆盖。")
    parser.add_argument("--keep-source", action="store_true", help="额外保留原始下载音频 sample.source.*。")
    parser.add_argument("--skip-download", action="store_true", help="只生成目录和描述，不下载试听音频。")
    parser.add_argument("--limit", type=int, help="只处理前 N 条，便于调试。")
    return parser.parse_args()


def load_voices(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"输入 JSON 顶层必须是数组：{path}")
    voices: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条音色必须是对象")
        voices.append(item)
    return voices


def build_voice_assets(
    voices: list[dict[str, Any]],
    output_dir: Path,
    *,
    en_start_index: int = DEFAULT_EN_START_INDEX,
    zh_start_index: int = DEFAULT_ZH_START_INDEX,
    limit: int | None = None,
) -> list[VoiceAsset]:
    assets: list[VoiceAsset] = []
    counters = {
        "zh": zh_start_index - 1,
        "en": en_start_index - 1,
        "other": 0,
    }
    selected_voices = voices[:limit] if limit is not None else voices
    for voice in selected_voices:
        language = detect_language(voice)
        language_code = language_code_for(language)
        counter_key = language_code if language_code in {"zh", "en"} else "other"
        counters[counter_key] += 1
        sequence = counters[counter_key]
        asset_id = format_asset_id(language_code, sequence, str(voice.get("voice_name") or "未命名音色"))
        assets.append(
            VoiceAsset(
                voice=voice,
                asset_id=asset_id,
                language=language,
                language_code=language_code,
                sequence=sequence,
                directory=output_dir / asset_id,
            )
        )
    return assets


def detect_language(voice: dict[str, Any]) -> str:
    for item in voice.get("tag_items") or []:
        if isinstance(item, dict) and item.get("category") == 1 and item.get("name"):
            return str(item["name"])
    for tag in voice.get("tag_list") or []:
        if str(tag).startswith(("中文", "英语")):
            return str(tag)
    return "未知"


def language_code_for(language: str) -> str:
    if language.startswith("中文"):
        return "zh"
    if language.startswith("英语"):
        return "en"
    return "xx"


def format_asset_id(language_code: str, sequence: int, voice_name: str) -> str:
    title = sanitize_voice_title(voice_name)
    return f"v_{language_code}_{sequence:03d}_{title}"


def sanitize_voice_title(voice_name: str, *, max_bytes: int = 180) -> str:
    normalized = unicodedata.normalize("NFKC", voice_name).strip()
    parts = re.split(r"\s+[-－—–]\s+", normalized, maxsplit=1)
    if len(parts) == 2:
        head = sanitize_path_segment(parts[0])
        tail = sanitize_path_segment(parts[1])
        title = f"{head}-{tail}" if tail else head
    else:
        title = sanitize_path_segment(normalized)
    return truncate_utf8_bytes(title or "未命名音色", max_bytes=max_bytes)


def sanitize_path_segment(value: str) -> str:
    text = value.strip()
    text = re.sub(r"[,，、;；/\\:：|]+", "_", text)
    text = re.sub(r"[<>\"?*\x00-\x1f]+", "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("._- ")


def truncate_utf8_bytes(value: str, *, max_bytes: int) -> str:
    current = bytearray()
    result: list[str] = []
    for char in value:
        raw = char.encode("utf-8")
        if len(current) + len(raw) > max_bytes:
            break
        current.extend(raw)
        result.append(char)
    return "".join(result).rstrip("._- ") or "未命名音色"


def write_voice_asset(asset: VoiceAsset) -> None:
    asset.directory.mkdir(parents=True, exist_ok=True)
    write_json(asset.directory / "voice.json", asset.voice)
    remove_obsolete_files(asset.directory, ("asset.json", "sample.url.txt"))
    (asset.directory / "README.md").write_text(render_readme(asset), encoding="utf-8")


def remove_obsolete_files(directory: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = directory / name
        if path.exists():
            path.unlink()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_readme(asset: VoiceAsset) -> str:
    voice = asset.voice
    tag_list = "、".join(str(item) for item in voice.get("tag_list") or []) or "无"
    return (
        f"# {voice.get('voice_name', '')}\n\n"
        f"- 目录 ID：`{asset.asset_id}`\n"
        f"- Voice Id：`{voice.get('voice_id', '')}`\n"
        f"- Uniq Id：`{voice.get('uniq_id', '')}`\n"
        f"- 标签：{tag_list}\n"
        "- 试听：`sample.wav`\n\n"
        f"{voice.get('description', '')}\n\n"
        "## 文件\n\n"
        "- `voice.json`：MiniMax 原始音色字段，包含标签、描述和试听来源 URL。\n"
        "- `sample.wav`：本地试听音频。\n"
    )


def download_sample_audio(
    url: str,
    output_wav: Path,
    *,
    overwrite: bool = False,
    timeout: float = 60.0,
    keep_source: bool = False,
) -> None:
    if not url:
        raise ValueError("sample_audio 为空")
    if output_wav.exists() and not overwrite:
        return

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    source_suffix = source_audio_suffix(url)
    with tempfile.TemporaryDirectory(prefix=".download-", dir=output_wav.parent) as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        source_path = tmp_dir / f"sample.source{source_suffix}"
        tmp_wav = tmp_dir / "sample.wav"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            source_path.write_bytes(response.read())
        if source_path.stat().st_size == 0:
            raise ValueError("sample_audio 下载为空，无法生成 sample.wav")

        if is_wav_file(source_path):
            shutil.copyfile(source_path, tmp_wav)
        else:
            convert_to_wav(source_path, tmp_wav)

        tmp_wav.replace(output_wav)
        if keep_source:
            shutil.copyfile(source_path, output_wav.parent / f"sample.source{source_suffix}")


def download_sample_audio_with_retries(
    url: str,
    output_wav: Path,
    *,
    overwrite: bool = False,
    timeout: float = 60.0,
    keep_source: bool = False,
    retries: int = 3,
) -> None:
    attempts = max(1, retries)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            download_sample_audio(
                url,
                output_wav,
                overwrite=overwrite,
                timeout=timeout,
                keep_source=keep_source,
            )
            return
        except Exception as exc:  # noqa: BLE001 - 重试后统一抛出最后一次错误。
            last_error = exc
    assert last_error is not None
    raise last_error


def source_audio_suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}:
        return suffix
    return ".audio"


def is_wav_file(path: Path) -> bool:
    with path.open("rb") as file:
        header = file.read(12)
    return header.startswith(b"RIFF") and header[8:12] == b"WAVE"


def convert_to_wav(source_path: Path, output_wav: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，无法把试听音频转换为 sample.wav")
    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                str(output_wav),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "无 stderr"
        raise RuntimeError(f"ffmpeg 转 WAV 失败：{stderr}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
