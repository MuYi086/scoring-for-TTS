#!/usr/bin/env python3
"""Step 6：导出 Easy Dataset 审核候选和 LLaMA-Factory ShareGPT 数据。"""

from __future__ import annotations

import argparse
from collections import Counter
import math
from pathlib import Path
import re
from typing import Any, Sequence

from step_1_prepare_stories import (
    DEFAULT_WORK_DIR,
    PipelineError,
    eligible_story_records,
    read_json,
    read_jsonl,
    sha256_text,
    utc_now,
    write_json,
    write_jsonl,
)
from step_3_rewrite_stories import validate_rewrite
from step_4_review_rewrites import deterministic_gate, validate_review
from step_5_adjudicate_stories import adjudication_gate, validate_adjudication


SYSTEM_PROMPT = (
    "你是中文悬疑有声小说编辑。将文学稿改写为适合有声演播的纯文本；完整保留人物、事实、"
    "线索、误导、反转和因果链，只优化断句、对白归属、指代与听觉节奏。只输出最终正文，"
    "不得输出解释、Markdown、导演标签或 TTS 控制字段。"
)
USER_PREFIX = "请将下面的完整文学稿改写为适合有声演播的纯文本：\n\n"
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def estimate_tokens(text: str) -> int:
    """保守估算中英文混合文本 Token 数，用于避免训练时静默截断。"""

    cjk_count = len(CJK_RE.findall(text))
    non_cjk = CJK_RE.sub("", text)
    non_whitespace_count = len(re.sub(r"\s", "", non_cjk))
    return cjk_count + math.ceil(non_whitespace_count / 4)


def load_approvals(path: Path | None) -> dict[str, dict[str, Any]]:
    """读取 Easy Dataset/人工审核结论；同一 source_id 只能出现一次。"""

    if path is None:
        return {}
    approvals: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        source_id = record.get("source_id")
        decision = record.get("decision")
        if not isinstance(source_id, str) or not source_id:
            raise PipelineError("审核清单每条记录都必须包含 source_id")
        if source_id in approvals:
            raise PipelineError(f"审核清单 source_id 重复：{source_id}")
        if decision not in {"approved", "rejected"}:
            raise PipelineError(f"审核 decision 必须是 approved/rejected：{source_id}")
        if decision == "approved" and not str(record.get("reviewer", "")).strip():
            raise PipelineError(f"approved 记录必须填写 reviewer：{source_id}")
        output_sha256 = record.get("output_sha256")
        if decision == "approved" and (
            not isinstance(output_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", output_sha256) is None
        ):
            raise PipelineError(f"approved 记录必须绑定 64 位 output_sha256：{source_id}")
        approvals[source_id] = record
    return approvals


def resolve_candidate(
    story: dict[str, Any], work_dir: Path, variant: str
) -> dict[str, Any]:
    """汇总 Step 3–5，为人工审核选择当前最佳 B 和流水线状态。"""

    source_id = str(story["source_id"])
    rewrite_path = work_dir / "rewrites" / variant / f"{source_id}.json"
    review_path = work_dir / "reviews" / variant / f"{source_id}.json"
    if not rewrite_path.is_file() or not review_path.is_file():
        raise PipelineError(f"缺少 {source_id} 的改写或复核结果")
    rewrite = read_json(rewrite_path)
    review = read_json(review_path)
    validate_rewrite(rewrite, source_id, str(story["sha256"]))
    validate_review(review, source_id)
    review_gate = review.get("_deterministic_gate") or deterministic_gate(review)
    output_b = rewrite["output_b"]
    pipeline_decision = review_gate["decision"]
    selected_stage = "terra_rewrite"
    adjudication_path = work_dir / "adjudications" / variant / f"{source_id}.json"
    adjudication: dict[str, Any] | None = None
    if adjudication_path.is_file():
        adjudication = read_json(adjudication_path)
        validate_adjudication(adjudication, source_id)
        sol_gate = adjudication.get("_deterministic_gate") or adjudication_gate(adjudication)
        pipeline_decision = "pass" if sol_gate["passed"] else sol_gate["decision"]
        if adjudication["final_output_b"].strip():
            output_b = adjudication["final_output_b"]
            selected_stage = "sol_adjudication"
    return {
        "source_id": source_id,
        "story": story,
        "output_b": output_b,
        "pipeline_decision": pipeline_decision,
        "selected_stage": selected_stage,
        "rewrite": rewrite,
        "review": review,
        "adjudication": adjudication,
    }


def easy_dataset_record(candidate: dict[str, Any], input_a: str) -> dict[str, Any]:
    """生成本地 Easy Dataset 文件导入器可直接映射的 Alpaca 风格候选。"""

    review = candidate["review"]
    return {
        "instruction": SYSTEM_PROMPT,
        "input": input_a,
        "output": candidate["output_b"],
        "system": SYSTEM_PROMPT,
        "source_id": candidate["source_id"],
        "title": candidate["story"]["title"],
        "split": candidate["story"]["split"],
        "pipeline_decision": candidate["pipeline_decision"],
        "selected_stage": candidate["selected_stage"],
        "output_sha256": sha256_text(candidate["output_b"]),
        "factual_consistency": review["factual_consistency"],
        "audio_readability": review["audio_readability"],
        "suspense_preservation": review["suspense_preservation"],
        "needs_human_review": candidate["rewrite"]["needs_human_review"],
    }


def sharegpt_record(input_a: str, output_b: str) -> dict[str, Any]:
    """生成与本地 Easy Dataset/LLaMA-Factory 一致的 messages 格式。"""

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PREFIX + input_a.strip()},
            {"role": "assistant", "content": output_b.strip()},
        ]
    }


