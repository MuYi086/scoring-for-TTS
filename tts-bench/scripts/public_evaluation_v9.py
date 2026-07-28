#!/usr/bin/env python3
"""执行 Task 9 V9 的受限公共长音频评测。

该入口只运行公共任务允许的长音频观测：音频交付原始测量、SenseVoice
CER（字符错误率）和 Whisper-large-v3-turbo CER。它刻意不导入长音频
SIM、UTMOSv2 或 NISQA，也不会计算跨指标综合分。
"""

from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_automated_evaluation import (  # noqa: E402
    SenseVoiceAsrEvaluator,
    WhisperAsrEvaluator,
    character_error_rate,
    normalize_zh_v1,
    project_path,
    project_relative_path,
    sha256_file,
)


PUBLIC_METRICS = ("audio_delivery", "sensevoice_cer", "whisper_cer")


@dataclass(frozen=True)
class AudioInput:
    """一个已核验哈希、可供 ASR 或交付测量的音频输入。"""

    audio_id: str
    kind: str
    model_id: str
    case_id: str
    role: str
    path: Path
    sha256: str
    expected_text: str


def load_json(path: Path) -> dict[str, Any]:
    """读取并校验一个 JSON 对象。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到冻结配置：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"冻结配置不是有效 JSON：{path} ({exc})") from exc
    if not isinstance(value, dict):
        raise ValueError("冻结配置顶层必须是对象")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL（JSON Lines，逐行 JSON）文件。"""

    if not path.is_file():
        raise ValueError(f"找不到原始结果：{path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} 不是有效 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} 必须是 JSON 对象")
        rows.append(value)
    if not rows:
        raise ValueError(f"原始结果为空：{path}")
    return rows


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """以原子替换方式保存 JSONL，避免中断写出半份结果。"""

    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_config(
    config: dict[str, Any], *, expected_schema_version: str = "9.0", version_label: str = "V9"
) -> None:
    """校验会改变受限公共评测统计对象或范围的冻结字段。"""

    if config.get("schema_version") != expected_schema_version:
        raise ValueError(
            f"公共 {version_label} 入口只支持 schema_version={expected_schema_version}"
        )
    if config.get("evaluation_profile") != "public-task-restricted":
        raise ValueError(f"{version_label} 配置必须声明 public-task-restricted 评测范围")
    policy = config.get("policy", {})
    if policy.get("normalization_id") != "zh-v1":
        raise ValueError("当前只支持 zh-v1 文本规范化")
    if tuple(policy.get("long_audio_metrics", ())) != PUBLIC_METRICS:
        raise ValueError(f"长音频指标必须严格为：{', '.join(PUBLIC_METRICS)}")
    prohibited = set(policy.get("prohibited_long_audio_metrics", ()))
    required_prohibited = {
        "wavlm_sim",
        "speechbrain_ecapa_sim",
        "utmosv2",
        "nisqa",
        "cross_metric_weighted_score",
    }
    if not required_prohibited <= prohibited:
        raise ValueError(f"{version_label} 配置没有完整禁止公共任务排除的长音频指标或综合分")

    source = config.get("source", {})
    required_source = {
        "raw_text_path",
        "raw_text_sha256",
        "dialogue_path",
        "dialogue_sha256",
        "dialogue_count",
        "normalized_character_count",
        "raw_text_normalized_character_count",
        "cer_reference",
    }
    if required_source - set(source):
        raise ValueError(f"source 缺少 {version_label} 台词串冻结字段")
    if source.get("cer_reference") != "ai_deal_dialogue_concatenation":
        raise ValueError("全文 CER 参考必须为 ai_deal.json 的 dialogue 台词串")

    models = config.get("models", [])
    references = config.get("references", [])
    if len(models) != int(config.get("expected_model_count", -1)):
        raise ValueError("models 数量与 expected_model_count 不一致")
    if len(references) != int(config.get("expected_reference_count", -1)):
        raise ValueError("references 数量与 expected_reference_count 不一致")
    if len({item.get("model_id") for item in models}) != len(models):
        raise ValueError("models 中存在空值或重复 model_id")
    if len({item.get("role") for item in references}) != len(references):
        raise ValueError("references 中存在空值或重复角色")
    for item in [*models, *references]:
        if not item.get("audio_path") or not item.get("sha256"):
            raise ValueError("模型与参考音频必须冻结路径和 SHA-256")

    for backend in ("sensevoice", "whisper"):
        section = config.get(backend, {})
        for key in ("model_id", "revision", "model_sha256", "device", "long_audio_chunk_seconds"):
            if key not in section:
                raise ValueError(f"{backend} 缺少冻结字段：{key}")
        chunk_seconds = float(section["long_audio_chunk_seconds"])
        if not 0 < chunk_seconds <= 60:
            raise ValueError(f"{backend}.long_audio_chunk_seconds 必须在 (0, 60] 秒内")
    if config["whisper"].get("model_id") != "openai/whisper-large-v3-turbo":
        raise ValueError("第二个 CER 后端必须是 Whisper-large-v3-turbo，不能替换为原版 large-v3")

    delivery = config.get("audio_delivery", {}).get("measurement", {})
    for key in (
        "clip_sample_threshold",
        "silence_threshold_dbfs",
        "analysis_window_seconds",
        "reported_silence_minimum_seconds",
    ):
        if key not in delivery:
            raise ValueError(f"audio_delivery.measurement 缺少冻结测量参数：{key}")
    if not 0 < float(delivery["clip_sample_threshold"]) <= 1:
        raise ValueError("clip_sample_threshold 必须在 (0, 1] 内")
    if float(delivery["analysis_window_seconds"]) <= 0:
        raise ValueError("analysis_window_seconds 必须大于 0")
    if float(delivery["reported_silence_minimum_seconds"]) <= 0:
        raise ValueError("reported_silence_minimum_seconds 必须大于 0")
    for check in ("forced_alignment", "role_routing"):
        if config.get("checks", {}).get(check, {}).get("status") != "not_configured":
            raise ValueError(f"{check} 未实现时必须冻结为 not_configured")


