#!/usr/bin/env python3
"""Step 2b：由 Terra 独立裁决可否安全应用连续边界修复建议。"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_STORY_BATCH_LIMIT,
    DEFAULT_WORK_DIR,
    PipelineError,
    canonical_json_sha256,
    codex_command,
    eligible_story_records,
    limit_pending_items,
    read_json,
    read_jsonl,
    relative_to_repo,
    run_codex_task,
    run_parallel_tasks,
    utc_now,
    validate_automatic_model_policy,
    validate_exact_keys,
    write_json,
    write_jsonl,
)
from step_2_analyze_stories import build_story_boundary_context, validate_analysis


DEFAULT_MODEL = "gpt-5.6-terra"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "boundary_repair_decision.schema.json"
REQUIRED_KEYS = {
    "source_id", "decision", "start_line", "end_line", "confidence", "rationale", "unresolved_risks"
}


def repair_has_changed_range(repair: dict[str, Any]) -> bool:
    """仅允许模型裁决确实改变现有连续范围的建议。"""

    return (
        repair.get("suggested_start_line") not in (None, repair.get("current_start_line"))
        or repair.get("suggested_end_line") not in (None, repair.get("current_end_line"))
    )


def validate_decision(value: dict[str, Any], repair: dict[str, Any]) -> None:
    """验证裁决绑定，并防止模型擅自发明新的边界。"""

    validate_exact_keys(value, required=REQUIRED_KEYS, optional={"_provenance"})
    if value["source_id"] != repair["source_id"]:
        raise PipelineError("自动边界裁决 source_id 不匹配")
    if value["decision"] not in {"approve", "reject"}:
        raise PipelineError("自动边界裁决 decision 无效")
    if not isinstance(value["confidence"], (int, float)) or isinstance(value["confidence"], bool):
        raise PipelineError("自动边界裁决 confidence 必须为数字")
    if not 0 <= value["confidence"] <= 1:
        raise PipelineError("自动边界裁决 confidence 必须在 0–1")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise PipelineError("自动边界裁决 rationale 必须为非空字符串")
    if not isinstance(value["unresolved_risks"], list) or not all(
        isinstance(item, str) for item in value["unresolved_risks"]
    ):
        raise PipelineError("自动边界裁决 unresolved_risks 必须为字符串数组")
    if value["decision"] == "reject":
        return
    start = repair.get("suggested_start_line") or repair["current_start_line"]
    end = repair.get("suggested_end_line") or repair["current_end_line"]
    if value["start_line"] != start or value["end_line"] != end:
        raise PipelineError("approve 只能接受 Step 2 已建议的精确连续范围")
    if value["confidence"] < 0.90:
        raise PipelineError("approve 的 confidence 必须至少为 0.90")
    if value["unresolved_risks"]:
        raise PipelineError("approve 不得保留 unresolved_risks")


def build_prompt(repair: dict[str, Any], analysis_path: Path, context_path: Path) -> str:
    """构造只读、保守的 Terra 二次裁决提示。"""

    start = repair.get("suggested_start_line") or repair["current_start_line"]
    end = repair.get("suggested_end_line") or repair["current_end_line"]
    return f"""你在执行训练数据流水线 Step 2b：独立裁决一条连续边界修复建议。

只读取以下两个文件：
- Step 2 分析：`{relative_to_repo(analysis_path)}`
- 带精确行号的边界上下文：`{relative_to_repo(context_path)}`

输入绑定：source_id=`{repair['source_id']}`，来源=`{repair['source_path']}`。
当前范围是 L{repair['current_start_line']}–L{repair['current_end_line']}；唯一候选范围是
L{start}–L{end}。Step 2 的问题说明为：{repair['issues']}

你只能输出 approve 或 reject。只有同时确认候选范围是一个完整、连续的独立故事，包含完整开头和结局，
且没有相邻故事、广告、栏目、编辑文字、内部串页或未解决缺段，才输出 approve。approve 时必须精确返回
start_line={start}、end_line={end}、confidence>=0.90、unresolved_risks=[]。

