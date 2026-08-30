#!/usr/bin/env python3
"""Step 0：为恐惧悬疑数据集生成可复现、按来源分组的冻结清单。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "training" / "原始资源"
DEFAULT_PLAN_DIR = REPO_ROOT / "training" / "数据集规划" / "fear-suspense-v1"
DEFAULT_DATASET_VERSION = "fear-suspense-v1"
DEFAULT_COLLECTIONS = ("怖客", "猛鬼杂志故事", "男生女生金版", "悚族")
DEFAULT_SEED = 20260830
DEFAULT_SPLIT_QUOTAS = {
    "train": 14,
    "validation": 2,
    "blind": 2,
    "test": 2,
}
ALLOWED_SPLITS = frozenset(DEFAULT_SPLIT_QUOTAS)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
YEAR_MONTH_RE = re.compile(
    r"(?P<year>20\d{2})\s*年?\s*[-._ ]?\s*(?P<month>1[0-2]|0?[1-9])(?!\d)\s*月?"
)
SECONDARY_EDITION_RE = re.compile(r"副刊|赠刊|增刊|特刊")


class PlanError(RuntimeError):
    """来源规划输入或输出不满足冻结契约。"""


def utc_now() -> str:
    """返回便于审计的 UTC 时间。"""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    """计算字节内容的 SHA-256。"""

    return hashlib.sha256(content).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """计算不受对象键顺序影响的 JSON SHA-256。"""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def atomic_write_text(path: Path, content: str) -> None:
    """在目标目录中原子写入 UTF-8 文本。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def jsonl_text(records: Iterable[dict[str, Any]]) -> str:
    """把对象序列编码为 JSONL。"""

    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)


def stable_rank(seed: int, *parts: str) -> str:
    """生成用于稳定抽样而非安全用途的哈希排序键。"""

    return sha256_bytes(":".join((str(seed), *parts)).encode("utf-8"))


def parse_year_month(filename: str) -> tuple[int | None, int | None]:
    """从常见刊物文件名中提取年份和月份。"""

    match = YEAR_MONTH_RE.search(filename)
    if not match:
        return None, None
    return int(match.group("year")), int(match.group("month"))


def source_group_id(collection: str, filename: str) -> tuple[str, int | None]:
    """返回防止同月 A/B 版、副刊跨集合的来源组及年份。"""

    year, month = parse_year_month(filename)
    if year is not None and month is not None:
        return f"{collection}:issue:{year:04d}-{month:02d}", year
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", Path(filename).stem).lower()
    digest = sha256_bytes(f"{collection}:{normalized}".encode("utf-8"))[:16]
    return f"{collection}:source:{digest}", year


def collect_source_inventory(
    source_root: Path,
    collections: Sequence[str],
) -> list[dict[str, Any]]:
    """读取目标来源的确定性元数据，不扫描未声明的目录。"""

    if not source_root.is_dir():
        raise PlanError(f"原始资源目录不存在：{source_root}")
    inventory: list[dict[str, Any]] = []
    for collection in collections:
        collection_dir = source_root / collection
        if not collection_dir.is_dir():
            raise PlanError(f"目标来源目录不存在：{collection_dir}")
        paths = sorted(collection_dir.glob("*.md"), key=lambda path: path.name)
        if not paths:
            raise PlanError(f"目标来源没有 Markdown：{collection_dir}")
        for path in paths:
            content = path.read_bytes()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise PlanError(f"来源不是有效 UTF-8：{path}: {error}") from error
            source_path = path.relative_to(source_root).as_posix()
            source_group, year = source_group_id(collection, path.name)
            inventory.append(
                {
                    "source_path": source_path,
                    "source_collection": collection,
                    "source_group": source_group,
                    "year": year,
                    "sha256": sha256_bytes(content),
                    "bytes": len(content),
                    "line_count": len(text.splitlines()),
                    "heading_count": sum(
                        HEADING_RE.match(line) is not None for line in text.splitlines()
                    ),
                }
            )
    return sorted(inventory, key=lambda record: str(record["source_path"]))


