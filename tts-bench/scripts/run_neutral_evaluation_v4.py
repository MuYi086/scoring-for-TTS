#!/usr/bin/env python3
"""Task 5 V4 长音频六后端中立评测入口。

V4 对完整有声书计算双 CER；使用 Whisper 时间戳与冻结角色台词做单调对齐，
再按角色抽取片段计算双 SIM；自然度使用固定等距窗口，避免单次随机裁剪代表整部作品。
脚本只读取已有 WAV，不调用 TTS 模型，也不计算跨后端加权总分。
"""

from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_automated_evaluation import (  # noqa: E402
    SenseVoiceAsrEvaluator,
    UtmosV2Evaluator,
    WavLMSpeakerEvaluator,
    character_error_rate,
    lazy_import_audio_stack,
    load_json,
    load_mono_audio,
    normalize_zh_v1,
    project_path,
    project_relative_path,
    sha256_file,
)
from run_neutral_evaluation_v2 import (  # noqa: E402
    AudioInput,
    SpeechBrainEcapaEvaluator,
    cosine,
    predict_nisqa_batch,
    read_jsonl,
    release_model,
    write_jsonl_atomic,
)


METRICS = (
    "sensevoice_cer",
    "whisper_cer",
    "wavlm_sim",
    "speechbrain_ecapa_sim",
    "utmosv2",
    "nisqa",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "longAudioTest" / "评测结果" / "task5-v4-raw"


@dataclass(frozen=True)
class QualityWindow:
    """自然度评价的一段固定时间窗。"""

    audio_id: str
    parent_audio_id: str
    index: int
    start_seconds: float
    end_seconds: float
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v4.json",
        help="V4 长音频冻结配置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="本次原始结果目录；正式复测应使用一个尚不存在的新目录。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=METRICS,
        default=list(METRICS),
        help="只运行指定后端，用于排错或断点续跑。",
    )
    parser.add_argument(
        "--model-id",
        required=True,
        help="本次唯一允许分析的模型；一次调用不得处理多条模型长音频。",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=PROJECT_ROOT / "longAudioTest" / "评测结果",
        help="单模型六后端完成后写入独立评价报告的目录。",
    )
    parser.add_argument("--resume", action="store_true", help="续跑同一次未完成的 V4 评测。")
    parser.add_argument("--strict", action="store_true", help="所选后端存在任一缺失或错误时返回非零状态。")
    return parser.parse_args()


def validate_config(config: dict[str, Any]) -> None:
    """校验 V4 配置中会影响统计对象的冻结约束。"""

    if config.get("schema_version") != "4.0":
        raise ValueError("V4 长音频评测仅支持 schema_version=4.0")
    if config.get("policy", {}).get("normalization_id") != "zh-v1":
        raise ValueError("当前只实现 zh-v1 文本规范化")
    if config.get("source", {}).get("cer_reference") != "ai_deal_dialogue_concatenation":
        raise ValueError("V4 CER 参考必须冻结为 ai_deal.json 的 dialogue 台词串")
    if not os.environ.get("HF_MIRROR_ROOT"):
        raise ValueError("必须设置 HF_MIRROR_ROOT，V4 评测不允许隐式联网下载")
    models = config.get("models", [])
    references = config.get("references", [])
    if len(models) != int(config.get("expected_model_count", -1)):
        raise ValueError("models 数量与 expected_model_count 不一致")
    if len({item["model_id"] for item in models}) != len(models):
        raise ValueError("models 中存在重复 model_id")
    if len({item["role"] for item in references}) != len(references):
        raise ValueError("references 中存在重复角色")
    if int(config["alignment"]["max_excerpts_per_role"]) < 1:
        raise ValueError("max_excerpts_per_role 必须大于 0")
    for backend in ("sensevoice", "whisper"):
        chunk_seconds = float(config[backend]["long_audio_chunk_seconds"])
        if not 0 < chunk_seconds <= 60:
            raise ValueError(f"{backend}.long_audio_chunk_seconds 必须在 (0, 60] 秒内")
    if float(config["alignment"]["max_merge_gap_seconds"]) < 0:
        raise ValueError("alignment.max_merge_gap_seconds 不能小于 0")
    if (
        config["alignment"].get("mixed_role_chunk_policy")
        != "split_by_exact_character_run_linear_time"
    ):
        raise ValueError("V4 混合角色时间戳块必须使用冻结的线性切分策略")
    if float(config["quality_sampling"]["window_seconds"]) <= 0:
        raise ValueError("quality_sampling.window_seconds 必须大于 0")
    if int(config["quality_sampling"]["window_count"]) < 1:
        raise ValueError("quality_sampling.window_count 必须大于 0")


def load_dialogues(config: dict[str, Any]) -> list[dict[str, Any]]:
    """读取并核对冻结的 148 段角色台词。"""

    source = config["source"]
    dialogue_path = project_path(source["dialogue_path"])
    raw_text_path = project_path(source["raw_text_path"])
    for path, expected_hash in [
        (dialogue_path, source["dialogue_sha256"]),
        (raw_text_path, source["raw_text_sha256"]),
    ]:
        if not path.is_file():
            raise ValueError(f"找不到 V4 输入文件：{path}")
        if sha256_file(path) != expected_hash:
            raise ValueError(f"V4 输入文件 SHA-256 与冻结配置不一致：{path}")

    rows = json.loads(dialogue_path.read_text(encoding="utf-8"))
    dialogues = [row for row in rows if row.get("type") == "dialogue"]
    if len(dialogues) != int(source["dialogue_count"]):
        raise ValueError(f"ai_deal.json dialogue 数量应为 {source['dialogue_count']}，实际 {len(dialogues)}")
    if any(not row.get("role_name") or not row.get("text_content") for row in dialogues):
        raise ValueError("ai_deal.json 存在缺少 role_name 或 text_content 的 dialogue")
    normalized = "".join(normalize_zh_v1(row["text_content"]) for row in dialogues)
    if len(normalized) != int(source["normalized_character_count"]):
        raise ValueError(
            "ai_deal.json 规范化字符数应为 "
            f"{source['normalized_character_count']}，实际 {len(normalized)}"
        )
    configured_roles = {item["role"] for item in config["references"]}
    actual_roles = {row["role_name"] for row in dialogues}
    if actual_roles != configured_roles:
        raise ValueError(f"角色集合与参考音频不一致：台词 {sorted(actual_roles)}，参考 {sorted(configured_roles)}")
    return dialogues


