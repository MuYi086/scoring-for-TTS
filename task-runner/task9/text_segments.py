"""Task 9 两个模型共用的长文分段、停顿与可复核清单规则。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import wave
from pathlib import Path
from typing import Any


PLAN_VERSION = "task9-segment-plan-v2"
_SENTENCE_ENDINGS = "。！？；;!?"
_CLAUSE_ENDINGS = "，,、：:"
_CLOSING_QUOTES = "”’」』）】"
_PAUSE_BY_BOUNDARY_MS = {
    "clause": 250,
    "forced": 250,
    "sentence": 500,
    "paragraph": 750,
    "end": 0,
}


def read_synthesis_text(path: Path) -> str:
    """读取原文；只去除文件首尾空白，不改写实际台词。"""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"合成原文为空：{path}")
    return text


def normalize_zh_v1(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def speech_rate_from_reference(reference_audio: Path, reference_text: str) -> dict[str, float]:
    """以参考音频的实际语速估算本次旁白的文本时长预算。"""
    try:
        with wave.open(str(reference_audio), "rb") as audio:
            duration_seconds = audio.getnframes() / audio.getframerate()
    except (wave.Error, OSError) as exc:
        raise ValueError(f"无法读取旁白参考 WAV 以估算语速：{reference_audio}: {exc}") from exc
    characters = len(normalize_zh_v1(reference_text))
    if duration_seconds <= 0 or characters <= 0:
        raise ValueError("旁白参考音频时长或参考文案字符数无效。")
    return {
        "reference_duration_seconds": duration_seconds,
        "reference_normalized_characters": float(characters),
        "characters_per_second": characters / duration_seconds,
    }


def sentence_units(paragraph: str) -> list[str]:
    """保留句末引号的中文断句，避免把 `。”` 中的引号移到下一段。"""
    pattern = rf".+?[{_SENTENCE_ENDINGS}][{_CLOSING_QUOTES}]*|.+$"
    return [item.strip() for item in re.findall(pattern, paragraph, flags=re.S) if item.strip()]


def normalized_length(text: str) -> int:
    return len(normalize_zh_v1(text))


def split_long_unit(text: str, max_normalized_characters: int) -> list[str]:
    """长句优先按次级标点拆分，仍超限时按规范化字符预算硬切。"""
    pattern = rf".+?[{_CLAUSE_ENDINGS}][{_CLOSING_QUOTES}]*|.+$"
    parts = [item.strip() for item in re.findall(pattern, text, flags=re.S) if item.strip()]
    chunks: list[str] = []
    current = ""
    for part in parts:
        if normalized_length(part) > max_normalized_characters:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(hard_split(part, max_normalized_characters))
            continue
        if current and normalized_length(current + part) > max_normalized_characters:
            chunks.append(current)
            current = part
        else:
            current += part
    if current:
        chunks.append(current)
    return chunks


def hard_split(text: str, max_normalized_characters: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for char in text:
        contribution = normalized_length(char)
        if current and count + contribution > max_normalized_characters:
            chunks.append("".join(current))
            current = []
            count = 0
        current.append(char)
        count += contribution
    if current:
        chunks.append("".join(current))
    return chunks


def boundary_kind(text: str, paragraph_end: bool, is_final: bool) -> str:
    if is_final:
        return "end"
    if paragraph_end:
        return "paragraph"
    trimmed = text.rstrip().rstrip(_CLOSING_QUOTES)
    if trimmed and trimmed[-1] in _CLAUSE_ENDINGS:
        return "clause"
    if trimmed and trimmed[-1] in _SENTENCE_ENDINGS:
        return "sentence"
    return "forced"


def build_segment_plan(
    text: str,
    reference_audio: Path,
    reference_text: str,
    target_seconds: float,
    max_segment_seconds: float,
) -> dict[str, Any]:
    """构造语义完整、按参考语速预算且可供两个模型共用的分段清单。"""
    if target_seconds <= 0 or max_segment_seconds < target_seconds:
        raise ValueError("分段时长预算必须满足 0 < target_seconds <= max_segment_seconds。")
    rate = speech_rate_from_reference(reference_audio, reference_text)
    target_characters = max(20, round(rate["characters_per_second"] * target_seconds))
    max_characters = max(target_characters, round(rate["characters_per_second"] * max_segment_seconds))
    raw_segments: list[dict[str, Any]] = []
    paragraphs = [item for item in re.split(r"\n\s*\n", text) if item.strip()]
    current = ""
    current_paragraph_end = False
    for paragraph_index, paragraph in enumerate(paragraphs):
        units = sentence_units(paragraph)
        for unit_index, unit in enumerate(units):
            pieces = (
                split_long_unit(unit, max_characters)
                if normalized_length(unit) > max_characters
                else [unit]
            )
            for piece_index, piece in enumerate(pieces):
                connector = "\n\n" if current and unit_index == 0 and piece_index == 0 else ""
                if current and normalized_length(current + connector + piece) > target_characters:
                    raw_segments.append({"text": current, "paragraph_end": current_paragraph_end})
                    current = ""
                    current_paragraph_end = False
                    connector = ""
                if normalized_length(piece) > max_characters:
                    raise RuntimeError("长句硬切后仍超过最大字符预算。")
                current += connector + piece
                current_paragraph_end = unit_index == len(units) - 1 and piece_index == len(pieces) - 1
    if current:
        raw_segments.append({"text": current, "paragraph_end": current_paragraph_end})
    if not raw_segments:
        raise ValueError("无法从原文生成分段。")
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(raw_segments):
        value = str(item["text"])
        kind = boundary_kind(
            value,
            paragraph_end=bool(item["paragraph_end"]),
            is_final=index == len(raw_segments) - 1,
        )
        segments.append(
            {
                "segment_id": f"{index + 1:03d}",
                "text": value,
                "text_sha256": sha256_text(value),
                "normalized_character_count": normalized_length(value),
                "estimated_duration_seconds": normalized_length(value) / rate["characters_per_second"],
                "boundary_after": kind,
                "pause_after_ms": _PAUSE_BY_BOUNDARY_MS[kind],
            }
        )
    source_normalized = normalize_zh_v1(text)
    joined_normalized = "".join(normalize_zh_v1(item["text"]) for item in segments)
    if source_normalized != joined_normalized:
        raise RuntimeError("分段后的文本与原文不一致，拒绝开始合成。")
    return {
        "schema_version": PLAN_VERSION,
        "source_text_sha256": sha256_text(text),
        "source_normalized_sha256": sha256_text(source_normalized),
        "source_normalized_character_count": len(source_normalized),
        "reference_audio_sha256": hashlib.sha256(reference_audio.read_bytes()).hexdigest(),
        "reference_text_sha256": sha256_text(reference_text),
        "reference_speech_rate": rate,
        "policy": {
            "target_seconds": target_seconds,
            "max_segment_seconds": max_segment_seconds,
            "target_normalized_characters": target_characters,
            "max_normalized_characters": max_characters,
            "sentence_boundary": "保留完整句和句末引号；仅在超过最大时长预算时按次级标点或硬字符预算切分。",
            "pause_policy_ms": _PAUSE_BY_BOUNDARY_MS,
            "context_policy": "相邻上下文只记录在可复核清单中；不注入模型待朗读文本，避免污染全文 CER 参考。",
        },
        "segments": segments,
    }


def write_segment_plan(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_segment_plan(path: Path, text: str) -> list[dict[str, Any]]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取共享分段清单：{path}: {exc}") from exc
    if plan.get("schema_version") != PLAN_VERSION:
        raise ValueError("共享分段清单版本不匹配。")
    if plan.get("source_text_sha256") != sha256_text(text):
        raise ValueError("共享分段清单对应的 text.md 已变化。")
    segments = plan.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("共享分段清单不含片段。")
    joined = "".join(normalize_zh_v1(str(item.get("text", ""))) for item in segments)
    if joined != normalize_zh_v1(text):
        raise ValueError("共享分段清单的片段文本与 text.md 不一致。")
    return segments


def split_synthesis_text(text: str, max_chars: int) -> list[str]:
    """供单元测试和短文本工具复用的无参考音频断句兼容入口。"""
    if max_chars < 20:
        raise ValueError("文本上限必须不小于 20。")
    chunks: list[str] = []
    for paragraph in (item for item in re.split(r"\n\s*\n", text) if item.strip()):
        current = ""
        for unit in sentence_units(paragraph):
            pieces = split_long_unit(unit, max_chars) if normalized_length(unit) > max_chars else [unit]
            for piece in pieces:
                if current and normalized_length(current + piece) > max_chars:
                    chunks.append(current)
                    current = ""
                current += piece
        if current:
            chunks.append(current)
    return chunks


def join_waveforms(waveforms: list[Any], sample_rate: int, pauses_ms: list[int], np: Any) -> Any:
    """以共享清单的每个边界停顿拼接单声道 float32 片段。"""
    if not waveforms:
        raise RuntimeError("模型未返回任何音频片段。")
    if len(pauses_ms) != len(waveforms) - 1:
        raise ValueError("片段数与边界停顿数不匹配。")
    segments = []
    for waveform in waveforms:
        segment = np.asarray(waveform, dtype=np.float32)
        if segment.ndim == 2:
            segment = segment.mean(axis=1)
        segments.append(segment.reshape(-1))
    joined: list[Any] = []
    for index, segment in enumerate(segments):
        joined.append(segment)
        if index < len(pauses_ms):
            joined.append(np.zeros(round(sample_rate * max(pauses_ms[index], 0) / 1000), dtype=np.float32))
    return np.concatenate(joined)
