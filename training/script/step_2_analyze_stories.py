#!/usr/bin/env python3
"""Step 2：使用 GPT-5.6 Luna 批量理解经授权的完整故事。"""

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
    REPO_ROOT,
    atomic_write_text,
    codex_command,
    eligible_story_records,
    limit_pending_items,
    read_json,
    relative_to_repo,
    run_codex_task,
    run_parallel_tasks,
    utc_now,
    validate_automatic_model_policy,
    validate_exact_keys,
    write_json,
    write_jsonl,
)


DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_ANALYSIS_SPLITS = frozenset({"train", "validation"})
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "story_analysis.schema.json"
REQUIRED_KEYS = {
    "source_id",
    "characters",
    "immutable_facts",
    "clues",
    "misdirection",
    "twist",
    "story_dna",
    "ocr_flags",
    "difficulty",
    "boundary_assessment",
}


def validate_analysis(value: dict[str, Any], source_id: str | None = None) -> None:
    """校验 Luna 故事理解结果。"""

    validate_exact_keys(value, required=REQUIRED_KEYS, optional={"_provenance"})
    if source_id is not None and value["source_id"] != source_id:
        raise PipelineError(
            f"分析结果 source_id 不匹配：期望 {source_id}，得到 {value['source_id']}"
        )
    for key in ("characters", "immutable_facts", "clues", "misdirection", "ocr_flags"):
        if not isinstance(value[key], list):
            raise PipelineError(f"分析结果 {key} 必须是数组")
    if not isinstance(value["story_dna"], dict):
        raise PipelineError("分析结果 story_dna 必须是对象")
    if value["difficulty"] not in {"normal", "hard"}:
        raise PipelineError("分析结果 difficulty 必须是 normal 或 hard")
    boundary = value["boundary_assessment"]
    if not isinstance(boundary, dict):
        raise PipelineError("分析结果 boundary_assessment 必须是对象")
    validate_exact_keys(
        boundary,
        required={
            "status",
            "confidence",
            "issues",
            "suggested_start_line",
            "suggested_end_line",
        },
    )
    if boundary["status"] not in {"complete", "incomplete", "uncertain"}:
        raise PipelineError("boundary_assessment.status 无效")
    confidence = boundary["confidence"]
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise PipelineError("boundary_assessment.confidence 必须为 0–1")
    if not isinstance(boundary["issues"], list) or not all(
        isinstance(item, str) for item in boundary["issues"]
    ):
        raise PipelineError("boundary_assessment.issues 必须是字符串数组")
    for key in ("suggested_start_line", "suggested_end_line"):
        line = boundary[key]
        if line is not None and (
            not isinstance(line, int) or isinstance(line, bool) or line < 1
        ):
            raise PipelineError(f"boundary_assessment.{key} 必须是正整数或 null")


def boundary_assessment_passes(value: dict[str, Any], minimum_confidence: float = 0.80) -> bool:
    """判断 Step 2 是否确认来源边界足以进入改写。"""

    boundary = value["boundary_assessment"]
    return (
        boundary["status"] == "complete"
        and boundary["confidence"] >= minimum_confidence
        and not boundary["issues"]
    )


def build_story_boundary_context(
    story_record: dict[str, Any],
    source_file: Path,
    *,
    context_lines: int = 60,
) -> str:
    """生成故事边界两侧的带行号局部原文，不复制整期杂志。"""

    if context_lines < 1:
        raise PipelineError("context_lines 必须大于 0")
    lines = source_file.read_text(encoding="utf-8").splitlines()
    start_line = int(story_record["start_line"])
    end_line = int(story_record["end_line"])
    windows = (
        (max(1, start_line - context_lines), min(len(lines), start_line + context_lines)),
        (max(1, end_line - context_lines), min(len(lines), end_line + context_lines)),
    )
    parts = [
        f"source_path={story_record['source_path']}",
        f"story_boundary=L{start_line}-L{end_line}",
    ]
    seen: set[tuple[int, int]] = set()
    for window_start, window_end in windows:
        if (window_start, window_end) in seen:
            continue
        seen.add((window_start, window_end))
        parts.append(f"[context L{window_start}-L{window_end}]")
        parts.extend(
            f"L{line_number}\t{lines[line_number - 1]}"
            for line_number in range(window_start, window_end + 1)
        )
    return "\n".join(parts).rstrip() + "\n"