def choose_group_representatives(
    records: Sequence[dict[str, Any]], seed: int
) -> list[dict[str, Any]]:
    """每个期刊组只取一份，优先正刊并用固定哈希消除路径顺序偏差。"""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["source_group"])].append(record)
    representatives: list[dict[str, Any]] = []
    for group, group_records in sorted(grouped.items()):
        chosen = min(
            group_records,
            key=lambda record: (
                SECONDARY_EDITION_RE.search(str(record["source_path"])) is not None,
                stable_rank(seed, "representative", group, str(record["source_path"])),
            ),
        )
        representatives.append(dict(chosen))
    return representatives


def stratified_select(
    records: Sequence[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    """跨年份轮转抽样；无年份来源使用固定哈希抽样。"""

    representatives = choose_group_representatives(records, seed)
    if len(representatives) < count:
        raise PlanError(
            f"独立来源组只有 {len(representatives)} 个，少于每类要求的 {count} 个"
        )
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in representatives:
        year = record.get("year")
        bucket = str(year) if isinstance(year, int) else "unknown"
        buckets[bucket].append(record)
    for bucket, bucket_records in buckets.items():
        bucket_records.sort(
            key=lambda record: stable_rank(
                seed,
                "selection",
                bucket,
                str(record["source_path"]),
                str(record["sha256"]),
            )
        )
    bucket_names = sorted(
        buckets,
        key=lambda value: (value == "unknown", int(value) if value != "unknown" else 0),
    )
    selected: list[dict[str, Any]] = []
    while len(selected) < count:
        made_progress = False
        for bucket in bucket_names:
            if buckets[bucket] and len(selected) < count:
                selected.append(buckets[bucket].pop(0))
                made_progress = True
        if not made_progress:
            break
    return selected


def assign_collection_splits(
    records: Sequence[dict[str, Any]],
    quotas: dict[str, int],
    seed: int,
) -> list[dict[str, Any]]:
    """以固定哈希打散选中来源，再按明确配额冻结 split。"""

    ordered = sorted(
        (dict(record) for record in records),
        key=lambda record: stable_rank(
            seed,
            "split",
            str(record["source_collection"]),
            str(record["source_group"]),
            str(record["sha256"]),
        ),
    )
    cursor = 0
    for split in ("train", "validation", "blind", "test"):
        next_cursor = cursor + quotas[split]
        for record in ordered[cursor:next_cursor]:
            record["split"] = split
        cursor = next_cursor
    if cursor != len(ordered):
        raise PlanError("split 配额之和必须等于每类选择数量")
    return ordered


def build_plan(
    inventory: Sequence[dict[str, Any]],
    *,
    dataset_version: str,
    collections: Sequence[str],
    per_collection: int,
    quotas: dict[str, int],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """生成全量审计清单、80 份冻结清单及计划摘要。"""

    if set(quotas) != ALLOWED_SPLITS or any(value < 0 for value in quotas.values()):
        raise PlanError("split 配额必须完整包含 train/validation/blind/test 且不能为负数")
    if sum(quotas.values()) != per_collection:
        raise PlanError("split 配额之和必须等于 per-collection")
    selected: list[dict[str, Any]] = []
    for collection in collections:
        candidates = [
            record for record in inventory if record["source_collection"] == collection
        ]
        chosen = stratified_select(candidates, per_collection, seed)
        selected.extend(assign_collection_splits(chosen, quotas, seed))
    selected.sort(key=lambda record: str(record["source_path"]))
    selected_by_path = {str(record["source_path"]): record for record in selected}
    audited_inventory: list[dict[str, Any]] = []
    for source in inventory:
        record = dict(source)
        selected_record = selected_by_path.get(str(source["source_path"]))
        record["selection_status"] = "selected" if selected_record else "source_reserve"
        record["split"] = selected_record["split"] if selected_record else None
        audited_inventory.append(record)
    selected_content = jsonl_text(selected)
    inventory_content = jsonl_text(audited_inventory)
    plan_basis = {
        "dataset_version": dataset_version,
        "seed": seed,
        "collections": list(collections),
        "per_collection": per_collection,
        "split_quotas_per_collection": quotas,
        "selected_sources_sha256": sha256_bytes(selected_content.encode("utf-8")),
        "source_inventory_sha256": sha256_bytes(inventory_content.encode("utf-8")),
    }
    plan = {
        **plan_basis,
        "plan_sha256": canonical_json_sha256(plan_basis),
        "source_count": len(inventory),
        "selected_source_count": len(selected),
        "source_reserve_count": len(inventory) - len(selected),
        "collection_counts": dict(Counter(record["source_collection"] for record in selected)),
        "split_counts": dict(Counter(record["split"] for record in selected)),
        "selected_bytes": sum(int(record["bytes"]) for record in selected),
        "selected_line_count": sum(int(record["line_count"]) for record in selected),
        "generated_at": utc_now(),
    }
    return audited_inventory, selected, plan


def write_plan(
    plan_dir: Path,
    inventory: Sequence[dict[str, Any]],
    selected: Sequence[dict[str, Any]],
    plan: dict[str, Any],
    *,
    overwrite: bool,
) -> None:
    """原子写入来源规划及四个便于人工核对的路径列表。"""

    outputs = [
        plan_dir / "plan.json",
        plan_dir / "source_inventory.jsonl",
        plan_dir / "selected_sources.jsonl",
        *(plan_dir / f"{split}.txt" for split in ("train", "validation", "blind", "test")),
    ]
    if not overwrite and any(path.exists() for path in outputs):
        raise PlanError(f"规划文件已存在：{plan_dir}；确认后使用 --overwrite")
    atomic_write_text(
        plan_dir / "plan.json",
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(plan_dir / "source_inventory.jsonl", jsonl_text(inventory))
    atomic_write_text(plan_dir / "selected_sources.jsonl", jsonl_text(selected))
    for split in ("train", "validation", "blind", "test"):
        paths = sorted(
            str(record["source_path"]) for record in selected if record["split"] == split
        )
        atomic_write_text(plan_dir / f"{split}.txt", "".join(f"{path}\n" for path in paths))


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 0 命令行。"""

    parser = argparse.ArgumentParser(description="冻结恐惧悬疑数据集来源和四集合分配")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_DIR)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    parser.add_argument("--collection", action="append", dest="collections")
    parser.add_argument("--per-collection", type=int, default=20)
    parser.add_argument("--train-per-collection", type=int, default=14)
    parser.add_argument("--validation-per-collection", type=int, default=2)
    parser.add_argument("--blind-per-collection", type=int, default=2)
    parser.add_argument("--test-per-collection", type=int, default=2)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行来源规划。"""

    args = build_parser().parse_args(argv)
    collections = tuple(args.collections or DEFAULT_COLLECTIONS)
    if len(set(collections)) != len(collections):
        raise PlanError("collection 不能重复")
    if args.per_collection < 1:
        raise PlanError("per-collection 必须大于 0")
    quotas = {
        "train": args.train_per_collection,
        "validation": args.validation_per_collection,
        "blind": args.blind_per_collection,
        "test": args.test_per_collection,
    }
    inventory = collect_source_inventory(args.source_root, collections)
    audited_inventory, selected, plan = build_plan(
        inventory,
        dataset_version=args.dataset_version,
        collections=collections,
        per_collection=args.per_collection,
        quotas=quotas,
        seed=args.seed,
    )
    print(
        f"目标来源：{len(inventory)}；冻结选择：{len(selected)}；"
        f"来源备用：{len(inventory) - len(selected)}"
    )
    print(f"按刊物：{plan['collection_counts']}")
    print(f"按集合：{plan['split_counts']}")
    print(
        f"选中文本：{plan['selected_bytes'] / 1024 / 1024:.1f} MiB；"
        f"总行数：{plan['selected_line_count']}；计划哈希：{plan['plan_sha256']}"
    )
    if args.dry_run:
        print("Step 0 检查通过：dry-run 未写入规划文件。")
        return 0
    write_plan(
        args.plan_dir,
        audited_inventory,
        selected,
        plan,
        overwrite=args.overwrite,
    )
    print(f"Step 0 已冻结：{args.plan_dir / 'selected_sources.jsonl'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanError as error:
        raise SystemExit(f"错误：{error}") from None
