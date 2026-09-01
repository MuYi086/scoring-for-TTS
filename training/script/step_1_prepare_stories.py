#!/usr/bin/env python3
"""Step 1：自动识别、校验并清洗 MinerU Markdown 中的完整故事。

本模块也提供后续步骤共用的 JSONL、哈希、Codex CLI 和原子写入工具。把共用逻辑放在
第一步，是为了让所有可执行脚本仍遵循 ``step_N_具体业务.py`` 的命名约定。
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import time
import unicodedata
from typing import Any, Callable, Iterable, Sequence, TypeVar


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "training" / "原始资源"
DEFAULT_SOURCE_MANIFEST = (
    REPO_ROOT
    / "training"
    / "数据集规划"
    / "fear-suspense-v1"
    / "selected_sources.jsonl"
)
DEFAULT_WORK_DIR = REPO_ROOT / "work" / "training-pipeline-fear-v1"
APPROVED_RIGHTS_STATUS = "approved_for_cloud_training"
ALLOWED_SPLITS = {"train", "validation", "blind", "test"}
APPROVED_BOUNDARY_STATUSES = {"approved", "auto_approved"}
DEFAULT_BOUNDARY_MODEL = "gpt-5.6-luna"
DEFAULT_BOUNDARY_REASONING_EFFORT = "medium"
DEFAULT_BOUNDARY_REVIEW_MODEL = "gpt-5.6-terra"
DEFAULT_BOUNDARY_REVIEW_REASONING_EFFORT = "medium"
DEFAULT_BOUNDARY_REVIEW_LIMIT = 10
DEFAULT_BOUNDARY_REVIEW_CONTEXT_LINES = 30
DEFAULT_STORY_BATCH_LIMIT = 20
AUTOMATIC_CLOUD_MODELS = frozenset({"gpt-5.6-luna", "gpt-5.6-terra"})
AUTOMATIC_REASONING_EFFORTS = frozenset({"low", "medium", "high"})
BOUNDARY_SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "story_boundaries.schema.json"
DEFAULT_HEARTBEAT_SECONDS = 30.0
MAX_PARALLEL_WORKERS = 16

IMAGE_LINE_RE = re.compile(r"^\s*!\[[^]]*]\([^)]*\)\s*$")
MARKDOWN_LINK_RE = re.compile(r"\[([^]]+)]\((?:https?://|mailto:)[^)]+\)")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
HTML_TAG_RE = re.compile(r"</?[^>]+>")
URL_ONLY_RE = re.compile(r"^\s*(?:https?://|www\.)\S+\s*$", re.IGNORECASE)
PAGE_NUMBER_RE = re.compile(
    r"^(?:\s*第\s*\d{1,4}\s*页\s*|\s*[-—]\s*\d{1,4}\s*[-—]\s*)$"
)
ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\ufeff]")
NAME_RE = re.compile(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4})(?=说|问|道|喊|答|叫)")
NOISE_LINE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^(?:编辑部|编辑部地址|编辑地址|发行|发行范围|发行主管|出版日期|出版单位)[：:]",
        r"^(?:邮编|电话|传真|网址|电子信箱|广告部电话|广告部传真)[：:]",
        r"^(?:国内总发行|国外总发行|国内订阅处|广告总代理|印刷)[：:]",
        r"^(?:中国标准刊号|国内统一刊号|广告经营许可证)[：:]?",
        r"^(?:ISSN|CN\s*\d{2})[-—\d/]",
        r"^定价[：:]?\s*\d",
        r"^www\.[a-z0-9.-]+$",
    )
)


class PipelineError(RuntimeError):
    """流水线输入、输出或外部命令不满足契约。"""


class PipelineInterrupted(PipelineError):
    """用户中断了模型流水线；已完成的原子结果仍可续跑。"""


class PipelineQuotaExhausted(PipelineError):
    """模型额度已经耗尽；继续提交任务只会重复失败并浪费时间。"""


class PipelineTaskFailed(PipelineError):
    """单个模型任务在有限的临时重试后仍失败。"""

    def __init__(self, message: str, *, failure_kind: str) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind


class PipelineManualEscalationRequired(PipelineError):
    """自动 Luna/Terra 路径无法可靠完成，需要用户手工调用 Sol。"""


ParallelItem = TypeVar("ParallelItem")


@dataclass(frozen=True)
class Boundary:
    """一篇完整故事在来源 Markdown 中经 AI、人工或外部流程确认的边界。"""

    source_path: str
    title: str
    start_line: int
    end_line: int
    boundary_status: str
    rights_status: str
    split: str
    boundary_source: str = "human"
    boundary_confidence: float = 1.0
    boundary_notes: str = ""
    source_collection: str = ""
    source_group: str = ""
    source_year: int | None = None


@dataclass(frozen=True)
class FrozenSource:
    """Step 0 冻结的一份来源及其不可变集合分配。"""

    path: Path
    source_path: str
    source_collection: str
    source_group: str
    source_year: int | None
    split: str
    sha256: str
    bytes: int
    line_count: int
    heading_count: int


_MODEL_TASK_CANCELLED = threading.Event()
_ACTIVE_MODEL_PROCESSES: set[subprocess.Popen[str]] = set()
_ACTIVE_MODEL_PROCESSES_LOCK = threading.Lock()
QUOTA_EXHAUSTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"you(?:'|’)ve hit your usage limit",
        r"you have hit your usage limit",
        r"insufficient_quota",
        r"quota[_ ]exceeded",
        r"usage limit.{0,160}(?:purchase more credits|try again at|upgrade)",
    )
)
TRANSIENT_MODEL_FAILURE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"tls handshake",
        r"failed to connect",
        r"connection (?:reset|closed|refused)",
        r"transport channel closed",
        r"http/request failed",
        r"request timed out",
        r"stream disconnected",
        r"websocket",
        r"temporar(?:y|ily) unavailable",
        r"timeout waiting for child process",
    )
)


def utc_now() -> str:
    """返回稳定、可排序的 UTC 时间字符串。"""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    """计算 UTF-8 文本的 SHA-256。"""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """计算不受对象键顺序和排版影响的 JSON SHA-256。"""

    content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(content)


def atomic_write_text(path: Path, text: str) -> None:
    """在同目录写临时文件后原子替换目标文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和可审阅缩进写入 JSON。"""

    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """写入每行一个对象的 JSONL。"""

    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    atomic_write_text(path, content)


def write_stage_progress(
    path: Path,
    *,
    stage: str,
    stage_label: str,
    status: str,
    total_items: int,
    completed_items: int,
    skipped_existing_items: int,
    scheduled_this_run: int,
    completed_this_run: int,
    failed_this_run: int,
    started_at: str,
    last_error: str | None = None,
) -> None:
    """原子写入可供人和脚本读取的阶段断点摘要。"""

    if total_items < 0 or not 0 <= completed_items <= total_items:
        raise PipelineError("阶段进度计数无效")
    write_json(
        path,
        {
            "schema_version": 1,
            "stage": stage,
            "stage_label": stage_label,
            "status": status,
            "total_items": total_items,
            "completed_items": completed_items,
            "pending_items": total_items - completed_items,
            "skipped_existing_items": skipped_existing_items,
            "scheduled_this_run": scheduled_this_run,
            "completed_this_run": completed_this_run,
            "failed_this_run": failed_this_run,
            "started_at": started_at,
            "updated_at": utc_now(),
            "last_error": last_error,
            "resume_instruction": "重复同一条命令；不要添加 --overwrite 或刷新参数",
        },
    )


def quota_exhaustion_detail(output: str) -> str | None:
    """从 Codex 输出中识别不可通过重试恢复的硬额度耗尽。"""

    if not any(pattern.search(output) for pattern in QUOTA_EXHAUSTION_PATTERNS):
        return None
    matching_lines = [
        line.strip()
        for line in output.splitlines()
        if any(pattern.search(line) for pattern in QUOTA_EXHAUSTION_PATTERNS)
    ]
    detail = matching_lines[-1] if matching_lines else "usage limit"
    return re.sub(r"\s+", " ", detail)[:500]


def read_json(path: Path) -> dict[str, Any]:
    """读取并校验顶层为对象的 JSON。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"无法读取 JSON：{path}: {error}") from error
    if not isinstance(value, dict):
        raise PipelineError(f"JSON 顶层必须是对象：{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL，并在错误中给出确切行号。"""

    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PipelineError(f"无法读取 JSONL：{path}: {error}") from error
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise PipelineError(f"JSONL 第 {line_number} 行无效：{path}: {error}") from error
        if not isinstance(value, dict):
            raise PipelineError(f"JSONL 第 {line_number} 行必须是对象：{path}")
        records.append(value)
    return records


def is_noise_line(line: str) -> bool:
    """判断一整行是否是可确定删除的出版信息或解析噪声。"""

    stripped = line.strip()
    if not stripped:
        return False
    if IMAGE_LINE_RE.fullmatch(stripped):
        return True
    if URL_ONLY_RE.fullmatch(stripped) or PAGE_NUMBER_RE.fullmatch(stripped):
        return True
    if len(stripped) <= 160 and any(pattern.search(stripped) for pattern in NOISE_LINE_PATTERNS):
        return True
    return False


def clean_markdown(text: str) -> str:
    """执行保守、确定性的 Markdown 清洗，不改写小说语义。"""

    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = ZERO_WIDTH_RE.sub("", normalized)
    cleaned_lines: list[str] = []
    for source_line in normalized.splitlines():
        if is_noise_line(source_line):
            continue
        line = html.unescape(source_line).strip()
        heading_match = HEADING_RE.match(line)
        if heading_match:
            line = heading_match.group(2).strip()
        line = MARKDOWN_LINK_RE.sub(r"\1", line)
        line = HTML_TAG_RE.sub("", line).strip()
        line = re.sub(r"[ \t]+", " ", line)
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(line)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()
    return "\n".join(cleaned_lines).strip() + "\n"


def normalized_content(text: str) -> str:
    """生成精确去重使用的规范化文本。"""

    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text).lower()


def simhash64(text: str) -> int:
    """用字符三元组计算 64 位 SimHash，检测排版差异造成的近重复。"""

    compact = normalized_content(text)
    if not compact:
        return 0
    tokens = (compact[index : index + 3] for index in range(max(1, len(compact) - 2)))
    vector = [0] * 64
    for token in tokens:
        digest = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest())
        for bit in range(64):
            vector[bit] += 1 if digest & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(vector):
        if weight >= 0:
            result |= 1 << bit
    return result


def hamming_distance(left: int, right: int) -> int:
    """返回两个 64 位整数的汉明距离。"""

    return (left ^ right).bit_count()


def extract_name_candidates(text: str, limit: int = 50) -> list[str]:
    """从常见对白归属结构中提取人物名称候选，供后续一致性初检。"""

    counts = Counter(NAME_RE.findall(text))
    return [name for name, _ in counts.most_common(limit)]


FROZEN_SOURCE_KEYS = {
    "source_path",
    "source_collection",
    "source_group",
    "year",
    "split",
    "sha256",
    "bytes",
    "line_count",
    "heading_count",
}


