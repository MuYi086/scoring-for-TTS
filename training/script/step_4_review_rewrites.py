#!/usr/bin/env python3
"""Step 4：使用第二次独立 Terra 调用比较 A 与 B，只纠错、不重写。"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_WORK_DIR,
    PipelineError,
    canonical_json_sha256,
    codex_command,
    eligible_story_records,
    read_json,
    relative_to_repo,
    run_codex_task,
    sha256_text,
    utc_now,
    validate_exact_keys,
    write_json,
)
from step_2_analyze_stories import validate_analysis
from step_3_rewrite_stories import validate_rewrite


DEFAULT_MODEL = "gpt-5.6-terra"
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
) -> str:
    """构造独立 A/B 保真复核任务。"""

    return f"""你正在执行训练数据流水线 Step 4：独立比较原稿 A 与有声稿 B。

读取：
- 完整原稿 A：`{relative_to_repo(story_path)}`
- Step 2 事实清单：`{relative_to_repo(analysis_path)}`
- Step 3 改写结果 B：`{relative_to_repo(rewrite_path)}`

只做检查，不重新创作，不直接修改 B。输出必须严格符合给定 JSON Schema，source_id 必须是
`{story_record['source_id']}`。

逐项核对 B 是否遗漏、篡改或新增人物、时间、地点、死亡方式、关键物件、线索、误导、反转和
因果链；再评估断句、对白归属、指代和有声朗读节奏。problems 的 evidence 用简短定位说明，
不要复制长段原文。任何无法确认的硬事实应 decision=escalate，明显可修问题为 revise，只有无硬伤且
达到高质量时才 pass。不要执行其他文件操作。
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 4 命令行。"""

    parser = argparse.ArgumentParser(description="用独立 Terra 调用复核 A/B 保真度")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--profile", help="可选 Codex profile；默认 Standard")
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=2400)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 4。"""

    args = build_parser().parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.variant):
        raise PipelineError("variant 只能包含字母、数字、点、下划线和连字符")
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    analysis_dir = args.analysis_dir or args.work_dir / "analysis"
    rewrite_dir = args.work_dir / "rewrites" / args.variant
    output_dir = args.work_dir / "reviews" / args.variant
    include_splits = set(args.include_split) if args.include_split else None
    stories = eligible_story_records(manifest, include_splits)
    if args.limit is not None:
        if args.limit < 0:
            raise PipelineError("limit 不能小于 0")
        stories = stories[: args.limit]
    pending: list[tuple[dict[str, Any], Path, Path, str, str]] = []
    for story in stories:
        source_id = str(story["source_id"])
        analysis_path = analysis_dir / f"{source_id}.json"
        rewrite_path = rewrite_dir / f"{source_id}.json"
        if not analysis_path.is_file() or not rewrite_path.is_file():
            raise PipelineError(f"缺少 {source_id} 的 Step 2 或 Step 3 输出")
        analysis = read_json(analysis_path)
        rewrite = read_json(rewrite_path)
        validate_analysis(analysis, source_id)
        validate_rewrite(rewrite, source_id, str(story["sha256"]))
        analysis_sha256 = canonical_json_sha256(
            {key: value for key, value in analysis.items() if not key.startswith("_")}
        )
        rewrite_sha256 = sha256_text(rewrite["output_b"])
        output_path = output_dir / f"{source_id}.json"
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_review(existing, source_id)
                provenance = existing.get("_provenance", {})
                if (
                    provenance.get("rewrite_sha256") == rewrite_sha256
                    and provenance.get("analysis_sha256") == analysis_sha256
                ):
                    continue
            except PipelineError:
                pass
        pending.append(
            (story, analysis_path, rewrite_path, analysis_sha256, rewrite_sha256)
        )
    print(f"独立复核待处理：{len(pending)} / 可用故事：{len(stories)}")
    if args.dry_run:
        if pending:
            story, analysis_path, rewrite_path, _, _ = pending[0]
            story_path = args.work_dir / story["story_path"]
            command = codex_command(
                prompt=build_prompt(story, story_path, analysis_path, rewrite_path),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{story['source_id']}.json.tmp",
                profile=args.profile,
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    failures = 0
    for index, item in enumerate(pending, 1):
        story, analysis_path, rewrite_path, analysis_sha256, rewrite_sha256 = item
        source_id = str(story["source_id"])
        story_path = args.work_dir / story["story_path"]
        output_path = output_dir / f"{source_id}.json"
        print(f"[{index}/{len(pending)}] Terra 独立复核 {source_id}", flush=True)
        try:
            result = run_codex_task(
                prompt=build_prompt(story, story_path, analysis_path, rewrite_path),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_path,
                validator=lambda value, expected=source_id: validate_review(value, expected),
                retries=args.retries,
                timeout=args.timeout,
                profile=args.profile,
            )
            result["_deterministic_gate"] = deterministic_gate(result)
            result["_provenance"] = {
                "stage": "rewrite_review",
                "variant": args.variant,
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "speed": "profile" if args.profile else "standard",
                "profile": args.profile,
                "input_sha256": story["sha256"],
                "analysis_sha256": analysis_sha256,
                "rewrite_sha256": rewrite_sha256,
                "generated_at": utc_now(),
            }
            write_json(output_path, result)
        except PipelineError as error:
            failures += 1
            write_json(
                args.work_dir / "errors" / "step_4" / args.variant / f"{source_id}.json",
                {"source_id": source_id, "stage": "rewrite_review", "error": str(error)},
            )
            if not args.continue_on_error:
                raise
    print(f"复核完成：{len(pending) - failures}；失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