def input_from_config(
    *,
    audio_id: str,
    kind: str,
    model_id: str,
    case_id: str,
    role: str,
    path_value: str,
    expected_sha256: str,
    expected_text: str,
) -> AudioInput:
    path = project_path(path_value)
    if not path.is_file():
        raise ValueError(f"找不到 V4 音频：{path}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_sha256:
        raise ValueError(f"V4 音频 SHA-256 与冻结配置不一致：{path}")
    return AudioInput(
        audio_id=audio_id,
        kind=kind,
        model_id=model_id,
        run_id=None,
        case_id=case_id,
        role=role,
        path=path,
        sha256=actual_hash,
        expected_text=expected_text,
    )


def build_inputs(
    config: dict[str, Any],
    dialogues: list[dict[str, Any]],
) -> tuple[list[AudioInput], list[AudioInput]]:
    """从配置中的显式路径和哈希建立六条参考与七条长音频。"""

    expected_text = "".join(row["text_content"] for row in dialogues)
    references = [
        input_from_config(
            audio_id=f"reference:{item['role']}",
            kind="reference",
            model_id="原始参考音频",
            case_id=f"reference:{item['role']}",
            role=item["role"],
            path_value=item["audio_path"],
            expected_sha256=item["sha256"],
            expected_text=item["transcript"],
        )
        for item in config["references"]
    ]
    syntheses = [
        input_from_config(
            audio_id=f"synthesis:{item['model_id']}",
            kind="synthesis",
            model_id=item["model_id"],
            case_id="task5_v4_full_audiobook",
            role="完整有声书",
            path_value=item["audio_path"],
            expected_sha256=item["sha256"],
            expected_text=expected_text,
        )
        for item in config["models"]
    ]
    return references, syntheses


def audio_duration(path: Path) -> float:
    _, sf, _ = lazy_import_audio_stack()
    return float(sf.info(path).duration)


def base_audio_record(audio: AudioInput) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "audio_id": audio.audio_id,
        "kind": audio.kind,
        "model_id": audio.model_id,
        "case_id": audio.case_id,
        "role": audio.role,
        "audio": {
            "path": project_relative_path(audio.path),
            "sha256": audio.sha256,
            "duration_seconds": audio_duration(audio.path),
        },
        "expected_text": audio.expected_text,
        "metrics": {},
        "errors": [],
    }


def base_similarity_records(
    references: list[AudioInput], syntheses: list[AudioInput]
) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "4.0",
            "model_id": synthesis.model_id,
            "role": reference.role,
            "reference_audio": {
                "path": project_relative_path(reference.path),
                "sha256": reference.sha256,
            },
            "synthesis_audio": {
                "path": project_relative_path(synthesis.path),
                "sha256": synthesis.sha256,
            },
            "alignment_excerpts": [],
            "metrics": {},
            "errors": [],
        }
        for synthesis in syntheses
        for reference in references
    ]