def load_frozen_sources(input_dir: Path, manifest_path: Path) -> tuple[list[FrozenSource], str]:
    """读取并校验 Step 0 清单，防止路径、内容或集合在运行后漂移。"""

    if not manifest_path.is_file():
        raise PipelineError(
            f"冻结来源清单不存在：{manifest_path}；先执行 step_0_plan_sources.py"
        )
    manifest_content = manifest_path.read_text(encoding="utf-8")
    records = read_jsonl(manifest_path)
    if not records:
        raise PipelineError(f"冻结来源清单为空：{manifest_path}")
    planned: list[FrozenSource] = []
    seen_paths: set[str] = set()
    group_splits: dict[str, str] = {}
    for line_number, record in enumerate(records, 1):
        missing = FROZEN_SOURCE_KEYS - record.keys()
        extra = record.keys() - FROZEN_SOURCE_KEYS
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"缺少 {', '.join(sorted(missing))}")
            if extra:
                detail.append(f"多出 {', '.join(sorted(extra))}")
            raise PipelineError(f"冻结来源清单第 {line_number} 行字段无效：{'；'.join(detail)}")
        source_path = str(record["source_path"])
        if source_path in seen_paths:
            raise PipelineError(f"冻结来源清单存在重复路径：{source_path}")
        seen_paths.add(source_path)
        split = str(record["split"])
        if split not in {"train", "validation", "blind", "test"}:
            raise PipelineError(f"冻结来源清单第 {line_number} 行 split 无效：{split}")
        source_collection = str(record["source_collection"])
        if not source_collection or Path(source_path).parts[:1] != (source_collection,):
            raise PipelineError(
                f"冻结来源清单第 {line_number} 行 source_collection 与路径不一致"
            )
        source_group = str(record["source_group"])
        previous_split = group_splits.setdefault(source_group, split)
        if previous_split != split:
            raise PipelineError(f"同一 source_group 跨集合：{source_group}")
        source_file = safe_source_path(input_dir, source_path)
        content = source_file.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != record["sha256"]:
            raise PipelineError(f"冻结后来源内容已变化：{source_path}")
        try:
            text_value = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise PipelineError(f"来源不是有效 UTF-8：{source_path}: {error}") from error
        line_count = len(text_value.splitlines())
        heading_count = len(heading_candidates(text_value))
        if record["bytes"] != len(content):
            raise PipelineError(f"冻结来源字节数不匹配：{source_path}")
        if record["line_count"] != line_count:
            raise PipelineError(f"冻结来源行数不匹配：{source_path}")
        if record["heading_count"] != heading_count:
            raise PipelineError(f"冻结来源标题数不匹配：{source_path}")
        year = record["year"]
        if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
            raise PipelineError(f"冻结来源清单第 {line_number} 行 year 必须是整数或 null")
        planned.append(
            FrozenSource(
                path=source_file,
                source_path=source_path,
                source_collection=source_collection,
                source_group=source_group,
                source_year=year,
                split=split,
                sha256=digest,
                bytes=len(content),
                line_count=line_count,
                heading_count=heading_count,
            )
        )
    adjacent_plan = manifest_path.parent / "plan.json"
    if adjacent_plan.is_file():
        expected_hash = read_json(adjacent_plan).get("selected_sources_sha256")
        actual_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            raise PipelineError(f"冻结来源清单与 plan.json 哈希不一致：{manifest_path}")
    return sorted(planned, key=lambda source: source.source_path), sha256_text(manifest_content)


def limit_pilot_sources(
    sources: Sequence[FrozenSource], per_collection: int | None
) -> list[FrozenSource]:
    """为代表性试跑按刊物各取 N 份，不再取全局路径前 N 份。"""

    if per_collection is None:
        return list(sources)
    if per_collection < 1:
        raise PipelineError("pilot-per-collection 必须大于 0")
    selected: list[FrozenSource] = []
    counts: Counter[str] = Counter()
    ordered_sources = sorted(
        sources,
        key=lambda source: (source.split != "train", source.source_collection, source.source_path),
    )
    for source in ordered_sources:
        if counts[source.source_collection] >= per_collection:
            continue
        selected.append(source)
        counts[source.source_collection] += 1
    available = Counter(source.source_collection for source in sources)
    shortages = {
        collection: per_collection - counts[collection]
        for collection in available
        if counts[collection] < per_collection
    }
    if shortages:
        raise PipelineError(f"代表性试跑来源不足：{shortages}")
    return selected


def heading_candidates(text: str) -> list[dict[str, Any]]:
    """列出 Markdown 标题作为 AI 证据或可选人工候选，不声称标题就是故事边界。"""

    headings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = HEADING_RE.match(line)
        if match:
            headings.append(
                {"line": line_number, "level": len(match.group(1)), "title": match.group(2).strip()}
            )
    return headings


def parse_boundary(record: dict[str, Any], line_number: int) -> Boundary:
    """把一条边界记录转换为强类型对象。"""

    required = ("source_path", "title", "start_line", "end_line")
    missing = [key for key in required if key not in record]
    if missing:
        raise PipelineError(f"边界清单第 {line_number} 条缺少字段：{', '.join(missing)}")
    start_line = record["start_line"]
    end_line = record["end_line"]
    if not isinstance(start_line, int) or not isinstance(end_line, int):
        raise PipelineError(f"边界清单第 {line_number} 条的 start_line/end_line 必须是整数")
    if start_line < 1 or end_line < start_line:
        raise PipelineError(f"边界清单第 {line_number} 条行号范围无效")
    split = str(record.get("split", ""))
    if split not in ALLOWED_SPLITS:
        raise PipelineError(f"边界清单第 {line_number} 条 split 无效：{split}")
    boundary_status = str(record.get("boundary_status", "needs_review"))
    if boundary_status not in APPROVED_BOUNDARY_STATUSES:
        raise PipelineError(
            f"边界清单第 {line_number} 条不是已批准边界：{boundary_status}"
        )
    confidence = record.get("boundary_confidence", 1.0)
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise PipelineError(f"边界清单第 {line_number} 条 boundary_confidence 必须为 0–1")
    return Boundary(
        source_path=str(record["source_path"]),
        title=str(record["title"]).strip(),
        start_line=start_line,
        end_line=end_line,
        boundary_status=boundary_status,
        rights_status=str(record.get("rights_status", "unknown")),
        split=split,
        boundary_source=str(record.get("boundary_source", "human")),
        boundary_confidence=float(confidence),
        boundary_notes=str(record.get("boundary_notes", "")),
        source_collection=str(record.get("source_collection", "")),
        source_group=str(record.get("source_group", "")),
        source_year=(
            int(record["source_year"])
            if isinstance(record.get("source_year"), int)
            and not isinstance(record.get("source_year"), bool)
            else None
        ),
    )


def safe_source_path(input_dir: Path, relative_path: str) -> Path:
    """解析来源路径并阻止边界清单逃逸出输入目录。"""

    input_root = input_dir.resolve()
    source_path = (input_root / relative_path).resolve()
    if not source_path.is_relative_to(input_root):
        raise PipelineError(f"来源路径越过训练文本目录：{relative_path}")
    if not source_path.is_file():
        raise PipelineError(f"来源 Markdown 不存在：{relative_path}")
    if source_path.suffix.lower() != ".md":
        raise PipelineError(f"来源文件必须是 Markdown：{relative_path}")
    return source_path


def mark_duplicates(records: list[dict[str, Any]], threshold: int) -> None:
    """标记精确重复和 SimHash 近重复，不删除任何来源证据。"""

    exact: dict[str, str] = {}
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    protected_priority = {"test": 0, "blind": 1, "validation": 2, "train": 3}
    for record in sorted(
        records,
        key=lambda item: (
            protected_priority.get(str(item.get("split")), 5),
            item["source_id"],
        ),
    ):
        content_hash = record["content_hash"]
        if content_hash in exact:
            record["duplicate_of"] = exact[content_hash]
            record["duplicate_kind"] = "exact"
            continue
        fingerprint = int(record["simhash64"], 16)
        candidates: dict[str, dict[str, Any]] = {}
        for chunk in range(4):
            key = (chunk, (fingerprint >> (chunk * 16)) & 0xFFFF)
            for candidate in buckets.get(key, []):
                candidates[candidate["source_id"]] = candidate
        for candidate in sorted(candidates.values(), key=lambda item: item["source_id"]):
            distance = hamming_distance(fingerprint, int(candidate["simhash64"], 16))
            if distance <= threshold:
                record["duplicate_of"] = candidate["source_id"]
                record["duplicate_kind"] = f"simhash_distance_{distance}"
                break
        if record["duplicate_of"] is None:
            for chunk in range(4):
                key = (chunk, (fingerprint >> (chunk * 16)) & 0xFFFF)
                buckets.setdefault(key, []).append(record)
        exact[content_hash] = record["duplicate_of"] or record["source_id"]


