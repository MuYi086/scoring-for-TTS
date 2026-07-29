#!/usr/bin/env python3
"""按本地计划串行生成 Task 8 V8 长文本旁白候选成品。

本入口是 Task 8 的第一阶段：每个计划模型都以 V8 的全文、旁白参考
音频和固定参考文案进行声音克隆（voice cloning），最终写出
``longAudioTestV8/audio_<模型标识>.wav``。第二阶段才由
``run_task8_evaluation.py`` 对这些成品进行公共评测。

计划文件不进入版本库，因为它包含本机模型目录、Conda 环境或源码目录。
命令必须是 JSON 字符串数组，禁止 shell 字符串；入口只替换预定义占位符。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TASK_DIR.parents[1]
TASK9_DIR = PROJECT_ROOT / "task-runner" / "task9"
if str(TASK9_DIR) not in sys.path:
    sys.path.insert(0, str(TASK9_DIR))

from synthesis_evidence import load_verified_synthesis_evidence  # noqa: E402
from text_segments import build_segment_plan, load_segment_plan, write_segment_plan  # noqa: E402

TASK_ID = "task8"
TASK_LABEL = "Task 8"
DEFAULT_TASK_DIR = PROJECT_ROOT / "longAudioTestV8"
DEFAULT_PLAN = DEFAULT_TASK_DIR / ".task8-synthesis-plan.json"
PLAN_SCHEMA_VERSION = "task8-synthesis-plan-v2"
VERSION = "V8"
TEXT_PATH = "longAudioTestV8/text.md"
REFERENCE_AUDIO_PATH = "longAudioTestV8/mimo_旁白_v8.wav"
REFERENCE_TRANSCRIPT = "车轮碾过积雪，细碎声响中驯鹿的身影在漆黑的夜里纹丝不动。"
VOICE_DESCRIPTION = (
    "男性，三十至四十五岁，中低音域，音色厚实沉稳，略带沙哑质感，明亮度偏暗，共鸣饱满。"
    "咬字清晰有力，语速中等偏慢，节奏平稳，停顿自然，默认情绪基调冷静克制，"
    "带有成人叙述故事的神秘感和沉稳气质。"
)
EXPECTED_MODEL_IDS = ("indextts2", "voxcpm2")
SEGMENT_TARGET_SECONDS = 25
SEGMENT_MAX_SECONDS = 35
MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SENSITIVE_OPTION_NAMES = frozenset(
    {"--api-key", "--token", "--access-token", "--password", "--secret", "--authorization"}
)


@dataclass(frozen=True)
class SynthesisModel:
    """一个本地模型的无 shell 合成调用。"""

    model_id: str
    output_mode: str
    command: tuple[str, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="本机 V8 合成计划 JSON")
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR, help="固定 V8 输入与输出目录")
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="仅执行指定模型标识；默认按计划顺序执行全部模型",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅校验计划并打印展开后的调用，不运行模型")
    parser.add_argument("--overwrite", action="store_true", help="明确允许替换已存在的同名 V8 成品")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_nonempty_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label}不存在：{resolved}")
    if resolved.stat().st_size == 0:
        raise ValueError(f"{label}为空：{resolved}")
    return resolved


def require_decodable_wav(path: Path, label: str) -> None:
    """只依赖标准库确认 WAV 可读取且有采样，不替代评测阶段完整解码检查。"""
    try:
        with wave.open(str(path), "rb") as reader:
            if reader.getnframes() <= 0:
                raise ValueError(f"{label}不含任何采样：{path}")
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"{label}不是可解码的 WAV：{path}: {exc}") from exc


def task_path(task_dir: Path, relative_path: str) -> Path:
    resolved_task_dir = task_dir.expanduser().resolve()
    path = (PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(resolved_task_dir)
    except ValueError as exc:
        raise ValueError(f"{TASK_LABEL} 路径越出 {VERSION} 目录：{relative_path}") from exc
    return path


def load_plan(path: Path) -> tuple[dict[str, Any], list[SynthesisModel]]:
    resolved = path.expanduser().resolve()
    try:
        plan = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 {TASK_LABEL} 合成计划：{resolved}: {exc}") from exc
    if not isinstance(plan, dict):
        raise ValueError(f"{TASK_LABEL} 合成计划必须是 JSON 对象")
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION or plan.get("version") != VERSION:
        raise ValueError(f"{TASK_LABEL} 合成计划版本不匹配")
    source = plan.get("source")
    expected_source = {
        "text_path": TEXT_PATH,
        "reference_audio_path": REFERENCE_AUDIO_PATH,
        "reference_transcript": REFERENCE_TRANSCRIPT,
        "voice_description": VOICE_DESCRIPTION,
    }
    if source != expected_source:
        raise ValueError(f"{TASK_LABEL} 合成计划必须使用冻结的 {VERSION} 全文、旁白参考音频、参考文案和音色说明")
    raw_models = plan.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError(f"{TASK_LABEL} 合成计划至少要声明一个模型")
    models: list[SynthesisModel] = []
    model_ids: list[str] = []
    for item in raw_models:
        if not isinstance(item, dict):
            raise ValueError(f"{TASK_LABEL} 合成计划的每个模型必须是对象")
        model_id = item.get("model_id")
        output_mode = item.get("output_mode", "exact_path")
        command = item.get("command")
        if not isinstance(model_id, str) or not MODEL_ID_PATTERN.fullmatch(model_id):
            raise ValueError(f"模型标识非法：{model_id!r}")
        if model_id in model_ids:
            raise ValueError(f"模型标识重复：{model_id}")
        if output_mode not in {"exact_path", "single_wav_in_output_dir"}:
            raise ValueError(f"{model_id} 的 output_mode 非法：{output_mode!r}")
        if not isinstance(command, list) or not command or not all(isinstance(token, str) and token for token in command):
            raise ValueError(f"{model_id} 的 command 必须是非空字符串数组")
        # V8 与 Task 9 一样，两个模型必须从同一份语义分段清单读取文本，并
        # 产出与最终成品哈希绑定的片段音频证据。只给 VoxCPM2 分段会让
        # IndexTTS2 的长音频无法进入同一条可复核评测链路。
        required_placeholders = {
            "{text_file}",
            "{reference_audio}",
            "{segment_manifest}",
            "{segment_evidence_root}",
        }
        if output_mode == "exact_path":
            required_placeholders.add("{output_path}")
        else:
            required_placeholders.add("{output_dir}")
        command_text = "\u0000".join(command)
        if model_id == "voxcpm2" and any(
            token == "--style-prompt" or token.startswith("--style-prompt=") for token in command
        ):
            raise ValueError(
                "VoxCPM2 不得传入 --style-prompt：当前本地实现会把它拼入 text 并实际朗读；"
                "音色只能由参考音频和参考文案提供。"
            )
        missing = sorted(item for item in required_placeholders if item not in command_text)
        if missing:
            raise ValueError(f"{model_id} 的 command 缺少占位符：{'、'.join(missing)}")
        model_ids.append(model_id)
        models.append(SynthesisModel(model_id, output_mode, tuple(command)))
    if tuple(model_ids) != EXPECTED_MODEL_IDS:
        raise ValueError(
            f"{TASK_LABEL} 只比较并且必须按顺序合成 IndexTTS2 与 VoxCPM2："
            + "、".join(EXPECTED_MODEL_IDS)
        )
    return plan, models


def selected_models(models: list[SynthesisModel], requested: list[str] | None) -> list[SynthesisModel]:
    if not requested:
        return models
    available = {item.model_id: item for item in models}
    duplicates = {model_id for model_id in requested if requested.count(model_id) > 1}
    if duplicates:
        raise ValueError("--models 包含重复模型标识：" + "、".join(sorted(duplicates)))
    unknown = [model_id for model_id in requested if model_id not in available]
    if unknown:
        raise ValueError("--models 包含计划外模型：" + "、".join(unknown))
    requested_ids = set(requested)
    return [item for item in models if item.model_id in requested_ids]


def output_path(task_dir: Path, model_id: str) -> Path:
    return task_dir.expanduser().resolve() / f"audio_{model_id}.wav"


def validate_preflight(task_dir: Path, models: list[SynthesisModel], overwrite: bool, dry_run: bool) -> dict[str, Path]:
    resolved_task_dir = task_dir.expanduser().resolve()
    if resolved_task_dir != DEFAULT_TASK_DIR.resolve():
        raise ValueError(f"{TASK_LABEL} 合成只能使用固定目录：{DEFAULT_TASK_DIR.resolve()}")
    text_file = require_nonempty_file(task_path(resolved_task_dir, TEXT_PATH), f"{VERSION} 合成原文 text.md")
    reference_audio = require_nonempty_file(
        task_path(resolved_task_dir, REFERENCE_AUDIO_PATH), f"{VERSION} 旁白参考音频"
    )
    require_decodable_wav(reference_audio, f"{VERSION} 旁白参考音频")
    if not dry_run and not overwrite:
        existing = [str(output_path(resolved_task_dir, item.model_id)) for item in models if output_path(resolved_task_dir, item.model_id).exists()]
        if existing:
            raise FileExistsError("目标成品已存在；重新合成必须显式传入 --overwrite：" + "、".join(existing))
    return {
        "task_dir": resolved_task_dir,
        "text_file": text_file,
        "reference_audio": reference_audio,
        "segment_manifest": resolved_task_dir / f".{TASK_ID}_segment_manifest.json",
        "segment_evidence_root": resolved_task_dir / f".{TASK_ID}_synthesis_evidence",
    }


def build_shared_segment_plan(inputs: dict[str, Path]) -> dict[str, Any]:
    """为两个模型建立按旁白参考语速约束的共享分段清单。"""
    return build_segment_plan(
        inputs["text_file"].read_text(encoding="utf-8").strip(),
        inputs["reference_audio"],
        REFERENCE_TRANSCRIPT,
        SEGMENT_TARGET_SECONDS,
        SEGMENT_MAX_SECONDS,
    )


def expand_command(model: SynthesisModel, inputs: dict[str, Path], staging_dir: Path) -> list[str]:
    replacements = {
        "{project_root}": str(PROJECT_ROOT),
        "{task_dir}": str(inputs["task_dir"]),
        "{text_file}": str(inputs["text_file"]),
        "{reference_audio}": str(inputs["reference_audio"]),
        "{reference_transcript}": REFERENCE_TRANSCRIPT,
        "{voice_description}": VOICE_DESCRIPTION,
        "{segment_manifest}": str(inputs["segment_manifest"]),
        "{segment_evidence_root}": str(inputs["segment_evidence_root"]),
        "{output_path}": str(staging_dir / "output.wav"),
        "{output_dir}": str(staging_dir),
    }
    command: list[str] = []
    for token in model.command:
        expanded = token
        for placeholder, value in replacements.items():
            expanded = expanded.replace(placeholder, value)
        unresolved = re.findall(r"\{(?:project_root|task_dir|text_file|reference_audio|reference_transcript|voice_description|segment_manifest|segment_evidence_root|output_path|output_dir)\}", expanded)
        if unresolved:
            raise ValueError(f"{model.model_id} 的 command 含未展开占位符：{'、'.join(sorted(set(unresolved)))}")
        command.append(expanded)
    return command


def redact_command(command: list[str]) -> list[str]:
    """避免将计划中误传的认证值写入本地合成记录。"""
    redacted: list[str] = []
    hide_next = False
    for token in command:
        if hide_next:
            redacted.append("***")
            hide_next = False
            continue
        option, separator, _value = token.partition("=")
        if option.lower() in SENSITIVE_OPTION_NAMES:
            redacted.append(f"{option}=***" if separator else option)
            hide_next = not bool(separator)
            continue
        redacted.append(token)
    return redacted


def produced_wav(model: SynthesisModel, staging_dir: Path) -> Path:
    if model.output_mode == "exact_path":
        return require_nonempty_file(staging_dir / "output.wav", f"{model.model_id} 合成成品")
    candidates = sorted(path for path in staging_dir.glob("*.wav") if path.is_file())
    if len(candidates) != 1:
        raise ValueError(f"{model.model_id} 应在临时输出目录恰好生成一条 WAV，实际为 {len(candidates)} 条")
    return require_nonempty_file(candidates[0], f"{model.model_id} 合成成品")


def write_record(task_dir: Path, model: SynthesisModel, command: list[str], inputs: dict[str, Path], output: Path, plan: dict[str, Any], started_at: str) -> Path:
    record_path = task_dir / f".{TASK_ID}_synthesis" / model.model_id / "synthesis-record.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    source_segments = load_segment_plan(
        inputs["segment_manifest"], inputs["text_file"].read_text(encoding="utf-8").strip()
    )
    evidence = load_verified_synthesis_evidence(
        evidence_root=inputs["segment_evidence_root"],
        model_id=model.model_id,
        output_audio=output,
        source_segment_manifest=inputs["segment_manifest"],
        source_segments=source_segments,
    )
    record = {
        "schema_version": f"{TASK_ID}-synthesis-record-v1",
        "version": VERSION,
        "model_id": model.model_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "plan_sha256": sha256_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "source": {
            "text_path": str(inputs["text_file"]),
            "text_sha256": sha256_file(inputs["text_file"]),
            "reference_audio_path": str(inputs["reference_audio"]),
            "reference_audio_sha256": sha256_file(inputs["reference_audio"]),
            "reference_transcript": REFERENCE_TRANSCRIPT,
            "voice_description": VOICE_DESCRIPTION,
            "shared_segment_manifest_path": str(inputs["segment_manifest"]),
            "shared_segment_manifest_sha256": sha256_file(inputs["segment_manifest"]),
        },
        "command": redact_command(command),
        "output": {
            "path": str(output),
            "sha256": sha256_file(output),
            "file_size_bytes": output.stat().st_size,
        },
        "segment_evidence": {
            "root": str(inputs["segment_evidence_root"]),
            "manifest_path": str(evidence["manifest_path"]),
            "manifest_sha256": sha256_file(Path(evidence["manifest_path"])),
            "full_audio_sha256": evidence["full_audio_sha256"],
            "segment_count": len(evidence["segments"]),
        },
        "evaluation_note": f"{TASK_LABEL} 使用与最终 WAV 哈希绑定的逐段合成证据；后续 CER 必须按该证据逐段转写。",
    }
    temporary = record_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(record_path)
    return record_path


def synthesize_model(model: SynthesisModel, inputs: dict[str, Path], plan: dict[str, Any]) -> tuple[Path, Path]:
    task_dir = inputs["task_dir"]
    staging_root = task_dir / f".{TASK_ID}_synthesis_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f"{model.model_id}-", dir=staging_root))
    command = expand_command(model, inputs, staging_dir)
    started_at = utc_now()
    try:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{model.model_id} 合成命令失败，退出码：{completed.returncode}")
        staged_output = produced_wav(model, staging_dir)
        require_decodable_wav(staged_output, f"{model.model_id} 合成成品")
        final_output = output_path(task_dir, model.model_id)
        staged_output.replace(final_output)
        record_path = write_record(task_dir, model, command, inputs, final_output, plan, started_at)
        return final_output, record_path
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def run(args: argparse.Namespace) -> int:
    plan, models = load_plan(args.plan)
    selected = selected_models(models, args.models)
    inputs = validate_preflight(args.task_dir, selected, args.overwrite, args.dry_run)
    shared_plan = build_shared_segment_plan(inputs)
    if args.dry_run:
        dry_staging = inputs["task_dir"] / f".{TASK_ID}_synthesis_staging" / "dry-run"
        print(
            f"将冻结共享分段清单：{inputs['segment_manifest']}；"
            f"{len(shared_plan['segments'])} 段，目标/最大 "
            f"{shared_plan['policy']['target_normalized_characters']}/"
            f"{shared_plan['policy']['max_normalized_characters']} 个规范化字符。"
        )
        for model in selected:
            print(json.dumps({"model_id": model.model_id, "command": redact_command(expand_command(model, inputs, dry_staging))}, ensure_ascii=False))
        return 0
    write_segment_plan(inputs["segment_manifest"], shared_plan)
    print(
        f"已冻结 {VERSION} 共享分段清单：{inputs['segment_manifest']}；"
        f"{len(shared_plan['segments'])} 段，目标/最大 "
        f"{shared_plan['policy']['target_normalized_characters']}/"
        f"{shared_plan['policy']['max_normalized_characters']} 个规范化字符。"
    )
    for model in selected:
        final_output, record_path = synthesize_model(model, inputs, plan)
        print(f"{model.model_id} 合成完成：{final_output}；证据：{record_path}")
    return 0


def main() -> int:
    try:
        return run(parse_args())
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"{TASK_LABEL} 合成失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
