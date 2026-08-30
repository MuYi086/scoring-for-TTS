#!/usr/bin/env python3
"""Step 7：匿名打包冻结 blind 故事，并选取最多 10 篇音频盲听子集。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path
import random
import re
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_WORK_DIR,
    PipelineError,
    atomic_write_text,
    eligible_story_records,
    read_json,
    utc_now,
    write_json,
)
from step_3_rewrite_stories import validate_rewrite


DEFAULT_VARIANTS = {
    "local_qwen": "local_qwen",
    "luna_high": "luna_high",
    "luna_xhigh": "luna_xhigh",
    "terra_high": "terra_high",
    "terra_xhigh": "terra_xhigh",
}


def parse_variant(specification: str, work_dir: Path) -> tuple[str, Path]:
    """解析 ``名称=目录`` 变体参数。"""

    if "=" not in specification:
        raise PipelineError("variant 必须使用 名称=目录 格式")
    name, raw_path = specification.split("=", 1)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise PipelineError(f"无效变体名称：{name}")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = work_dir / path
    return name, path


def variant_directories(specifications: list[str] | None, work_dir: Path) -> dict[str, Path]:
    """返回盲测变体到 Step 3 输出目录的映射。"""

    if not specifications:
        return {
            name: work_dir / "rewrites" / directory
            for name, directory in DEFAULT_VARIANTS.items()
        }
    result: dict[str, Path] = {}
    for specification in specifications:
        name, path = parse_variant(specification, work_dir)
        if name in result:
            raise PipelineError(f"变体重复：{name}")
        result[name] = path
    return result


def anonymous_code(*parts: str, length: int = 10) -> str:
    """从冻结标识生成不暴露模型名称的匿名代码。"""

    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()
    return digest[:length].upper()


def scoring_csv(rows: list[dict[str, str]]) -> str:
    """生成带固定权重列的人工评分表。"""

    fields = [
        "story_code",
        "candidate_code",
        "剧情与事实保真_35",
        "悬疑恐惧氛围_25",
        "有声朗读适配_20",
        "人物与对白清晰_10",
        "导演层兼容性_10",
        "notes",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 7 命令行。"""

    parser = argparse.ArgumentParser(description="打包匿名文本盲测和音频盲听子集")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--variant",
        action="append",
        help="变体名称=Step3输出目录；省略时使用五个推荐变体",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="盲测故事数；默认使用全部冻结 blind 故事",
    )
    parser.add_argument("--audio-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 7。"""

    args = build_parser().parse_args(argv)
    if args.count is not None and args.count < 1:
        raise PipelineError("count 必须大于 0")
    if args.audio_count < 0:
        raise PipelineError("audio-count 不能小于 0")
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    output_dir = args.output_dir or args.work_dir / "blind_test"
    variants = variant_directories(args.variant, args.work_dir)
    blind_stories = eligible_story_records(manifest, {"blind"})
    count = args.count if args.count is not None else len(blind_stories)
    if count < 1:
        raise PipelineError("冻结 blind 故事为空")
    if len(blind_stories) < count:
        raise PipelineError(
            f"冻结 blind 故事只有 {len(blind_stories)} 篇，少于要求的 {count} 篇"
        )
    if args.count is not None and args.audio_count > count:
        raise PipelineError("audio-count 不能大于显式指定的 count")
    audio_count = min(args.audio_count, count)
    blind_stories.sort(key=lambda record: (record["sha256"], record["source_id"]))
    selected = blind_stories[:count]
    assignments: list[dict[str, Any]] = []
    score_rows: list[dict[str, str]] = []
    packages: list[tuple[Path, str]] = []
    for story in selected:
        source_id = str(story["source_id"])
        story_code = f"S-{anonymous_code(str(args.seed), source_id, length=8)}"
        source_text = (args.work_dir / story["story_path"]).read_text(encoding="utf-8")
        packages.append((output_dir / "packages" / story_code / "source_a.txt", source_text))
        candidates: list[dict[str, str]] = []
        for variant_name, variant_dir in variants.items():
            path = variant_dir / f"{source_id}.json"
            if not path.is_file():
                raise PipelineError(f"盲测缺少变体 {variant_name}：{path}")
            rewrite = read_json(path)
            validate_rewrite(rewrite, source_id, str(story["sha256"]))
            candidate_code = f"C-{anonymous_code(str(args.seed), source_id, variant_name)}"
            candidates.append(
                {
                    "candidate_code": candidate_code,
                    "variant": variant_name,
                    "text": rewrite["output_b"],
                }
            )
        random.Random(f"{args.seed}:{source_id}").shuffle(candidates)
        assignments.append(
            {
                "source_id": source_id,
                "story_code": story_code,
                "title": story["title"],
                "candidates": [
                    {"candidate_code": item["candidate_code"], "variant": item["variant"]}
                    for item in candidates
                ],
            }
        )
        for item in candidates:
            package_path = (
                output_dir / "packages" / story_code / f"{item['candidate_code']}.txt"
            )
            packages.append((package_path, item["text"]))
            score_rows.append(
                {
                    "story_code": story_code,
                    "candidate_code": item["candidate_code"],
                    "剧情与事实保真_35": "",
                    "悬疑恐惧氛围_25": "",
                    "有声朗读适配_20": "",
                    "人物与对白清晰_10": "",
                    "导演层兼容性_10": "",
                    "notes": "",
                }
            )
    audio_subset = [assignment["story_code"] for assignment in assignments[:audio_count]]
    report = {
        "generated_at": utc_now(),
        "seed": args.seed,
        "story_count": len(assignments),
        "variant_count": len(variants),
        "audio_story_count": len(audio_subset),
        "weights": {
            "剧情与事实保真": 35,
            "悬疑恐惧氛围": 25,
            "有声朗读适配": 20,
            "人物与对白清晰": 10,
            "导演层兼容性": 10,
        },
        "audio_workflow": (
            "将 audio_subset 中每个匿名候选分别导入 ~/github/TTS-Studio-WebUI 的脚本制作页，"
            "使用同一导演 Prompt、同一参考音色和 VoxCPM2 8322，再匿名评分。"
        ),
    }
    print(
        f"盲测故事：{len(assignments)}；变体：{len(variants)}；"
        f"音频子集：{len(audio_subset)}"
    )
    if args.dry_run:
        return 0
    marker = output_dir / "assignments_private.json"
    if marker.exists() and not args.overwrite:
        raise PipelineError("盲测包已存在；确认后使用 --overwrite")
    for path, text in packages:
        atomic_write_text(path, text.strip() + "\n")
    write_json(output_dir / "assignments_private.json", assignments)
    write_json(output_dir / "audio_subset.json", audio_subset)
    write_json(output_dir / "blind_test_report.json", report)
    atomic_write_text(output_dir / "scoring_sheet.csv", scoring_csv(score_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