def prepare_stories(
    input_dir: Path,
    work_dir: Path,
    boundary_manifest: Path,
    *,
    min_chars: int,
    max_chars: int,
    simhash_threshold: int,
    dry_run: bool,
    frozen_source_manifest: str | None = None,
    frozen_source_manifest_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """根据通过状态与范围校验的边界提取、清洗并登记完整故事。"""

    raw_boundaries = read_jsonl(boundary_manifest)
    boundaries: list[Boundary] = []
    invalid_approved: list[str] = []
    for index, record in enumerate(raw_boundaries, 1):
        if str(record.get("boundary_status", "needs_review")) not in (
            APPROVED_BOUNDARY_STATUSES
        ):
            continue
        try:
            boundaries.append(parse_boundary(record, index))
        except PipelineError as error:
            invalid_approved.append(str(error))
    if invalid_approved:
        examples = "；".join(invalid_approved[:3])
        raise PipelineError(
            f"边界清单中有 {len(invalid_approved)} 条 approved 记录缺少有效完整边界；"
            f"approved 必须同时填写整数 start_line/end_line。示例：{examples}"
        )
    approved_ranges: dict[str, list[Boundary]] = {}
    for boundary in boundaries:
        approved_ranges.setdefault(boundary.source_path, []).append(boundary)
    for source_path, ranges in approved_ranges.items():
        ranges.sort(key=lambda item: (item.start_line, item.end_line))
        for previous, current in zip(ranges, ranges[1:]):
            if current.start_line <= previous.end_line:
                raise PipelineError(
                    f"同一来源的已批准故事边界重叠：{source_path}: "
                    f"{previous.start_line}–{previous.end_line} 与 "
                    f"{current.start_line}–{current.end_line}"
                )
    stories: list[dict[str, Any]] = []
    story_texts: dict[str, str] = {}
    for boundary in boundaries:
        source_path = safe_source_path(input_dir, boundary.source_path)
        source_text = source_path.read_text(encoding="utf-8")
        source_lines = source_text.splitlines()
        if boundary.end_line > len(source_lines):
            raise PipelineError(
                f"故事 {boundary.title!r} 的 end_line={boundary.end_line} 超过来源总行数 "
                f"{len(source_lines)}：{boundary.source_path}"
            )
        raw_story = "\n".join(source_lines[boundary.start_line - 1 : boundary.end_line])
        cleaned = clean_markdown(raw_story)
        character_count = len(re.sub(r"\s", "", cleaned))
        if character_count < min_chars or character_count > max_chars:
            raise PipelineError(
                f"故事 {boundary.title!r} 清洗后为 {character_count} 字，不在 "
                f"{min_chars}–{max_chars} 范围内"
            )
        source_key = (
            f"{boundary.source_path}:{boundary.start_line}:{boundary.end_line}:"
            f"{sha256_text(cleaned)}"
        )
        source_id = f"story_{sha256_text(source_key)[:16]}"
        content_hash = sha256_text(normalized_content(cleaned))
        try:
            source_file_reference = relative_to_repo(source_path)
        except PipelineError:
            source_file_reference = str(source_path)
        record: dict[str, Any] = {
            "source_id": source_id,
            "title": boundary.title,
            "source_path": boundary.source_path,
            "source_file": source_file_reference,
            "start_line": boundary.start_line,
            "end_line": boundary.end_line,
            "story_path": f"stories/{source_id}.md",
            "sha256": sha256_text(cleaned),
            "content_hash": content_hash,
            "simhash64": f"{simhash64(cleaned):016x}",
            "character_count": character_count,
            "name_candidates": extract_name_candidates(cleaned),
            "boundary_status": boundary.boundary_status,
            "boundary_source": boundary.boundary_source,
            "boundary_confidence": boundary.boundary_confidence,
            "boundary_notes": boundary.boundary_notes,
            "source_collection": boundary.source_collection,
            "source_group": boundary.source_group,
            "source_year": boundary.source_year,
            "rights_status": boundary.rights_status,
            "eligible_for_cloud": boundary.rights_status == APPROVED_RIGHTS_STATUS,
            "split": boundary.split,
            "duplicate_of": None,
            "duplicate_kind": None,
        }
        stories.append(record)
        story_texts[source_id] = cleaned
    mark_duplicates(stories, simhash_threshold)
    stories.sort(key=lambda record: record["source_id"])
    if not dry_run:
        for record in stories:
            atomic_write_text(work_dir / record["story_path"], story_texts[record["source_id"]])
        write_jsonl(work_dir / "stories.jsonl", stories)
        write_json(
            work_dir / "step_1_report.json",
            {
                "generated_at": utc_now(),
                "source_manifest": str(boundary_manifest),
                "frozen_source_manifest": frozen_source_manifest,
                "frozen_source_manifest_sha256": frozen_source_manifest_sha256,
                "story_count": len(stories),
                "eligible_count": sum(record["eligible_for_cloud"] for record in stories),
                "duplicate_count": sum(record["duplicate_of"] is not None for record in stories),
                "split_counts": dict(Counter(record["split"] for record in stories)),
            },
        )
    return stories


def eligible_story_records(
    manifest_path: Path, include_splits: set[str] | None = None
) -> list[dict[str, Any]]:
    """读取可发送至云端且不是重复项的完整故事。"""

    records = read_jsonl(manifest_path)
    selected = []
    for record in records:
        if record.get("rights_status") != APPROVED_RIGHTS_STATUS:
            continue
        if record.get("eligible_for_cloud") is not True or record.get("duplicate_of"):
            continue
        if include_splits and record.get("split") not in include_splits:
            continue
        selected.append(record)
    return sorted(selected, key=lambda record: str(record["source_id"]))


def limit_pending_items(items: Sequence[Any], limit: int | None) -> list[Any]:
    """限制本次尚未完成项数量；重复运行时自然推进到后续批次。"""

    if limit is None:
        return list(items)
    if limit < 0:
        raise PipelineError("limit 不能小于 0")
    return list(items[:limit])


def validate_parallel_settings(workers: int, heartbeat_seconds: float) -> None:
    """校验模型并发数和无输出心跳周期。"""

    if not 1 <= workers <= MAX_PARALLEL_WORKERS:
        raise PipelineError(f"workers 必须在 1–{MAX_PARALLEL_WORKERS} 之间")
    if heartbeat_seconds <= 0:
        raise PipelineError("heartbeat-seconds 必须大于 0")


def _terminate_model_process(process: subprocess.Popen[str], grace_seconds: float = 2.0) -> None:
    """终止 Codex 进程组，避免 Node 包装进程或原生子进程成为孤儿。"""

    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except (OSError, ProcessLookupError):
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass


def cancel_active_model_tasks() -> int:
    """请求所有模型任务停止，并返回发出终止请求时的活动进程数。"""

    _MODEL_TASK_CANCELLED.set()
    with _ACTIVE_MODEL_PROCESSES_LOCK:
        active = list(_ACTIVE_MODEL_PROCESSES)
    for process in active:
        _terminate_model_process(process)
    return len(active)


def run_parallel_tasks(
    items: Sequence[ParallelItem],
    *,
    workers: int,
    heartbeat_seconds: float,
    stage_label: str,
    item_label: Callable[[ParallelItem], str],
    task: Callable[[ParallelItem], None],
    on_error: Callable[[ParallelItem, Exception], None],
    continue_on_error: bool,
    progress_path: Path | None = None,
    progress_stage: str | None = None,
    total_items: int | None = None,
    completed_before: int = 0,
) -> int:
    """并发执行独立模型任务，并持久化可续跑进度。"""

    validate_parallel_settings(workers, heartbeat_seconds)
    total_items = total_items if total_items is not None else completed_before + len(items)
    if completed_before < 0 or total_items < completed_before + len(items):
        raise PipelineError("并发任务的总数、既有完成数和本次任务数不一致")
    progress_started_at = utc_now()

    def record_progress(
        status: str,
        *,
        completed_this_run: int,
        failed_this_run: int,
        last_error: str | None = None,
    ) -> None:
        if progress_path is None:
            return
        write_stage_progress(
            progress_path,
            stage=progress_stage or stage_label,
            stage_label=stage_label,
            status=status,
            total_items=total_items,
            completed_items=completed_before + completed_this_run,
            skipped_existing_items=completed_before,
            scheduled_this_run=len(items),
            completed_this_run=completed_this_run,
            failed_this_run=failed_this_run,
            started_at=progress_started_at,
            last_error=last_error,
        )

    if not items:
        status = "completed" if completed_before == total_items else "partial"
        record_progress(status, completed_this_run=0, failed_this_run=0)
        return 0
    started_at = time.monotonic()
    completed_count = 0
    success_count = 0
    failure_count = 0
    first_error: tuple[ParallelItem, Exception] | None = None
    quota_error: tuple[ParallelItem, PipelineQuotaExhausted] | None = None
    record_progress("running", completed_this_run=0, failed_this_run=0)

    def timed_task(item: ParallelItem) -> float:
        item_started_at = time.monotonic()
        task(item)
        return time.monotonic() - item_started_at

    print(f"{stage_label}：{len(items)} 项，并发数 {min(workers, len(items))}", flush=True)
    if progress_path is not None:
        print(f"进度记录：{progress_path}", flush=True)
    _MODEL_TASK_CANCELLED.clear()
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="training-model")
    item_iterator = iter(items)
    future_items: dict[Future[float], ParallelItem] = {}

    def submit_next() -> bool:
        try:
            item = next(item_iterator)
        except StopIteration:
            return False
        future_items[executor.submit(timed_task, item)] = item
        return True

    for _ in range(min(workers, len(items))):
        submit_next()
    interrupted = False
    try:
        while future_items:
            done, _ = wait(
                set(future_items),
                timeout=heartbeat_seconds,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                elapsed = int(time.monotonic() - started_at)
                print(
                    f"[{stage_label}] 运行中：已结束 {completed_count}/{len(items)}；"
                    f"成功 {success_count}；失败 {failure_count}；"
                    f"仍在运行或排队 {len(items) - completed_count}；已用 {elapsed} 秒",
                    flush=True,
                )
                record_progress(
                    "running",
                    completed_this_run=success_count,
                    failed_this_run=failure_count,
                )
                continue
            for future in done:
                item = future_items.pop(future)
                completed_count += 1
                try:
                    duration = future.result()
                except PipelineQuotaExhausted as error:
                    failure_count += 1
                    quota_error = (item, error)
                    on_error(item, error)
                    print(
                        f"[{stage_label} 额度耗尽 {completed_count}/{len(items)}] "
                        f"{item_label(item)}：{error}",
                        flush=True,
                    )
                    break
                except PipelineInterrupted:
                    interrupted = True
                    break
                except Exception as error:
                    failure_count += 1
                    on_error(item, error)
                    print(
                        f"[{stage_label} 失败 {completed_count}/{len(items)}] "
                        f"{item_label(item)}：{error}",
                        flush=True,
                    )
                    if not continue_on_error and first_error is None:
                        first_error = (item, error)
                else:
                    success_count += 1
                    print(
                        f"[{stage_label} 完成 {completed_count}/{len(items)}] "
                        f"{item_label(item)}（{duration:.1f} 秒）",
                        flush=True,
                    )
                record_progress(
                    "running",
                    completed_this_run=success_count,
                    failed_this_run=failure_count,
                )
                if first_error is None and quota_error is None and not interrupted:
                    submit_next()
            if first_error is not None or quota_error is not None or interrupted:
                break
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if interrupted or quota_error is not None or first_error is not None:
            for future in future_items:
                future.cancel()
            active_count = cancel_active_model_tasks()
            if interrupted:
                print(
                    f"[{stage_label}] 收到中断：已完成 {completed_count}/{len(items)}；"
                    f"正在取消未启动任务并终止 {active_count} 个模型进程。",
                    flush=True,
                )
            elif quota_error is not None:
                print(
                    f"[{stage_label}] 检测到额度耗尽：已成功 {success_count}/{len(items)}；"
                    f"正在取消未启动任务并终止 {active_count} 个模型进程。",
                    flush=True,
                )
        executor.shutdown(
            wait=True,
            cancel_futures=(
                interrupted or quota_error is not None or first_error is not None
            ),
        )
        if interrupted or quota_error is not None or first_error is not None:
            for future, item in future_items.items():
                if future.cancelled():
                    continue
                try:
                    duration = future.result()
                except Exception:
                    continue
                success_count += 1
                completed_count += 1
                print(
                    f"[{stage_label} 停线前完成 {completed_count}/{len(items)}] "
                    f"{item_label(item)}（{duration:.1f} 秒）",
                    flush=True,
                )
    if interrupted:
        record_progress(
            "interrupted",
            completed_this_run=success_count,
            failed_this_run=failure_count,
            last_error="用户中断",
        )
        raise PipelineInterrupted(
            f"{stage_label} 已由用户中断；已完成结果已保留，重复同一命令可续跑"
        )
    if quota_error is not None:
        item, error = quota_error
        record_progress(
            "quota_exhausted",
            completed_this_run=success_count,
            failed_this_run=failure_count,
            last_error=str(error),
        )
        raise PipelineQuotaExhausted(
            f"{stage_label} 额度已耗尽，已停止后续任务；"
            f"触发项：{item_label(item)}。有效结果已保留，额度恢复后重复同一命令续跑"
        ) from error
    if first_error is not None:
        item, error = first_error
        record_progress(
            "failed",
            completed_this_run=success_count,
            failed_this_run=failure_count,
            last_error=str(error),
        )
        raise PipelineError(f"{stage_label} 失败：{item_label(item)}：{error}") from error
    final_status = (
        "completed"
        if completed_before + success_count == total_items
        else "partial"
    )
    record_progress(
        final_status,
        completed_this_run=success_count,
        failed_this_run=failure_count,
    )
    return failure_count


def automatic_run_can_resume(
    work_dir: Path, source_manifest_sha256: str | None = None
) -> bool:
    """仅允许自动边界流程重建自己上次生成的 stories.jsonl。"""

    report_path = work_dir / "step_1_report.json"
    boundary_path = work_dir / "boundaries.auto.jsonl"
    if not report_path.is_file() or not boundary_path.is_file():
        return False
    try:
        source_manifest = read_json(report_path).get("source_manifest")
    except PipelineError:
        return False
    valid_manifest = (
        isinstance(source_manifest, str)
        and Path(source_manifest).resolve() == boundary_path.resolve()
    )
    if not valid_manifest:
        return False
    if source_manifest_sha256 is None:
        return True
    return read_json(report_path).get("frozen_source_manifest_sha256") == (
        source_manifest_sha256
    )


def relative_to_repo(path: Path) -> str:
    """返回相对仓库路径；运行数据必须位于仓库中才能被 Codex 只读访问。"""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise PipelineError(f"Codex 输入必须位于仓库内：{path}") from error


def validate_automatic_model_policy(
    model: str,
    reasoning_effort: str,
    *,
    local_provider: str | None = None,
) -> None:
    """禁止自动 Sol、隐式 Sol 别名、过高推理和用户 Fast 配置。"""

    if reasoning_effort not in AUTOMATIC_REASONING_EFFORTS:
        allowed = "、".join(sorted(AUTOMATIC_REASONING_EFFORTS))
        raise PipelineError(
            f"自动流水线 reasoning effort 只允许 {allowed}；"
            "xhigh/max/pro 请改走人工升级"
        )
    if local_provider is not None:
        return
    if model not in AUTOMATIC_CLOUD_MODELS:
        allowed = "、".join(sorted(AUTOMATIC_CLOUD_MODELS))
        raise PipelineError(
            f"自动云端模型只允许 {allowed}；禁止 Sol 和会隐式路由到 Sol 的模型别名"
        )


def is_transient_model_failure(detail: str) -> bool:
    """仅把网络、传输和进程超时视为可原样重试的临时故障。"""

    return any(pattern.search(detail) for pattern in TRANSIENT_MODEL_FAILURE_PATTERNS)


def codex_command(
    *,
    prompt: str,
    model: str,
    reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
    local_provider: str | None = None,
) -> list[str]:
    """构造固定 Standard、最小权限、非交互、结构化输出的 Codex CLI 命令。"""

    validate_automatic_model_policy(
        model,
        reasoning_effort,
        local_provider=local_provider,
    )

    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--cd",
        str(REPO_ROOT),
        "--model",
        model,
    ]
    if local_provider:
        command.extend(["--oss", "--local-provider", local_provider])
    command.extend(
        [
            "--config",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            prompt,
        ]
    )
    return command