def build_calibration_records(references: list[AudioInput]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reference in references:
        rows.append(
            {
                "schema_version": "4.0",
                "control_type": "same_speaker_split_half",
                "left_role": reference.role,
                "right_role": reference.role,
                "label": f"{reference.role}原始音频前半段 ↔ 后半段",
                "metrics": {},
                "errors": [],
            }
        )
    for left, right in combinations(references, 2):
        rows.append(
            {
                "schema_version": "4.0",
                "control_type": "different_speaker_reference_pair",
                "left_role": left.role,
                "right_role": right.role,
                "label": f"{left.role}原始音频 ↔ {right.role}原始音频",
                "metrics": {},
                "errors": [],
            }
        )
    return rows


def restore_or_create_records(
    output_dir: Path,
    references: list[AudioInput],
    syntheses: list[AudioInput],
    config: dict[str, Any],
    resume: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = [
        output_dir / "per_audio.jsonl",
        output_dir / "speaker_similarity.jsonl",
        output_dir / "speaker_calibration.jsonl",
    ]
    if resume:
        metadata_path = output_dir / "run_metadata.json"
        if not metadata_path.is_file():
            raise ValueError("--resume 要求 run_metadata.json 已存在")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("config") != config:
            raise ValueError("--resume 的已有结果配置与当前 V4 配置不一致")
        rows = [read_jsonl(path) for path in paths]
        if any(not item for item in rows):
            raise ValueError("--resume 要求三份原始结果文件都已存在且非空")
        return rows[0], rows[1], rows[2]
    return (
        [base_audio_record(item) for item in [*references, *syntheses]],
        base_similarity_records(references, syntheses),
        build_calibration_records(references),
    )


def metric_error(metric: str, exc: Exception) -> dict[str, str]:
    return {"metric": metric, "error": str(exc)}


def clear_metric_error(record: dict[str, Any], metric: str) -> None:
    record["errors"] = [item for item in record["errors"] if item.get("metric") != metric]


def sensevoice_intervals(
    duration_seconds: float,
    chunk_seconds: float,
) -> list[tuple[float, float]]:
    """把长音频切成连续、不重叠且完整覆盖全长的固定时间段。"""

    if duration_seconds <= 0 or chunk_seconds <= 0:
        raise ValueError("SenseVoice 分段参数必须为正数")
    intervals = []
    start = 0.0
    while start < duration_seconds:
        end = min(duration_seconds, start + chunk_seconds)
        intervals.append((start, end))
        start = end
    return intervals


def transcribe_sensevoice_long_audio(
    evaluator: Any,
    path: Path,
    chunk_seconds: float,
    audio_id: str,
) -> dict[str, Any]:
    """顺序转写固定分段，避免把整条长音频一次载入 SenseVoice。"""

    np, sf, _ = lazy_import_audio_stack()
    duration_seconds = float(sf.info(path).duration)
    intervals = sensevoice_intervals(duration_seconds, chunk_seconds)
    if len(intervals) == 1:
        transcript = evaluator.transcribe(path)
        return {
            "text": transcript,
            "segments": [
                {
                    "index": 0,
                    "start_seconds": 0.0,
                    "end_seconds": duration_seconds,
                    "text": transcript,
                }
            ],
        }

    transcripts: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="task5-v4-sensevoice-") as temporary_dir:
        with sf.SoundFile(path) as source:
            sample_rate = int(source.samplerate)
            frame_count = len(source)
            for index, (start_seconds, end_seconds) in enumerate(intervals):
                start = min(frame_count, round(start_seconds * sample_rate))
                stop = min(frame_count, round(end_seconds * sample_rate))
                if stop <= start:
                    raise ValueError(
                        f"SenseVoice 分段区间无效：{start_seconds:.3f}-{end_seconds:.3f}"
                    )
                source.seek(start)
                waveform = source.read(stop - start, dtype="float32", always_2d=True)
                mono = np.mean(waveform, axis=1)
                segment_path = Path(temporary_dir) / f"segment-{index:04d}.wav"
                sf.write(segment_path, mono, sample_rate, subtype="PCM_16")
                transcript = evaluator.transcribe(segment_path)
                transcripts.append(
                    {
                        "index": index,
                        "start_seconds": start / sample_rate,
                        "end_seconds": stop / sample_rate,
                        "text": transcript,
                    }
                )
                segment_path.unlink()
                print(
                    f"[sensevoice_cer] {audio_id} 分段 {index + 1}/{len(intervals)}",
                    flush=True,
                )
    return {
        "text": "".join(item["text"] for item in transcripts),
        "segments": transcripts,
    }


def apply_sensevoice(
    config: dict[str, Any],
    inputs: dict[str, AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Callable[[], None],
) -> None:
    evaluator = SenseVoiceAsrEvaluator(config)
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, "sensevoice_cer")
            try:
                result = transcribe_sensevoice_long_audio(
                    evaluator,
                    inputs[row["audio_id"]].path,
                    float(config["long_audio_chunk_seconds"]),
                    row["audio_id"],
                )
                hypothesis_raw = result["text"]
                reference_normalized = normalize_zh_v1(row["expected_text"])
                hypothesis_normalized = normalize_zh_v1(hypothesis_raw)
                row["metrics"]["sensevoice_cer"] = {
                    "hypothesis_raw": hypothesis_raw,
                    "segments": result["segments"],
                    "normalization_id": "zh-v1",
                    "reference_normalized": reference_normalized,
                    "hypothesis_normalized": hypothesis_normalized,
                    "cer": character_error_rate(reference_normalized, hypothesis_normalized),
                }
            except Exception as exc:
                row["metrics"].pop("sensevoice_cer", None)
                row["errors"].append(metric_error("sensevoice_cer", exc))
            print(f"[sensevoice_cer] {index}/{len(rows)} {row['audio_id']}", flush=True)
            checkpoint()
    finally:
        release_model(evaluator)


def clean_whisper_result(
    result: Any,
    *,
    offset_seconds: float,
    segment_end_seconds: float,
    segment_index: int,
) -> dict[str, Any]:
    """校验单段 Whisper 输出，并把相对字词时间戳平移到全局时间轴。"""

    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise RuntimeError("Whisper 未返回 text 字段")
    chunks = result.get("chunks")
    if not isinstance(chunks, list):
        raise RuntimeError("Whisper 长音频未返回 chunks 时间戳")
    cleaned: list[dict[str, Any]] = []
    for chunk in chunks:
        timestamp = chunk.get("timestamp") if isinstance(chunk, dict) else None
        if (
            not isinstance(timestamp, (tuple, list))
            or len(timestamp) != 2
            or timestamp[0] is None
            or timestamp[1] is None
        ):
            continue
        start = max(offset_seconds, offset_seconds + float(timestamp[0]))
        end = min(segment_end_seconds, offset_seconds + float(timestamp[1]))
        text = chunk.get("text")
        if isinstance(text, str) and end > start >= 0:
            cleaned.append(
                {
                    "text": text,
                    "start_seconds": start,
                    "end_seconds": end,
                    "segment_index": segment_index,
                }
            )
    if not cleaned:
        raise RuntimeError(f"Whisper 第 {segment_index + 1} 段没有返回可用的正时长时间戳块")
    return {"text": result["text"], "chunks": cleaned}


def transcribe_whisper_long_audio(
    evaluator: Any,
    path: Path,
    return_timestamps: str,
    chunk_seconds: float,
    audio_id: str,
) -> dict[str, Any]:
    """逐段运行 Whisper，避免流水线一次读取并展开整条长音频。"""

    np, sf, _ = lazy_import_audio_stack()
    duration_seconds = float(sf.info(path).duration)
    intervals = sensevoice_intervals(duration_seconds, chunk_seconds)
    transcripts: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="task5-v4-whisper-") as temporary_dir:
        with sf.SoundFile(path) as source:
            sample_rate = int(source.samplerate)
            frame_count = len(source)
            for index, (start_seconds, end_seconds) in enumerate(intervals):
                start = min(frame_count, round(start_seconds * sample_rate))
                stop = min(frame_count, round(end_seconds * sample_rate))
                if stop <= start:
                    raise ValueError(
                        f"Whisper 分段区间无效：{start_seconds:.3f}-{end_seconds:.3f}"
                    )
                source.seek(start)
                waveform = source.read(stop - start, dtype="float32", always_2d=True)
                mono = np.mean(waveform, axis=1)
                segment_path = Path(temporary_dir) / f"segment-{index:04d}.wav"
                sf.write(segment_path, mono, sample_rate, subtype="PCM_16")
                raw_result = evaluator.pipeline(
                    str(segment_path),
                    generate_kwargs=evaluator.generate_kwargs,
                    return_timestamps=return_timestamps,
                )
                actual_start = start / sample_rate
                actual_end = stop / sample_rate
                result = clean_whisper_result(
                    raw_result,
                    offset_seconds=actual_start,
                    segment_end_seconds=actual_end,
                    segment_index=index,
                )
                transcripts.append(
                    {
                        "index": index,
                        "start_seconds": actual_start,
                        "end_seconds": actual_end,
                        "text": result["text"],
                    }
                )
                chunks.extend(result["chunks"])
                segment_path.unlink()
                del waveform, mono, raw_result, result
                print(
                    f"[whisper_cer] {audio_id} 分段 {index + 1}/{len(intervals)}",
                    flush=True,
                )
    return {
        "text": "".join(item["text"] for item in transcripts),
        "segments": transcripts,
        "chunks": chunks,
    }


