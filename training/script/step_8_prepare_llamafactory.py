#!/usr/bin/env python3
"""Step 8：为本地 LLaMA-Factory 生成 Qwen3.5-9B QLoRA 配置。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_WORK_DIR,
    PipelineError,
    atomic_write_text,
    read_json,
    utc_now,
    write_json,
    write_stage_progress,
)


DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_TEMPLATE = "qwen3_5_nothink"


def load_json_array(path: Path) -> list[Any]:
    """读取 ShareGPT JSON 数组。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"无法读取数据集：{path}: {error}") from error
    if not isinstance(value, list):
        raise PipelineError(f"数据集顶层必须是数组：{path}")
    return value


def verify_llamafactory_checkout(path: Path) -> None:
    """确认本地源码支持任务所需 Qwen3.5 模型和模板。"""

    constants = path / "src" / "llamafactory" / "extras" / "constants.py"
    templates = path / "src" / "llamafactory" / "data" / "template.py"
    dataset_readme = path / "data" / "README_zh.md"
    for required in (constants, templates, dataset_readme):
        if not required.is_file():
            raise PipelineError(f"LLaMA-Factory checkout 缺少文件：{required}")
    constants_text = constants.read_text(encoding="utf-8")
    if "Qwen3.5-9B" not in constants_text or 'template="qwen3_5"' not in constants_text:
        raise PipelineError("当前 LLaMA-Factory checkout 未识别 Qwen3.5-9B/qwen3_5 模板")


def yaml_string(value: str | Path) -> str:
    """用 JSON 双引号生成兼容 YAML 的字符串标量。"""

    return json.dumps(str(value), ensure_ascii=False)


def training_yaml(
    *,
    model_name_or_path: str,
    dataset_dir: Path,
    output_dir: Path,
    cutoff_len: int,
    has_validation: bool,
) -> str:
    """生成适合单张 16 GB GPU 起步验证的 QLoRA 配置。"""

    lines = [
        "### model",
        f"model_name_or_path: {yaml_string(model_name_or_path)}",
        "trust_remote_code: true",
        "quantization_bit: 4",
        "quantization_method: bnb",
        "",
        "### method",
        "stage: sft",
        "do_train: true",
        "finetuning_type: lora",
        "lora_rank: 16",
        "lora_alpha: 32",
        "lora_dropout: 0.05",
        "lora_target: all",
        "",
        "### dataset",
        f"dataset_dir: {yaml_string(dataset_dir.resolve())}",
        "dataset: audio_polisher_train",
        f"template: {DEFAULT_TEMPLATE}",
        "enable_thinking: false",
        f"cutoff_len: {cutoff_len}",
        "packing: false",
        "overwrite_cache: false",
        "preprocessing_num_workers: 4",
        "dataloader_num_workers: 2",
    ]
    if has_validation:
        lines.extend(
            [
                "eval_dataset: audio_polisher_validation",
                "per_device_eval_batch_size: 1",
                "eval_strategy: steps",
                "eval_steps: 100",
            ]
        )
    lines.extend(
        [
            "",
            "### output",
            f"output_dir: {yaml_string(output_dir.resolve())}",
            "logging_steps: 5",
            "save_steps: 100",
            "save_total_limit: 3",
            "plot_loss: true",
            "overwrite_output_dir: false",
            "save_only_model: false",
            "report_to: none",
            "",
            "### train",
            "per_device_train_batch_size: 1",
            "gradient_accumulation_steps: 8",
            "gradient_checkpointing: true",
            "learning_rate: 1.0e-4",
            "num_train_epochs: 3.0",
            "lr_scheduler_type: cosine",
            "warmup_ratio: 0.1",
            "bf16: true",
            "ddp_timeout: 180000000",
            "resume_from_checkpoint: null",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 8 命令行。"""

    parser = argparse.ArgumentParser(description="生成 Qwen3.5-9B audio-polisher QLoRA 配置")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument(
        "--llamafactory-dir",
        type=Path,
        default=Path.home() / "github" / "LlamaFactory",
    )
    parser.add_argument("--model-name-or-path", default=DEFAULT_MODEL)
    parser.add_argument("--cutoff-len", type=int, default=8192)
    parser.add_argument("--adapter-output-dir", type=Path)
    parser.add_argument("--output-config", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 8。"""

    args = build_parser().parse_args(argv)
    progress_started_at = utc_now()
    if args.cutoff_len < 512:
        raise PipelineError("cutoff-len 不能小于 512")
    export_dir = args.export_dir or args.work_dir / "exports"
    adapter_output_dir = (
        args.adapter_output_dir
        or args.work_dir / "llamafactory" / "saves" / "audio-polisher-lora"
    )
    output_config = (
        args.output_config or args.work_dir / "llamafactory" / "audio_polisher_lora_sft.yaml"
    )
    verify_llamafactory_checkout(args.llamafactory_dir)
    dataset_config = read_json(export_dir / "dataset_info.json")
    if "audio_polisher_train" not in dataset_config:
        raise PipelineError("dataset_info.json 缺少 audio_polisher_train")
    train_records = load_json_array(export_dir / "sharegpt_train.json")
    validation_records = load_json_array(export_dir / "sharegpt_validation.json")
    if not train_records:
        raise PipelineError("训练集为空；先完成 Step 6 自动门禁/必要人审并导出")
    config = training_yaml(
        model_name_or_path=args.model_name_or_path,
        dataset_dir=export_dir,
        output_dir=adapter_output_dir,
        cutoff_len=args.cutoff_len,
        has_validation=bool(validation_records),
    )
    command = f"llamafactory-cli train {output_config.resolve()}"
    print(
        f"LLaMA-Factory 配置：训练 {len(train_records)} 条，"
        f"验证 {len(validation_records)} 条，cutoff_len={args.cutoff_len}"
    )
    print(f"运行命令（在 {args.llamafactory_dir} 中）：{command}")
    if args.dry_run:
        return 0
    if output_config.exists() and not args.overwrite:
        raise PipelineError("训练配置已存在；确认后使用 --overwrite")
    atomic_write_text(output_config, config)
    write_json(
        output_config.with_suffix(".report.json"),
        {
            "generated_at": utc_now(),
            "llamafactory_dir": str(args.llamafactory_dir.resolve()),
            "model_name_or_path": args.model_name_or_path,
            "template": DEFAULT_TEMPLATE,
            "train_count": len(train_records),
            "validation_count": len(validation_records),
            "cutoff_len": args.cutoff_len,
            "command": command,
        },
    )
    write_stage_progress(
        args.work_dir / "progress" / "step_8_llamafactory.json",
        stage="step_8_llamafactory",
        stage_label="Step 8 LLaMA-Factory 配置",
        status="completed",
        total_items=1,
        completed_items=1,
        skipped_existing_items=0,
        scheduled_this_run=1,
        completed_this_run=1,
        failed_this_run=0,
        started_at=progress_started_at,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