def run_codex_task(
    *,
    prompt: str,
    model: str,
    reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
    validator: Callable[[dict[str, Any]], None],
    retries: int,
    timeout: float,
    local_provider: str | None = None,
) -> dict[str, Any]:
    """执行一次独立 Codex 任务，校验最终 JSON，并只重试临时失败。"""

    if retries < 0:
        raise PipelineError("retries 不能小于 0")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    command = codex_command(
        prompt=prompt,
        model=model,
        reasoning_effort=reasoning_effort,
        schema_path=schema_path,
        output_path=temporary_path,
        local_provider=local_provider,
    )
    last_error = ""
    failure_kind = "process"
    attempts = 0
    for attempt in range(retries + 1):
        attempts += 1
        if _MODEL_TASK_CANCELLED.is_set():
            raise PipelineInterrupted("模型任务已取消")
        if temporary_path.exists():
            temporary_path.unlink()
        try:
            popen_options: dict[str, Any] = {}
            if os.name == "posix":
                popen_options["start_new_session"] = True
            elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **popen_options,
            )
        except OSError as error:
            last_error = str(error)
            failure_kind = "transport"
        else:
            with _ACTIVE_MODEL_PROCESSES_LOCK:
                _ACTIVE_MODEL_PROCESSES.add(process)
            deadline = time.monotonic() + timeout
            stdout = ""
            stderr = ""
            timed_out = False
            try:
                while True:
                    if _MODEL_TASK_CANCELLED.is_set():
                        _terminate_model_process(process)
                        raise PipelineInterrupted("模型任务已取消")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        _terminate_model_process(process)
                        stdout, stderr = process.communicate()
                        break
                    try:
                        stdout, stderr = process.communicate(timeout=min(0.25, remaining))
                    except subprocess.TimeoutExpired:
                        continue
                    break
            finally:
                with _ACTIVE_MODEL_PROCESSES_LOCK:
                    _ACTIVE_MODEL_PROCESSES.discard(process)
            if _MODEL_TASK_CANCELLED.is_set():
                raise PipelineInterrupted("模型任务已取消")
            quota_detail = quota_exhaustion_detail(f"{stdout}\n{stderr}")
            if quota_detail is not None:
                if temporary_path.exists():
                    temporary_path.unlink()
                raise PipelineQuotaExhausted(
                    f"Codex 使用额度已耗尽：{quota_detail}"
                )
            if timed_out:
                last_error = f"运行超过 {timeout:g} 秒"
                failure_kind = "timeout"
            elif process.returncode == 0 and temporary_path.is_file():
                try:
                    value = read_json(temporary_path)
                    validator(value)
                except PipelineError as error:
                    last_error = f"结构化输出校验失败：{error}"
                    failure_kind = "validation"
                else:
                    temporary_path.unlink()
                    return value
            else:
                stderr_tail = stderr.strip()[-1000:]
                last_error = f"退出码 {process.returncode}: {stderr_tail or '无错误输出'}"
                failure_kind = (
                    "transport" if is_transient_model_failure(stderr_tail) else "process"
                )
        retryable = failure_kind in {"transport", "timeout"}
        if attempt < retries and retryable:
            if _MODEL_TASK_CANCELLED.wait(min(2**attempt, 8)):
                raise PipelineInterrupted("模型任务已取消")
            continue
        break
    if temporary_path.exists():
        temporary_path.unlink()
    raise PipelineTaskFailed(
        f"Codex 任务失败（已尝试 {attempts} 次，类型 {failure_kind}）：{last_error}",
        failure_kind=failure_kind,
    )


def run_codex_task_with_quality_fallback(
    *,
    prompt: str,
    model: str,
    reasoning_effort: str,
    fallback_model: str,
    fallback_reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
    validator: Callable[[dict[str, Any]], None],
    retries: int,
    timeout: float,
) -> tuple[dict[str, Any], str, str, bool]:
    """结构校验失败时仅用 Terra high 修复一次；传输失败留待续跑。"""

    try:
        result = run_codex_task(
            prompt=prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            schema_path=schema_path,
            output_path=output_path,
            validator=validator,
            retries=retries,
            timeout=timeout,
        )
        return result, model, reasoning_effort, False
    except PipelineTaskFailed as first_error:
        if first_error.failure_kind != "validation":
            raise
        repair_prompt = (
            prompt
            + "\n\n上一轮输出未通过本地结构校验。只修正结构、绑定字段和明确指出的问题，"
            + "不要扩大任务范围。校验错误："
            + str(first_error)[-800:]
        )
        try:
            result = run_codex_task(
                prompt=repair_prompt,
                model=fallback_model,
                reasoning_effort=fallback_reasoning_effort,
                schema_path=schema_path,
                output_path=output_path,
                validator=validator,
                retries=0,
                timeout=timeout,
            )
        except PipelineTaskFailed as fallback_error:
            raise PipelineManualEscalationRequired(
                "Terra medium 与一次 Terra high 定向修复均未通过校验；"
                f"需要人工 Sol。最后错误：{fallback_error}"
            ) from fallback_error
        return result, fallback_model, fallback_reasoning_effort, True


def write_manual_escalation_package(
    *,
    package_dir: Path,
    item_id: str,
    stage: str,
    prompt: str,
    schema_path: Path,
    manual_result_path: Path,
    error: str,
) -> Path:
    """写出可复制给 Sol 的最小人工升级说明，不自动调用 Sol。"""

    package_path = package_dir / f"{item_id}.md"
    content = f"""# 人工 Sol 升级：{stage}

自动流程已停止，未自动调用 Sol。

- 项目：`{item_id}`
- 最后错误：{error}
- 输出 Schema：`{relative_to_repo(schema_path)}`
- 将人工得到的纯 JSON 保存到：`{relative_to_repo(manual_result_path)}`

## 可复制提示词

```text
{prompt}
```
"""
    atomic_write_text(package_path, content)
    return package_path


def validate_exact_keys(
    value: dict[str, Any], *, required: set[str], optional: set[str] | None = None
) -> None:
    """执行无需第三方依赖的顶层字段契约检查。"""

    optional = optional or set()
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise PipelineError(f"结构化输出缺少字段：{', '.join(sorted(missing))}")
    if extra:
        raise PipelineError(f"结构化输出包含未允许字段：{', '.join(sorted(extra))}")


BOUNDARY_DETECTION_KEYS = {
    "source_path",
    "source_sha256",
    "line_count",
    "stories",
    "document_notes",
}
BOUNDARY_STORY_KEYS = {
    "title",
    "start_line",
    "end_line",
    "confidence",
    "completeness",
    "content_kind",
    "target_genre",
    "reason",
}