def apply_whisper(
    config: dict[str, Any],
    inputs: dict[str, AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Callable[[], None],
) -> None:
    from run_automated_evaluation import WhisperAsrEvaluator

    evaluator = WhisperAsrEvaluator(config, allow_model_download=False)
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, "whisper_cer")
            try:
                result = transcribe_whisper_long_audio(
                    evaluator,
                    inputs[row["audio_id"]].path,
                    str(config["return_timestamps"]),
                    float(config["long_audio_chunk_seconds"]),
                    row["audio_id"],
                )
                reference_normalized = normalize_zh_v1(row["expected_text"])
                hypothesis_normalized = normalize_zh_v1(result["text"])
                row["metrics"]["whisper_cer"] = {
                    "hypothesis_raw": result["text"],
                    "segments": result["segments"],
                    "chunks": result["chunks"],
                    "normalization_id": "zh-v1",
                    "reference_normalized": reference_normalized,
                    "hypothesis_normalized": hypothesis_normalized,
                    "cer": character_error_rate(reference_normalized, hypothesis_normalized),
                }
            except Exception as exc:
                row["metrics"].pop("whisper_cer", None)
                row["errors"].append(metric_error("whisper_cer", exc))
            print(f"[whisper_cer] {index}/{len(rows)} {row['audio_id']}", flush=True)
            checkpoint()
    finally:
        release_model(evaluator)