def build_prompt(
    story_record: dict[str, Any], story_path: Path, boundary_context_path: Path
) -> str:
    """构造只提取事实、不改写原文的 Luna 任务。"""

    return f"""你正在执行训练数据流水线 Step 2，只做故事理解和第二次边界审计，不改写正文。

读取：
- Step 1 提取稿：`{relative_to_repo(story_path)}`
- Python 生成的边界前后局部原文：`{relative_to_repo(boundary_context_path)}`
- Step 1 边界：{story_record['start_line']}–{story_record['end_line']}（1 起始、包含端点）

不要打开原始整期来源；局部包已提供边界审计所需的带行号上下文。

输出必须严格符合给定 JSON Schema，并满足：

1. source_id 必须是 `{story_record['source_id']}`。
2. characters 合并同一人物的称呼并保留 aliases；不要把普通名词当人名。
3. immutable_facts 只记录后续改写绝不能改变的人物、时间、地点、死亡方式、关键物件和因果。
4. clues、misdirection、twist 分开记录，不补写原文没有的信息。
5. 对照局部包中的边界前后内容，判断提取稿是否有完整开头和结局、是否混入相邻故事、广告或
   刊后内容。只有无问题时 boundary_assessment.status=complete、issues=[]；不得因为 Step 1 已标为
   auto_approved 就默认通过。
6. 若边界错误，给出可由 Python 应用的 suggested_start_line/suggested_end_line；无法可靠判断时用
   null，status=uncertain。边界完整时两个建议都用 null。
7. story_dna 只做抽象分析；ocr_flags 记录疑似 OCR 错字、串页、缺段或乱码。
8. 多人对白、叙述者不可靠、双时间线、身份隐藏或密集伏笔任一明显存在时，difficulty=hard。
9. 不引用长段原文，不输出 Markdown，不执行其他文件操作。
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 2 命令行。"""

    parser = argparse.ArgumentParser(description="用 Luna 提取故事人物、事实、线索和故事 DNA")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
        help="限制处理集合；可重复，默认只处理 train 和 validation",
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
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="并发故事数，默认 2；额度受限时降为 1",
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


