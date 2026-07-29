"""Task 9 合成逐段音频证据的写入与校验。"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


EVIDENCE_SCHEMA_VERSION = "task9-synthesis-evidence-v1"
EVIDENCE_MANIFEST_NAME = "synthesis-segment-evidence.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_mono_float32(waveform: Any, np: Any) -> Any:
    """与共享拼接器一致地转换为单声道 float32。"""
    value = np.asarray(waveform, dtype=np.float32)
    if value.ndim == 2:
        value = value.mean(axis=1)
    return value.reshape(-1)


def evidence_manifest_path(evidence_root: Path, model_id: str, audio_sha256: str) -> Path:
    return evidence_root.expanduser().resolve() / model_id / audio_sha256 / EVIDENCE_MANIFEST_NAME


def write_synthesis_evidence(
    *,
    evidence_root: Path,
    model_id: str,
    output_audio: Path,
    segment_manifest: Path,
    segments: list[dict[str, Any]],
    waveforms: list[Any],
    sample_rate: int,
    pauses_ms: list[int],
    first_segment_trimmed_samples: int,
    np: Any,
    sf: Any,
) -> Path:
    """保存与最终 WAV 哈希绑定的逐段音频及其可复核清单。

    证据目录按最终成品 SHA-256 命名；同一成品已有完整证据时复用，避免隐式
    覆盖历史证据。片段 WAV 不包含段间补静音，清单则记录其在最终成品中的时间。
    """
    output = output_audio.expanduser().resolve()
    source_manifest = segment_manifest.expanduser().resolve()
    if len(segments) != len(waveforms):
        raise ValueError("逐段音频数与共享分段清单不一致。")
    if len(pauses_ms) != max(0, len(segments) - 1):
        raise ValueError("逐段音频数与边界停顿数不一致。")
    if first_segment_trimmed_samples < 0:
        raise ValueError("前导静音裁剪样本数不能为负数。")

    audio_sha256 = sha256_file(output)
    destination = evidence_manifest_path(evidence_root, model_id, audio_sha256).parent
    existing_manifest = destination / EVIDENCE_MANIFEST_NAME
    if existing_manifest.is_file():
        existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
        if existing.get("full_audio_sha256") == audio_sha256:
            return existing_manifest
        raise ValueError(f"逐段证据目录与目标音频哈希冲突：{destination}")
    if destination.exists():
        raise FileExistsError(f"逐段证据目录已存在但缺少清单，拒绝覆盖：{destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="task9-evidence-", dir=destination.parent))
    try:
        cursor_frames = 0
        entries: list[dict[str, Any]] = []
        for index, (segment, source_waveform) in enumerate(zip(segments, waveforms), start=1):
            waveform = to_mono_float32(source_waveform, np)
            if index == 1 and first_segment_trimmed_samples:
                waveform = waveform[first_segment_trimmed_samples:]
            if not len(waveform):
                raise ValueError(f"片段 {index} 在裁剪后为空，无法保存证据。")
            filename = f"segment-{index:03d}.wav"
            audio_path = temporary / filename
            sf.write(str(audio_path), waveform, sample_rate, format="WAV")
            start_frame = cursor_frames
            end_frame = start_frame + len(waveform)
            pause_after_ms = int(pauses_ms[index - 1]) if index <= len(pauses_ms) else 0
            entries.append(
                {
                    "segment_id": str(segment["segment_id"]),
                    "text_sha256": str(segment["text_sha256"]),
                    "normalized_character_count": int(segment["normalized_character_count"]),
                    "audio_filename": filename,
                    "audio_sha256": sha256_file(audio_path),
                    "frames": len(waveform),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_seconds": start_frame / sample_rate,
                    "end_seconds": end_frame / sample_rate,
                    "pause_after_ms": pause_after_ms,
                }
            )
            cursor_frames = end_frame + round(sample_rate * max(pause_after_ms, 0) / 1000)

        payload = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "model_id": model_id,
            "full_audio_filename": output.name,
            "full_audio_sha256": audio_sha256,
            "source_segment_manifest_sha256": sha256_file(source_manifest),
            "sample_rate_hz": int(sample_rate),
            "first_segment_trimmed_samples": first_segment_trimmed_samples,
            "segments": entries,
        }
        manifest_path = temporary / EVIDENCE_MANIFEST_NAME
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination / EVIDENCE_MANIFEST_NAME
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def load_verified_synthesis_evidence(
    *,
    evidence_root: Path,
    model_id: str,
    output_audio: Path,
    source_segment_manifest: Path,
    source_segments: list[dict[str, Any]],
) -> dict[str, Any]:
    """读取并校验逐段证据；任一哈希或顺序不符即拒绝评测。"""
    output = output_audio.expanduser().resolve()
    audio_sha256 = sha256_file(output)
    manifest_path = evidence_manifest_path(evidence_root, model_id, audio_sha256)
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "缺少与当前成品音频哈希绑定的逐段合成证据："
            f"{manifest_path}；请先用 Task 9 合成编排器重新合成。"
        )
    try:
        evidence = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"逐段合成证据 JSON 无法解析：{manifest_path}: {exc}") from exc
    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("逐段合成证据版本不匹配。")
    if evidence.get("model_id") != model_id:
        raise ValueError("逐段合成证据的模型标识不匹配。")
    if evidence.get("full_audio_sha256") != audio_sha256:
        raise ValueError("逐段合成证据与当前成品音频哈希不匹配。")
    if evidence.get("source_segment_manifest_sha256") != sha256_file(source_segment_manifest):
        raise ValueError("逐段合成证据与当前共享分段清单哈希不匹配。")

    entries = evidence.get("segments")
    if not isinstance(entries, list) or len(entries) != len(source_segments):
        raise ValueError("逐段合成证据的片段数量与共享清单不一致。")
    resolved_entries: list[dict[str, Any]] = []
    for source, entry in zip(source_segments, entries):
        if not isinstance(entry, dict):
            raise ValueError("逐段合成证据包含非法片段记录。")
        if entry.get("segment_id") != source.get("segment_id"):
            raise ValueError("逐段合成证据的片段顺序或标识不一致。")
        if entry.get("text_sha256") != source.get("text_sha256"):
            raise ValueError("逐段合成证据的片段文本哈希不一致。")
        filename = entry.get("audio_filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("逐段合成证据的音频文件名非法。")
        segment_audio = manifest_path.parent / filename
        if not segment_audio.is_file() or segment_audio.stat().st_size == 0:
            raise FileNotFoundError(f"逐段证据音频不存在或为空：{segment_audio}")
        if entry.get("audio_sha256") != sha256_file(segment_audio):
            raise ValueError(f"逐段证据音频哈希不匹配：{segment_audio}")
        resolved_entries.append({**entry, "audio_path": segment_audio})
    return {**evidence, "manifest_path": manifest_path, "segments": resolved_entries}
