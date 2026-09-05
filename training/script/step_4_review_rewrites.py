#!/usr/bin/env python3
"""Step 4：优先用 Luna 独立比较 A/B，风险样本路由 Terra。"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_STORY_BATCH_LIMIT,
    DEFAULT_WORK_DIR,
    PipelineError,
    REPO_ROOT,
    atomic_write_text,
    canonical_json_sha256,
    codex_command,
    eligible_story_records,
    limit_pending_items,
    read_json,
    relative_to_repo,
    run_codex_task,
    run_parallel_tasks,
    sha256_text,
    utc_now,
    validate_automatic_model_policy,
    validate_exact_keys,
    write_json,
    write_jsonl,
)
from step_2_analyze_stories import (
    boundary_assessment_passes,
    build_story_boundary_context,
    validate_analysis,
)
from step_3_rewrite_stories import DEFAULT_TEACHER_SPLITS, validate_rewrite


DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REVIEW_MODEL = "gpt-5.6-terra"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "story_review.schema.json"
REQUIRED_KEYS = {
    "source_id",
    "factual_consistency",
    "audio_readability",
    "suspense_preservation",
    "problems",
    "decision",
}


def validate_review(value: dict[str, Any], source_id: str | None = None) -> None:
    """校验独立复核结果。"""

    validate_exact_keys(
        value,
        required=REQUIRED_KEYS,
        optional={"_provenance", "_deterministic_gate"},
    )
    if source_id is not None and value["source_id"] != source_id:
        raise PipelineError(f"复核结果 source_id 不匹配：{value['source_id']} != {source_id}")
    for key in ("factual_consistency", "audio_readability", "suspense_preservation"):
        score = value[key]
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
            raise PipelineError(f"复核结果 {key} 必须是 0–1 数字")
    if value["decision"] not in {"pass", "revise", "escalate"}:
        raise PipelineError("复核 decision 无效")
    if not isinstance(value["problems"], list):
        raise PipelineError("复核 problems 必须是数组")
    for problem in value["problems"]:
        if not isinstance(problem, dict) or problem.get("severity") not in {
            "minor",
            "major",
            "critical",
        }:
            raise PipelineError("复核 problem 结构或 severity 无效")
        if problem.get("category") not in {
            "source_boundary",
            "character",
            "time",
            "location",
            "death_method",
            "key_object",
            "clue",
            "misdirection",
            "twist",
            "causality",
            "readability",
            "suspense",
            "other",
        }:
            raise PipelineError("复核 problem.category 无效")


def deterministic_gate(review: dict[str, Any]) -> dict[str, Any]:
    """把模型评分转成稳定的 pass/revise/escalate 门禁。"""

    severities = [problem.get("severity") for problem in review["problems"]]
    thresholds_met = (
        review["factual_consistency"] >= 0.95
        and review["audio_readability"] >= 0.85
        and review["suspense_preservation"] >= 0.85
    )
    if "critical" in severities or review["decision"] == "escalate":
        gate_decision = "escalate"
    elif review["decision"] != "pass" or not thresholds_met or "major" in severities:
        gate_decision = "revise"
    else:
        gate_decision = "pass"
    return {
        "decision": gate_decision,
        "thresholds": {
            "factual_consistency": 0.95,
            "audio_readability": 0.85,
            "suspense_preservation": 0.85,
        },
        "thresholds_met": thresholds_met,
        "has_major_problem": "major" in severities,
        "has_critical_problem": "critical" in severities,
    }


def build_prompt(
    story_record: dict[str, Any],
    story_path: Path,
    analysis_path: Path,
    rewrite_path: Path,
    boundary_context_path: Path,
) -> str:
    """构造独立 A/B 保真复核任务。"""

    return f"""你正在执行训练数据流水线 Step 4：独立比较原稿 A 与有声稿 B。

读取：
- 完整原稿 A：`{relative_to_repo(story_path)}`
- Python 生成的边界前后局部原文：`{relative_to_repo(boundary_context_path)}`
- Step 2 事实清单：`{relative_to_repo(analysis_path)}`
- Step 3 改写结果 B：`{relative_to_repo(rewrite_path)}`

不要打开原始整期来源；边界局部包已经包含起止位置审计所需的带行号上下文。

只做检查，不重新创作，不直接修改 B。输出必须严格符合给定 JSON Schema，source_id 必须是
`{story_record['source_id']}`。