def build_boundary_evidence(source_text: str) -> str:
    """生成覆盖全部标题及各段首尾的紧凑边界证据。"""

    lines = source_text.splitlines()
    headings: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(lines, 1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((line_number, len(match.group(1)), match.group(2).strip()))
    evidence = [f"total_lines={len(lines)}", f"heading_count={len(headings)}", ""]
    for index, (line_number, level, title) in enumerate(headings):
        next_line = headings[index + 1][0] if index + 1 < len(headings) else len(lines) + 1
        meaningful_lines: list[tuple[int, str]] = []
        for candidate_line, candidate in enumerate(
            lines[line_number : next_line - 1],
            line_number + 1,
        ):
            stripped = candidate.strip()
            if not stripped or HEADING_RE.match(stripped) or is_noise_line(stripped):
                continue
            meaningful_lines.append((candidate_line, re.sub(r"\s+", " ", stripped)[:120]))
        head = meaningful_lines[:2]
        tail = meaningful_lines[-2:] if len(meaningful_lines) > 2 else []
        segment_end = meaningful_lines[-1][0] if meaningful_lines else line_number

        def format_excerpt(excerpts: Sequence[tuple[int, str]]) -> str:
            if not excerpts:
                return "<无>"
            return " / ".join(f"L{number}:{content}" for number, content in excerpts)

        evidence.append(
            f"L{line_number}\tH{level}\tto_next={next_line - line_number}\t"
            f"segment_end=L{segment_end}\ttitle={title}\t"
            f"head={format_excerpt(head)}\ttail={format_excerpt(tail)}"
        )
    return "\n".join(evidence).rstrip() + "\n"


def validate_boundary_detection(
    value: dict[str, Any],
    *,
    source_path: str,
    source_sha256: str,
    line_count: int,
) -> None:
    """校验 AI 对整期来源给出的故事边界。"""

    validate_exact_keys(value, required=BOUNDARY_DETECTION_KEYS, optional={"_provenance"})
    if value["source_path"] != source_path:
        raise PipelineError("边界识别结果 source_path 与输入不匹配")
    if value["source_sha256"] != source_sha256:
        raise PipelineError("边界识别结果 source_sha256 与输入不匹配")
    if value["line_count"] != line_count:
        raise PipelineError("边界识别结果 line_count 与输入不匹配")
    stories = value["stories"]
    if not isinstance(stories, list):
        raise PipelineError("边界识别结果 stories 必须是数组")
    previous_end = 0
    for index, story in enumerate(stories, 1):
        if not isinstance(story, dict):
            raise PipelineError(f"边界识别第 {index} 个 story 必须是对象")
        validate_exact_keys(story, required=BOUNDARY_STORY_KEYS)
        title = story["title"]
        start_line = story["start_line"]
        end_line = story["end_line"]
        confidence = story["confidence"]
        if not isinstance(title, str) or not title.strip():
            raise PipelineError(f"边界识别第 {index} 个 story 标题为空")
        if (
            not isinstance(start_line, int)
            or isinstance(start_line, bool)
            or not isinstance(end_line, int)
            or isinstance(end_line, bool)
            or start_line < 1
            or end_line < start_line
            or end_line > line_count
        ):
            raise PipelineError(f"边界识别第 {index} 个 story 行号范围无效")
        if start_line <= previous_end:
            raise PipelineError(f"边界识别第 {index} 个 story 与前一故事重叠或未排序")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise PipelineError(f"边界识别第 {index} 个 story confidence 无效")
        if story["completeness"] not in {"complete", "installment", "uncertain"}:
            raise PipelineError(f"边界识别第 {index} 个 story completeness 无效")
        if story["content_kind"] not in {"fiction", "narrative_nonfiction", "other"}:
            raise PipelineError(f"边界识别第 {index} 个 story content_kind 无效")
        if not isinstance(story["target_genre"], bool):
            raise PipelineError(f"边界识别第 {index} 个 story target_genre 必须是布尔值")
        if not isinstance(story["reason"], str):
            raise PipelineError(f"边界识别第 {index} 个 story reason 必须是字符串")
        previous_end = end_line
    if not isinstance(value["document_notes"], str):
        raise PipelineError("边界识别结果 document_notes 必须是字符串")


def build_boundary_prompt(
    *,
    source_path: str,
    source_file: Path,
    evidence_path: Path,
    source_sha256: str,
    line_count: int,
    inspect_full_source: bool = False,
) -> str:
    """构造整期刊物的故事边界识别任务。"""

    inspection_rule = (
        "先读证据包定位，再按需检查原始 Markdown 中候选边界附近的少量行；不要从头扫描全文。"
        if inspect_full_source
        else "首轮只读证据包，不打开或扫描原始 Markdown。证据不足时降低置信度并标为 uncertain。"
    )

    return f"""你正在执行训练数据流水线 Step 1：从整期杂志 Markdown 中识别完整小说边界。

读取：
- 原始 Markdown：`{relative_to_repo(source_file)}`
- Python 生成的标题、行号、间距和局部正文提纲：`{relative_to_repo(evidence_path)}`

输入绑定：
- source_path 必须是 `{source_path}`
- source_sha256 必须是 `{source_sha256}`
- line_count 必须是 {line_count}

任务规则：

1. {inspection_rule}
   证据包覆盖全部 Markdown 标题，并给出各标题段的首尾正文、segment_end 和精确行号。
2. stories 只列独立小说或完整短篇。排除封面、目录、广告、声明、征稿、导读、作者简介、答案、
   书评、新闻、知识文章、栏目页、下期预告和纯图片说明。
3. 同一小说内部的章节、小节、序章、尾声、数字标题和作者署名不是新故事；必须并入所属故事。
4. start_line 从故事标题或紧邻标题的作者署名开始；end_line 是结局正文最后一行，不包含下一篇、
   广告或刊后内容。行号均为 1 起始且包含端点。
5. 目录中提前出现的标题不是正文起点；同名标题重复时必须选择正文实际开始位置。
6. 连载片段、上篇但本期无结局、明显缺开头/结尾的内容标为 installment 或 uncertain，不得声称
   complete。只有完整、有开端与结局的小说标为 complete。
7. content_kind 仅小说使用 fiction；纪实报道用 narrative_nonfiction，其他内容用 other。
   target_genre 只有悬疑、恐怖、推理、犯罪、惊悚、怪谈或明显相邻类型小说才为 true；普通校园、
   爱情、娱乐和科普内容为 false。
8. confidence 表示边界可靠度。无法确认时降低 confidence，不要伪造确定性。
9. stories 按 start_line 升序且不得重叠。不要复制长段原文，不执行文件写入。

输出严格符合 JSON Schema。即使没有完整小说，也输出空 stories 数组并在 document_notes 说明。
"""


def build_boundary_review_prompt(
    *,
    source_path: str,
    previous_detection_path: Path,
    review_packet_path: Path,
    source_sha256: str,
    line_count: int,
) -> str:
    """构造只复核风险边界、保留其余首轮结果的 Terra 任务。"""

    return f"""你正在执行训练数据流水线 Step 1 的低成本边界复核。

只读取：
- 第一遍完整边界结果：`{relative_to_repo(previous_detection_path)}`
- Python 生成的紧凑标题清单和风险边界局部原文包：`{relative_to_repo(review_packet_path)}`

不要打开原始整期 Markdown，不要从头扫描全文。局部包已包含风险故事起止位置附近的带行号原文。

输入绑定：
- source_path 必须是 `{source_path}`
- source_sha256 必须是 `{source_sha256}`
- line_count 必须是 {line_count}

输出仍须符合完整 story_boundaries JSON Schema：先复制第一遍 stories；只修改局部包明确标出的
低置信度或 completeness=uncertain 项。没有证据表明存在问题的故事必须逐字段原样保留。允许合并误拆
章节、修正 start_line/end_line、标题、完整性和类型；不得靠猜测添加证据包中不存在的故事。

边界规则：目录标题不是正文起点；start_line 是正文标题或紧邻署名，end_line 是结局最后一行且不含
下一篇、广告或刊后内容；连载或缺头缺尾不得标 complete；stories 必须升序且不重叠。不要复制长段
原文，不执行文件写入。若局部证据不足，保留 uncertain 并降低 confidence，不要扫描全文补证。
"""


def build_boundary_review_packet(
    source_text: str,
    detection: dict[str, Any],
    *,
    minimum_confidence: float,
    context_lines: int = 60,
) -> str:
    """只打包风险故事起止附近原文，避免 Terra 重读整期杂志。"""

    if context_lines < 1:
        raise PipelineError("boundary review context_lines 必须大于 0")
    lines = source_text.splitlines()
    risky: list[tuple[int, dict[str, Any], list[str]]] = []
    for index, story in enumerate(detection["stories"]):
        reasons: list[str] = []
        if story["completeness"] == "uncertain":
            reasons.append("completeness_uncertain")
        if float(story["confidence"]) < minimum_confidence:
            reasons.append("confidence_below_threshold")
        if reasons:
            risky.append((index, story, reasons))

    header = {
        "source_path": detection["source_path"],
        "source_sha256": detection["source_sha256"],
        "line_count": detection["line_count"],
        "minimum_confidence": minimum_confidence,
        "risky_story_count": len(risky),
    }
    parts = [json.dumps(header, ensure_ascii=False, sort_keys=True)]
    parts.append(
        "HEADINGS "
        + json.dumps(
            heading_candidates(source_text),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    if not risky:
        parts.append("没有单篇风险候选；下面提供每个标题附近的短上下文用于确认空 stories。")
        for heading in heading_candidates(source_text):
            center = int(heading["line"])
            start = max(1, center - 4)
            end = min(len(lines), center + 12)
            parts.append(f"[heading context L{start}-L{end}]")
            parts.extend(
                f"L{line_number}\t{lines[line_number - 1]}"
                for line_number in range(start, end + 1)
            )
        return "\n".join(parts).rstrip() + "\n"

    for index, story, reasons in risky:
        parts.append(
            "\nRISK "
            + json.dumps(
                {"story_index": index, "reasons": reasons, "story": story},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        windows = (
            (
                max(1, int(story["start_line"]) - context_lines),
                min(len(lines), int(story["start_line"]) + context_lines),
                "start",
            ),
            (
                max(1, int(story["end_line"]) - context_lines),
                min(len(lines), int(story["end_line"]) + context_lines),
                "end",
            ),
        )
        seen_ranges: set[tuple[int, int]] = set()
        for start, end, label in windows:
            if (start, end) in seen_ranges:
                continue
            seen_ranges.add((start, end))
            parts.append(f"[{label} context L{start}-L{end}]")
            parts.extend(
                f"L{line_number}\t{lines[line_number - 1]}"
                for line_number in range(start, end + 1)
            )
    return "\n".join(parts).rstrip() + "\n"


def automatic_boundary_records(
    detection: dict[str, Any],
    source_text: str,
    *,
    minimum_confidence: float,
    min_chars: int,
    max_chars: int,
    rights_status: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把 AI 结果转成可提取清单，并隔离低置信度候选。"""

    lines = source_text.splitlines()
    source_path = str(detection["source_path"])
    collection = Path(source_path).parts[0] if Path(source_path).parts else ""
    records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    provenance = detection.get("_provenance", {})
    for story in detection["stories"]:
        start_line = int(story["start_line"])
        end_line = int(story["end_line"])
        raw_story = "\n".join(lines[start_line - 1 : end_line])
        cleaned = clean_markdown(raw_story)
        character_count = len(re.sub(r"\s", "", cleaned))
        title_key = normalized_content(str(story["title"]))
        opening_key = normalized_content(
            "\n".join(lines[start_line - 1 : min(end_line, start_line + 12)])
        )
        exclusion_reasons: list[str] = []
        ambiguity_reasons: list[str] = []
        warning_reasons: list[str] = []
        if story["content_kind"] != "fiction":
            exclusion_reasons.append(f"content_kind_{story['content_kind']}")
        if story["target_genre"] is not True:
            exclusion_reasons.append("not_target_genre")
        if story["completeness"] == "installment":
            exclusion_reasons.append("completeness_installment")
        if story["completeness"] == "uncertain":
            ambiguity_reasons.append("completeness_uncertain")
        if float(story["confidence"]) < minimum_confidence:
            ambiguity_reasons.append("confidence_below_threshold")
        if character_count < min_chars:
            exclusion_reasons.append("too_short")
        if character_count > max_chars:
            exclusion_reasons.append("too_long")
        if len(title_key) >= 2 and title_key not in opening_key:
            warning_reasons.append("title_not_near_start")
        excluded = bool(exclusion_reasons)
        boundary_status = (
            "excluded"
            if excluded
            else ("needs_review" if ambiguity_reasons else "auto_approved")
        )
        record = {
            "source_path": source_path,
            "source_collection": collection,
            "title": str(story["title"]).strip(),
            "start_line": start_line,
            "end_line": end_line,
            "boundary_status": boundary_status,
            "boundary_source": str(provenance.get("model", DEFAULT_BOUNDARY_MODEL)),
            "boundary_confidence": float(story["confidence"]),
            "boundary_notes": str(story["reason"]),
            "rights_status": rights_status,
            "split": "auto",
            "content_kind": story["content_kind"],
            "target_genre": story["target_genre"],
            "completeness": story["completeness"],
            "character_count_estimate": character_count,
            "review_reasons": exclusion_reasons + ambiguity_reasons + warning_reasons,
        }
        records.append(record)
        if boundary_status == "needs_review":
            review_queue.append(record)
    return records, review_queue


def source_detection_name(source_path: str) -> str:
    """返回不暴露长文件名且稳定的整期识别结果文件名。"""

    return f"source_{sha256_text(source_path)[:16]}.json"


def apply_frozen_source_metadata(
    records: Iterable[dict[str, Any]], source: FrozenSource
) -> None:
    """把 Step 0 冻结的集合与来源组写入边界记录。"""

    for record in records:
        record["split"] = source.split
        record["source_collection"] = source.source_collection
        record["source_group"] = source.source_group
        record["source_year"] = source.source_year


def validate_source_run_contract(
    work_dir: Path,
    *,
    input_dir: Path,
    source_manifest: Path,
    source_manifest_sha256: str,
    dry_run: bool,
) -> None:
    """把运行目录绑定到冻结清单，禁止无意混合两个数据集版本。"""

    contract_path = work_dir / "source_run_contract.json"
    contract = {
        "input_dir": str(input_dir.resolve()),
        "source_manifest": str(source_manifest.resolve()),
        "source_manifest_sha256": source_manifest_sha256,
    }
    if contract_path.is_file():
        if read_json(contract_path) != contract:
            raise PipelineError(
                f"运行目录已绑定其他来源规划：{contract_path}；请使用新的 --work-dir"
            )
        return
    if not dry_run:
        write_json(contract_path, contract)


def run_automatic_boundaries(args: argparse.Namespace) -> int:
    """按整期来源运行 AI 边界识别，再由 Python 自动提取高置信度故事。"""

    if not 0 <= args.auto_confidence <= 1:
        raise PipelineError("auto-confidence 必须在 0–1 之间")
    if args.boundary_review_context_lines < 1:
        raise PipelineError("boundary-review-context-lines 必须大于 0")
    validate_automatic_model_policy(
        args.boundary_model,
        args.boundary_reasoning_effort,
    )
    validate_automatic_model_policy(
        args.boundary_review_model,
        args.boundary_review_reasoning_effort,
    )
    validate_parallel_settings(args.boundary_workers, args.heartbeat_seconds)
    validate_parallel_settings(args.boundary_review_workers, args.heartbeat_seconds)
    if not args.dry_run and args.rights_status != APPROVED_RIGHTS_STATUS:
        raise PipelineError(
            "--auto-boundaries 会把来源交给云端模型；确认授权后必须显式传入 "
            "--rights-status approved_for_cloud_training"
        )
    frozen_sources, source_manifest_sha256 = load_frozen_sources(
        args.input_dir, args.source_manifest
    )
    validate_source_run_contract(
        args.work_dir,
        input_dir=args.input_dir,
        source_manifest=args.source_manifest,
        source_manifest_sha256=source_manifest_sha256,
        dry_run=args.dry_run,
    )
    frozen_sources = limit_pilot_sources(frozen_sources, args.pilot_per_collection)
    sources = [source.path for source in frozen_sources]
    source_plan = {source.source_path: source for source in frozen_sources}
    if not sources:
        raise PipelineError("没有匹配的来源 Markdown")
    split_counts = Counter(source.split for source in frozen_sources)
    collection_counts = Counter(source.source_collection for source in frozen_sources)
    print(
        f"冻结来源：{len(sources)}；按刊物：{dict(collection_counts)}；"
        f"按集合：{dict(split_counts)}"
    )
    manifest_path = args.work_dir / "stories.jsonl"
    if (
        manifest_path.exists()
        and not args.overwrite
        and not args.dry_run
        and not automatic_run_can_resume(args.work_dir, source_manifest_sha256)
    ):
        raise PipelineError("stories.jsonl 不是自动边界流程产物；确认后使用 --overwrite")

    detection_dir = args.work_dir / "boundary_detection"
    evidence_dir = args.work_dir / "boundary_evidence"
    pending: list[tuple[Path, str, str, int, Path, Path]] = []
    for source_file in sources:
        source_text = source_file.read_text(encoding="utf-8")
        relative = source_file.relative_to(args.input_dir).as_posix()
        source_hash = sha256_text(source_text)
        line_count = len(source_text.splitlines())
        output_path = detection_dir / source_detection_name(relative)
        evidence_path = output_path.with_name(output_path.stem + ".txt")
        evidence_path = evidence_dir / evidence_path.name
        if output_path.is_file() and not args.refresh_boundaries:
            try:
                existing = read_json(output_path)
                validate_boundary_detection(
                    existing,
                    source_path=relative,
                    source_sha256=source_hash,
                    line_count=line_count,
                )
                if existing.get("_provenance", {}).get("input_sha256") == source_hash:
                    continue
            except PipelineError:
                pass
        pending.append(
            (source_file, relative, source_hash, line_count, evidence_path, output_path)
        )

    print(f"AI 边界识别待处理：{len(pending)} / 来源文件：{len(sources)}")
    if args.dry_run:
        if pending:
            source_file, relative, source_hash, line_count, evidence_path, output_path = pending[0]
            command = codex_command(
                prompt=build_boundary_prompt(
                    source_path=relative,
                    source_file=source_file,
                    evidence_path=evidence_path,
                    source_sha256=source_hash,
                    line_count=line_count,
                    inspect_full_source=args.boundary_full_source,
                ),
                model=args.boundary_model,
                reasoning_effort=args.boundary_reasoning_effort,
                schema_path=BOUNDARY_SCHEMA_PATH,
                output_path=output_path.with_suffix(".json.tmp"),
            )
            print("正式运行命令预览（仅展示，本次未执行）：")
            print(f"  {' '.join(command[:12])} ...（后续参数已省略）")
        review_required = 0
        review_completed = 0
        review_manual = 0
        if args.resolve_ambiguous:
            for source_file in sources:
                relative = source_file.relative_to(args.input_dir).as_posix()
                first_path = detection_dir / source_detection_name(relative)
                if not first_path.is_file():
                    continue
                source_text = source_file.read_text(encoding="utf-8")
                detection = read_json(first_path)
                records, queued = automatic_boundary_records(
                    detection,
                    source_text,
                    minimum_confidence=args.auto_confidence,
                    min_chars=args.min_chars,
                    max_chars=args.max_chars,
                    rights_status=args.rights_status,
                )
                if records and not queued:
                    continue
                review_required += 1
                review_name = source_detection_name(relative)
                review_path = args.work_dir / "boundary_detection_review" / review_name
                manual_path = (
                    args.work_dir
                    / "manual_results"
                    / "step_1_boundary_review"
                    / review_name
                )
                package_path = (
                    args.work_dir
                    / "manual_escalation"
                    / "step_1"
                    / f"{Path(review_name).stem}.md"
                )
                if package_path.is_file() and not manual_path.is_file():
                    review_manual += 1
                    continue
                source_hash = sha256_text(source_text)
                line_count = len(source_text.splitlines())
                candidate_path = manual_path if manual_path.is_file() else review_path
                if candidate_path.is_file():
                    try:
                        existing = read_json(candidate_path)
                        validate_boundary_detection(
                            existing,
                            source_path=relative,
                            source_sha256=source_hash,
                            line_count=line_count,
                        )
                        provenance = existing.get("_provenance", {})
                        if candidate_path == manual_path or provenance.get(
                            "input_sha256"
                        ) == source_hash:
                            review_completed += 1
                            continue
                    except PipelineError:
                        pass
            print(
                f"Terra 边界复核：已完成 {review_completed}/{review_required}；"
                f"自动待处理 {review_required - review_completed - review_manual}；"
                f"等待人工 Sol {review_manual}；每批上限 {args.boundary_review_limit}"
            )
        print(
            "Step 1a 检查通过（退出码 0）：dry-run 未调用模型，也未写入流水线文件。"
        )
        if pending:
            print(
                "下一步：先执行 Step 1b 代表性实跑，再执行 Step 1c；"
                "实跑才会调用模型并写入运行目录。"
            )
        elif (
            args.resolve_ambiguous
            and review_required - review_completed - review_manual > 0
        ):
            print("下一步：重复 Step 1c 正式命令，按批继续 Terra 局部复核。")
        elif args.resolve_ambiguous and review_manual > 0:
            print(
                "下一步：处理 Step 1d 人工 Sol 升级包，把纯 JSON 保存到对应的 "
                "manual_results/step_1_boundary_review/ 路径；随后执行 Step 1e 正式命令导入。"
            )
        else:
            print("Step 1 当前没有待处理的模型任务。")
        return 0

    def detect_source(item: tuple[Path, str, str, int, Path, Path]) -> None:
        source_file, relative, source_hash, line_count, evidence_path, output_path = item
        source_text = source_file.read_text(encoding="utf-8")
        atomic_write_text(evidence_path, build_boundary_evidence(source_text))
        started_at = time.monotonic()
        result = run_codex_task(
            prompt=build_boundary_prompt(
                source_path=relative,
                source_file=source_file,
                evidence_path=evidence_path,
                source_sha256=source_hash,
                line_count=line_count,
                inspect_full_source=args.boundary_full_source,
            ),
            model=args.boundary_model,
            reasoning_effort=args.boundary_reasoning_effort,
            schema_path=BOUNDARY_SCHEMA_PATH,
            output_path=output_path,
            validator=lambda value, path=relative, digest=source_hash, count=line_count: (
                validate_boundary_detection(
                    value,
                    source_path=path,
                    source_sha256=digest,
                    line_count=count,
                )
            ),
            retries=args.retries,
            timeout=args.timeout,
        )
        result["_provenance"] = {
            "stage": "automatic_story_boundaries",
            "model": args.boundary_model,
            "reasoning_effort": args.boundary_reasoning_effort,
            "speed": "standard",
            "input_sha256": source_hash,
            "evidence_only": not args.boundary_full_source,
            "duration_seconds": round(time.monotonic() - started_at, 1),
            "generated_at": utc_now(),
        }
        write_json(output_path, result)
        (args.work_dir / "errors" / "step_1" / source_detection_name(relative)).unlink(
            missing_ok=True
        )

    def record_detection_error(
        item: tuple[Path, str, str, int, Path, Path], error: Exception
    ) -> None:
        relative = item[1]
        write_json(
            args.work_dir / "errors" / "step_1" / source_detection_name(relative),
            {
                "source_path": relative,
                "stage": "automatic_story_boundaries",
                "error": str(error),
            },
        )

    failures = run_parallel_tasks(
        pending,
        workers=args.boundary_workers,
        heartbeat_seconds=args.heartbeat_seconds,
        stage_label="Luna 边界识别",
        item_label=lambda item: item[1],
        task=detect_source,
        on_error=record_detection_error,
        continue_on_error=args.continue_on_error,
        progress_path=args.work_dir / "progress" / "step_1_boundary_detection.json",
        progress_stage="step_1_boundary_detection",
        total_items=len(sources),
        completed_before=len(sources) - len(pending),
    )

    ambiguous_sources: list[tuple[Path, str, str, int, Path, Path]] = []
    usable_review_source_paths: set[str] = set()
    manual_review_waiting: list[tuple[str, Path, Path]] = []
    for source_file in sources:
        relative = source_file.relative_to(args.input_dir).as_posix()
        first_path = detection_dir / source_detection_name(relative)
        if not first_path.is_file():
            continue
        source_text = source_file.read_text(encoding="utf-8")
        detection = read_json(first_path)
        detected_records, queued = automatic_boundary_records(
            detection,
            source_text,
            minimum_confidence=args.auto_confidence,
            min_chars=args.min_chars,
            max_chars=args.max_chars,
            rights_status=args.rights_status,
        )
        apply_frozen_source_metadata(detected_records, source_plan[relative])
        apply_frozen_source_metadata(queued, source_plan[relative])
        has_boundary_ambiguity = not detected_records or bool(queued)
        if not has_boundary_ambiguity:
            continue
        evidence_path = evidence_dir / f"{Path(source_detection_name(relative)).stem}.txt"
        review_path = args.work_dir / "boundary_detection_review" / source_detection_name(
            relative
        )
        manual_result_path = (
            args.work_dir
            / "manual_results"
            / "step_1_boundary_review"
            / source_detection_name(relative)
        )
        source_hash = sha256_text(source_text)
        line_count = len(source_text.splitlines())
        if manual_result_path.is_file() and not args.refresh_boundaries:
            manual_result = read_json(manual_result_path)
            validate_boundary_detection(
                manual_result,
                source_path=relative,
                source_sha256=source_hash,
                line_count=line_count,
            )
            manual_result["_provenance"] = {
                "stage": "manual_story_boundaries_review",
                "model": "manual-sol",
                "reasoning_effort": "manual",
                "speed": "standard",
                "input_sha256": source_hash,
                "imported_at": utc_now(),
            }
            write_json(review_path, manual_result)
        manual_package_path = (
            args.work_dir
            / "manual_escalation"
            / "step_1"
            / f"{Path(source_detection_name(relative)).stem}.md"
        )
        if manual_package_path.is_file() and not manual_result_path.is_file():
            manual_review_waiting.append(
                (relative, manual_package_path, manual_result_path)
            )
            continue
        if review_path.is_file() and not args.refresh_boundaries:
            try:
                existing = read_json(review_path)
                validate_boundary_detection(
                    existing,
                    source_path=relative,
                    source_sha256=source_hash,
                    line_count=line_count,
                )
                if existing.get("_provenance", {}).get("input_sha256") == source_hash:
                    usable_review_source_paths.add(relative)
                    continue
            except PipelineError:
                pass
        ambiguous_sources.append(
            (source_file, relative, source_hash, line_count, evidence_path, review_path)
        )

    review_pending_total = len(ambiguous_sources) + len(manual_review_waiting)
    reviewed_source_count = len(usable_review_source_paths)
    review_failures = 0
    selected_ambiguous_sources: list[tuple[Path, str, str, int, Path, Path]] = []
    if args.resolve_ambiguous:
        selected_ambiguous_sources = limit_pending_items(
            ambiguous_sources,
            args.boundary_review_limit,
        )
        print(
            f"Terra 二次边界裁决本批：{len(selected_ambiguous_sources)} / "
            f"全部待处理：{review_pending_total}；"
            f"等待人工 Sol：{len(manual_review_waiting)}"
        )
        for relative, package_path, manual_result_path in manual_review_waiting:
            print(
                f"[等待人工 Sol] {relative}：{package_path}；"
                f"保存结果到 {manual_result_path}",
                flush=True,
            )

        def review_source(item: tuple[Path, str, str, int, Path, Path]) -> None:
            source_file, relative, source_hash, line_count, _, review_path = item
            source_text = source_file.read_text(encoding="utf-8")
            first_path = detection_dir / source_detection_name(relative)
            first_detection = read_json(first_path)
            packet_path = (
                args.work_dir
                / "boundary_review_packets"
                / f"{Path(source_detection_name(relative)).stem}.txt"
            )
            atomic_write_text(
                packet_path,
                build_boundary_review_packet(
                    source_text,
                    first_detection,
                    minimum_confidence=args.auto_confidence,
                    context_lines=args.boundary_review_context_lines,
                ),
            )
            prompt = build_boundary_review_prompt(
                source_path=relative,
                previous_detection_path=first_path,
                review_packet_path=packet_path,
                source_sha256=source_hash,
                line_count=line_count,
            )
            started_at = time.monotonic()
            result, effective_model, effective_effort, used_fallback = (
                run_codex_task_with_quality_fallback(
                    prompt=prompt,
                    model=args.boundary_review_model,
                    reasoning_effort=args.boundary_review_reasoning_effort,
                    fallback_model="gpt-5.6-terra",
                    fallback_reasoning_effort="high",
                    schema_path=BOUNDARY_SCHEMA_PATH,
                    output_path=review_path,
                    validator=lambda value, path=relative, digest=source_hash, count=line_count: (
                        validate_boundary_detection(
                            value,
                            source_path=path,
                            source_sha256=digest,
                            line_count=count,
                        )
                    ),
                    retries=args.retries,
                    timeout=args.timeout,
                )
            )
            result["_provenance"] = {
                "stage": "automatic_story_boundaries_review",
                "model": effective_model,
                "reasoning_effort": effective_effort,
                "quality_fallback_used": used_fallback,
                "speed": "standard",
                "input_sha256": source_hash,
                "targeted_packet": relative_to_repo(packet_path),
                "duration_seconds": round(time.monotonic() - started_at, 1),
                "generated_at": utc_now(),
            }
            write_json(review_path, result)
            (
                args.work_dir
                / "errors"
                / "step_1_review"
                / source_detection_name(relative)
            ).unlink(missing_ok=True)

        def record_review_error(
            item: tuple[Path, str, str, int, Path, Path], error: Exception
        ) -> None:
            relative = item[1]
            if isinstance(error, PipelineManualEscalationRequired):
                first_path = detection_dir / source_detection_name(relative)
                packet_path = (
                    args.work_dir
                    / "boundary_review_packets"
                    / f"{Path(source_detection_name(relative)).stem}.txt"
                )
                prompt = build_boundary_review_prompt(
                    source_path=relative,
                    previous_detection_path=first_path,
                    review_packet_path=packet_path,
                    source_sha256=item[2],
                    line_count=item[3],
                )
                manual_result_path = (
                    args.work_dir
                    / "manual_results"
                    / "step_1_boundary_review"
                    / source_detection_name(relative)
                )
                package_path = write_manual_escalation_package(
                    package_dir=args.work_dir / "manual_escalation" / "step_1",
                    item_id=Path(source_detection_name(relative)).stem,
                    stage="Step 1 Terra 边界复核",
                    prompt=prompt,
                    schema_path=BOUNDARY_SCHEMA_PATH,
                    manual_result_path=manual_result_path,
                    error=str(error),
                )
                print(
                    f"[需人工 Sol] {relative}：{package_path}；"
                    f"结果保存到 {manual_result_path} 后重跑同一命令",
                    flush=True,
                )
            write_json(
                args.work_dir / "errors" / "step_1_review" / source_detection_name(relative),
                {
                    "source_path": relative,
                    "stage": "boundary_review",
                    "error": str(error),
                },
            )

        review_failures = run_parallel_tasks(
            selected_ambiguous_sources,
            workers=args.boundary_review_workers,
            heartbeat_seconds=args.heartbeat_seconds,
            stage_label="Terra 边界复核",
            item_label=lambda item: item[1],
            task=review_source,
            on_error=record_review_error,
            continue_on_error=args.continue_on_error,
            progress_path=args.work_dir / "progress" / "step_1_boundary_review.json",
            progress_stage="step_1_boundary_review",
            total_items=review_pending_total + len(usable_review_source_paths),
            completed_before=len(usable_review_source_paths),
        )
        failures += review_failures
        reviewed_source_count += len(selected_ambiguous_sources) - review_failures
        for _, relative, source_hash, line_count, _, review_path in (
            selected_ambiguous_sources
        ):
            if not review_path.is_file():
                continue
            try:
                existing = read_json(review_path)
                validate_boundary_detection(
                    existing,
                    source_path=relative,
                    source_sha256=source_hash,
                    line_count=line_count,
                )
            except PipelineError:
                continue
            if existing.get("_provenance", {}).get("input_sha256") == source_hash:
                usable_review_source_paths.add(relative)

    boundaries: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    semantic_manual_waiting: list[str] = []
    completed_sources = 0
    for source_file in sources:
        relative = source_file.relative_to(args.input_dir).as_posix()
        first_path = detection_dir / source_detection_name(relative)
        review_path = args.work_dir / "boundary_detection_review" / source_detection_name(
            relative
        )
        output_path = (
            review_path
            if args.resolve_ambiguous
            and relative in usable_review_source_paths
            and review_path.is_file()
            else first_path
        )
        if not output_path.is_file():
            continue
        source_text = source_file.read_text(encoding="utf-8")
        detection = read_json(output_path)
        validate_boundary_detection(
            detection,
            source_path=relative,
            source_sha256=sha256_text(source_text),
            line_count=len(source_text.splitlines()),
        )
        accepted, queued = automatic_boundary_records(
            detection,
            source_text,
            minimum_confidence=args.auto_confidence,
            min_chars=args.min_chars,
            max_chars=args.max_chars,
            rights_status=args.rights_status,
        )
        apply_frozen_source_metadata(accepted, source_plan[relative])
        apply_frozen_source_metadata(queued, source_plan[relative])
        provenance = detection.get("_provenance", {})
        if (
            queued
            and output_path == review_path
            and provenance.get("model") == "gpt-5.6-terra"
        ):
            packet_path = (
                args.work_dir
                / "boundary_review_packets"
                / f"{Path(source_detection_name(relative)).stem}.txt"
            )
            manual_result_path = (
                args.work_dir
                / "manual_results"
                / "step_1_boundary_review"
                / source_detection_name(relative)
            )
            prompt = build_boundary_review_prompt(
                source_path=relative,
                previous_detection_path=first_path,
                review_packet_path=packet_path,
                source_sha256=sha256_text(source_text),
                line_count=len(source_text.splitlines()),
            )
            prompt += (
                "\n\n自动 Terra 复核结果仍留下低置信度或 completeness=uncertain 项："
                f"`{relative_to_repo(review_path)}`。请读取它并只解决其中未决边界。"
            )
            package_path = write_manual_escalation_package(
                package_dir=args.work_dir / "manual_escalation" / "step_1",
                item_id=Path(source_detection_name(relative)).stem,
                stage="Step 1 Terra 边界复核未决",
                prompt=prompt,
                schema_path=BOUNDARY_SCHEMA_PATH,
                manual_result_path=manual_result_path,
                error="Terra medium/high 后仍有低置信度或完整性不确定边界",
            )
            semantic_manual_waiting.append(relative)
            print(
                f"[需人工 Sol] {relative}：Terra 结果仍未决；{package_path}；"
                f"保存结果到 {manual_result_path} 后重跑同一命令",
                flush=True,
            )
        boundaries.extend(accepted)
        review_queue.extend(queued)
        completed_sources += 1

    boundary_manifest = args.work_dir / "boundaries.auto.jsonl"
    write_jsonl(boundary_manifest, boundaries)
    write_jsonl(args.work_dir / "boundary_review_queue.jsonl", review_queue)
    auto_approved = sum(
        record["boundary_status"] == "auto_approved" for record in boundaries
    )
    excluded_count = sum(record["boundary_status"] == "excluded" for record in boundaries)
    write_json(
        args.work_dir / "automatic_boundary_report.json",
        {
            "generated_at": utc_now(),
            "source_count": len(sources),
            "completed_source_count": completed_sources,
            "failed_source_count": (
                failures + len(manual_review_waiting) + len(semantic_manual_waiting)
            ),
            "second_pass_source_count": reviewed_source_count,
            "second_pass_pending_count": max(
                0,
                review_pending_total
                - (len(selected_ambiguous_sources) - review_failures)
                + len(semantic_manual_waiting),
            ),
            "manual_escalation_count": (
                len(manual_review_waiting) + len(semantic_manual_waiting)
            ),
            "candidate_count": len(boundaries),
            "auto_approved_count": auto_approved,
            "excluded_count": excluded_count,
            "review_queue_count": len(review_queue),
            "minimum_confidence": args.auto_confidence,
            "model": args.boundary_model,
            "reasoning_effort": args.boundary_reasoning_effort,
            "evidence_only": not args.boundary_full_source,
            "boundary_workers": args.boundary_workers,
            "boundary_review_workers": args.boundary_review_workers,
            "frozen_source_manifest": str(args.source_manifest),
            "frozen_source_manifest_sha256": source_manifest_sha256,
            "source_split_counts": dict(split_counts),
            "source_collection_counts": dict(collection_counts),
            "rights_status": args.rights_status,
        },
    )
    stories = prepare_stories(
        args.input_dir,
        args.work_dir,
        boundary_manifest,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        simhash_threshold=args.simhash_threshold,
        dry_run=False,
        frozen_source_manifest=str(args.source_manifest),
        frozen_source_manifest_sha256=source_manifest_sha256,
    )
    eligible = sum(record["eligible_for_cloud"] for record in stories)
    print(
        f"自动批准边界：{auto_approved}；低置信度队列：{len(review_queue)}；"
        f"排除非目标内容：{excluded_count}；已提取故事：{len(stories)}；云端可用：{eligible}"
    )
    return 1 if failures or manual_review_waiting or semantic_manual_waiting else 0


def apply_boundary_repairs(args: argparse.Namespace) -> int:
    """应用 Step 2 的高置信度行号建议，并重新生成故事清单。"""

    if not args.overwrite:
        raise PipelineError("应用边界修复会重建 stories.jsonl，必须显式传入 --overwrite")
    frozen_sources, source_manifest_sha256 = load_frozen_sources(
        args.input_dir, args.source_manifest
    )
    validate_source_run_contract(
        args.work_dir,
        input_dir=args.input_dir,
        source_manifest=args.source_manifest,
        source_manifest_sha256=source_manifest_sha256,
        dry_run=False,
    )
    source_plan = {source.source_path: source for source in frozen_sources}
    boundary_manifest = args.boundary_manifest or args.work_dir / "boundaries.auto.jsonl"
    repair_manifest = args.repair_manifest or args.work_dir / "boundary_repair_queue.jsonl"
    if not boundary_manifest.is_file():
        raise PipelineError(f"找不到待修复边界清单：{boundary_manifest}")
    if not repair_manifest.is_file():
        raise PipelineError(f"找不到 Step 2 修复队列：{repair_manifest}")
    boundaries = read_jsonl(boundary_manifest)
    for boundary in boundaries:
        source_path = str(boundary.get("source_path", ""))
        if source_path not in source_plan:
            raise PipelineError(f"边界来源不在冻结清单中：{source_path}")
        apply_frozen_source_metadata([boundary], source_plan[source_path])
    repairs = read_jsonl(repair_manifest)
    repairs_by_range: dict[tuple[str, int, int], dict[str, Any]] = {}
    for repair in repairs:
        key = (
            str(repair.get("source_path", "")),
            int(repair.get("current_start_line", 0)),
            int(repair.get("current_end_line", 0)),
        )
        repairs_by_range[key] = repair

    applied = 0
    still_queued: list[dict[str, Any]] = []
    for boundary in boundaries:
        current_start = boundary.get("start_line")
        current_end = boundary.get("end_line")
        if not isinstance(current_start, int) or not isinstance(current_end, int):
            continue
        key = (str(boundary.get("source_path", "")), current_start, current_end)
        repair = repairs_by_range.get(key)
        if repair is None:
            continue
        confidence = repair.get("confidence", 0)
        suggested_start = repair.get("suggested_start_line")
        suggested_end = repair.get("suggested_end_line")
        new_start = suggested_start if isinstance(suggested_start, int) else current_start
        new_end = suggested_end if isinstance(suggested_end, int) else current_end
        reasons: list[str] = []
        source_file = safe_source_path(args.input_dir, key[0])
        source_lines = source_file.read_text(encoding="utf-8").splitlines()
        if not isinstance(confidence, (int, float)) or confidence < args.auto_confidence:
            reasons.append("step_2_confidence_below_threshold")
        if suggested_start is None and suggested_end is None:
            reasons.append("step_2_has_no_line_suggestion")
        if new_start < 1 or new_end < new_start or new_end > len(source_lines):
            reasons.append("suggested_range_invalid")
        character_count = 0
        if not reasons:
            cleaned = clean_markdown("\n".join(source_lines[new_start - 1 : new_end]))
            character_count = len(re.sub(r"\s", "", cleaned))
            if character_count < args.min_chars:
                reasons.append("suggested_story_too_short")
            if character_count > args.max_chars:
                reasons.append("suggested_story_too_long")
        boundary["start_line"] = new_start
        boundary["end_line"] = new_end
        boundary["boundary_status"] = "needs_review" if reasons else "auto_approved"
        boundary["boundary_source"] = "step_2_boundary_repair"
        boundary["boundary_confidence"] = float(confidence) if isinstance(
            confidence, (int, float)
        ) else 0.0
        boundary["boundary_notes"] = "；".join(str(item) for item in repair.get("issues", []))
        boundary["character_count_estimate"] = character_count
        boundary["review_reasons"] = reasons
        if reasons:
            still_queued.append(boundary)
        else:
            applied += 1

    approved_by_source: dict[str, list[dict[str, Any]]] = {}
    for boundary in boundaries:
        if boundary.get("boundary_status") in APPROVED_BOUNDARY_STATUSES:
            approved_by_source.setdefault(str(boundary["source_path"]), []).append(boundary)
    for source_path, source_boundaries in approved_by_source.items():
        source_boundaries.sort(key=lambda item: (item["start_line"], item["end_line"]))
        for previous, current in zip(source_boundaries, source_boundaries[1:]):
            if current["start_line"] <= previous["end_line"]:
                current["boundary_status"] = "needs_review"
                current.setdefault("review_reasons", []).append("repair_overlaps_previous_story")
                still_queued.append(current)

    repaired_manifest = args.work_dir / "boundaries.repaired.jsonl"
    write_jsonl(repaired_manifest, boundaries)
    write_jsonl(args.work_dir / "boundary_repair_remaining.jsonl", still_queued)
    stories = prepare_stories(
        args.input_dir,
        args.work_dir,
        repaired_manifest,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        simhash_threshold=args.simhash_threshold,
        dry_run=False,
        frozen_source_manifest=str(args.source_manifest),
        frozen_source_manifest_sha256=source_manifest_sha256,
    )
    print(
        f"Step 2 边界建议已自动应用：{applied}；仍需复核：{len(still_queued)}；"
        f"重新提取故事：{len(stories)}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 1 命令行。"""

    parser = argparse.ArgumentParser(description="按 Step 0 冻结来源自动识别并提取完整故事")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=DEFAULT_SOURCE_MANIFEST,
        help="Step 0 生成的 selected_sources.jsonl",
    )
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument(
        "--auto-boundaries",
        action="store_true",
        help="用 Luna 按整期来源自动识别完整故事，并直接提取高置信度结果",
    )
    parser.add_argument(
        "--apply-boundary-repairs",
        action="store_true",
        help="应用 Step 2 的高置信度建议并重建故事；需要 --overwrite",
    )
    parser.add_argument(
        "--boundary-manifest",
        type=Path,
        help="应用 Step 2 修复时覆盖默认的 boundaries.auto.jsonl",
    )
    parser.add_argument("--boundary-model", default=DEFAULT_BOUNDARY_MODEL)
    parser.add_argument(
        "--resolve-ambiguous",
        action="store_true",
        help="让 Terra 对 Luna 的风险边界做局部复核；不会自动调用 Sol",
    )
    parser.add_argument("--boundary-review-model", default=DEFAULT_BOUNDARY_REVIEW_MODEL)
    parser.add_argument(
        "--boundary-review-reasoning-effort",
        default=DEFAULT_BOUNDARY_REVIEW_REASONING_EFFORT,
    )
    parser.add_argument(
        "--boundary-workers",
        type=int,
        default=3,
        help="Luna 首轮并发来源数，默认 3；额度受限时降为 1",
    )
    parser.add_argument(
        "--boundary-review-workers",
        type=int,
        default=2,
        help="Terra 风险复核并发来源数，默认 2；额度受限时降为 1",
    )
    parser.add_argument(
        "--boundary-review-limit",
        type=int,
        default=DEFAULT_BOUNDARY_REVIEW_LIMIT,
        help="每次最多复核的未完成来源，默认 10；重复命令续跑",
    )
    parser.add_argument(
        "--boundary-review-context-lines",
        type=int,
        default=DEFAULT_BOUNDARY_REVIEW_CONTEXT_LINES,
        help="风险故事起止两侧各保留的局部原文行数，默认 30",
    )
    parser.add_argument(
        "--boundary-full-source",
        action="store_true",
        help="首轮也允许 Luna 检查整份原文；更慢，默认仅使用 Python 边界证据包",
    )
    parser.add_argument("--repair-manifest", type=Path)
    parser.add_argument(
        "--boundary-reasoning-effort",
        default=DEFAULT_BOUNDARY_REASONING_EFFORT,
    )
    parser.add_argument(
        "--rights-status",
        choices=("unknown", APPROVED_RIGHTS_STATUS),
        default="unknown",
        help="自动边界记录使用的授权状态；脚本不会自行判断版权",
    )
    parser.add_argument("--auto-confidence", type=float, default=0.80)
    parser.add_argument(
        "--pilot-per-collection",
        type=int,
        help="代表性试跑时每个目标刊物处理 N 份；正式运行省略",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="仅临时网络/传输失败的额外重试次数，默认 1",
    )
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="并发模型任务无完成结果时的进度心跳间隔",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--refresh-boundaries",
        action="store_true",
        help="忽略已有且来源哈希匹配的 AI 边界结果并重新调用模型",
    )
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--max-chars", type=int, default=50000)
    parser.add_argument("--simhash-threshold", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="只检查并打印统计，不写文件")
    parser.add_argument("--overwrite", action="store_true", help="允许替换已有 Step 1 清单")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 1。"""

    args = build_parser().parse_args(argv)
    if args.min_chars < 1 or args.max_chars < args.min_chars:
        raise PipelineError("字符数范围无效")
    if not 0 <= args.simhash_threshold <= 16:
        raise PipelineError("simhash-threshold 必须在 0–16 之间")
    if args.auto_boundaries and args.boundary_manifest is not None:
        raise PipelineError("--boundary-manifest 只能与 --apply-boundary-repairs 一起使用")
    if args.auto_boundaries and args.apply_boundary_repairs:
        raise PipelineError("--auto-boundaries 与 --apply-boundary-repairs 不能同时使用")
    if args.auto_boundaries:
        return run_automatic_boundaries(args)
    if args.apply_boundary_repairs:
        return apply_boundary_repairs(args)
    raise PipelineError("必须指定 --auto-boundaries 或 --apply-boundary-repairs")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as error:
        raise SystemExit(f"错误：{error}") from None
