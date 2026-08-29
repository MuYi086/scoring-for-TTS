#!/usr/bin/env python3
"""Step 2：使用 GPT-5.6 Luna 批量理解经授权的完整故事。"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_WORK_DIR,
    PipelineError,
    REPO_ROOT,
    codex_command,
    eligible_story_records,
    read_json,
    relative_to_repo,
    run_codex_task,
    utc_now,
    validate_exact_keys,
    write_json,
)


DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
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


def build_prompt(story_record: dict[str, Any], story_path: Path) -> str:
    """构造只提取事实、不改写原文的 Luna 任务。"""

    return f"""你正在执行训练数据流水线 Step 2，只做完整故事理解，不改写正文。

读取仓库文件 `{relative_to_repo(story_path)}`。这是经人工确认边界的一篇完整故事。
输出必须严格符合给定 JSON Schema，并满足：

1. source_id 必须是 `{story_record['source_id']}`。
2. characters 合并同一人物的称呼并保留 aliases；不要把普通名词当人名。
3. immutable_facts 只记录后续改写绝不能改变的人物、时间、地点、死亡方式、关键物件和因果。
4. clues、misdirection、twist 分开记录，不补写原文没有的信息。
5. story_dna 只做抽象分析；ocr_flags 记录疑似 OCR 错字、串页、缺段或乱码。
6. 多人对白、叙述者不可靠、双时间线、身份隐藏或密集伏笔任一明显存在时，difficulty=hard。
7. 不引用长段原文，不输出 Markdown，不执行其他文件操作。
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 2 命令行。"""

    parser = argparse.ArgumentParser(description="用 Luna 提取故事人物、事实、线索和故事 DNA")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--profile", help="可选 Codex 配置 profile；默认不启用 Fast")
    parser.add_argument(
        "--include-split",
        action="append",
        choices=("train", "validation", "blind", "test"),
        help="限制处理集合；可重复，默认处理全部经授权集合",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 2。"""

    args = build_parser().parse_args(argv)
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    include_splits = set(args.include_split) if args.include_split else None
    stories = eligible_story_records(manifest, include_splits)
    if args.limit is not None:
        if args.limit < 0:
            raise PipelineError("limit 不能小于 0")
        stories = stories[: args.limit]
    output_dir = args.work_dir / "analysis"
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
    print(f"Luna 待处理：{len(pending)} / 可用故事：{len(stories)}")
    if args.dry_run:
        if pending:
            sample = pending[0]
            sample_path = args.work_dir / sample["story_path"]
            command = codex_command(
                prompt=build_prompt(sample, sample_path),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_dir / f"{sample['source_id']}.json.tmp",
                profile=args.profile,
            )
            print(f"示例命令：{shlex.join(command)}")
        return 0
    failures = 0
    for index, story in enumerate(pending, 1):
        source_id = str(story["source_id"])
        story_path = args.work_dir / story["story_path"]
        output_path = output_dir / f"{source_id}.json"
        print(f"[{index}/{len(pending)}] Luna 分析 {source_id}", flush=True)
        try:
            result = run_codex_task(
                prompt=build_prompt(story, story_path),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                schema_path=SCHEMA_PATH,
                output_path=output_path,
                validator=lambda value, expected=source_id: validate_analysis(value, expected),
                retries=args.retries,
                timeout=args.timeout,
                profile=args.profile,
            )
            result["_provenance"] = {
                "stage": "story_analysis",
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "speed": "profile" if args.profile else "standard",
                "profile": args.profile,
                "input_sha256": story["sha256"],
                "generated_at": utc_now(),
                "codex_cwd": str(REPO_ROOT),
            }
            write_json(output_path, result)
        except PipelineError as error:
            failures += 1
            write_json(
                args.work_dir / "errors" / "step_2" / f"{source_id}.json",
                {"source_id": source_id, "stage": "story_analysis", "error": str(error)},
            )
            if not args.continue_on_error:
                raise
    print(f"Luna 完成：{len(pending) - failures}；失败：{failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