先独立核对 A 的起止边界是否完整、是否混入相邻作品；发现问题必须添加 category=source_boundary、
severity=critical 并 decision=escalate，不能靠重写 B 掩盖残缺来源。再逐项核对 B 是否遗漏、篡改或
新增人物、时间、地点、死亡方式、关键物件、线索、误导、反转和因果链，并评估断句、对白归属、
指代和有声朗读节奏。problems 的 evidence 用简短定位说明，不要复制长段原文。任何无法确认的硬事实
应 decision=escalate，明显可修问题为 revise，只有来源完整、无硬伤且达到高质量时才 pass。
不要执行其他文件操作。
"""


def stable_terra_audit_source_ids(
    source_ids: Sequence[str],
    percent: int,
) -> set[str]:
    """稳定选择普通 train 的 Terra 抽检项，并向上取整保证非空批次有覆盖。"""

    if percent <= 0 or not source_ids:
        return set()
    audit_count = min(len(source_ids), math.ceil(len(source_ids) * percent / 100))
    return set(sorted(source_ids, key=sha256_text)[:audit_count])


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 4 命令行。"""

    parser = argparse.ArgumentParser(description="用 Luna/Terra 风险路由复核 A/B 保真度")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--review-model", default=DEFAULT_REVIEW_MODEL)
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--review-reasoning-effort", default="medium")
    parser.add_argument(
        "--terra-audit-percent",
        type=int,
        default=10,
        help="普通 train 样本稳定抽取给 Terra 的百分比，默认 10",
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
    parser.add_argument("--timeout", type=float, default=2400)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="并发复核故事数，默认 2；额度受限时降为 1",
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
    """运行 Step 4。"""

    args = build_parser().parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.variant):
        raise PipelineError("variant 只能包含字母、数字、点、下划线和连字符")
    if not 0 <= args.terra_audit_percent <= 100:
        raise PipelineError("terra-audit-percent 必须在 0–100 之间")
    validate_automatic_model_policy(args.model, args.reasoning_effort)
    validate_automatic_model_policy(
        args.review_model,
        args.review_reasoning_effort,
    )
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    analysis_dir = args.analysis_dir or args.work_dir / "analysis"
    rewrite_dir = args.work_dir / "rewrites" / args.variant
    output_dir = args.work_dir / "reviews" / args.variant
    context_dir = args.work_dir / "boundary_context"
    include_splits = (
        set(args.include_split) if args.include_split else set(DEFAULT_TEACHER_SPLITS)
    )
    split_scope = "_".join(sorted(include_splits))
    stories = eligible_story_records(manifest, include_splits)
    candidates: list[tuple[dict[str, Any], Path, Path, dict[str, Any], dict[str, Any]]] = []
    pending: list[tuple[dict[str, Any], Path, Path, str, str, str, str, str]] = []
    skipped: list[dict[str, str]] = []
    for story in stories:
        source_id = str(story["source_id"])
        analysis_path = analysis_dir / f"{source_id}.json"
        rewrite_path = rewrite_dir / f"{source_id}.json"
        if not analysis_path.is_file():
            skipped.append({"source_id": source_id, "reason": "missing_step_2_analysis"})
            continue
        analysis = read_json(analysis_path)
        validate_analysis(analysis, source_id)
        if not boundary_assessment_passes(analysis):
            skipped.append({"source_id": source_id, "reason": "boundary_not_complete"})
            continue
        if not rewrite_path.is_file():
            skipped.append({"source_id": source_id, "reason": "missing_step_3_rewrite"})
            continue
        rewrite = read_json(rewrite_path)
        validate_rewrite(rewrite, source_id, str(story["sha256"]))
        candidates.append((story, analysis_path, rewrite_path, analysis, rewrite))

    normal_train_source_ids = []
    for story, _, _, analysis, rewrite in candidates:
        checks = rewrite.get("_deterministic_checks", {})
        is_risk = (
            analysis["difficulty"] == "hard"
            or story.get("split") == "validation"
            or rewrite["needs_human_review"]
            or bool(checks.get("new_name_candidates", []))
        )
        if story.get("split") == "train" and not is_risk:
            normal_train_source_ids.append(str(story["source_id"]))
    terra_audit_source_ids = stable_terra_audit_source_ids(
        normal_train_source_ids,
        args.terra_audit_percent,
    )

    for story, analysis_path, rewrite_path, analysis, rewrite in candidates:
        source_id = str(story["source_id"])
        analysis_sha256 = canonical_json_sha256(
            {key: value for key, value in analysis.items() if not key.startswith("_")}
        )
        rewrite_sha256 = sha256_text(rewrite["output_b"])
        checks = rewrite.get("_deterministic_checks", {})
        needs_terra = (
            analysis["difficulty"] == "hard"
            or story.get("split") == "validation"
            or rewrite["needs_human_review"]
            or bool(checks.get("new_name_candidates", []))
            or source_id in terra_audit_source_ids
        )
        model = args.review_model if needs_terra else args.model
        effort = (
            args.review_reasoning_effort if needs_terra else args.reasoning_effort
        )
        route = "risk_or_audit_review" if needs_terra else "luna_default_review"
        output_path = output_dir / f"{source_id}.json"
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_review(existing, source_id)
                provenance = existing.get("_provenance", {})
                if (
                    provenance.get("rewrite_sha256") == rewrite_sha256
                    and provenance.get("analysis_sha256") == analysis_sha256
                    and provenance.get("model") == model
                    and provenance.get("reasoning_effort") == effort
                    and provenance.get("model_route") == route
                ):
                    continue
            except PipelineError:
                pass
        pending.append(
            (
                story,
                analysis_path,
                rewrite_path,
                analysis_sha256,
                rewrite_sha256,
                model,
                effort,
                route,
            )
        )
    candidate_count = len(candidates)
    pending_total = len(pending)
    completed_before = candidate_count - pending_total
    pending = limit_pending_items(pending, args.limit)
    print(
        f"独立复核待处理：{len(pending)} / 可用故事：{len(stories)}；"
        f"前序阻断：{len(skipped)}"
    )
    if args.dry_run:
        if pending:
            story, analysis_path, rewrite_path, _, _, model, effort, _ = pending[0]
            story_path = args.work_dir / story["story_path"]
            context_path = context_dir / f"{story['source_id']}.txt"
            command = codex_command(
                prompt=build_prompt(
                    story,
                    story_path,
                    analysis_path,
                    rewrite_path,
                    context_path,
                ),
                model=model,
                reasoning_effort=effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{story['source_id']}.json.tmp",
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    def review_story(
        item: tuple[dict[str, Any], Path, Path, str, str, str, str, str]
    ) -> None:
        (
            story,
            analysis_path,
            rewrite_path,
            analysis_sha256,
            rewrite_sha256,
            model,
            effort,
            route,
        ) = item
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
        result = run_codex_task(
            prompt=build_prompt(
                story,
                story_path,
                analysis_path,
                rewrite_path,
                context_path,
            ),
            model=model,
            reasoning_effort=effort,
            schema_path=SCHEMA_PATH,
            output_path=output_path,
            validator=lambda value, expected=source_id: validate_review(value, expected),
            retries=args.retries,
            timeout=args.timeout,
        )
        result["_deterministic_gate"] = deterministic_gate(result)
        result["_provenance"] = {
            "stage": "rewrite_review",
            "variant": args.variant,
            "model": model,
            "reasoning_effort": effort,
            "model_route": route,
            "speed": "standard",
            "boundary_context": relative_to_repo(context_path),
            "input_sha256": story["sha256"],
            "analysis_sha256": analysis_sha256,
            "rewrite_sha256": rewrite_sha256,
            "generated_at": utc_now(),
        }
        write_json(output_path, result)
        (
            args.work_dir / "errors" / "step_4" / args.variant / f"{source_id}.json"
        ).unlink(missing_ok=True)

    def record_review_error(
        item: tuple[dict[str, Any], Path, Path, str, str, str, str, str],
        error: Exception,
    ) -> None:
        source_id = str(item[0]["source_id"])
        write_json(
            args.work_dir / "errors" / "step_4" / args.variant / f"{source_id}.json",
            {"source_id": source_id, "stage": "rewrite_review", "error": str(error)},
        )

    failures = run_parallel_tasks(
        pending,
        workers=args.workers,
        heartbeat_seconds=args.heartbeat_seconds,
        stage_label="Luna/Terra 独立复核",
        item_label=lambda item: str(item[0]["source_id"]),
        task=review_story,
        on_error=record_review_error,
        continue_on_error=args.continue_on_error,
        progress_path=(
            args.work_dir
            / "progress"
            / f"step_4_{args.variant}_{split_scope}.json"
        ),
        progress_stage=f"step_4_{args.variant}_{split_scope}",
        total_items=candidate_count,
        completed_before=completed_before,
    )
    write_jsonl(
        args.work_dir / "errors" / "step_4" / args.variant / "prerequisite_blocked.jsonl",
        skipped,
    )
    print(f"复核完成：{len(pending) - failures}；失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