def evenly_spaced(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """按源时间均匀取样，避免只挑高分或只取开头片段。"""

    if len(items) <= limit:
        return items
    if limit == 1:
        return [items[len(items) // 2]]
    indexes = [round(index * (len(items) - 1) / (limit - 1)) for index in range(limit)]
    return [items[index] for index in indexes]


def split_mixed_role_chunk(
    *,
    part: str,
    chunk: dict[str, Any],
    chunk_index: int,
    hypothesis_start_index: int,
    hypothesis_to_expected: dict[int, int],
    expected_roles: list[str],
) -> list[dict[str, Any]]:
    """按精确匹配字符的角色连续区间切分一个跨角色 Whisper 块。"""

    matched = [
        (local_index, expected_roles[hypothesis_to_expected[hypothesis_start_index + local_index]])
        for local_index in range(len(part))
        if hypothesis_start_index + local_index in hypothesis_to_expected
    ]
    if not matched:
        return []
    groups: list[dict[str, Any]] = []
    for local_index, role in matched:
        if not groups or groups[-1]["role"] != role:
            groups.append(
                {
                    "role": role,
                    "first_match_index": local_index,
                    "last_match_index": local_index,
                    "exact_match_characters": 1,
                }
            )
        else:
            groups[-1]["last_match_index"] = local_index
            groups[-1]["exact_match_characters"] += 1

    boundaries = [0]
    for left, right in zip(groups, groups[1:]):
        boundaries.append(
            round((left["last_match_index"] + 1 + right["first_match_index"]) / 2)
        )
    boundaries.append(len(part))
    chunk_start = float(chunk["start_seconds"])
    chunk_end = float(chunk["end_seconds"])
    chunk_duration = chunk_end - chunk_start
    pieces: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        character_start = boundaries[index]
        character_end = boundaries[index + 1]
        if character_end <= character_start:
            continue
        start_seconds = chunk_start + chunk_duration * character_start / len(part)
        end_seconds = chunk_start + chunk_duration * character_end / len(part)
        pieces.append(
            {
                "role": group["role"],
                "chunk_index": chunk_index,
                "chunk_end_index": chunk_index,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "asr_text": part[character_start:character_end],
                "normalized_characters": character_end - character_start,
                "exact_match_characters": group["exact_match_characters"],
                "role_exact_match_characters": group["exact_match_characters"],
                "time_boundary_method": "linear_by_normalized_character_position",
            }
        )
    return pieces


def align_role_excerpts(
    dialogues: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """把 Whisper 时间戳块单调对齐到角色台词，并冻结每角色等距片段。"""

    expected_parts = [normalize_zh_v1(row["text_content"]) for row in dialogues]
    expected_text = "".join(expected_parts)
    expected_roles: list[str] = []
    for row, part in zip(dialogues, expected_parts):
        expected_roles.extend([str(row["role_name"])] * len(part))

    hypothesis_parts = [normalize_zh_v1(chunk["text"]) for chunk in chunks]
    hypothesis_text = "".join(hypothesis_parts)
    chunk_ranges: list[tuple[int, int]] = []
    offset = 0
    for part in hypothesis_parts:
        chunk_ranges.append((offset, offset + len(part)))
        offset += len(part)

    matcher = SequenceMatcher(None, expected_text, hypothesis_text, autojunk=False)
    hypothesis_to_expected: dict[int, int] = {}
    matched_characters = 0
    for block in matcher.get_matching_blocks():
        for delta in range(block.size):
            hypothesis_to_expected[block.b + delta] = block.a + delta
        matched_characters += block.size

    alignment = config["alignment"]
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected = Counter()
    current: dict[str, Any] | None = None

    def finish_current() -> None:
        nonlocal current
        if current is None:
            return
        duration = current["end_seconds"] - current["start_seconds"]
        if current["exact_match_characters"] < int(alignment["min_exact_match_characters"]):
            rejected["too_few_exact_matches"] += 1
        elif duration < float(alignment["min_excerpt_seconds"]):
            rejected["too_short"] += 1
        else:
            current["match_ratio"] = (
                current["exact_match_characters"] / current["normalized_characters"]
            )
            current["role_purity"] = (
                current["role_exact_match_characters"]
                / current["exact_match_characters"]
            )
            current.pop("role_exact_match_characters")
            role = current.pop("role")
            candidates[role].append(current)
        current = None

    max_gap = float(alignment["max_merge_gap_seconds"])
    max_duration = float(alignment["max_excerpt_seconds"])
    def consume_piece(piece: dict[str, Any]) -> None:
        nonlocal current
        match_ratio = piece["exact_match_characters"] / piece["normalized_characters"]
        if match_ratio < float(alignment["min_chunk_match_ratio"]):
            finish_current()
            rejected["low_match_ratio"] += 1
            return
        duration = piece["end_seconds"] - piece["start_seconds"]
        if duration > max_duration:
            finish_current()
            rejected["too_long"] += 1
            return
        can_merge = (
            current is not None
            and current["role"] == piece["role"]
            and piece["start_seconds"] - current["end_seconds"] <= max_gap
            and piece["end_seconds"] - current["start_seconds"] <= max_duration
        )
        if not can_merge:
            finish_current()
            current = piece
        else:
            current["chunk_end_index"] = piece["chunk_end_index"]
            current["end_seconds"] = piece["end_seconds"]
            current["asr_text"] += piece["asr_text"]
            current["normalized_characters"] += piece["normalized_characters"]
            current["exact_match_characters"] += piece["exact_match_characters"]
            current["role_exact_match_characters"] += piece[
                "role_exact_match_characters"
            ]
            if "time_boundary_method" in piece:
                current["time_boundary_method"] = piece["time_boundary_method"]

    split_mixed_chunk_count = 0
    for index, (chunk, part, (start_index, end_index)) in enumerate(
        zip(chunks, hypothesis_parts, chunk_ranges)
    ):
        if not part:
            rejected["empty_after_normalization"] += 1
            continue
        expected_positions = [
            hypothesis_to_expected[position]
            for position in range(start_index, end_index)
            if position in hypothesis_to_expected
        ]
        matched = len(expected_positions)
        if matched == 0:
            finish_current()
            rejected["too_few_exact_matches"] += 1
            continue
        role_counts = Counter(expected_roles[position] for position in expected_positions)
        role, role_count = role_counts.most_common(1)[0]
        role_purity = role_count / matched
        if role_purity < float(alignment["min_role_purity"]):
            split_mixed_chunk_count += 1
            pieces = split_mixed_role_chunk(
                part=part,
                chunk=chunk,
                chunk_index=index,
                hypothesis_start_index=start_index,
                hypothesis_to_expected=hypothesis_to_expected,
                expected_roles=expected_roles,
            )
            for piece in pieces:
                consume_piece(piece)
            continue
        consume_piece(
            {
                "role": role,
                "chunk_index": index,
                "chunk_end_index": index,
                "start_seconds": float(chunk["start_seconds"]),
                "end_seconds": float(chunk["end_seconds"]),
                "asr_text": chunk["text"],
                "normalized_characters": len(part),
                "exact_match_characters": matched,
                "role_exact_match_characters": role_count,
            }
        )

    finish_current()

    limit = int(alignment["max_excerpts_per_role"])
    roles = {str(row["role_name"]) for row in dialogues}
    selected = {
        role: evenly_spaced(sorted(candidates.get(role, []), key=lambda item: item["start_seconds"]), limit)
        for role in sorted(roles)
    }
    missing = [role for role, items in selected.items() if not items]
    if missing:
        raise ValueError(f"Whisper 对齐后角色没有可用片段：{', '.join(missing)}")
    summary = {
        "expected_characters": len(expected_text),
        "hypothesis_characters": len(hypothesis_text),
        "exact_matched_characters": matched_characters,
        "exact_alignment_ratio_to_expected": matched_characters / len(expected_text),
        "chunk_count": len(chunks),
        "candidate_count_by_role": {role: len(candidates.get(role, [])) for role in sorted(roles)},
        "selected_count_by_role": {role: len(selected[role]) for role in sorted(roles)},
        "split_mixed_chunk_count": split_mixed_chunk_count,
        "rejected_chunk_counts": dict(sorted(rejected.items())),
    }
    return selected, summary


def load_mono_segment(
    path: Path,
    start_seconds: float,
    end_seconds: float,
    target_sample_rate: int,
) -> Any:
    """只读取一个时间片并下混单声道，避免重复加载整条长音频。"""

    np, sf, torch_audio = lazy_import_audio_stack()
    torch, torchaudio = torch_audio
    with sf.SoundFile(path) as file:
        source_rate = int(file.samplerate)
        start = max(0, round(start_seconds * source_rate))
        stop = min(len(file), round(end_seconds * source_rate))
        if stop <= start:
            raise ValueError(f"无效片段区间：{start_seconds:.3f}-{end_seconds:.3f}")
        file.seek(start)
        waveform = file.read(stop - start, dtype="float32", always_2d=True)
    mono = np.mean(waveform, axis=1)
    if source_rate == target_sample_rate:
        return mono
    tensor = torch.from_numpy(mono).unsqueeze(0)
    return (
        torchaudio.functional.resample(tensor, source_rate, target_sample_rate)
        .squeeze(0)
        .cpu()
        .numpy()
    )


def populate_alignment_excerpts(
    rows: list[dict[str, Any]],
    audio_rows: list[dict[str, Any]],
    dialogues: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    needed_model_ids = {row["model_id"] for row in rows}
    synthesis_audio_rows = {
        row["model_id"]: row
        for row in audio_rows
        if row["kind"] == "synthesis" and row["model_id"] in needed_model_ids
    }
    for model_id, audio_row in synthesis_audio_rows.items():
        whisper = audio_row.get("metrics", {}).get("whisper_cer")
        if not isinstance(whisper, dict) or not whisper.get("chunks"):
            raise ValueError(f"{model_id} 缺少 Whisper 时间戳；双 SIM 必须在 whisper_cer 完成后运行")
        selected, summary = align_role_excerpts(dialogues, whisper["chunks"], config)
        whisper["alignment_summary"] = summary
        for row in rows:
            if row["model_id"] == model_id:
                row["alignment_excerpts"] = selected[row["role"]]


def metric_summary(scores: list[float]) -> dict[str, Any]:
    if not scores:
        raise ValueError("不能汇总空分数")
    return {
        "mean": mean(scores),
        "min": min(scores),
        "max": max(scores),
        "std": pstdev(scores),
        "count": len(scores),
        "scores": scores,
    }


def apply_similarity_metric(
    metric: str,
    evaluator: Any,
    references: dict[str, AudioInput],
    syntheses: dict[str, AudioInput],
    rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    checkpoint: Callable[[], None],
) -> None:
    reference_embeddings: dict[str, Any] = {}

    def reference_embedding(role: str) -> Any:
        if role not in reference_embeddings:
            waveform, _ = load_mono_audio(references[role].path, evaluator.sample_rate_hz)
            reference_embeddings[role] = evaluator.embedding(waveform)
        return reference_embeddings[role]

    for index, row in enumerate(rows, 1):
        clear_metric_error(row, metric)
        try:
            synthesis = syntheses[row["model_id"]]
            scores = []
            for excerpt in row["alignment_excerpts"]:
                waveform = load_mono_segment(
                    synthesis.path,
                    float(excerpt["start_seconds"]),
                    float(excerpt["end_seconds"]),
                    evaluator.sample_rate_hz,
                )
                scores.append(cosine(reference_embedding(row["role"]), evaluator.embedding(waveform)))
            row["metrics"][metric] = metric_summary(scores)
        except Exception as exc:
            row["metrics"].pop(metric, None)
            row["errors"].append(metric_error(metric, exc))
        print(f"[{metric}] {index}/{len(rows)} {row['model_id']} / {row['role']}", flush=True)
        checkpoint()

    for row in calibration_rows:
        clear_metric_error(row, metric)
        try:
            left = references[row["left_role"]]
            right = references[row["right_role"]]
            if row["control_type"] == "same_speaker_split_half":
                waveform, _ = load_mono_audio(left.path, evaluator.sample_rate_hz)
                midpoint = len(waveform) // 2
                if midpoint < evaluator.sample_rate_hz:
                    raise ValueError("原始音频过短，无法构造至少一秒的前后半段校准对")
                left_embedding = evaluator.embedding(waveform[:midpoint])
                right_embedding = evaluator.embedding(waveform[midpoint:])
            else:
                left_embedding = reference_embedding(left.role)
                right_embedding = reference_embedding(right.role)
            row["metrics"][metric] = cosine(left_embedding, right_embedding)
        except Exception as exc:
            row["metrics"].pop(metric, None)
            row["errors"].append(metric_error(metric, exc))
        checkpoint()


def quality_intervals(
    duration_seconds: float,
    window_seconds: float,
    window_count: int,
) -> list[tuple[float, float]]:
    """按可容纳的不重叠窗数量确定样本数，再在全长上等距放置。"""

    if duration_seconds <= 0 or window_seconds <= 0 or window_count < 1:
        raise ValueError("自然度窗口参数必须为正数")
    if duration_seconds <= window_seconds:
        return [(0.0, duration_seconds)]
    effective_count = min(window_count, max(1, math.floor(duration_seconds / window_seconds)))
    if effective_count == 1:
        start = (duration_seconds - window_seconds) / 2
        return [(start, start + window_seconds)]
    last_start = duration_seconds - window_seconds
    starts = [index * last_start / (effective_count - 1) for index in range(effective_count)]
    return [(start, start + window_seconds) for start in starts]


def materialize_quality_windows(
    inputs: list[AudioInput],
    sampling: dict[str, Any],
    directory: Path,
) -> dict[str, list[QualityWindow]]:
    """在临时目录生成下混单声道窗口；目录随单个后端运行结束删除。"""

    np, sf, _ = lazy_import_audio_stack()
    result: dict[str, list[QualityWindow]] = {}
    for audio_index, audio in enumerate(inputs):
        duration = audio_duration(audio.path)
        intervals = quality_intervals(
            duration,
            float(sampling["window_seconds"]),
            int(sampling["window_count"]),
        )
        windows: list[QualityWindow] = []
        with sf.SoundFile(audio.path) as source:
            sample_rate = int(source.samplerate)
            for index, (start_seconds, end_seconds) in enumerate(intervals):
                start = max(0, round(start_seconds * sample_rate))
                stop = min(len(source), round(end_seconds * sample_rate))
                source.seek(start)
                waveform = source.read(stop - start, dtype="float32", always_2d=True)
                mono = np.mean(waveform, axis=1)
                path = directory / f"audio-{audio_index:02d}-window-{index:02d}.wav"
                sf.write(path, mono, sample_rate, subtype="PCM_16")
                windows.append(
                    QualityWindow(
                        audio_id=f"{audio.audio_id}:quality-window:{index}",
                        parent_audio_id=audio.audio_id,
                        index=index,
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        path=path,
                    )
                )
        result[audio.audio_id] = windows
    return result


def quality_metric_record(windows: list[QualityWindow], scores: list[float]) -> dict[str, Any]:
    summary = metric_summary(scores)
    summary["windows"] = [
        {
            "index": window.index,
            "start_seconds": window.start_seconds,
            "end_seconds": window.end_seconds,
            "score": score,
        }
        for window, score in zip(windows, scores)
    ]
    return summary


def apply_utmosv2(
    config: dict[str, Any],
    sampling: dict[str, Any],
    inputs: list[AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Callable[[], None],
) -> None:
    evaluator = UtmosV2Evaluator(config)
    try:
        with tempfile.TemporaryDirectory(prefix="task5-v4-utmos-") as temporary_dir:
            windows_by_audio = materialize_quality_windows(inputs, sampling, Path(temporary_dir))
            for index, row in enumerate(rows, 1):
                clear_metric_error(row, "utmosv2")
                try:
                    windows = windows_by_audio[row["audio_id"]]
                    scores = [evaluator.predict(window.path) for window in windows]
                    row["metrics"]["utmosv2"] = quality_metric_record(windows, scores)
                except Exception as exc:
                    row["metrics"].pop("utmosv2", None)
                    row["errors"].append(metric_error("utmosv2", exc))
                print(f"[utmosv2] {index}/{len(rows)} {row['audio_id']}", flush=True)
                checkpoint()
    finally:
        release_model(evaluator)


def apply_nisqa(
    config: dict[str, Any],
    sampling: dict[str, Any],
    inputs: list[AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Callable[[], None],
) -> None:
    with tempfile.TemporaryDirectory(prefix="task5-v4-nisqa-") as temporary_dir:
        windows_by_audio = materialize_quality_windows(inputs, sampling, Path(temporary_dir))
        input_by_id = {audio.audio_id: audio for audio in inputs}
        window_inputs: list[AudioInput] = []
        for audio in inputs:
            for window in windows_by_audio[audio.audio_id]:
                window_inputs.append(
                    AudioInput(
                        audio_id=window.audio_id,
                        kind=audio.kind,
                        model_id=audio.model_id,
                        run_id=None,
                        case_id=audio.case_id,
                        role=audio.role,
                        path=window.path,
                        sha256="temporary-window",
                        expected_text="",
                    )
                )
        try:
            scores_by_id = predict_nisqa_batch(config, window_inputs)
        except Exception as exc:
            for row in rows:
                clear_metric_error(row, "nisqa")
                row["metrics"].pop("nisqa", None)
                row["errors"].append(metric_error("nisqa", exc))
                checkpoint()
            return

        for row in rows:
            clear_metric_error(row, "nisqa")
            try:
                _ = input_by_id[row["audio_id"]]
                windows = windows_by_audio[row["audio_id"]]
                scores = [scores_by_id[window.audio_id] for window in windows]
                value = quality_metric_record(windows, scores)
                value["model"] = str(config["model_name"])
                row["metrics"]["nisqa"] = value
            except Exception as exc:
                row["metrics"].pop("nisqa", None)
                row["errors"].append(metric_error("nisqa", exc))
            checkpoint()


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in ["torch", "torchaudio", "transformers", "funasr", "speechbrain", "utmosv2"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def metric_coverage(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for metric in ["sensevoice_cer", "whisper_cer", "utmosv2", "nisqa"]:
        coverage[metric] = {
            "complete": sum(metric in row["metrics"] for row in audio_rows),
            "expected": len(audio_rows),
        }
    for metric in ["wavlm_sim", "speechbrain_ecapa_sim"]:
        combined = [*similarity_rows, *calibration_rows]
        coverage[metric] = {
            "complete": sum(metric in row["metrics"] for row in combined),
            "expected": len(combined),
        }
    return coverage


def scoped_metric_rows(
    metric: str,
    model_id: str,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """返回单模型调用对某个后端负责的记录，包含共享原始音频基线。"""

    if metric in {"sensevoice_cer", "whisper_cer", "utmosv2", "nisqa"}:
        return [
            row
            for row in audio_rows
            if row["kind"] == "reference" or row["model_id"] == model_id
        ]
    return [
        *[row for row in similarity_rows if row["model_id"] == model_id],
        *calibration_rows,
    ]


def missing_metric_rows(rows: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    """断点续跑时只返回尚未成功完成当前后端的记录。"""

    return [row for row in rows if metric not in row["metrics"]]


def scoped_metric_coverage(
    model_id: str,
    metrics: Iterable[str],
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """计算当前单模型及共享基线的覆盖，供严格模式和独立报告使用。"""

    return {
        metric: {
            "complete": sum(
                metric in row["metrics"]
                for row in scoped_metric_rows(
                    metric,
                    model_id,
                    audio_rows,
                    similarity_rows,
                    calibration_rows,
                )
            ),
            "expected": len(
                scoped_metric_rows(
                    metric,
                    model_id,
                    audio_rows,
                    similarity_rows,
                    calibration_rows,
                )
            ),
        }
        for metric in metrics
    }


def save_state(
    output_dir: Path,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    config: dict[str, Any],
    selected_metrics: list[str],
    active_model_id: str,
) -> None:
    write_jsonl_atomic(output_dir / "per_audio.jsonl", audio_rows)
    write_jsonl_atomic(output_dir / "speaker_similarity.jsonl", similarity_rows)
    write_jsonl_atomic(output_dir / "speaker_calibration.jsonl", calibration_rows)
    metadata = {
        "schema_version": "4.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "selected_metrics_this_invocation": selected_metrics,
        "active_model_id_this_invocation": active_model_id,
        "single_model_per_invocation": True,
        "offline": True,
        "cross_metric_weighted_score": False,
        "audio_count": len(audio_rows),
        "reference_audio_count": sum(row["kind"] == "reference" for row in audio_rows),
        "synthesis_audio_count": sum(row["kind"] == "synthesis" for row in audio_rows),
        "synthesis_role_pair_count": len(similarity_rows),
        "calibration_pair_count": len(calibration_rows),
        "coverage": metric_coverage(audio_rows, similarity_rows, calibration_rows),
        "package_versions": package_versions(),
        "config": config,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> int:
    """执行一次可断点续跑的 V4 长音频评测。"""

    config = load_json(args.config)
    validate_config(config)
    dialogues = load_dialogues(config)
    selected_metrics = list(dict.fromkeys(args.metrics))

    if args.output_dir.exists() and not args.resume:
        raise ValueError(f"输出目录已存在；如需续跑请增加 --resume：{args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=args.resume)

    references, syntheses = build_inputs(config, dialogues)
    configured_model_ids = {item.model_id for item in syntheses}
    if args.model_id not in configured_model_ids:
        raise ValueError(
            f"未知 --model-id：{args.model_id}；可选值：{', '.join(sorted(configured_model_ids))}"
        )
    all_inputs = [*references, *syntheses]
    inputs_by_id = {item.audio_id: item for item in all_inputs}
    references_by_role = {item.role: item for item in references}
    syntheses_by_model = {item.model_id: item for item in syntheses}
    audio_rows, similarity_rows, calibration_rows = restore_or_create_records(
        args.output_dir,
        references,
        syntheses,
        config,
        args.resume,
    )

    def checkpoint() -> None:
        save_state(
            args.output_dir,
            audio_rows,
            similarity_rows,
            calibration_rows,
            config,
            selected_metrics,
            args.model_id,
        )

    checkpoint()
    for metric in selected_metrics:
        scope = scoped_metric_rows(
            metric,
            args.model_id,
            audio_rows,
            similarity_rows,
            calibration_rows,
        )
        pending_rows = missing_metric_rows(scope, metric)
        print(
            f"开始评价：{metric}；本次唯一模型：{args.model_id}；"
            f"待处理 {len(pending_rows)}/{len(scope)} 条",
            flush=True,
        )
        if not pending_rows:
            continue
        if metric == "sensevoice_cer":
            apply_sensevoice(config["sensevoice"], inputs_by_id, pending_rows, checkpoint)
        elif metric == "whisper_cer":
            apply_whisper(config["whisper"], inputs_by_id, pending_rows, checkpoint)
        elif metric in {"wavlm_sim", "speechbrain_ecapa_sim"}:
            model_similarity_rows = [
                row for row in similarity_rows if row["model_id"] == args.model_id
            ]
            populate_alignment_excerpts(model_similarity_rows, audio_rows, dialogues, config)
            evaluator = (
                WavLMSpeakerEvaluator(config["wavlm"], allow_model_download=False)
                if metric == "wavlm_sim"
                else SpeechBrainEcapaEvaluator(config["speechbrain_ecapa"])
            )
            try:
                apply_similarity_metric(
                    metric,
                    evaluator,
                    references_by_role,
                    syntheses_by_model,
                    [row for row in pending_rows if "model_id" in row],
                    [row for row in pending_rows if "control_type" in row],
                    checkpoint,
                )
            finally:
                release_model(evaluator)
        elif metric == "utmosv2":
            pending_ids = {row["audio_id"] for row in pending_rows}
            pending_inputs = [item for item in all_inputs if item.audio_id in pending_ids]
            apply_utmosv2(
                config["utmosv2"],
                config["quality_sampling"],
                pending_inputs,
                pending_rows,
                checkpoint,
            )
        elif metric == "nisqa":
            pending_ids = {row["audio_id"] for row in pending_rows}
            pending_inputs = [item for item in all_inputs if item.audio_id in pending_ids]
            apply_nisqa(
                config["nisqa"],
                config["quality_sampling"],
                pending_inputs,
                pending_rows,
                checkpoint,
            )
        checkpoint()
        gc.collect()

    coverage = metric_coverage(audio_rows, similarity_rows, calibration_rows)
    model_coverage = scoped_metric_coverage(
        args.model_id,
        METRICS,
        audio_rows,
        similarity_rows,
        calibration_rows,
    )
    print(
        json.dumps(
            {"model_id": args.model_id, "model_coverage": model_coverage, "global_coverage": coverage},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    incomplete = [
        metric
        for metric in selected_metrics
        if model_coverage[metric]["complete"] != model_coverage[metric]["expected"]
    ]
    if args.strict and incomplete:
        print(f"以下后端结果不完整：{', '.join(incomplete)}", file=sys.stderr)
        return 2
    all_model_metrics_complete = all(
        item["complete"] == item["expected"] for item in model_coverage.values()
    )
    if all_model_metrics_complete:
        from generate_neutral_v4_reports import write_model_report

        report_path = write_model_report(args.output_dir, args.reports_dir, args.model_id)
        print(f"单模型评价报告：{report_path}", flush=True)
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"V4 长音频中立评测失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
