#!/usr/bin/env python3
"""Step 5：用 Terra 裁决疑难样本；自动失败后生成手工 Sol 升级包。"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_STORY_BATCH_LIMIT,
    DEFAULT_WORK_DIR,
    PipelineError,
    PipelineManualEscalationRequired,
    PipelineTaskFailed,
    REPO_ROOT,
    atomic_write_text,
    canonical_json_sha256,
    codex_command,
    eligible_story_records,
    limit_pending_items,
    read_json,
    read_jsonl,
    relative_to_repo,
    run_codex_task,
    run_codex_task_with_quality_fallback,
    run_parallel_tasks,
    utc_now,
    validate_automatic_model_policy,
    validate_exact_keys,
    write_json,
    write_jsonl,
    write_manual_escalation_package,
)
from step_2_analyze_stories import (
    boundary_assessment_passes,
    build_story_boundary_context,
    validate_analysis,
)
from step_3_rewrite_stories import (
    DEFAULT_TEACHER_SPLITS,
    forbidden_output_markers,
    validate_rewrite,
)
from step_4_review_rewrites import deterministic_gate, validate_review


DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_REPAIR_REASONING_EFFORT = "high"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "story_adjudication.schema.json"
REQUIRED_KEYS = {
    "source_id",
    "decision",
    "factual_consistency",
    "audio_readability",
    "suspense_preservation",
    "required_corrections",
    "final_output_b",
    "rationale",
}


def validate_adjudication(value: dict[str, Any], source_id: str | None = None) -> None:
    """校验 Terra 或人工 Sol 裁决和最终文本。"""

    validate_exact_keys(
        value,
        required=REQUIRED_KEYS,
        optional={"_provenance", "_deterministic_gate"},
    )
    if source_id is not None and value["source_id"] != source_id:
        raise PipelineError(f"裁决结果 source_id 不匹配：{value['source_id']} != {source_id}")
    if value["decision"] not in {"pass", "revise", "reject"}:
        raise PipelineError("裁决 decision 无效")
    for key in ("factual_consistency", "audio_readability", "suspense_preservation"):
        score = value[key]
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
            raise PipelineError(f"裁决结果 {key} 必须是 0–1 数字")
    if not isinstance(value["required_corrections"], list) or not all(
        isinstance(item, str) for item in value["required_corrections"]
    ):
        raise PipelineError("required_corrections 必须是字符串数组")
    if not isinstance(value["final_output_b"], str):
        raise PipelineError("final_output_b 必须是字符串")
    if value["decision"] == "pass" and not value["final_output_b"].strip():
        raise PipelineError("pass 裁决必须提供非空 final_output_b")
    markers = forbidden_output_markers(value["final_output_b"])
    if markers:
        raise PipelineError(f"final_output_b 含禁用标签：{', '.join(markers[:5])}")


def adjudication_gate(value: dict[str, Any]) -> dict[str, Any]:
    """对裁决应用最终确定性质量门槛。"""

    thresholds_met = (
        value["factual_consistency"] >= 0.97
        and value["audio_readability"] >= 0.85
        and value["suspense_preservation"] >= 0.88
    )
    passed = (
        value["decision"] == "pass"
        and thresholds_met
        and not value["required_corrections"]
        and bool(value["final_output_b"].strip())
    )
    return {
        "decision": "pass" if passed else value["decision"],
        "passed": passed,
        "thresholds": {
            "factual_consistency": 0.97,
            "audio_readability": 0.85,
            "suspense_preservation": 0.88,
        },
        "thresholds_met": thresholds_met,
    }


def load_gold_ids(path: Path | None) -> set[str]:
    """读取显式金标准样本 ID。"""

    if path is None:
        return set()
    ids: set[str] = set()
    for record in read_jsonl(path):
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise PipelineError(f"金标准清单缺少 source_id：{path}")
        ids.add(source_id)
    return ids


def build_prompt(
    story_record: dict[str, Any],
    story_path: Path,
    analysis_path: Path,
    rewrite_path: Path,
    review_path: Path,
    boundary_context_path: Path,
    *,
    gold_standard: bool,
    previous_adjudication_path: Path | None = None,
) -> str:
    """构造质量优先的 Terra 裁决或一次定向修复任务。"""

    gold_note = "这是验证/测试金标准样本，按最高保真标准裁决。" if gold_standard else ""
    repair_note = (
        "\n- 上一轮 Terra 裁决："
        f"`{relative_to_repo(previous_adjudication_path)}`。逐项解决其中未通过的门禁，"
        "不要重复未修复的 revise 结论。"
        if previous_adjudication_path is not None
        else ""
    )
    return f"""你正在执行训练数据流水线 Step 5：裁决疑难 A→B 样本。{gold_note}