def dataset_info() -> dict[str, Any]:
    """返回本地 LLaMA-Factory 当前支持的 ShareGPT 映射。"""

    base = {
        "formatting": "sharegpt",
        "columns": {"messages": "messages"},
        "tags": {
            "role_tag": "role",
            "content_tag": "content",
            "user_tag": "user",
            "assistant_tag": "assistant",
            "system_tag": "system",
        },
    }
    return {
        "audio_polisher_train": {"file_name": "sharegpt_train.json", **base},
        "audio_polisher_validation": {"file_name": "sharegpt_validation.json", **base},
    }


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 6 命令行。"""

    parser = argparse.ArgumentParser(description="导出审核候选和 audio-polisher 数据集")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--variant", default="teacher")
    parser.add_argument("--approval-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-estimated-tokens", type=int, default=7500)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 6。"""

    args = build_parser().parse_args(argv)
    if args.max_estimated_tokens < 1:
        raise PipelineError("max-estimated-tokens 必须大于 0")
    manifest = args.manifest or args.work_dir / "stories.jsonl"
    output_dir = args.output_dir or args.work_dir / "exports"
    approvals = load_approvals(args.approval_manifest)
    all_stories = eligible_story_records(manifest)
    stories = [record for record in all_stories if record.get("split") in {"train", "validation"}]
    protected_story_count = len(all_stories) - len(stories)
    candidates: list[dict[str, Any]] = []
    input_texts: dict[str, str] = {}
    for story in stories:
        candidate = resolve_candidate(story, args.work_dir, args.variant)
        story_path = args.work_dir / story["story_path"]
        input_a = story_path.read_text(encoding="utf-8")
        candidates.append(candidate)
        input_texts[str(story["source_id"])] = input_a
    candidate_records = [
        easy_dataset_record(candidate, input_texts[candidate["source_id"]])
        for candidate in candidates
    ]
    train_records: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for candidate in candidates:
        source_id = candidate["source_id"]
        story = candidate["story"]
        approval = approvals.get(source_id)
        if approval is None or approval["decision"] != "approved":
            rejected.append({"source_id": source_id, "reason": "not_human_approved"})
            continue
        if candidate["pipeline_decision"] != "pass":
            rejected.append({"source_id": source_id, "reason": "pipeline_not_passed"})
            continue
        if approval["output_sha256"] != sha256_text(candidate["output_b"]):
            rejected.append({"source_id": source_id, "reason": "stale_approval_output_changed"})
            continue
        split = str(story["split"])
        if split not in {"train", "validation"}:
            rejected.append({"source_id": source_id, "reason": f"protected_split_{split}"})
            continue
        approval_split = approval.get("split")
        if approval_split is not None and approval_split != split:
            raise PipelineError(f"审核 split 与冻结 split 不一致：{source_id}")
        input_a = input_texts[source_id]
        record = sharegpt_record(input_a, candidate["output_b"])
        estimated = estimate_tokens(
            SYSTEM_PROMPT + USER_PREFIX + input_a + candidate["output_b"]
        )
        if estimated > args.max_estimated_tokens:
            rejected.append({"source_id": source_id, "reason": "estimated_tokens_exceeded"})
            continue
        if split == "train":
            train_records.append(record)
        else:
            validation_records.append(record)
    report = {
        "generated_at": utc_now(),
        "variant": args.variant,
        "candidate_count": len(candidate_records),
        "protected_story_count": protected_story_count,
        "approval_count": len(approvals),
        "train_count": len(train_records),
        "validation_count": len(validation_records),
        "rejected_count": len(rejected),
        "rejection_reasons": dict(Counter(item["reason"] for item in rejected)),
        "max_estimated_tokens": args.max_estimated_tokens,
        "protected_splits": ["blind", "test"],
    }
    print(
        f"审核候选：{len(candidate_records)}；训练：{len(train_records)}；"
        f"验证：{len(validation_records)}；保护集：{protected_story_count}；"
        f"未导出：{len(rejected)}"
    )
    if args.dry_run:
        return 0
    outputs = [
        output_dir / "easy_dataset_candidates.jsonl",
        output_dir / "sharegpt_train.json",
        output_dir / "sharegpt_train.jsonl",
        output_dir / "sharegpt_validation.json",
        output_dir / "sharegpt_validation.jsonl",
        output_dir / "dataset_info.json",
        output_dir / "export_report.json",
        output_dir / "rejected.jsonl",
    ]
    if not args.overwrite and any(path.exists() for path in outputs):
        raise PipelineError("导出文件已存在；确认后使用 --overwrite")
    write_jsonl(output_dir / "easy_dataset_candidates.jsonl", candidate_records)
    write_json(output_dir / "sharegpt_train.json", train_records)
    write_jsonl(output_dir / "sharegpt_train.jsonl", train_records)
    write_json(output_dir / "sharegpt_validation.json", validation_records)
    write_jsonl(output_dir / "sharegpt_validation.jsonl", validation_records)
    write_json(output_dir / "dataset_info.json", dataset_info())
    write_json(output_dir / "export_report.json", report)
    write_jsonl(output_dir / "rejected.jsonl", rejected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
