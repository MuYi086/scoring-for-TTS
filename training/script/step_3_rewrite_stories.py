#!/usr/bin/env python3
"""Step 3：使用 Terra 将完整文学稿 A 改写为有声友好纯文本 B。"""

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
    extract_name_candidates,
    read_json,
    relative_to_repo,
    run_codex_task,
    utc_now,
    validate_exact_keys,
    write_json,
)
from step_2_analyze_stories import validate_analysis


DEFAULT_MODEL = "gpt-5.6-terra"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "story_rewrite.schema.json"
REQUIRED_KEYS = {
    "source_id",
    "input_sha256",
    "output_b",
    "quality_flags",
    "needs_human_review",
}
FORBIDDEN_TAG_RE = re.compile(
    r"(?im)(?:"
    r"</?(?:speaker|emotion|sfx|bgm|control_instruction|nonverbal_tags)\b[^>]*>"
    r"|\[(?:SFX|BGM|speaker|emotion|control_instruction|旁白|角色)[^]]*]"
    r"|^\s*[\"']?(?:speaker|emotion|sfx|bgm|control_instruction|nonverbal_tags)"
    r"[\"']?\s*[:=]"
    r")"
)
MARKDOWN_OUTPUT_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s|```|[-*+]\s+)")


def forbidden_output_markers(text: str) -> list[str]:
    """返回 B 文本中禁止进入第一阶段 LoRA 的导演或格式标签。"""

    markers = [match.group(0).strip() for match in FORBIDDEN_TAG_RE.finditer(text)]
    if MARKDOWN_OUTPUT_RE.search(text):
        markers.append("markdown")
    return sorted(set(markers))


def new_name_candidates(input_a: str, output_b: str) -> list[str]:
    """找出 B 中出现、但 A 中未出现的人物名称候选。"""

    input_names = set(extract_name_candidates(input_a))
    return sorted(set(extract_name_candidates(output_b)) - input_names)


def validate_rewrite(
    value: dict[str, Any], source_id: str | None = None, input_sha256: str | None = None
) -> None:
    """校验 A→B 结构、来源绑定和纯文本边界。"""

    validate_exact_keys(
        value,
        required=REQUIRED_KEYS,
        optional={"_provenance", "_deterministic_checks"},
    )
    if source_id is not None and value["source_id"] != source_id:
        raise PipelineError(f"改写结果 source_id 不匹配：{value['source_id']} != {source_id}")
    if input_sha256 is not None and value["input_sha256"] != input_sha256:
        raise PipelineError("改写结果 input_sha256 与完整故事不匹配")
    if not isinstance(value["output_b"], str) or not value["output_b"].strip():
        raise PipelineError("改写结果 output_b 必须是非空字符串")
    if not isinstance(value["quality_flags"], list) or not all(
        isinstance(item, str) for item in value["quality_flags"]
    ):
        raise PipelineError("改写结果 quality_flags 必须是字符串数组")
    if not isinstance(value["needs_human_review"], bool):
        raise PipelineError("改写结果 needs_human_review 必须是布尔值")
    markers = forbidden_output_markers(value["output_b"])
    if markers:
        raise PipelineError(f"output_b 含禁用标签或 Markdown：{', '.join(markers[:5])}")


def build_prompt(
    story_record: dict[str, Any], story_path: Path, analysis_path: Path
) -> str:
    """构造保真优先的完整故事有声化改写任务。"""

    return f"""你正在执行训练数据流水线 Step 3：把文学稿 A 改写为有声友好纯文本 B。

读取完整故事 `{relative_to_repo(story_path)}`，并读取独立事实清单
`{relative_to_repo(analysis_path)}`。输出必须严格符合给定 JSON Schema。

硬约束：

1. source_id 必须是 `{story_record['source_id']}`；input_sha256 必须是
   `{story_record['sha256']}`。
2. 完整保留人物身份与称呼、时间、地点、死亡方式、关键物件、线索、误导、反转和因果链。
3. 只调整断句、对白归属、听觉节奏、口语顺滑度和容易混淆的指代；不得续写、删情节或美化事实。
4. output_b 只包含最终可朗读正文，不含解释、Markdown、JSON、章节列表、speaker/emotion、
   SFX、BGM、control_instruction、非语言标签或任何 TTS/导演控制字段。
5. 数字、专名和人名拿不准时保留 A 的原写法，并加入 quality_flags；不要猜测修复 OCR。
6. 发现来源疑似缺段、串页或无法保真的地方，将 needs_human_review 设为 true。
7. 一次处理整篇故事，不把任务拆成互不知晓上下文的段落。
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 3 命令行。"""

    parser = argparse.ArgumentParser(description="用 Terra 生成有声友好纯文本 B")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--normal-reasoning-effort", default="high")
    parser.add_argument("--hard-reasoning-effort", default="xhigh")
    parser.add_argument("--profile", help="可选 Codex profile；默认 Standard")
    parser.add_argument("--local-provider", choices=("ollama", "lmstudio"))
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 3。"""

    args = build_parser().parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.variant):
        raise PipelineError("variant 只能包含字母、数字、点、下划线和连字符")
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    analysis_dir = args.analysis_dir or args.work_dir / "analysis"
    include_splits = set(args.include_split) if args.include_split else None
    stories = eligible_story_records(manifest, include_splits)
    if args.limit is not None:
        if args.limit < 0:
            raise PipelineError("limit 不能小于 0")
        stories = stories[: args.limit]
    output_dir = args.work_dir / "rewrites" / args.variant
    pending: list[tuple[dict[str, Any], dict[str, Any], Path, str]] = []
    for story in stories:
        source_id = str(story["source_id"])
        analysis_path = analysis_dir / f"{source_id}.json"
        if not analysis_path.is_file():
            raise PipelineError(f"缺少 Step 2 分析：{analysis_path}")
        analysis = read_json(analysis_path)
        validate_analysis(analysis, source_id)
        analysis_digest = canonical_json_sha256(
            {key: value for key, value in analysis.items() if not key.startswith("_")}
        )
        output_path = output_dir / f"{source_id}.json"
        if output_path.exists() and not args.overwrite:
            try:
                existing = read_json(output_path)
                validate_rewrite(existing, source_id, str(story["sha256"]))
                if existing.get("_provenance", {}).get("analysis_sha256") == analysis_digest:
                    continue
            except PipelineError:
                pass
        pending.append((story, analysis, analysis_path, analysis_digest))
    print(f"{args.variant} 待改写：{len(pending)} / 可用故事：{len(stories)}")
    if args.dry_run:
        if pending:
            story, analysis, analysis_path, _ = pending[0]
            effort = (
                args.hard_reasoning_effort
                if analysis["difficulty"] == "hard"
                else args.normal_reasoning_effort
            )
            story_path = args.work_dir / story["story_path"]
            command = codex_command(
                prompt=build_prompt(story, story_path, analysis_path),
                model=args.model,
                reasoning_effort=effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{story['source_id']}.json.tmp",
                profile=args.profile,
                local_provider=args.local_provider,
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    failures = 0
    for index, (story, analysis, analysis_path, analysis_digest) in enumerate(pending, 1):
        source_id = str(story["source_id"])
        story_path = args.work_dir / story["story_path"]
        output_path = output_dir / f"{source_id}.json"
        effort = (
            args.hard_reasoning_effort
            if analysis["difficulty"] == "hard"
            else args.normal_reasoning_effort
        )
        print(
            f"[{index}/{len(pending)}] {args.model} {effort} 改写 {source_id}",
            flush=True,
        )
        try:
            result = run_codex_task(
                prompt=build_prompt(story, story_path, analysis_path),
                model=args.model,
                reasoning_effort=effort,
                schema_path=SCHEMA_PATH,
                output_path=output_path,
                validator=lambda value, expected=source_id, digest=str(
                    story["sha256"]
                ): validate_rewrite(value, expected, digest),
                retries=args.retries,
                timeout=args.timeout,
                profile=args.profile,
                local_provider=args.local_provider,
            )
            input_a = story_path.read_text(encoding="utf-8")
            result["_deterministic_checks"] = {
                "forbidden_markers": forbidden_output_markers(result["output_b"]),
                "new_name_candidates": new_name_candidates(input_a, result["output_b"]),
            }
            result["_provenance"] = {
                "stage": "audio_rewrite",
                "variant": args.variant,
                "model": args.model,
                "reasoning_effort": effort,
                "speed": "profile" if args.profile else "standard",
                "profile": args.profile,
                "local_provider": args.local_provider,
                "input_sha256": story["sha256"],
                "analysis_sha256": analysis_digest,
                "generated_at": utc_now(),
            }
            write_json(output_path, result)
        except PipelineError as error:
            failures += 1
            write_json(
                args.work_dir / "errors" / "step_3" / args.variant / f"{source_id}.json",
                {"source_id": source_id, "stage": "audio_rewrite", "error": str(error)},
            )
            if not args.continue_on_error:
                raise
    print(f"改写完成：{len(pending) - failures}；失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
