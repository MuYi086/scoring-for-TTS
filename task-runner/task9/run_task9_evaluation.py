#!/usr/bin/env python3
"""Task 9 V9 长音频的受限公共评测入口。

每次仅评测一个模型成品，严格使用 ``longAudioTestV9/text.md`` 作为全文
CER（字符错误率）参考。该入口只运行 SenseVoiceSmall 与
Whisper-large-v3-turbo，并报告音频交付的原始测量；不加载旧版六后端指标，
也不产生跨量纲综合分。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

from synthesis_evidence import EVIDENCE_SCHEMA_VERSION, load_verified_synthesis_evidence
from text_segments import load_segment_plan, read_synthesis_text


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
DEFAULT_CONTRACT = TASK_DIR / "evaluation-contract.json"
SENSEVOICE_CONTROL_TAG = re.compile(r"<\|[^|>]+\|>")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT, help="冻结的机器可读评测契约")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="本次原始结果目录；首次必须是尚不存在的新目录",
    )
    parser.add_argument("--model-id", required=True, help="本次唯一允许评测的模型标识")
    parser.add_argument(
        "--hf-mirror-root",
        type=Path,
        default=os.getenv("HF_MIRROR_ROOT"),
        help="评价模型的本地镜像根目录；默认读取 HF_MIRROR_ROOT",
    )
    parser.add_argument("--resume", action="store_true", help="仅续跑同一未完成结果目录")
    parser.add_argument("--strict", action="store_true", help="任一已选后端失败时以非零状态退出")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_zh_v1(text: str) -> str:
    """与项目 zh-v1 规则一致：NFKC、小写、移除空白和 Unicode 标点。"""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def strip_sensevoice_control_tags(text: str) -> str:
    """移除 SenseVoice 的语言、情绪、事件等控制标记，保留实际台词。

    SenseVoiceSmall 会把 ``<|zh|>``、``<|HAPPY|>`` 一类解码元数据直接
    拼在 text 字段中。这些不是被合成音频朗读的台词，不能计入全文 CER。
    原始字段仍逐段保存到结果 JSON 的 ``raw_transcription`` 以便复核。
    """
    return SENSEVOICE_CONTROL_TAG.sub("", text).strip()


def levenshtein_alignment(reference: str, hypothesis: str) -> tuple[int, list[dict[str, Any]]]:
    """返回完整字符编辑距离及可复核的插入、删除、替换位置。"""
    rows, columns = len(reference), len(hypothesis)
    matrix = [[0] * (columns + 1) for _ in range(rows + 1)]
    for index in range(rows + 1):
        matrix[index][0] = index
    for index in range(columns + 1):
        matrix[0][index] = index
    for ref_index in range(1, rows + 1):
        for hyp_index in range(1, columns + 1):
            matrix[ref_index][hyp_index] = min(
                matrix[ref_index - 1][hyp_index] + 1,
                matrix[ref_index][hyp_index - 1] + 1,
                matrix[ref_index - 1][hyp_index - 1]
                + (reference[ref_index - 1] != hypothesis[hyp_index - 1]),
            )

    errors: list[dict[str, Any]] = []
    ref_index, hyp_index = rows, columns
    while ref_index or hyp_index:
        if (
            ref_index
            and hyp_index
            and matrix[ref_index][hyp_index]
            == matrix[ref_index - 1][hyp_index - 1]
            and reference[ref_index - 1] == hypothesis[hyp_index - 1]
        ):
            ref_index -= 1
            hyp_index -= 1
            continue
        if (
            ref_index
            and hyp_index
            and matrix[ref_index][hyp_index]
            == matrix[ref_index - 1][hyp_index - 1] + 1
        ):
            errors.append(
                {
                    "operation": "substitution",
                    "reference_index": ref_index - 1,
                    "reference_character": reference[ref_index - 1],
                    "hypothesis_index": hyp_index - 1,
                    "hypothesis_character": hypothesis[hyp_index - 1],
                }
            )
            ref_index -= 1
            hyp_index -= 1
            continue
        if ref_index and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index] + 1:
            errors.append(
                {
                    "operation": "deletion",
                    "reference_index": ref_index - 1,
                    "reference_character": reference[ref_index - 1],
                    "hypothesis_index": hyp_index,
                    "hypothesis_character": "",
                }
            )
            ref_index -= 1
            continue
        if hyp_index and matrix[ref_index][hyp_index] == matrix[ref_index][hyp_index - 1] + 1:
            errors.append(
                {
                    "operation": "insertion",
                    "reference_index": ref_index,
                    "reference_character": "",
                    "hypothesis_index": hyp_index - 1,
                    "hypothesis_character": hypothesis[hyp_index - 1],
                }
            )
            hyp_index -= 1
            continue
        raise RuntimeError("编辑距离回溯失败")
    errors.reverse()
    return matrix[rows][columns], errors


def levenshtein_token_alignment(reference: list[str], hypothesis: list[str]) -> tuple[int, list[dict[str, Any]]]:
    """返回 token 级编辑距离及拼音 token 位置，避免把多字符 token 拆开计算。"""
    rows, columns = len(reference), len(hypothesis)
    matrix = [[0] * (columns + 1) for _ in range(rows + 1)]
    for index in range(rows + 1):
        matrix[index][0] = index
    for index in range(columns + 1):
        matrix[0][index] = index
    for ref_index in range(1, rows + 1):
        for hyp_index in range(1, columns + 1):
            matrix[ref_index][hyp_index] = min(
                matrix[ref_index - 1][hyp_index] + 1,
                matrix[ref_index][hyp_index - 1] + 1,
                matrix[ref_index - 1][hyp_index - 1]
                + (reference[ref_index - 1] != hypothesis[hyp_index - 1]),
            )
    errors: list[dict[str, Any]] = []
    ref_index, hyp_index = rows, columns
    while ref_index or hyp_index:
        if (
            ref_index
            and hyp_index
            and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index - 1]
            and reference[ref_index - 1] == hypothesis[hyp_index - 1]
        ):
            ref_index -= 1
            hyp_index -= 1
            continue
        if (
            ref_index
            and hyp_index
            and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index - 1] + 1
        ):
            errors.append(
                {
                    "operation": "substitution",
                    "reference_index": ref_index - 1,
                    "reference_token": reference[ref_index - 1],
                    "hypothesis_index": hyp_index - 1,
                    "hypothesis_token": hypothesis[hyp_index - 1],
                }
            )
            ref_index -= 1
            hyp_index -= 1
            continue
        if ref_index and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index] + 1:
            errors.append(
                {
                    "operation": "deletion",
                    "reference_index": ref_index - 1,
                    "reference_token": reference[ref_index - 1],
                    "hypothesis_index": hyp_index,
                    "hypothesis_token": "",
                }
            )
            ref_index -= 1
            continue
        if hyp_index and matrix[ref_index][hyp_index] == matrix[ref_index][hyp_index - 1] + 1:
            errors.append(
                {
                    "operation": "insertion",
                    "reference_index": ref_index,
                    "reference_token": "",
                    "hypothesis_index": hyp_index - 1,
                    "hypothesis_token": hypothesis[hyp_index - 1],
                }
            )
            hyp_index -= 1
            continue
        raise RuntimeError("拼音编辑距离回溯失败")
    errors.reverse()
    return matrix[rows][columns], errors


def load_contract(path: Path) -> dict[str, Any]:
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取评测契约：{path}: {exc}") from exc
    validate_contract(contract)
    return contract


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "task9-v2" or contract.get("version") != "V9":
        raise ValueError("评测契约不是 Task 9 V9 的冻结格式")
    source = contract.get("source")
    if not isinstance(source, dict) or source.get("cer_reference") != "text_md_actual_synthesis_order":
        raise ValueError("Task 9 CER 必须使用 text.md 实际合成顺序")
    if not isinstance(source.get("segment_manifest_path"), str):
        raise ValueError("Task 9 必须登记共享分段清单路径")
    if not isinstance(contract.get("models"), list) or len(contract["models"]) != 2:
        raise ValueError("Task 9 必须登记两条待测模型音频")
    model_ids = [item.get("model_id") for item in contract["models"]]
    if len(set(model_ids)) != len(model_ids) or not all(isinstance(item, str) and item for item in model_ids):
        raise ValueError("模型标识必须唯一且非空")
    evaluation = contract.get("asr_evaluation")
    if not isinstance(evaluation, dict) or evaluation.get("mode") != "synthesis_segment_evidence":
        raise ValueError("Task 9 V2 必须使用逐段合成音频证据评测。")
    if not isinstance(evaluation.get("evidence_root"), str):
        raise ValueError("Task 9 V2 缺少逐段证据根目录。")
    if evaluation.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("Task 9 V2 逐段证据版本未冻结或不匹配。")
    health = evaluation.get("health")
    if not isinstance(health, dict):
        raise ValueError("Task 9 V2 缺少 ASR 健康门控配置。")
    required_health = (
        "minimum_hypothesis_to_reference_ratio",
        "maximum_hypothesis_to_reference_ratio",
        "maximum_consecutive_deletions",
        "maximum_backend_disagreement_cer",
        "ranking_requires_healthy_segments",
    )
    if any(name not in health for name in required_health):
        raise ValueError("Task 9 V2 的 ASR 健康门控配置不完整。")
    phonetic = evaluation.get("phonetic")
    if not isinstance(phonetic, dict) or phonetic.get("library") != "pypinyin":
        raise ValueError("Task 9 V2 必须冻结 pypinyin 拼音辅助指标配置。")
    if not isinstance(phonetic.get("version"), str) or phonetic.get("style") != "tone3":
        raise ValueError("Task 9 V2 的拼音指标版本或风格不完整。")
    if not isinstance(phonetic.get("phrase_overrides"), dict):
        raise ValueError("Task 9 V2 的拼音词典覆盖项必须是对象。")


def project_path(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"契约路径越出项目目录：{relative_path}") from exc
    return path


def require_nonempty_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label}不存在：{path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{label}为空：{path}")


def require_decodable_audio(path: Path, label: str) -> None:
    """只读确认 WAV 可解码且至少含一个采样，避免把损坏成品带入正式评测。"""
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("评测环境缺少 soundfile，无法验证成品 WAV") from exc
    try:
        info = sf.info(str(path))
        waveform, _ = sf.read(str(path), frames=1, dtype="float32", always_2d=True)
    except RuntimeError as exc:
        raise ValueError(f"{label}无法解码：{path}: {exc}") from exc
    if info.frames <= 0 or len(waveform) == 0:
        raise ValueError(f"{label}可打开但不含可解码采样：{path}")


def model_entry(contract: dict[str, Any], model_id: str) -> dict[str, Any]:
    for item in contract["models"]:
        if item["model_id"] == model_id:
            return item
    choices = "、".join(item["model_id"] for item in contract["models"])
    raise ValueError(f"未知模型标识 {model_id}；可选值：{choices}")


def command_output(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def collect_runtime_metadata() -> dict[str, Any]:
    pip_freeze = command_output([sys.executable, "-m", "pip", "freeze"])
    pip_check = command_output([sys.executable, "-m", "pip", "check"])
    nvidia_smi = command_output(["nvidia-smi"])
    return {
        "captured_at": utc_now(),
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "pip_freeze": pip_freeze,
        "pip_check": pip_check,
        "nvidia_smi": nvidia_smi,
        "environment": {
            name: os.environ.get(name)
            for name in ("HF_MIRROR_ROOT", "HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        },
    }


def check_preflight(contract: dict[str, Any], hf_mirror_root: Path | None) -> list[str]:
    """返回所有前置条件错误；函数本身不写入正式结果目录。"""
    errors: list[str] = []
    raw_text_path = project_path(contract["source"]["text_path"])
    segment_manifest_path = project_path(contract["source"]["segment_manifest_path"])
    reference_path = project_path(contract["reference"]["audio_path"])
    for path, label in ((raw_text_path, "CER 参考 text.md"), (reference_path, "旁白参考音频")):
        try:
            require_nonempty_file(path, label)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
    source_segments: list[dict[str, Any]] = []
    if raw_text_path.is_file():
        raw_text = raw_text_path.read_text(encoding="utf-8").strip()
        normalized_count = len(normalize_zh_v1(raw_text))
        if normalized_count != contract["source"]["normalized_character_count"]:
            errors.append(
                "text.md 规范化字符数发生变化："
                f"当前 {normalized_count}，冻结值 {contract['source']['normalized_character_count']}"
            )
        try:
            source_segments = load_segment_plan(segment_manifest_path, raw_text)
        except (FileNotFoundError, ValueError) as exc:
            errors.append(f"共享分段清单检查失败：{exc}")
    for item in contract["models"]:
        audio_path = project_path(item["audio_path"])
        try:
            require_nonempty_file(audio_path, f"{item['display_name']} 成品音频")
            require_decodable_audio(audio_path, f"{item['display_name']} 成品音频")
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if source_segments:
            try:
                load_verified_synthesis_evidence(
                    evidence_root=project_path(contract["asr_evaluation"]["evidence_root"]),
                    model_id=str(item["model_id"]),
                    output_audio=audio_path,
                    source_segment_manifest=segment_manifest_path,
                    source_segments=source_segments,
                )
            except (FileNotFoundError, ValueError) as exc:
                errors.append(f"{item['display_name']} 逐段证据检查失败：{exc}")
    if hf_mirror_root is None:
        errors.append("必须传入 --hf-mirror-root 或设置 HF_MIRROR_ROOT；正式评测不允许隐式联网下载")
    elif not hf_mirror_root.expanduser().is_dir():
        errors.append(f"HF_MIRROR_ROOT 不存在：{hf_mirror_root.expanduser()}")
    else:
        root = hf_mirror_root.expanduser().resolve()
        for backend_name, backend in contract["asr"].items():
            marker = root / backend["model_id"] / backend["marker"]
            if not marker.is_file():
                errors.append(f"{backend_name} 本地模型或标记文件缺失：{marker}")
    pip_check = command_output([sys.executable, "-m", "pip", "check"])
    if pip_check["returncode"] != 0:
        errors.append("python -m pip check 失败：" + (pip_check["stdout"] or pip_check["stderr"]))
    try:
        import torch
    except ImportError as exc:
        errors.append(f"评测环境缺少 torch：{exc}")
    else:
        if not torch.cuda.is_available():
            errors.append("评测契约要求 CUDA，但 torch.cuda.is_available() 为 False")
    try:
        import pypinyin
    except ImportError as exc:
        errors.append(f"评测环境缺少 pypinyin：{exc}")
    else:
        expected = str(contract["asr_evaluation"]["phonetic"]["version"])
        actual = str(getattr(pypinyin, "__version__", "unknown"))
        if actual != expected:
            errors.append(f"pypinyin 版本不匹配：当前 {actual}，冻结值 {expected}")
    return errors


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_results_directory(output_dir: Path, resume: bool) -> tuple[Path, Path]:
    resolved = output_dir.expanduser().resolve()
    result_path = resolved / "task9_evaluation_results.json"
    if resolved.exists():
        if not resume:
            raise ValueError(f"输出目录已存在；新评测必须使用新目录：{resolved}")
        if not result_path.is_file():
            raise ValueError(f"--resume 只能继续已有 Task 9 结果目录：{resolved}")
    else:
        if resume:
            raise ValueError(f"--resume 指向的结果目录不存在：{resolved}")
        resolved.mkdir(parents=True)
    return resolved, result_path


def load_or_create_results(
    result_path: Path, contract: dict[str, Any], contract_path: Path, hf_mirror_root: Path
) -> dict[str, Any]:
    if result_path.is_file():
        results = json.loads(result_path.read_text(encoding="utf-8"))
        if results.get("contract_sha256") != sha256_file(contract_path):
            raise ValueError("续跑结果使用的评测契约与本次不同")
        return results
    text_path = project_path(contract["source"]["text_path"])
    segment_manifest_path = project_path(contract["source"]["segment_manifest_path"])
    reference_path = project_path(contract["reference"]["audio_path"])
    segment_manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "task9-v2",
        "version": contract["version"],
        "created_at": utc_now(),
        "contract_path": str(contract_path.resolve()),
        "contract_sha256": sha256_file(contract_path),
        "contract": contract,
        "inputs": {
            "text_path": str(text_path),
            "text_sha256": sha256_file(text_path),
            "text_normalized_character_count": len(normalize_zh_v1(text_path.read_text(encoding="utf-8"))),
            "segment_manifest_path": str(segment_manifest_path),
            "segment_manifest_sha256": sha256_file(segment_manifest_path),
            "segment_manifest": segment_manifest,
            "reference_audio_path": str(reference_path),
            "reference_audio_sha256": sha256_file(reference_path),
            "hf_mirror_root": str(hf_mirror_root),
        },
        "runtime": collect_runtime_metadata(),
        "models": {},
    }


def audio_measurement(audio_path: Path, measurement_config: dict[str, Any]) -> dict[str, Any]:
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("音频交付测量缺少 numpy 或 soundfile") from exc
    info = sf.info(str(audio_path))
    waveform, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
    if len(waveform) == 0:
        raise ValueError("音频可解码但不含任何采样")
    mono = np.mean(waveform, axis=1)
    threshold = 10 ** (float(measurement_config["silence_threshold_dbfs"]) / 20)
    silent = np.abs(mono) < threshold
    leading = 0
    while leading < len(silent) and silent[leading]:
        leading += 1
    trailing = 0
    while trailing < len(silent) and silent[len(silent) - trailing - 1]:
        trailing += 1
    long_regions: list[dict[str, float]] = []
    minimum_samples = round(float(measurement_config["long_silence_min_seconds"]) * sample_rate)
    start: int | None = None
    for index, is_silent in enumerate(silent):
        if is_silent and start is None:
            start = index
        elif not is_silent and start is not None:
            if index - start >= minimum_samples:
                long_regions.append({"start_seconds": start / sample_rate, "end_seconds": index / sample_rate})
            start = None
    if start is not None and len(silent) - start >= minimum_samples:
        long_regions.append({"start_seconds": start / sample_rate, "end_seconds": len(silent) / sample_rate})
    peak = max(float(np.max(np.abs(mono))), 1e-12)
    rms = max(float(np.sqrt(np.mean(np.square(mono)))), 1e-12)
    return {
        "decode_status": "decoded",
        "sha256": sha256_file(audio_path),
        "file_size_bytes": audio_path.stat().st_size,
        "format": info.format,
        "subtype": info.subtype,
        "sample_rate_hz": sample_rate,
        "channels": info.channels,
        "frames": info.frames,
        "duration_seconds": len(waveform) / sample_rate,
        "clipping_ratio": float(np.mean(np.abs(mono) >= float(measurement_config["clipping_threshold"]))),
        "max_sample_peak_dbfs": 20 * math.log10(peak),
        "rms_dbfs": 20 * math.log10(rms),
        "dc_offset": float(np.mean(mono)),
        "leading_silence_seconds": leading / sample_rate,
        "trailing_silence_seconds": trailing / sample_rate,
        "long_silence_regions": long_regions,
        "measurement_parameters": {
            "silence_threshold_dbfs": measurement_config["silence_threshold_dbfs"],
            "long_silence_min_seconds": measurement_config["long_silence_min_seconds"],
            "clipping_threshold": measurement_config["clipping_threshold"],
        },
    }


def clear_cuda_cache(torch: Any) -> None:
    if not torch.cuda.is_available():
        return
    try:
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
    except Exception:
        pass


def whisper_waveform_input(audio_path: Path) -> dict[str, Any]:
    """以波形而非文件名调用 Whisper，避免隐式依赖系统 ffmpeg。

    逐段证据均为 WAV，``soundfile`` 已是评测环境的冻结依赖。直接传入
    ``raw`` 与 ``sampling_rate`` 还能确保 Hugging Face pipeline 不会自行
    将短片段重新切为固定时间窗口。
    """
    try:
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Whisper 读取逐段证据需要 soundfile") from exc
    try:
        waveform, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
    except RuntimeError as exc:
        raise RuntimeError(f"Whisper 无法读取逐段证据音频：{audio_path}: {exc}") from exc
    if len(waveform) == 0:
        raise RuntimeError(f"Whisper 逐段证据音频为空：{audio_path}")
    return {"raw": waveform.mean(axis=1), "sampling_rate": int(sample_rate)}


def each_synthesis_segment(
    audio_segments: list[dict[str, Any]], callback: Callable[[Path, float, float], str | tuple[str, str]]
) -> list[dict[str, Any]]:
    """按合成时冻结的语义片段转写，不再把长音频硬切成固定窗口。"""
    chunks: list[dict[str, Any]] = []
    for index, segment in enumerate(audio_segments):
        transcription_result = callback(
            Path(segment["audio_path"]), float(segment["start_seconds"]), float(segment["end_seconds"])
        )
        if isinstance(transcription_result, tuple):
            transcription, raw_transcription = transcription_result
        else:
            transcription = transcription_result
            raw_transcription = transcription
        record: dict[str, Any] = {
            "index": index,
            "segment_id": segment["segment_id"],
            "start_seconds": float(segment["start_seconds"]),
            "end_seconds": float(segment["end_seconds"]),
            "audio_sha256": segment["audio_sha256"],
            "transcription": transcription,
            "raw_transcription": raw_transcription,
        }
        chunks.append(record)
    if not chunks:
        raise RuntimeError("逐段合成证据不含可转写音频。")
    return chunks


def transcribe_sensevoice(
    audio_segments: list[dict[str, Any]], config: dict[str, Any], model_dir: Path
) -> tuple[str, list[dict[str, Any]]]:
    try:
        import torch
        from funasr import AutoModel
    except ImportError as exc:
        raise RuntimeError("SenseVoice 依赖缺失：需要 funasr、torch") from exc
    model = None
    try:
        model = AutoModel(model=str(model_dir), disable_update=True, device=str(config["device"]))

        def transcribe(chunk: Path, _start: float, _end: float) -> tuple[str, str]:
            result = model.generate(
                input=str(chunk),
                cache={},
                language=str(config["language"]),
                use_itn=bool(config["use_itn"]),
                batch_size_s=int(config["batch_size_s"]),
            )
            if not isinstance(result, list) or not result or not isinstance(result[0], dict):
                raise RuntimeError("SenseVoice 未返回预期的逐片段结果")
            text = result[0].get("text")
            if not isinstance(text, str):
                raise RuntimeError("SenseVoice 结果缺少 text")
            raw_text = text.strip()
            return strip_sensevoice_control_tags(raw_text), raw_text

        chunks = each_synthesis_segment(audio_segments, transcribe)
        return "".join(item["transcription"] for item in chunks), chunks
    finally:
        if model is not None:
            del model
        clear_cuda_cache(torch)


def transcribe_whisper(
    audio_segments: list[dict[str, Any]], config: dict[str, Any], model_dir: Path
) -> tuple[str, list[dict[str, Any]]]:
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    except ImportError as exc:
        raise RuntimeError("Whisper 依赖缺失：需要 transformers、torch") from exc
    model = None
    recognizer = None
    try:
        if str(config["device"]) == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Whisper 契约要求 CUDA，但当前不可用")
        device = 0 if str(config["device"]) == "cuda" else -1
        model = AutoModelForSpeechSeq2Seq.from_pretrained(str(model_dir), local_files_only=True)
        processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
        pipeline_options: dict[str, Any] = {
            "model": model,
            "tokenizer": processor.tokenizer,
            "feature_extractor": processor.feature_extractor,
            "device": device,
        }
        if "chunk_length_s" in config:
            pipeline_options["chunk_length_s"] = float(config["chunk_length_s"])
        recognizer = pipeline("automatic-speech-recognition", **pipeline_options)

        def transcribe(chunk: Path, _start: float, _end: float) -> str:
            result = recognizer(
                whisper_waveform_input(chunk),
                return_timestamps=True,
                generate_kwargs={"language": str(config["language"]), "task": str(config["task"])},
            )
            text = result.get("text") if isinstance(result, dict) else None
            if not isinstance(text, str):
                raise RuntimeError("Whisper-large-v3-turbo 结果缺少 text")
            return text.strip()

        chunks = each_synthesis_segment(audio_segments, transcribe)
        return "".join(item["transcription"] for item in chunks), chunks
    finally:
        del recognizer
        if model is not None:
            del model
        clear_cuda_cache(torch)


def phonetic_tokens(text: str, config: dict[str, Any]) -> list[str]:
    """将规范化文本映射为冻结版本的带调拼音 token。"""
    try:
        import pypinyin
        from pypinyin import Style, load_phrases_dict, pinyin
    except ImportError as exc:
        raise RuntimeError("拼音辅助指标缺少 pypinyin") from exc
    expected_version = str(config["version"])
    actual_version = str(getattr(pypinyin, "__version__", "unknown"))
    if actual_version != expected_version:
        raise RuntimeError(f"pypinyin 版本不匹配：当前 {actual_version}，冻结值 {expected_version}")
    if config.get("style") != "tone3":
        raise ValueError("当前仅支持 tone3 拼音风格。")
    overrides = config.get("phrase_overrides", {})
    if overrides:
        try:
            load_phrases_dict({phrase: [[token] for token in tokens] for phrase, tokens in overrides.items()})
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("冻结拼音词典覆盖项格式无效。") from exc
    values = pinyin(
        text,
        style=Style.TONE3,
        neutral_tone_with_five=True,
        errors=lambda item: list(item),
        strict=False,
    )
    return [str(token) for item in values for token in item]


def max_consecutive_deletions(errors: list[dict[str, Any]]) -> int:
    positions = sorted(item["reference_index"] for item in errors if item["operation"] == "deletion")
    maximum = 0
    current = 0
    previous: int | None = None
    for position in positions:
        if previous is not None and position == previous + 1:
            current += 1
        else:
            current = 1
        maximum = max(maximum, current)
        previous = position
    return maximum


def segment_health(
    reference_length: int, hypothesis_length: int, strict_errors: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    ratio = hypothesis_length / max(reference_length, 1)
    longest_deletion = max_consecutive_deletions(strict_errors)
    reasons: list[str] = []
    if ratio < float(config["minimum_hypothesis_to_reference_ratio"]):
        reasons.append("hypothesis_too_short")
    if ratio > float(config["maximum_hypothesis_to_reference_ratio"]):
        reasons.append("hypothesis_too_long")
    if longest_deletion > int(config["maximum_consecutive_deletions"]):
        reasons.append("consecutive_deletion_too_long")
    return {
        "status": "healthy" if not reasons else "unreliable",
        "hypothesis_to_reference_ratio": ratio,
        "maximum_consecutive_deletions": longest_deletion,
        "reasons": reasons,
    }


def classify_strict_errors(
    errors: list[dict[str, Any]], phonetic_config: dict[str, Any]
) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        if item["operation"] != "substitution":
            item["classification"] = item["operation"]
        elif phonetic_tokens(item["reference_character"], phonetic_config) == phonetic_tokens(
            item["hypothesis_character"], phonetic_config
        ):
            item["classification"] = "same_pronunciation_substitution"
        else:
            item["classification"] = "different_pronunciation_substitution"
        classified.append(item)
    return classified


def overall_health(chunks: list[dict[str, Any]], ranking_requires_healthy_segments: bool) -> dict[str, Any]:
    unreliable = [item["segment_id"] for item in chunks if item["asr_health"]["status"] != "healthy"]
    healthy = not unreliable
    return {
        "status": "healthy" if healthy else "unreliable",
        "unreliable_segment_ids": unreliable,
        "ranking_eligible": healthy or not ranking_requires_healthy_segments,
    }


def offset_error_locations(
    errors: list[dict[str, Any]], segment_id: str, reference_offset: int, hypothesis_offset: int
) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        item["segment_id"] = segment_id
        item["reference_index"] = int(item["reference_index"]) + reference_offset
        item["hypothesis_index"] = int(item["hypothesis_index"]) + hypothesis_offset
        locations.append(item)
    return locations


def evaluate_asr_backend(
    backend_key: str,
    transcriber: Callable[[list[dict[str, Any]], dict[str, Any], Path], tuple[str, list[dict[str, Any]]]],
    audio_segments: list[dict[str, Any]],
    backend_config: dict[str, Any],
    model_dir: Path,
    phonetic_config: dict[str, Any],
    health_config: dict[str, Any],
    evaluation_unit: str = "synthesis_segment_evidence",
) -> dict[str, Any]:
    transcription, raw_chunks = transcriber(audio_segments, backend_config, model_dir)
    if len(raw_chunks) != len(audio_segments):
        raise RuntimeError("ASR 返回的逐段转写数量与合成证据不一致。")
    chunks: list[dict[str, Any]] = []
    error_locations: list[dict[str, Any]] = []
    reference_offset = 0
    hypothesis_offset = 0
    strict_error_count = 0
    phonetic_error_count = 0
    reference_phonetic_count = 0
    hypothesis_phonetic_count = 0
    for evidence, raw_chunk in zip(audio_segments, raw_chunks):
        reference = normalize_zh_v1(str(evidence["text"]))
        hypothesis = normalize_zh_v1(str(raw_chunk["transcription"]))
        strict_errors, strict_locations = levenshtein_alignment(reference, hypothesis)
        strict_locations = classify_strict_errors(strict_locations, phonetic_config)
        reference_phonetic = phonetic_tokens(reference, phonetic_config)
        hypothesis_phonetic = phonetic_tokens(hypothesis, phonetic_config)
        phonetic_errors, phonetic_locations = levenshtein_token_alignment(reference_phonetic, hypothesis_phonetic)
        chunk = {
            **raw_chunk,
            "reference_text_sha256": evidence["text_sha256"],
            "reference_normalized": reference,
            "normalized_transcription": hypothesis,
            "strict_character_errors": strict_errors,
            "strict_character_error_locations": strict_locations,
            "phonetic_errors": phonetic_errors,
            "phonetic_error_locations": phonetic_locations,
            "reference_phonetic_token_count": len(reference_phonetic),
            "hypothesis_phonetic_token_count": len(hypothesis_phonetic),
            "asr_health": segment_health(len(reference), len(hypothesis), strict_locations, health_config),
        }
        chunks.append(chunk)
        error_locations.extend(offset_error_locations(strict_locations, str(evidence["segment_id"]), reference_offset, hypothesis_offset))
        reference_offset += len(reference)
        hypothesis_offset += len(hypothesis)
        strict_error_count += strict_errors
        phonetic_error_count += phonetic_errors
        reference_phonetic_count += len(reference_phonetic)
        hypothesis_phonetic_count += len(hypothesis_phonetic)
    reference_normalized = "".join(item["reference_normalized"] for item in chunks)
    hypothesis_normalized = "".join(item["normalized_transcription"] for item in chunks)
    return {
        "status": "complete",
        "backend": backend_key,
        "model_id": backend_config["model_id"],
        "revision": backend_config["revision"],
        "decode_parameters": {
            key: value for key, value in backend_config.items() if key not in {"model_id", "revision", "marker"}
        },
        "evaluation_unit": evaluation_unit,
        "full_transcription": transcription,
        "normalized_transcription": hypothesis_normalized,
        "normalized_reference_character_count": len(reference_normalized),
        "normalized_transcription_character_count": len(hypothesis_normalized),
        "character_errors": strict_error_count,
        "cer": strict_error_count / max(len(reference_normalized), 1),
        "strict_character_cer": strict_error_count / max(len(reference_normalized), 1),
        "phonetic_errors": phonetic_error_count,
        "phonetic_cer": phonetic_error_count / max(reference_phonetic_count, 1),
        "reference_phonetic_token_count": reference_phonetic_count,
        "hypothesis_phonetic_token_count": hypothesis_phonetic_count,
        "error_locations": error_locations,
        "chunks": chunks,
        "asr_health": overall_health(chunks, bool(health_config["ranking_requires_healthy_segments"])),
    }


def apply_cross_backend_health(record: dict[str, Any], health_config: dict[str, Any]) -> dict[str, Any]:
    """将同一语义段的双 ASR 明显分歧纳入两端健康状态，而不修改原始转写。"""
    sense = record["metrics"]["sensevoice_cer"]
    whisper = record["metrics"]["whisper_large_v3_turbo_cer"]
    sense_chunks = sense["chunks"]
    whisper_chunks = whisper["chunks"]
    if len(sense_chunks) != len(whisper_chunks):
        raise RuntimeError("双 ASR 的逐段结果数量不一致。")
    disagreements: list[dict[str, Any]] = []
    threshold = float(health_config["maximum_backend_disagreement_cer"])
    for sense_chunk, whisper_chunk in zip(sense_chunks, whisper_chunks):
        if sense_chunk["segment_id"] != whisper_chunk["segment_id"]:
            raise RuntimeError("双 ASR 的逐段结果标识不一致。")
        errors, _ = levenshtein_alignment(
            str(sense_chunk["normalized_transcription"]), str(whisper_chunk["normalized_transcription"])
        )
        denominator = max(
            len(str(sense_chunk["normalized_transcription"])),
            len(str(whisper_chunk["normalized_transcription"])),
            1,
        )
        rate = errors / denominator
        if rate > threshold:
            segment_id = str(sense_chunk["segment_id"])
            disagreements.append(
                {"segment_id": segment_id, "strict_character_disagreement_cer": rate}
            )
            for chunk in (sense_chunk, whisper_chunk):
                chunk["asr_health"]["status"] = "unreliable"
                chunk["asr_health"]["reasons"].append("cross_backend_disagreement")
                chunk["asr_health"]["strict_character_disagreement_cer"] = rate
    for metric in (sense, whisper):
        metric["asr_health"] = overall_health(
            metric["chunks"], bool(health_config["ranking_requires_healthy_segments"])
        )
    return {
        "status": "healthy" if not disagreements else "unreliable",
        "unreliable_segment_ids": [item["segment_id"] for item in disagreements],
        "segments": disagreements,
    }


def evaluate_model(
    contract: dict[str, Any], model: dict[str, Any], hf_mirror_root: Path, output_dir: Path
) -> dict[str, Any]:
    # 分段清单在合成阶段由 read_synthesis_text() 冻结；评测也必须采用
    # 同一份实际合成文本。原始 text.md 的完整字节哈希仍在预检和结果契约中校验。
    source_text = read_synthesis_text(project_path(contract["source"]["text_path"]))
    audio_path = project_path(model["audio_path"])
    segment_manifest_path = project_path(contract["source"]["segment_manifest_path"])
    source_segments = load_segment_plan(segment_manifest_path, source_text)
    evaluation_config = contract["asr_evaluation"]
    evidence = load_verified_synthesis_evidence(
        evidence_root=project_path(str(evaluation_config["evidence_root"])),
        model_id=str(model["model_id"]),
        output_audio=audio_path,
        source_segment_manifest=segment_manifest_path,
        source_segments=source_segments,
    )
    audio_segments = [
        {
            **entry,
            "text": source["text"],
            "text_sha256": source["text_sha256"],
        }
        for source, entry in zip(source_segments, evidence["segments"])
    ]
    record: dict[str, Any] = {
        "model_id": model["model_id"],
        "display_name": model["display_name"],
        "audio_path": str(audio_path),
        "started_at": utc_now(),
        "audio_delivery": audio_measurement(audio_path, contract["audio_measurement"]),
        "synthesis_evidence": {
            "schema_version": evidence["schema_version"],
            "manifest_path": str(evidence["manifest_path"]),
            "manifest_sha256": sha256_file(Path(evidence["manifest_path"])),
            "full_audio_sha256": evidence["full_audio_sha256"],
            "segment_count": len(audio_segments),
        },
        "metrics": {},
        "errors": [],
        "not_executed": contract["not_executed"],
    }
    backends: tuple[tuple[str, Callable[[list[dict[str, Any]], dict[str, Any], Path], tuple[str, list[dict[str, Any]]]], str], ...] = (
        ("sensevoice_cer", transcribe_sensevoice, "sensevoice"),
        ("whisper_large_v3_turbo_cer", transcribe_whisper, "whisper_large_v3_turbo"),
    )
    for metric_name, transcriber, config_name in backends:
        backend_config = contract["asr"][config_name]
        model_dir = hf_mirror_root / backend_config["model_id"]
        try:
            record["metrics"][metric_name] = evaluate_asr_backend(
                config_name,
                transcriber,
                audio_segments,
                backend_config,
                model_dir,
                evaluation_config["phonetic"],
                evaluation_config["health"],
            )
        except Exception as exc:
            record["metrics"][metric_name] = {
                "status": "error",
                "backend": config_name,
                "model_id": backend_config["model_id"],
                "error": str(exc),
            }
            record["errors"].append({"metric": metric_name, "error": str(exc)})
    if not record["errors"]:
        record["asr_consensus_health"] = apply_cross_backend_health(record, evaluation_config["health"])
    record["finished_at"] = utc_now()
    record["status"] = "complete" if not record["errors"] else "error"
    return record


def run(args: argparse.Namespace) -> int:
    contract_path = args.contract.expanduser().resolve()
    contract = load_contract(contract_path)
    model = model_entry(contract, args.model_id)
    hf_mirror_root = args.hf_mirror_root.expanduser().resolve() if args.hf_mirror_root else None
    preflight_errors = check_preflight(contract, hf_mirror_root)
    if preflight_errors:
        raise RuntimeError("Task 9 评测预检失败：\n- " + "\n- ".join(preflight_errors))
    assert hf_mirror_root is not None
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", str(hf_mirror_root))
    output_dir, result_path = prepare_results_directory(args.output_dir, args.resume)
    results = load_or_create_results(result_path, contract, contract_path, hf_mirror_root)
    existing = results["models"].get(model["model_id"])
    if existing and existing.get("status") == "complete":
        print(f"{model['display_name']} 已在本次结果目录完成；无需重复运行。")
        return 0
    results["models"][model["model_id"]] = evaluate_model(contract, model, hf_mirror_root, output_dir)
    results["updated_at"] = utc_now()
    write_json_atomic(result_path, results)
    status = results["models"][model["model_id"]]["status"]
    print(f"{model['display_name']} 评测完成，状态：{status}，结果：{result_path}")
    if args.strict and status != "complete":
        return 2
    return 0


def main() -> int:
    try:
        return run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Task 9 公共评测失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