读取：
- 完整原稿 A：`{relative_to_repo(story_path)}`
- Python 生成的边界前后局部原文：`{relative_to_repo(boundary_context_path)}`
- 不可变事实和故事结构：`{relative_to_repo(analysis_path)}`
- 改写 B：`{relative_to_repo(rewrite_path)}`
- 独立复核：`{relative_to_repo(review_path)}`{repair_note}

不要打开原始整期来源；局部包已经包含边界审计所需上下文。

输出必须严格符合给定 JSON Schema，source_id 必须是 `{story_record['source_id']}`。

以人物、时间、地点、死亡方式、关键物件、线索、误导、反转和因果链为硬约束。若 B 已合格，
decision=pass，并把确认后的完整纯文本写入 final_output_b。若问题明确且你能无歧义修正，可修正后
decision=pass；若仍需另一轮生成则 decision=revise 并列出 required_corrections；来源损坏或无法保真
则 reject。若原始边界缺开头、缺结尾或混入另一作品，必须 reject；不得通过续写、删节或猜测修复
边界问题。final_output_b 不能含 Markdown、解释、speaker/emotion、SFX、BGM 或 TTS/导演字段。
不要执行其他文件操作。
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 5 命令行。"""

    parser = argparse.ArgumentParser(description="用 Terra 裁决疑难故事并生成手工 Sol 升级包")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--gold-manifest", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument(
        "--repair-reasoning-effort",
        default=DEFAULT_REPAIR_REASONING_EFFORT,
        help="Terra 首轮未通过时唯一一次定向修复强度，默认 high",
    )
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
        help="限制处理集合；默认只处理 train 和 validation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_STORY_BATCH_LIMIT,
        help="每次最多处理的尚未完成项；重复执行同一命令会继续下一批",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="仅临时网络/传输失败的额外重试次数，默认 1",
    )
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="并发裁决故事数，默认 2；额度受限时降为 1",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_SECONDS,
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 5。"""

    args = build_parser().parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.variant):
        raise PipelineError("variant 只能包含字母、数字、点、下划线和连字符")
    validate_automatic_model_policy(args.model, args.reasoning_effort)
    validate_automatic_model_policy(args.model, args.repair_reasoning_effort)
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    analysis_dir = args.analysis_dir or args.work_dir / "analysis"
    rewrite_dir = args.work_dir / "rewrites" / args.variant
    review_dir = args.work_dir / "reviews" / args.variant
    output_dir = args.work_dir / "adjudications" / args.variant
    attempt_dir = args.work_dir / "adjudication_attempts" / args.variant
    context_dir = args.work_dir / "boundary_context"
    manual_result_dir = args.work_dir / "manual_results" / "step_5" / args.variant
    manual_package_dir = args.work_dir / "manual_escalation" / "step_5" / args.variant
    include_splits = (
        set(args.include_split) if args.include_split else set(DEFAULT_TEACHER_SPLITS)
    )
    split_scope = "_".join(sorted(include_splits))
    gold_ids = load_gold_ids(args.gold_manifest)
    stories = eligible_story_records(manifest, include_splits)
    selected: list[tuple[dict[str, Any], Path, Path, Path, bool, str]] = []
    skipped: list[dict[str, str]] = []
    manual_pending: list[dict[str, str]] = []
    candidate_count = 0
    for story in stories:
        source_id = str(story["source_id"])
        analysis_path = analysis_dir / f"{source_id}.json"
        rewrite_path = rewrite_dir / f"{source_id}.json"
        review_path = review_dir / f"{source_id}.json"
        if not all(path.is_file() for path in (analysis_path, rewrite_path, review_path)):
            skipped.append({"source_id": source_id, "reason": "missing_step_2_to_4_output"})
            continue
        analysis = read_json(analysis_path)
        rewrite = read_json(rewrite_path)
        review = read_json(review_path)
        validate_analysis(analysis, source_id)
        if not boundary_assessment_passes(analysis):
            skipped.append({"source_id": source_id, "reason": "boundary_not_complete"})
            continue
        validate_rewrite(rewrite, source_id, str(story["sha256"]))
        validate_review(review, source_id)
        gate = review.get("_deterministic_gate") or deterministic_gate(review)
        gold_standard = source_id in gold_ids or story.get("split") in {"validation", "test"}
        needs_adjudication = (
            analysis["difficulty"] == "hard"
            or gate["decision"] != "pass"
            or gold_standard
        )
        if not needs_adjudication:
            continue
        candidate_count += 1
        evidence_sha256 = canonical_json_sha256(
            {
                "analysis": {
                    key: value for key, value in analysis.items() if not key.startswith("_")
                },
                "rewrite_output_b": rewrite["output_b"],
                "review": {
                    key: value for key, value in review.items() if not key.startswith("_")
                },
            }
        )
        output_path = output_dir / f"{source_id}.json"
        manual_result_path = manual_result_dir / f"{source_id}.json"
        if manual_result_path.is_file() and not args.overwrite:
            manual_result = read_json(manual_result_path)
            validate_adjudication(manual_result, source_id)
            manual_result["_deterministic_gate"] = adjudication_gate(manual_result)
            manual_result["_provenance"] = {
                "stage": "manual_adjudication",
                "variant": args.variant,
                "model": "manual-sol",
                "reasoning_effort": "manual",
                "speed": "standard",
                "gold_standard": gold_standard,
                "input_sha256": story["sha256"],
                "evidence_sha256": evidence_sha256,
                "imported_at": utc_now(),
            }
            write_json(output_path, manual_result)
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_adjudication(existing, source_id)
                if existing.get("_provenance", {}).get("evidence_sha256") == evidence_sha256:
                    if existing.get("_provenance", {}).get(
                        "manual_escalation_required"
                    ):
                        manual_pending.append(
                            {
                                "source_id": source_id,
                                "package": relative_to_repo(
                                    manual_package_dir / f"{source_id}.md"
                                ),
                                "result_path": relative_to_repo(manual_result_path),
                            }
                        )
                    continue
            except PipelineError:
                pass
        selected.append(
            (story, analysis_path, rewrite_path, review_path, gold_standard, evidence_sha256)
        )
    pending_total = len(selected)
    completed_before = candidate_count - pending_total - len(manual_pending)
    selected = limit_pending_items(selected, args.limit)
    print(
        f"Terra 待裁决：{len(selected)} / 可用故事：{len(stories)}；"
        f"前序阻断：{len(skipped)}；等待人工 Sol：{len(manual_pending)}"
    )
    if args.dry_run:
        if selected:
            story, analysis_path, rewrite_path, review_path, gold, _ = selected[0]
            story_path = args.work_dir / story["story_path"]
            context_path = context_dir / f"{story['source_id']}.txt"
            command = codex_command(
                prompt=build_prompt(
                    story,
                    story_path,
                    analysis_path,
                    rewrite_path,
                    review_path,
                    context_path,
                    gold_standard=gold,
                ),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{story['source_id']}.json.tmp",
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    def adjudicate_story(
        item: tuple[dict[str, Any], Path, Path, Path, bool, str]
    ) -> None:
        story, analysis_path, rewrite_path, review_path, gold, evidence_sha256 = item
        source_id = str(story["source_id"])
        story_path = args.work_dir / story["story_path"]
        output_path = output_dir / f"{source_id}.json"
        source_file = REPO_ROOT / str(
            story.get("source_file", f"training/{story['source_path']}")
        )
        context_path = context_dir / f"{source_id}.txt"
        if not context_path.is_file():
            atomic_write_text(
                context_path,
                build_story_boundary_context(story, source_file),
            )
        first_prompt = build_prompt(
            story,
            story_path,
            analysis_path,
            rewrite_path,
            review_path,
            context_path,
            gold_standard=gold,
        )

        def require_manual(error: str, prompt: str) -> None:
            manual_result_path = manual_result_dir / f"{source_id}.json"
            package_path = write_manual_escalation_package(
                package_dir=manual_package_dir,
                item_id=source_id,
                stage="Step 5 Terra 裁决",
                prompt=prompt,
                schema_path=SCHEMA_PATH,
                manual_result_path=manual_result_path,
                error=error,
            )
            manual_pending.append(
                {
                    "source_id": source_id,
                    "package": relative_to_repo(package_path),
                    "result_path": relative_to_repo(manual_result_path),
                }
            )
            print(
                f"[需人工 Sol] {source_id}：{package_path}；"
                f"结果保存到 {manual_result_path} 后重跑同一命令",
                flush=True,
            )

        try:
            result, effective_model, effective_effort, used_fallback = (
                run_codex_task_with_quality_fallback(
                    prompt=first_prompt,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                    fallback_model=args.model,
                    fallback_reasoning_effort=args.repair_reasoning_effort,
                    schema_path=SCHEMA_PATH,
                    output_path=output_path,
                    validator=lambda value, expected=source_id: validate_adjudication(
                        value, expected
                    ),
                    retries=args.retries,
                    timeout=args.timeout,
                )
            )
        except PipelineManualEscalationRequired as error:
            require_manual(str(error), first_prompt)
            raise

        gate = adjudication_gate(result)
        if not gate["passed"] and not used_fallback:
            first_attempt_path = attempt_dir / f"{source_id}.medium.json"
            write_json(first_attempt_path, result)
            repair_prompt = build_prompt(
                story,
                story_path,
                analysis_path,
                rewrite_path,
                review_path,
                context_path,
                gold_standard=gold,
                previous_adjudication_path=first_attempt_path,
            )
            try:
                result = run_codex_task(
                    prompt=repair_prompt,
                    model=args.model,
                    reasoning_effort=args.repair_reasoning_effort,
                    schema_path=SCHEMA_PATH,
                    output_path=output_path,
                    validator=lambda value, expected=source_id: validate_adjudication(
                        value, expected
                    ),
                    retries=args.retries,
                    timeout=args.timeout,
                )
            except PipelineTaskFailed as error:
                if error.failure_kind in {"transport", "timeout"}:
                    raise
                require_manual(str(error), repair_prompt)
                raise PipelineManualEscalationRequired(
                    "Terra high 定向修复未能产生有效裁决；需要人工 Sol"
                ) from error
            effective_model = args.model
            effective_effort = args.repair_reasoning_effort
            used_fallback = True
            gate = adjudication_gate(result)

        manual_required = not gate["passed"]
        if manual_required:
            require_manual(
                "Terra medium 与一次 Terra high 后仍未通过最终门禁",
                build_prompt(
                    story,
                    story_path,
                    analysis_path,
                    rewrite_path,
                    review_path,
                    context_path,
                    gold_standard=gold,
                    previous_adjudication_path=(
                        attempt_dir / f"{source_id}.medium.json"
                        if (attempt_dir / f"{source_id}.medium.json").is_file()
                        else None
                    ),
                ),
            )
        result["_deterministic_gate"] = gate
        result["_provenance"] = {
            "stage": "terra_adjudication",
            "variant": args.variant,
            "model": effective_model,
            "reasoning_effort": effective_effort,
            "quality_fallback_used": used_fallback,
            "manual_escalation_required": manual_required,
            "speed": "standard",
            "boundary_context": relative_to_repo(context_path),
            "gold_standard": gold,
            "input_sha256": story["sha256"],
            "evidence_sha256": evidence_sha256,
            "generated_at": utc_now(),
        }
        write_json(output_path, result)
        if manual_required:
            raise PipelineManualEscalationRequired(
                "Terra 自动裁决已保留，但未通过最终门禁；需要人工 Sol"
            )
        (
            args.work_dir / "errors" / "step_5" / args.variant / f"{source_id}.json"
        ).unlink(missing_ok=True)

    def record_adjudication_error(
        item: tuple[dict[str, Any], Path, Path, Path, bool, str], error: Exception
    ) -> None:
        source_id = str(item[0]["source_id"])
        write_json(
            args.work_dir / "errors" / "step_5" / args.variant / f"{source_id}.json",
            {"source_id": source_id, "stage": "terra_adjudication", "error": str(error)},
        )

    failures = run_parallel_tasks(
        selected,
        workers=args.workers,
        heartbeat_seconds=args.heartbeat_seconds,
        stage_label="Terra 疑难裁决",
        item_label=lambda item: str(item[0]["source_id"]),
        task=adjudicate_story,
        on_error=record_adjudication_error,
        continue_on_error=args.continue_on_error,
        progress_path=(
            args.work_dir
            / "progress"
            / f"step_5_{args.variant}_{split_scope}.json"
        ),
        progress_stage=f"step_5_{args.variant}_{split_scope}",
        total_items=candidate_count,
        completed_before=completed_before,
    )
    write_jsonl(
        args.work_dir / "errors" / "step_5" / args.variant / "prerequisite_blocked.jsonl",
        skipped,
    )
    write_jsonl(
        args.work_dir / "manual_escalation" / "step_5" / args.variant / "pending.jsonl",
        manual_pending,
    )
    print(
        f"裁决完成：{len(selected) - failures}；失败：{failures}；"
        f"既有等待人工 Sol：{len(manual_pending)}"
    )
    return 1 if failures or manual_pending else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
