#!/usr/bin/env python3
"""Step 5：仅用 Sol 裁决疑难样本、冲突样本和金标准样本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_WORK_DIR,
    PipelineError,
    REPO_ROOT,
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
    validate_exact_keys,
    write_json,
    write_jsonl,
)
from step_2_analyze_stories import boundary_assessment_passes, validate_analysis
from step_3_rewrite_stories import (
    DEFAULT_TEACHER_SPLITS,
    forbidden_output_markers,
    validate_rewrite,
)
from step_4_review_rewrites import deterministic_gate, validate_review


DEFAULT_MODEL = "gpt-5.6-sol"
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
    """校验 Sol 裁决和最终文本。"""

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
    """对 Sol 裁决应用最终确定性质量门槛。"""

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
    *,
    gold_standard: bool,
) -> str:
    """构造质量优先的 Sol 裁决任务。"""

    gold_note = "这是验证/测试金标准样本，按最高保真标准裁决。" if gold_standard else ""
    source_file = REPO_ROOT / str(
        story_record.get("source_file", f"training/{story_record['source_path']}")
    )
    return f"""你正在执行训练数据流水线 Step 5：裁决疑难 A→B 样本。{gold_note}

读取：
- 完整原稿 A：`{relative_to_repo(story_path)}`
- 原始整期来源：`{relative_to_repo(source_file)}`，当前边界为
  {story_record['start_line']}–{story_record['end_line']}
- 不可变事实和故事结构：`{relative_to_repo(analysis_path)}`
- Terra 改写 B：`{relative_to_repo(rewrite_path)}`
- 独立 Terra 复核：`{relative_to_repo(review_path)}`

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

    parser = argparse.ArgumentParser(description="用 Sol 裁决疑难和金标准故事")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--gold-manifest", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--gold-reasoning-effort", default="xhigh")
    parser.add_argument("--profile", help="可选 Codex profile；默认 Standard")
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
        help="限制处理集合；默认只处理 train 和 validation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="每次最多处理的尚未完成项；重复执行同一命令会继续下一批",
    )
    parser.add_argument("--retries", type=int, default=1)
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
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    analysis_dir = args.analysis_dir or args.work_dir / "analysis"
    rewrite_dir = args.work_dir / "rewrites" / args.variant
    review_dir = args.work_dir / "reviews" / args.variant
    output_dir = args.work_dir / "adjudications" / args.variant
    include_splits = (
        set(args.include_split) if args.include_split else set(DEFAULT_TEACHER_SPLITS)
    )
    split_scope = "_".join(sorted(include_splits))
    gold_ids = load_gold_ids(args.gold_manifest)
    stories = eligible_story_records(manifest, include_splits)
    selected: list[tuple[dict[str, Any], Path, Path, Path, bool, str]] = []
    skipped: list[dict[str, str]] = []
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
        needs_sol = analysis["difficulty"] == "hard" or gate["decision"] != "pass" or gold_standard
        if not needs_sol:
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
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_adjudication(existing, source_id)
                if existing.get("_provenance", {}).get("evidence_sha256") == evidence_sha256:
                    continue
            except PipelineError:
                pass
        selected.append(
            (story, analysis_path, rewrite_path, review_path, gold_standard, evidence_sha256)
        )
    pending_total = len(selected)
    completed_before = candidate_count - pending_total
    selected = limit_pending_items(selected, args.limit)
    print(
        f"Sol 待裁决：{len(selected)} / 可用故事：{len(stories)}；"
        f"前序阻断：{len(skipped)}"
    )
    if args.dry_run:
        if selected:
            story, analysis_path, rewrite_path, review_path, gold, _ = selected[0]
            story_path = args.work_dir / story["story_path"]
            effort = args.gold_reasoning_effort if gold else args.reasoning_effort
            command = codex_command(
                prompt=build_prompt(
                    story,
                    story_path,
                    analysis_path,
                    rewrite_path,
                    review_path,
                    gold_standard=gold,
                ),
                model=args.model,
                reasoning_effort=effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{story['source_id']}.json.tmp",
                profile=args.profile,
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
        effort = args.gold_reasoning_effort if gold else args.reasoning_effort
        result = run_codex_task(
            prompt=build_prompt(
                story,
                story_path,
                analysis_path,
                rewrite_path,
                review_path,
                gold_standard=gold,
            ),
            model=args.model,
            reasoning_effort=effort,
            schema_path=SCHEMA_PATH,
            output_path=output_path,
            validator=lambda value, expected=source_id: validate_adjudication(
                value, expected
            ),
            retries=args.retries,
            timeout=args.timeout,
            profile=args.profile,
        )
        result["_deterministic_gate"] = adjudication_gate(result)
        result["_provenance"] = {
            "stage": "sol_adjudication",
            "variant": args.variant,
            "model": args.model,
            "reasoning_effort": effort,
            "speed": "profile" if args.profile else "standard",
            "profile": args.profile,
            "gold_standard": gold,
            "input_sha256": story["sha256"],
            "evidence_sha256": evidence_sha256,
            "generated_at": utc_now(),
        }
        write_json(output_path, result)
        (
            args.work_dir / "errors" / "step_5" / args.variant / f"{source_id}.json"
        ).unlink(missing_ok=True)

    def record_adjudication_error(
        item: tuple[dict[str, Any], Path, Path, Path, bool, str], error: Exception
    ) -> None:
        source_id = str(item[0]["source_id"])
        write_json(
            args.work_dir / "errors" / "step_5" / args.variant / f"{source_id}.json",
            {"source_id": source_id, "stage": "sol_adjudication", "error": str(error)},
        )

    failures = run_parallel_tasks(
        selected,
        workers=args.workers,
        heartbeat_seconds=args.heartbeat_seconds,
        stage_label="Sol 疑难裁决",
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
    print(f"裁决完成：{len(selected) - failures}；失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