只要上下文证据不足、存在内部污染/非连续正文、缺头缺尾，或无法确认相邻边界，就输出 reject；不要猜测，
不要建议不同的新范围。不得读取整期原文、不得写文件。输出严格符合 JSON Schema。"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Terra 自动裁决 Step 2 连续边界修复建议")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--limit", type=int, default=DEFAULT_STORY_BATCH_LIMIT)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--heartbeat-seconds", type=float, default=DEFAULT_HEARTBEAT_SECONDS)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_automatic_model_policy(args.model, args.reasoning_effort)
    if args.workers < 1:
        raise PipelineError("workers 必须大于 0")
    queue_path = args.work_dir / "boundary_repair_queue.jsonl"
    if not queue_path.is_file():
        raise PipelineError(f"找不到 Step 2 修复队列：{queue_path}")
    repairs = [item for item in read_jsonl(queue_path) if repair_has_changed_range(item)]
    stories = {item["source_id"]: item for item in eligible_story_records(args.work_dir / "stories.jsonl")}
    decisions_dir = args.work_dir / "boundary_repair_decisions"
    pending: list[tuple[dict[str, Any], dict[str, Any], Path, Path, str]] = []
    for repair in repairs:
        story = stories.get(repair["source_id"])
        analysis_path = args.work_dir / "analysis" / f"{repair['source_id']}.json"
        if story is None or not analysis_path.is_file():
            continue
        analysis = read_json(analysis_path)
        validate_analysis(analysis, repair["source_id"])
        digest = canonical_json_sha256(repair)
        output_path = decisions_dir / f"{repair['source_id']}.json"
        if output_path.is_file():
            try:
                existing = read_json(output_path)
                validate_decision(existing, repair)
                if existing.get("_provenance", {}).get("repair_sha256") == digest:
                    continue
            except PipelineError:
                pass
        context_path = args.work_dir / "boundary_context" / f"{repair['source_id']}.txt"
        if not context_path.is_file():
            source_file = Path("training/原始资源") / story["source_path"]
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(build_story_boundary_context(story, source_file), encoding="utf-8")
        pending.append((repair, story, analysis_path, context_path, digest))
    total = len(repairs)
    pending_total = len(pending)
    pending = limit_pending_items(pending, args.limit)
    print(f"自动边界裁决待处理：{len(pending)} / 有候选建议：{total}")
    if args.dry_run:
        if pending:
            repair, _, analysis_path, context_path, _ = pending[0]
            print("示例命令：" + shlex.join(codex_command(prompt=build_prompt(repair, analysis_path, context_path), model=args.model, reasoning_effort=args.reasoning_effort, schema_path=SCHEMA_PATH, output_path=decisions_dir / "example.json.tmp")))
        return 0

    def decide(item: tuple[dict[str, Any], dict[str, Any], Path, Path, str]) -> None:
        repair, _, analysis_path, context_path, digest = item
        output_path = decisions_dir / f"{repair['source_id']}.json"
        result = run_codex_task(prompt=build_prompt(repair, analysis_path, context_path), model=args.model, reasoning_effort=args.reasoning_effort, schema_path=SCHEMA_PATH, output_path=output_path, validator=lambda value: validate_decision(value, repair), retries=args.retries, timeout=args.timeout)
        result["_provenance"] = {"stage": "automatic_boundary_repair_decision", "model": args.model, "reasoning_effort": args.reasoning_effort, "repair_sha256": digest, "generated_at": utc_now()}
        write_json(output_path, result)

    failures = run_parallel_tasks(pending, workers=args.workers, heartbeat_seconds=args.heartbeat_seconds, stage_label="Terra 自动边界裁决", item_label=lambda item: str(item[0]["source_id"]), task=decide, on_error=lambda item, error: write_json(args.work_dir / "errors" / "step_2b" / f"{item[0]['source_id']}.json", {"source_id": item[0]["source_id"], "error": str(error)}), continue_on_error=args.continue_on_error, progress_path=args.work_dir / "progress" / "step_2b_boundary_decision.json", progress_stage="step_2b_boundary_decision", total_items=total, completed_before=total - pending_total)
    approved = []
    for repair in repairs:
        path = decisions_dir / f"{repair['source_id']}.json"
        if not path.is_file():
            continue
        decision = read_json(path)
        try:
            validate_decision(decision, repair)
        except PipelineError:
            continue
        if decision["decision"] == "approve":
            approved.append(repair)
    write_jsonl(args.work_dir / "boundary_repair_auto_approved.jsonl", approved)
    print(f"自动批准连续修复：{len(approved)}；裁决失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