def require_completed_step_1(work_dir: Path, manifest: Path) -> None:
    """默认清单必须来自完整结束且无模型失败的 Step 1。"""

    if manifest.resolve() != (work_dir / "stories.jsonl").resolve():
        return
    report_path = work_dir / "automatic_boundary_report.json"
    if report_path.is_file():
        report = read_json(report_path)
        source_count = report.get("source_count")
        completed_source_count = report.get("completed_source_count")
        failed_source_count = report.get("failed_source_count")
        if (
            not isinstance(source_count, int)
            or not isinstance(completed_source_count, int)
            or not isinstance(failed_source_count, int)
            or completed_source_count != source_count
            or failed_source_count != 0
        ):
            raise PipelineError(
                "Step 1 尚未完整结束或仍有模型失败；请先重复 Step 1c 原命令续跑"
            )
    for progress_name in (
        "step_1_boundary_detection.json",
        "step_1_boundary_review.json",
    ):
        progress_path = work_dir / "progress" / progress_name
        if progress_path.is_file() and read_json(progress_path).get("status") != "completed":
            raise PipelineError(
                f"Step 1 进度不是 completed：{progress_path}；请先续跑 Step 1c"
            )


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 2。"""

    args = build_parser().parse_args(argv)
    validate_automatic_model_policy(args.model, args.reasoning_effort)
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    require_completed_step_1(args.work_dir, manifest)
    include_splits = (
        set(args.include_split) if args.include_split else set(DEFAULT_ANALYSIS_SPLITS)
    )
    split_scope = "_".join(sorted(include_splits))
    stories = eligible_story_records(manifest, include_splits)
    output_dir = args.work_dir / "analysis"
    context_dir = args.work_dir / "boundary_context"
    pending: list[dict[str, Any]] = []
    for story in stories:
        output_path = output_dir / f"{story['source_id']}.json"
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_analysis(existing, str(story["source_id"]))
                if existing.get("_provenance", {}).get("input_sha256") == story["sha256"]:
                    continue
            except PipelineError:
                pass
        pending.append(story)
    pending_total = len(pending)
    completed_before = len(stories) - pending_total
    pending = limit_pending_items(pending, args.limit)
    print(f"Luna 待处理：{len(pending)} / 可用故事：{len(stories)}")
    if args.dry_run:
        if pending:
            sample = pending[0]
            sample_path = args.work_dir / sample["story_path"]
            context_path = context_dir / f"{sample['source_id']}.txt"
            command = codex_command(
                prompt=build_prompt(sample, sample_path, context_path),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{sample['source_id']}.json.tmp",
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    def analyze_story(story: dict[str, Any]) -> None:
        source_id = str(story["source_id"])
        story_path = args.work_dir / story["story_path"]
        output_path = output_dir / f"{source_id}.json"
        source_file = REPO_ROOT / str(
            story.get("source_file", f"training/{story['source_path']}")
        )
        context_path = context_dir / f"{source_id}.txt"
        atomic_write_text(context_path, build_story_boundary_context(story, source_file))
        result = run_codex_task(
            prompt=build_prompt(story, story_path, context_path),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            schema_path=SCHEMA_PATH,
            output_path=output_path,
            validator=lambda value, expected=source_id: validate_analysis(value, expected),
            retries=args.retries,
            timeout=args.timeout,
        )
        result["_provenance"] = {
            "stage": "story_analysis",
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "speed": "standard",
            "boundary_context": relative_to_repo(context_path),
            "input_sha256": story["sha256"],
            "generated_at": utc_now(),
            "codex_cwd": str(REPO_ROOT),
        }
        write_json(output_path, result)
        (args.work_dir / "errors" / "step_2" / f"{source_id}.json").unlink(
            missing_ok=True
        )

    def record_analysis_error(story: dict[str, Any], error: Exception) -> None:
        source_id = str(story["source_id"])
        write_json(
            args.work_dir / "errors" / "step_2" / f"{source_id}.json",
            {"source_id": source_id, "stage": "story_analysis", "error": str(error)},
        )

    failures = run_parallel_tasks(
        pending,
        workers=args.workers,
        heartbeat_seconds=args.heartbeat_seconds,
        stage_label="Luna 故事分析",
        item_label=lambda story: str(story["source_id"]),
        task=analyze_story,
        on_error=record_analysis_error,
        continue_on_error=args.continue_on_error,
        progress_path=args.work_dir / "progress" / f"step_2_analysis_{split_scope}.json",
        progress_stage=f"step_2_analysis_{split_scope}",
        total_items=len(stories),
        completed_before=completed_before,
    )
    repair_queue: list[dict[str, Any]] = []
    for story in stories:
        output_path = output_dir / f"{story['source_id']}.json"
        if not output_path.is_file():
            continue
        analysis = read_json(output_path)
        validate_analysis(analysis, str(story["source_id"]))
        if boundary_assessment_passes(analysis):
            continue
        repair_queue.append(
            {
                "source_id": story["source_id"],
                "source_path": story["source_path"],
                "current_start_line": story["start_line"],
                "current_end_line": story["end_line"],
                **analysis["boundary_assessment"],
            }
        )
    write_jsonl(args.work_dir / "boundary_repair_queue.jsonl", repair_queue)
    print(f"Luna 完成：{len(pending) - failures}；失败：{failures}")
    print(f"二次边界审计待修复：{len(repair_queue)}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
