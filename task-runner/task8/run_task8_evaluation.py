#!/usr/bin/env python3
"""Task 8 V8 长音频公共评测入口。

每次只评测一个 ``audio_*.wav`` 成品，全文 CER（字符错误率）严格使用
``longAudioTestV8/text.md`` 的实际合成顺序。V8 采用与 Task 9 相同的共享
语义分段和、与最终 WAV 哈希绑定的片段音频证据；双 ASR 必须逐段转写，
不能再把十余分钟成品作为单个 ASR 输入。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
TASK9_DIR = PROJECT_ROOT / "task-runner" / "task9"
if str(TASK9_DIR) not in sys.path:
    sys.path.insert(0, str(TASK9_DIR))

from run_task9_evaluation import (  # noqa: E402
    check_preflight as check_evidence_preflight,
    evaluate_model as evaluate_evidenced_model,
    normalize_zh_v1,
)


DEFAULT_CONTRACT = TASK_DIR / "evaluation-contract.json"
RESULT_FILE_NAME = "task8_evaluation_results.json"
LEGACY_TASK_SCHEMA_PATTERN = re.compile(r"^task([6-7])-v1$")
EVIDENCED_TASK_SCHEMA_PATTERN = re.compile(r"^task([6-8])-v2$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT, help="冻结的机器可读评测契约")
    parser.add_argument("--output-dir", type=Path, required=True, help="首次必须是尚不存在的新结果目录")
    parser.add_argument("--model-id", required=True, help="从 audio_*.wav 文件名导出的唯一模型标识")
    parser.add_argument(
        "--hf-mirror-root",
        type=Path,
        default=os.getenv("HF_MIRROR_ROOT"),
        help="评价模型本地镜像根目录；默认读取 HF_MIRROR_ROOT",
    )
    parser.add_argument("--resume", action="store_true", help="仅续跑同一未完成结果目录")
    parser.add_argument("--strict", action="store_true", help="任一 ASR 后端失败时以非零状态退出")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def load_contract(path: Path) -> dict[str, Any]:
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取评测契约：{path}: {exc}") from exc
    validate_contract(contract)
    return contract


def task_identity(contract: dict[str, Any]) -> tuple[str, str]:
    """区分逐段证据契约与历史整条成品契约。"""
    schema = contract.get("schema_version")
    version = contract.get("version")
    evidenced_match = EVIDENCED_TASK_SCHEMA_PATTERN.fullmatch(schema) if isinstance(schema, str) else None
    if evidenced_match is not None and version == f"V{evidenced_match.group(1)}":
        return f"Task {evidenced_match.group(1)}", str(version)
    match = LEGACY_TASK_SCHEMA_PATTERN.fullmatch(schema) if isinstance(schema, str) else None
    if match is None or version != f"V{match.group(1)}":
        raise ValueError("评测契约必须是 Task 6/7 历史整条格式，或 Task 6/7/8 的逐段证据格式")
    return f"Task {match.group(1)}", str(version)


def validate_contract(contract: dict[str, Any]) -> None:
    task_label, _version = task_identity(contract)
    source = contract.get("source")
    if not isinstance(source, dict) or source.get("cer_reference") != "text_md_actual_synthesis_order":
        raise ValueError(f"{task_label} CER 必须使用 text.md 实际合成顺序")
    if not isinstance(source.get("text_path"), str) or not isinstance(source.get("text_sha256"), str):
        raise ValueError(f"{task_label} 必须冻结 text.md 路径和 SHA-256")
    if not isinstance(source.get("normalized_character_count"), int):
        raise ValueError(f"{task_label} 必须冻结 text.md 规范化字符数")
    schema = contract.get("schema_version")
    is_evidenced = isinstance(schema, str) and EVIDENCED_TASK_SCHEMA_PATTERN.fullmatch(schema) is not None
    if not is_evidenced:
        discovery = contract.get("model_discovery")
        if not isinstance(discovery, dict) or not all(
            isinstance(discovery.get(key), str) for key in ("directory", "glob", "model_id_prefix")
        ):
            raise ValueError(f"{task_label} 缺少 audio_*.wav 候选发现规则")
        if not isinstance(discovery.get("minimum_model_count"), int) or discovery["minimum_model_count"] < 1:
            raise ValueError(f"{task_label} 候选模型最小数量必须为正整数")
        if discovery.get("required_model_ids") != ["indextts2", "voxcpm2"]:
            raise ValueError(f"{task_label} 必须且只能评测阶段一生成的 indextts2 与 voxcpm2")
        evaluation = contract.get("asr_evaluation")
        if not isinstance(evaluation, dict) or evaluation.get("mode") != "whole_audio":
            raise ValueError(f"{task_label} 必须明确使用整条成品评测单元")
        return
    if not isinstance(source.get("segment_manifest_path"), str):
        raise ValueError(f"{task_label} 必须冻结共享分段清单路径")
    models = contract.get("models")
    if not isinstance(models, list) or [item.get("model_id") for item in models if isinstance(item, dict)] != ["indextts2", "voxcpm2"]:
        raise ValueError(f"{task_label} 必须且只能登记 indextts2 与 voxcpm2")
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("display_name"), str)
        or not isinstance(item.get("audio_path"), str)
        for item in models
    ):
        raise ValueError(f"{task_label} 的候选模型登记不完整")
    evaluation = contract.get("asr_evaluation")
    if not isinstance(evaluation, dict) or evaluation.get("mode") != "synthesis_segment_evidence":
        raise ValueError(f"{task_label} 必须使用与最终 WAV 哈希绑定的逐段合成证据")
    if not isinstance(evaluation.get("evidence_root"), str) or evaluation.get("evidence_schema_version") != "task9-synthesis-evidence-v1":
        raise ValueError(f"{task_label} 的逐段合成证据配置不完整")
    health = evaluation.get("health")
    if not isinstance(health, dict) or not all(
        key in health
        for key in (
            "minimum_hypothesis_to_reference_ratio",
            "maximum_hypothesis_to_reference_ratio",
            "maximum_consecutive_deletions",
            "maximum_backend_disagreement_cer",
            "ranking_requires_healthy_segments",
        )
    ):
        raise ValueError(f"{task_label} 缺少 ASR 健康门控配置")
    phonetic = evaluation.get("phonetic")
    if not isinstance(phonetic, dict) or phonetic.get("library") != "pypinyin" or phonetic.get("version") != "0.55.0":
        raise ValueError(f"{task_label} 必须冻结 pypinyin==0.55.0 拼音辅助配置")
    if not isinstance(contract.get("asr"), dict) or set(contract["asr"]) != {"sensevoice", "whisper_large_v3_turbo"}:
        raise ValueError(f"{task_label} 只允许冻结 SenseVoiceSmall 与 Whisper-large-v3-turbo")


def discover_models(contract: dict[str, Any]) -> list[dict[str, str]]:
    """从冻结契约读取且只读取两个允许的候选成品。"""
    candidates: list[dict[str, str]] = []
    for item in contract["models"]:
        model_id = str(item["model_id"])
        audio_path = project_path(str(item["audio_path"]))
        if not audio_path.is_file():
            raise FileNotFoundError(f"{model_id} 成品音频不存在：{audio_path}")
        candidates.append(
            {
                "model_id": model_id,
                "display_name": str(item["display_name"]),
                "audio_path": str(audio_path),
                "audio_sha256": sha256_file(audio_path),
            }
        )
    return candidates


def model_entry(models: list[dict[str, str]], model_id: str) -> dict[str, str]:
    for item in models:
        if item["model_id"] == model_id:
            return item
    choices = "、".join(item["model_id"] for item in models)
    raise ValueError(f"未知模型标识 {model_id}；当前可选值：{choices}")


def command_output(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def collect_runtime_metadata() -> dict[str, Any]:
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        devices = [
            {
                "index": index,
                "name": torch.cuda.get_device_name(index),
                "capability": list(torch.cuda.get_device_capability(index)),
            }
            for index in range(torch.cuda.device_count())
        ] if cuda_available else []
        cuda_runtime: dict[str, Any] = {
            "torch_version": str(torch.__version__),
            "torch_cuda_version": str(torch.version.cuda),
            "cuda_available": cuda_available,
            "device_count": int(torch.cuda.device_count()),
            "devices": devices,
        }
    except (ImportError, RuntimeError) as exc:
        cuda_runtime = {"capture_error": str(exc)}
    return {
        "captured_at": utc_now(),
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "pip_freeze": command_output([sys.executable, "-m", "pip", "freeze"]),
        "pip_check": command_output([sys.executable, "-m", "pip", "check"]),
        "nvidia_smi": command_output(["nvidia-smi"]),
        "cuda_runtime": cuda_runtime,
        "environment": {
            name: os.environ.get(name)
            for name in ("HF_MIRROR_ROOT", "HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        },
    }


def check_preflight(contract: dict[str, Any], models: list[dict[str, str]], hf_mirror_root: Path | None) -> list[str]:
    """复用 Task 9 的证据预检，并额外校验 V8 冻结文本哈希。"""
    del models
    errors = check_evidence_preflight(contract, hf_mirror_root)
    source = contract["source"]
    text_path = project_path(source["text_path"])
    if text_path.is_file():
        actual_hash = sha256_file(text_path)
        if actual_hash != source["text_sha256"]:
            errors.append(f"text.md SHA-256 不匹配：当前 {actual_hash}，冻结值 {source['text_sha256']}")
    return errors


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_results_directory(
    output_dir: Path, resume: bool, contract: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    resolved = output_dir.expanduser().resolve()
    if contract is None:
        directory = "longAudioTestV8"
    elif "source" in contract:
        directory = str(Path(contract["source"]["text_path"]).parent)
    else:
        directory = str(contract["model_discovery"]["directory"])
    results_root = (project_path(directory) / "评测结果").resolve()
    try:
        relative_path = resolved.relative_to(results_root)
    except ValueError as exc:
        raise ValueError(
            f"原始结果目录必须位于 {results_root} 下：{resolved}"
        ) from exc
    if not relative_path.parts:
        raise ValueError(
            f"--output-dir 必须是 {results_root} 下的新建批次目录，不能直接使用报告目录本身"
        )
    result_path = resolved / RESULT_FILE_NAME
    if resolved.exists():
        if not resume:
            raise ValueError(f"输出目录已存在；新评测必须使用新目录：{resolved}")
        if not result_path.is_file():
            raise ValueError(f"--resume 只能继续已有原始结果目录：{resolved}")
    else:
        if resume:
            raise ValueError(f"--resume 指向的结果目录不存在：{resolved}")
        resolved.mkdir(parents=True)
    return resolved, result_path


def model_snapshot(models: list[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(item) for item in models]


def validate_frozen_input_snapshot(
    results: dict[str, Any], contract: dict[str, Any], models: list[dict[str, str]]
) -> None:
    """拒绝在同一结果目录混入变化后的文本、清单、证据或候选成品。"""
    expected_schema = contract.get("schema_version", "task8-v2")
    if results.get("schema_version") != expected_schema or results.get("version") != contract["version"]:
        raise ValueError("--resume 指向的结果与本次评测契约版本不一致")
    if results.get("candidate_models") != model_snapshot(models):
        raise ValueError("候选 audio_*.wav 清单或哈希已变化；不得对同一结果目录混用输入")
    inputs = results.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("已有结果缺少首次运行时冻结的输入快照")
    text_path = project_path(contract["source"]["text_path"])
    reference_path = project_path(contract["reference"]["audio_path"])
    segment_manifest_path = project_path(contract["source"]["segment_manifest_path"])
    current_inputs = {
        "text_path": str(text_path),
        "text_sha256": sha256_file(text_path),
        "text_normalized_character_count": len(normalize_zh_v1(text_path.read_text(encoding="utf-8"))),
        "reference_audio_path": str(reference_path),
        "reference_audio_sha256": sha256_file(reference_path),
        "segment_manifest_path": str(segment_manifest_path),
        "segment_manifest_sha256": sha256_file(segment_manifest_path),
    }
    for key, current_value in current_inputs.items():
        if inputs.get(key) != current_value:
            raise ValueError(f"{key} 已变化；不得对同一结果目录混用输入")


def load_or_create_results(
    result_path: Path,
    contract: dict[str, Any],
    contract_path: Path,
    hf_mirror_root: Path,
    models: list[dict[str, str]],
) -> dict[str, Any]:
    if result_path.is_file():
        try:
            results = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取已有原始结果：{result_path}: {exc}") from exc
        if results.get("contract_sha256") != sha256_file(contract_path):
            raise ValueError("续跑结果使用的评测契约与本次不同")
        validate_frozen_input_snapshot(results, contract, models)
        return results
    text_path = project_path(contract["source"]["text_path"])
    reference_path = project_path(contract["reference"]["audio_path"])
    segment_manifest_path = project_path(contract["source"]["segment_manifest_path"])
    source_text = text_path.read_text(encoding="utf-8")
    return {
        "schema_version": contract.get("schema_version", "task8-v2"),
        "version": contract["version"],
        "created_at": utc_now(),
        "contract_path": str(contract_path.resolve()),
        "contract_sha256": sha256_file(contract_path),
        "contract": contract,
        "inputs": {
            "text_path": str(text_path),
            "text_sha256": sha256_file(text_path),
            "source_text": source_text,
            "normalized_source_text": normalize_zh_v1(source_text),
            "text_normalized_character_count": len(normalize_zh_v1(source_text)),
            "reference_audio_path": str(reference_path),
            "reference_audio_sha256": sha256_file(reference_path),
            "segment_manifest_path": str(segment_manifest_path),
            "segment_manifest_sha256": sha256_file(segment_manifest_path),
            "segment_manifest": json.loads(segment_manifest_path.read_text(encoding="utf-8")),
            "hf_mirror_root": str(hf_mirror_root),
            "evaluation_unit": contract["asr_evaluation"]["mode"],
            "evaluation_unit_note": contract["asr_evaluation"]["evidence_note"],
        },
        "candidate_models": model_snapshot(models),
        "runtime": collect_runtime_metadata(),
        "models": {},
    }


def evaluate_model(contract: dict[str, Any], model: dict[str, str], hf_mirror_root: Path) -> dict[str, Any]:
    """复用 Task 9 已验证的证据读取、逐段 ASR 和健康门控实现。"""
    evaluation_model = next(
        item for item in contract["models"] if item["model_id"] == model["model_id"]
    )
    return evaluate_evidenced_model(contract, evaluation_model, hf_mirror_root, PROJECT_ROOT)


def run(args: argparse.Namespace) -> int:
    contract_path = args.contract.expanduser().resolve()
    contract = load_contract(contract_path)
    models = discover_models(contract)
    model = model_entry(models, args.model_id)
    hf_mirror_root = args.hf_mirror_root.expanduser().resolve() if args.hf_mirror_root else None
    preflight_errors = check_preflight(contract, models, hf_mirror_root)
    if preflight_errors:
        task_label, _version = task_identity(contract)
        raise RuntimeError(f"{task_label} 评测预检失败：\n- " + "\n- ".join(preflight_errors))
    assert hf_mirror_root is not None
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", str(hf_mirror_root))
    output_dir, result_path = prepare_results_directory(args.output_dir, args.resume, contract)
    results = load_or_create_results(result_path, contract, contract_path, hf_mirror_root, models)
    existing = results["models"].get(model["model_id"])
    if existing and existing.get("status") == "complete":
        print(f"{model['display_name']} 已在本次结果目录完成；无需重复运行。")
        return 0
    results["models"][model["model_id"]] = evaluate_model(contract, model, hf_mirror_root)
    results["updated_at"] = utc_now()
    write_json_atomic(result_path, results)
    status = results["models"][model["model_id"]]["status"]
    print(f"{model['display_name']} 评测完成，状态：{status}，结果：{result_path}")
    return 0 if not args.strict or status == "complete" else 2


def main() -> int:
    try:
        return run(parse_args())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Task 8 公共评测失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