def load_dialogues(config: dict[str, Any]) -> list[dict[str, Any]]:
    """读取实际参与合成的台词，并验证文本事实源和角色集合。"""

    source = config["source"]
    dialogue_path = project_path(source["dialogue_path"])
    raw_text_path = project_path(source["raw_text_path"])
    for path, expected_hash in (
        (dialogue_path, source["dialogue_sha256"]),
        (raw_text_path, source["raw_text_sha256"]),
    ):
        if not path.is_file():
            raise ValueError(f"找不到 V9 输入文件：{path}")
        if sha256_file(path) != expected_hash:
            raise ValueError(f"V9 输入文件 SHA-256 与冻结配置不一致：{path}")
    try:
        source_rows = json.loads(dialogue_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"ai_deal.json 不是有效 JSON：{dialogue_path}") from exc
    if not isinstance(source_rows, list):
        raise ValueError("ai_deal.json 顶层必须是数组")
    dialogues = [row for row in source_rows if isinstance(row, dict) and row.get("type") == "dialogue"]
    if len(dialogues) != int(source["dialogue_count"]):
        raise ValueError(f"ai_deal.json dialogue 数量应为 {source['dialogue_count']}，实际 {len(dialogues)}")
    if any(not row.get("role_name") or not row.get("text_content") for row in dialogues):
        raise ValueError("ai_deal.json 存在缺少 role_name 或 text_content 的 dialogue")
    dialogue_normalized = "".join(normalize_zh_v1(str(row["text_content"])) for row in dialogues)
    if len(dialogue_normalized) != int(source["normalized_character_count"]):
        raise ValueError(
            "ai_deal.json 规范化字符数应为 "
            f"{source['normalized_character_count']}，实际 {len(dialogue_normalized)}"
        )
    raw_count = len(normalize_zh_v1(raw_text_path.read_text(encoding="utf-8")))
    if raw_count != int(source["raw_text_normalized_character_count"]):
        raise ValueError(
            "text.md 规范化字符数应为 "
            f"{source['raw_text_normalized_character_count']}，实际 {raw_count}"
        )
    configured_roles = {str(item["role"]) for item in config["references"]}
    dialogue_roles = {str(row["role_name"]) for row in dialogues}
    if configured_roles != dialogue_roles:
        raise ValueError(f"角色集合与参考音频不一致：台词 {sorted(dialogue_roles)}，参考 {sorted(configured_roles)}")
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
    """构建一个已验证路径与哈希的输入记录。"""

    path = project_path(path_value)
    if not path.is_file():
        raise ValueError(f"找不到 V9 音频：{path}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_sha256:
        raise ValueError(f"V9 音频 SHA-256 与冻结配置不一致：{path}")
    return AudioInput(
        audio_id=audio_id,
        kind=kind,
        model_id=model_id,
        case_id=case_id,
        role=role,
        path=path,
        sha256=actual_hash,
        expected_text=expected_text,
    )


def build_inputs(config: dict[str, Any], dialogues: list[dict[str, Any]]) -> tuple[list[AudioInput], list[AudioInput]]:
    """从冻结配置构建五条参考与七条完整有声书输入。"""

    expected_text = "".join(str(row["text_content"]) for row in dialogues)
    references = [
        input_from_config(
            audio_id=f"reference:{item['role']}",
            kind="reference",
            model_id="原始参考音频",
            case_id=f"reference:{item['role']}",
            role=str(item["role"]),
            path_value=str(item["audio_path"]),
            expected_sha256=str(item["sha256"]),
            expected_text=str(item["transcript"]),
        )
        for item in config["references"]
    ]
    syntheses = [
        input_from_config(
            audio_id=f"synthesis:{item['model_id']}",
            kind="synthesis",
            model_id=str(item["model_id"]),
            case_id=str(config["source"].get("case_id", "task9_v9_full_audiobook")),
            role="完整有声书",
            path_value=str(item["audio_path"]),
            expected_sha256=str(item["sha256"]),
            expected_text=expected_text,
        )
        for item in config["models"]
    ]
    return references, syntheses


def audio_base_record(audio: Any, schema_version: str) -> dict[str, Any]:
    """把冻结输入转成公共评测的单音频原始记录。"""

    return {
        "schema_version": schema_version,
        "audio_id": audio.audio_id,
        "kind": audio.kind,
        "model_id": audio.model_id,
        "case_id": audio.case_id,
        "role": audio.role,
        "audio": {
            "path": project_relative_path(audio.path),
            "sha256": audio.sha256,
        },
        "expected_text": audio.expected_text,
        "metrics": {},
        "errors": [],
    }


def clear_metric_error(row: dict[str, Any], metric: str) -> None:
    row["errors"] = [item for item in row.get("errors", []) if item.get("metric") != metric]


def metric_error(metric: str, exc: Exception) -> dict[str, str]:
    return {"metric": metric, "error": str(exc)}


def dbfs(value: float) -> float:
    return 20 * math.log10(max(value, 1e-12))


def measure_audio_delivery(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    """解码并记录无阈值裁决的交付观测值。

    未给定发布渠道的硬性格式和响度规范时，本函数绝不判定通过或失败；仅输出
    可复核的格式、削波、直流偏置和静音区间。采样峰值并不冒充最大真峰值。
    """

    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("音频交付测量需要 numpy 和 soundfile") from exc

    measurement = config["measurement"]
    clip_threshold = float(measurement["clip_sample_threshold"])
    silence_threshold_dbfs = float(measurement["silence_threshold_dbfs"])
    window_seconds = float(measurement["analysis_window_seconds"])
    reported_minimum = float(measurement["reported_silence_minimum_seconds"])
    silence_linear = 10 ** (silence_threshold_dbfs / 20)

    info = sf.info(path)
    if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
        raise ValueError("音频为空或缺少有效格式信息")
    window_frames = max(1, round(window_seconds * info.samplerate))
    frame_count = 0
    absolute_sum = 0.0
    sample_peak = 0.0
    clipped_samples = 0
    windows: list[tuple[float, float, bool]] = []
    with sf.SoundFile(path) as source:
        while True:
            waveform = source.read(window_frames, dtype="float32", always_2d=True)
            if not len(waveform):
                break
            mono = np.mean(waveform, axis=1)
            absolute = np.abs(mono)
            frame_count += len(mono)
            absolute_sum += float(np.sum(mono))
            sample_peak = max(sample_peak, float(np.max(absolute)))
            clipped_samples += int(np.count_nonzero(absolute >= clip_threshold))
            rms = float(np.sqrt(np.mean(np.square(mono))))
            start = (frame_count - len(mono)) / info.samplerate
            end = frame_count / info.samplerate
            windows.append((start, end, rms <= silence_linear))

    if frame_count != info.frames:
        raise ValueError(f"解码帧数不一致：header={info.frames}，decoded={frame_count}")
    silence_runs: list[dict[str, float]] = []
    active_start: float | None = None
    active_end: float | None = None
    for start, end, is_silent in windows:
        if is_silent:
            if active_start is None:
                active_start = start
            active_end = end
        elif active_start is not None and active_end is not None:
            if active_end - active_start >= reported_minimum:
                silence_runs.append(
                    {
                        "start_seconds": active_start,
                        "end_seconds": active_end,
                        "duration_seconds": active_end - active_start,
                    }
                )
            active_start = None
            active_end = None
    if active_start is not None and active_end is not None and active_end - active_start >= reported_minimum:
        silence_runs.append(
            {
                "start_seconds": active_start,
                "end_seconds": active_end,
                "duration_seconds": active_end - active_start,
            }
        )

    duration_seconds = frame_count / info.samplerate
    leading_seconds = silence_runs[0]["duration_seconds"] if silence_runs and silence_runs[0]["start_seconds"] == 0 else 0.0
    trailing_seconds = (
        silence_runs[-1]["duration_seconds"]
        if silence_runs and abs(silence_runs[-1]["end_seconds"] - duration_seconds) < 1e-9
        else 0.0
    )
    return {
        "decode_status": "decoded",
        "file_bytes": path.stat().st_size,
        "format": {
            "sample_rate_hz": int(info.samplerate),
            "channels": int(info.channels),
            "subtype": str(info.subtype),
            "frames": int(info.frames),
            "duration_seconds": duration_seconds,
        },
        "sample_peak_dbfs": dbfs(sample_peak),
        "dc_offset": absolute_sum / frame_count,
        "clipping": {
            "measurement_threshold": clip_threshold,
            "sample_count_at_or_above_threshold": clipped_samples,
            "ratio": clipped_samples / frame_count,
        },
        "silence": {
            "measurement_window_seconds": window_seconds,
            "threshold_dbfs": silence_threshold_dbfs,
            "reported_minimum_seconds": reported_minimum,
            "leading_seconds": leading_seconds,
            "trailing_seconds": trailing_seconds,
            "runs": silence_runs,
        },
        "format_contract": config["format_contract"],
        "loudness_and_true_peak": {
            "status": "not_executed",
            "reason": config["loudness_contract"]["reason"],
        },
    }


def scoped_rows(rows: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    """返回当前单模型调用所需的共享参考与唯一成品。"""

    return [
        row
        for row in rows
        if row["kind"] == "reference" or row["model_id"] == model_id
    ]


def metric_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """统计全部音频记录的逐指标覆盖。"""

    return {
        metric: {
            "complete": sum(metric in row.get("metrics", {}) for row in rows),
            "expected": len(rows),
        }
        for metric in PUBLIC_METRICS
    }


def scoped_coverage(rows: list[dict[str, Any]], model_id: str) -> dict[str, dict[str, int]]:
    scope = scoped_rows(rows, model_id)
    return {
        metric: {
            "complete": sum(metric in row.get("metrics", {}) for row in scope),
            "expected": len(scope),
        }
        for metric in PUBLIC_METRICS
    }


def package_versions() -> dict[str, str | None]:
    """记录关键运行包版本；缺包保留为空以便审计。"""

    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover - Python 3.10+ 始终可用。
        return {}
    values: dict[str, str | None] = {}
    for package in ("torch", "torchaudio", "funasr", "transformers", "soundfile", "scipy", "jiwer"):
        try:
            values[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            values[package] = None
    return values


def environment_snapshot() -> dict[str, Any]:
    """把本次环境冻结到结果目录；不把机器路径写入仓库配置。"""

    try:
        pip_freeze = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pip_freeze = []
    gpu: dict[str, Any] = {"available": False}
    try:
        import torch

        gpu = {
            "available": bool(torch.cuda.is_available()),
            "torch_cuda": torch.version.cuda,
            "device_count": int(torch.cuda.device_count()),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    except ImportError:
        pass
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "package_versions": package_versions(),
        "pip_freeze": pip_freeze,
        "gpu": gpu,
        "offline_environment": {
            key: os.environ.get(key)
            for key in ("HF_MIRROR_ROOT", "HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        },
    }


def implementation_snapshot() -> dict[str, str]:
    """记录本入口与复用 ASR 代码的内容哈希。"""

    paths = [
        Path(__file__).resolve(),
        SCRIPT_DIR / "run_automated_evaluation.py",
    ]
    return {project_relative_path(path): sha256_file(path) for path in paths}


def create_metadata(config: dict[str, Any]) -> dict[str, Any]:
    """创建一次新运行不可变的元数据骨架。"""

    return {
        "schema_version": config["schema_version"],
        "evaluation_profile": config["evaluation_profile"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "single_model_per_invocation": True,
        "cross_metric_weighted_score": False,
        "long_audio_metrics": list(PUBLIC_METRICS),
        "prohibited_long_audio_metrics": config["policy"]["prohibited_long_audio_metrics"],
        "environment": environment_snapshot(),
        "implementation": implementation_snapshot(),
        "unexecuted_checks": config["checks"],
        "config": config,
    }


def save_state(
    output_dir: Path,
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    selected_metrics: list[str],
    active_model_id: str,
) -> None:
    """持久化逐音频记录及其当前覆盖范围。"""

    write_jsonl_atomic(output_dir / "per_audio.jsonl", rows)
    metadata.update(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "selected_metrics_this_invocation": selected_metrics,
            "active_model_id_this_invocation": active_model_id,
            "audio_count": len(rows),
            "reference_audio_count": sum(row["kind"] == "reference" for row in rows),
            "synthesis_audio_count": sum(row["kind"] == "synthesis" for row in rows),
            "coverage": metric_coverage(rows),
        }
    )
    temporary = output_dir / ".run_metadata.json.tmp"
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_dir / "run_metadata.json")


def restore_or_create(
    output_dir: Path,
    config: dict[str, Any],
    inputs: list[Any],
    resume: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """恢复同一次运行或创建新记录；拒绝覆盖旧结果。"""

    if resume:
        metadata_path = output_dir / "run_metadata.json"
        if not metadata_path.is_file():
            raise ValueError("--resume 要求 run_metadata.json 已存在")
        metadata = load_json(metadata_path)
        if metadata.get("config") != config:
            raise ValueError("--resume 的已有结果配置与当前冻结配置不一致")
        rows = read_jsonl(output_dir / "per_audio.jsonl")
        expected_ids = {item.audio_id for item in inputs}
        if {row.get("audio_id") for row in rows} != expected_ids:
            raise ValueError("--resume 的逐音频记录与冻结输入集合不一致")
        return rows, metadata
    return [audio_base_record(audio, config["schema_version"]) for audio in inputs], create_metadata(config)


def apply_audio_delivery(
    config: dict[str, Any],
    inputs_by_id: dict[str, Any],
    rows: list[dict[str, Any]],
    checkpoint: Any,
) -> None:
    """测量当前范围内尚未完成的音频交付字段。"""

    pending = [row for row in rows if "audio_delivery" not in row["metrics"]]
    for index, row in enumerate(pending, 1):
        clear_metric_error(row, "audio_delivery")
        try:
            row["metrics"]["audio_delivery"] = measure_audio_delivery(
                inputs_by_id[row["audio_id"]].path,
                config["audio_delivery"],
            )
        except Exception as exc:  # 单条不可解码音频仍保留其他模型的测量机会。
            row["metrics"].pop("audio_delivery", None)
            row["errors"].append(metric_error("audio_delivery", exc))
        print(f"[audio_delivery] {index}/{len(pending)} {row['audio_id']}", flush=True)
        checkpoint()


def intervals(duration_seconds: float, chunk_seconds: float) -> list[tuple[float, float]]:
    """以连续、不重叠分段覆盖整条音频。"""

    if duration_seconds <= 0 or chunk_seconds <= 0:
        raise ValueError("长音频分段参数必须为正数")
    result: list[tuple[float, float]] = []
    start = 0.0
    while start < duration_seconds:
        end = min(duration_seconds, start + chunk_seconds)
        result.append((start, end))
        start = end
    return result


def transcribe_sensevoice_long_audio(
    evaluator: Any, path: Path, chunk_seconds: float, audio_id: str
) -> dict[str, Any]:
    """顺序转写固定分段，避免一次把完整有声书交给 SenseVoice。"""

    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("SenseVoice 分段转写需要 numpy 和 soundfile") from exc
    info = sf.info(path)
    plan = intervals(float(info.duration), chunk_seconds)
    segments: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="task9-v9-sensevoice-") as temporary_dir:
        with sf.SoundFile(path) as source:
            for index, (start_seconds, end_seconds) in enumerate(plan):
                start = min(info.frames, round(start_seconds * info.samplerate))
                stop = min(info.frames, round(end_seconds * info.samplerate))
                if stop <= start:
                    raise ValueError(f"SenseVoice 分段区间无效：{start_seconds:.3f}-{end_seconds:.3f}")
                source.seek(start)
                waveform = source.read(stop - start, dtype="float32", always_2d=True)
                mono = np.mean(waveform, axis=1)
                segment_path = Path(temporary_dir) / f"segment-{index:04d}.wav"
                sf.write(segment_path, mono, info.samplerate, subtype="PCM_16")
                text = evaluator.transcribe(segment_path)
                segments.append(
                    {
                        "index": index,
                        "start_seconds": start / info.samplerate,
                        "end_seconds": stop / info.samplerate,
                        "text": text,
                    }
                )
                print(f"[sensevoice_cer] {audio_id} 分段 {index + 1}/{len(plan)}", flush=True)
    return {"text": "".join(item["text"] for item in segments), "segments": segments}


def transcribe_whisper_long_audio(
    evaluator: Any, path: Path, return_timestamps: str, chunk_seconds: float, audio_id: str
) -> dict[str, Any]:
    """顺序转写固定分段并保留全局字词时间戳，供人工复核而非角色 SIM。"""

    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Whisper 分段转写需要 numpy 和 soundfile") from exc
    info = sf.info(path)
    plan = intervals(float(info.duration), chunk_seconds)
    segments: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="task9-v9-whisper-") as temporary_dir:
        with sf.SoundFile(path) as source:
            for index, (start_seconds, end_seconds) in enumerate(plan):
                start = min(info.frames, round(start_seconds * info.samplerate))
                stop = min(info.frames, round(end_seconds * info.samplerate))
                if stop <= start:
                    raise ValueError(f"Whisper 分段区间无效：{start_seconds:.3f}-{end_seconds:.3f}")
                source.seek(start)
                waveform = source.read(stop - start, dtype="float32", always_2d=True)
                mono = np.mean(waveform, axis=1)
                segment_path = Path(temporary_dir) / f"segment-{index:04d}.wav"
                sf.write(segment_path, mono, info.samplerate, subtype="PCM_16")
                result = evaluator.pipeline(
                    str(segment_path),
                    generate_kwargs=evaluator.generate_kwargs,
                    return_timestamps=return_timestamps,
                )
                if not isinstance(result, dict) or not isinstance(result.get("text"), str):
                    raise RuntimeError(f"Whisper 第 {index + 1} 段未返回 text 字段")
                raw_chunks = result.get("chunks")
                if not isinstance(raw_chunks, list):
                    raise RuntimeError(f"Whisper 第 {index + 1} 段未返回字词时间戳")
                actual_start = start / info.samplerate
                actual_end = stop / info.samplerate
                cleaned = 0
                for chunk in raw_chunks:
                    if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
                        continue
                    timestamp = chunk.get("timestamp")
                    if (
                        not isinstance(timestamp, (list, tuple))
                        or len(timestamp) != 2
                        or timestamp[0] is None
                        or timestamp[1] is None
                    ):
                        continue
                    chunk_start = max(actual_start, actual_start + float(timestamp[0]))
                    chunk_end = min(actual_end, actual_start + float(timestamp[1]))
                    if chunk_end > chunk_start:
                        chunks.append(
                            {
                                "text": chunk["text"],
                                "start_seconds": chunk_start,
                                "end_seconds": chunk_end,
                                "segment_index": index,
                            }
                        )
                        cleaned += 1
                if not cleaned:
                    raise RuntimeError(f"Whisper 第 {index + 1} 段没有可用的正时长字词时间戳")
                segments.append(
                    {
                        "index": index,
                        "start_seconds": actual_start,
                        "end_seconds": actual_end,
                        "text": result["text"],
                    }
                )
                print(f"[whisper_cer] {audio_id} 分段 {index + 1}/{len(plan)}", flush=True)
    return {"text": "".join(item["text"] for item in segments), "segments": segments, "chunks": chunks}


def release_model(evaluator: Any) -> None:
    """在两个 ASR 后端之间释放显存。"""

    del evaluator
    try:
        import gc
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        return


def apply_sensevoice(
    config: dict[str, Any],
    inputs_by_id: dict[str, AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Any,
) -> None:
    """计算 SenseVoice CER 并在每条结果后检查点保存。"""

    evaluator = SenseVoiceAsrEvaluator(config)
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, "sensevoice_cer")
            try:
                result = transcribe_sensevoice_long_audio(
                    evaluator,
                    inputs_by_id[row["audio_id"]].path,
                    float(config["long_audio_chunk_seconds"]),
                    row["audio_id"],
                )
                reference = normalize_zh_v1(row["expected_text"])
                hypothesis = normalize_zh_v1(result["text"])
                row["metrics"]["sensevoice_cer"] = {
                    "hypothesis_raw": result["text"],
                    "segments": result["segments"],
                    "normalization_id": "zh-v1",
                    "reference_normalized": reference,
                    "hypothesis_normalized": hypothesis,
                    "cer": character_error_rate(reference, hypothesis),
                }
            except Exception as exc:
                row["metrics"].pop("sensevoice_cer", None)
                row["errors"].append(metric_error("sensevoice_cer", exc))
            print(f"[sensevoice_cer] {index}/{len(rows)} {row['audio_id']}", flush=True)
            checkpoint()
    finally:
        release_model(evaluator)


def apply_whisper(
    config: dict[str, Any],
    inputs_by_id: dict[str, AudioInput],
    rows: list[dict[str, Any]],
    checkpoint: Any,
) -> None:
    """计算 Whisper-large-v3-turbo CER 并保存分段与字词时间戳。"""

    evaluator = WhisperAsrEvaluator(config, allow_model_download=False)
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, "whisper_cer")
            try:
                result = transcribe_whisper_long_audio(
                    evaluator,
                    inputs_by_id[row["audio_id"]].path,
                    str(config["return_timestamps"]),
                    float(config["long_audio_chunk_seconds"]),
                    row["audio_id"],
                )
                reference = normalize_zh_v1(row["expected_text"])
                hypothesis = normalize_zh_v1(result["text"])
                row["metrics"]["whisper_cer"] = {
                    "hypothesis_raw": result["text"],
                    "segments": result["segments"],
                    "chunks": result["chunks"],
                    "normalization_id": "zh-v1",
                    "reference_normalized": reference,
                    "hypothesis_normalized": hypothesis,
                    "cer": character_error_rate(reference, hypothesis),
                }
            except Exception as exc:
                row["metrics"].pop("whisper_cer", None)
                row["errors"].append(metric_error("whisper_cer", exc))
            print(f"[whisper_cer] {index}/{len(rows)} {row['audio_id']}", flush=True)
            checkpoint()
    finally:
        release_model(evaluator)


def run(
    args: Any, *, expected_schema_version: str = "9.0", version_label: str = "V9"
) -> int:
    """执行一次单模型受限评测。"""

    config = load_json(args.config)
    validate_config(
        config,
        expected_schema_version=expected_schema_version,
        version_label=version_label,
    )
    if not os.environ.get("HF_MIRROR_ROOT"):
        raise ValueError(f"必须设置 HF_MIRROR_ROOT，公共 {version_label} 评测不允许隐式联网下载")
    dialogues = load_dialogues(config)
    references, syntheses = build_inputs(config, dialogues)
    configured_models = {item.model_id for item in syntheses}
    if args.model_id not in configured_models:
        raise ValueError(f"未知 --model-id：{args.model_id}；可选值：{', '.join(sorted(configured_models))}")
    selected_metrics = list(dict.fromkeys(args.metrics))
    if not selected_metrics or not set(selected_metrics) <= set(PUBLIC_METRICS):
        raise ValueError(f"只能选择公共指标：{', '.join(PUBLIC_METRICS)}")
    if args.output_dir.exists() and not args.resume:
        raise ValueError(f"输出目录已存在；仅续跑同一次评测时可使用 --resume：{args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=args.resume)
    all_inputs = [*references, *syntheses]
    inputs_by_id = {item.audio_id: item for item in all_inputs}
    rows, metadata = restore_or_create(args.output_dir, config, all_inputs, args.resume)

    def checkpoint() -> None:
        save_state(args.output_dir, rows, metadata, selected_metrics, args.model_id)

    checkpoint()
    scope = scoped_rows(rows, args.model_id)
    for metric in selected_metrics:
        pending = [row for row in scope if metric not in row["metrics"]]
        print(
            f"开始公共评测：{metric}；本次唯一模型：{args.model_id}；待处理 {len(pending)}/{len(scope)} 条",
            flush=True,
        )
        if not pending:
            continue
        if metric == "audio_delivery":
            apply_audio_delivery(config, inputs_by_id, scope, checkpoint)
        elif metric == "sensevoice_cer":
            apply_sensevoice(config["sensevoice"], inputs_by_id, pending, checkpoint)
        elif metric == "whisper_cer":
            apply_whisper(config["whisper"], inputs_by_id, pending, checkpoint)
        checkpoint()

    coverage = scoped_coverage(rows, args.model_id)
    print(
        json.dumps(
            {"model_id": args.model_id, "model_coverage": coverage, "global_coverage": metric_coverage(rows)},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    incomplete = [metric for metric in selected_metrics if coverage[metric]["complete"] != coverage[metric]["expected"]]
    if args.strict and incomplete:
        print(f"以下公共指标结果不完整：{', '.join(incomplete)}", file=sys.stderr)
        return 2
    return 0
