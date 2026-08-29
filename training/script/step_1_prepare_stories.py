#!/usr/bin/env python3
"""Step 1：清洗 MinerU Markdown，并按人工确认的边界生成完整故事。

本模块也提供后续步骤共用的 JSONL、哈希、Codex CLI 和原子写入工具。把共用逻辑放在
第一步，是为了让所有可执行脚本仍遵循 ``step_N_具体业务.py`` 的命名约定。
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unicodedata
from typing import Any, Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "training"
DEFAULT_WORK_DIR = REPO_ROOT / "work" / "training-pipeline"
APPROVED_RIGHTS_STATUS = "approved_for_cloud_training"
ALLOWED_SPLITS = {"auto", "train", "validation", "blind", "test"}

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


@dataclass(frozen=True)
class Boundary:
    """一篇完整故事在来源 Markdown 中的人工确认边界。"""

    source_path: str
    title: str
    start_line: int
    end_line: int
    boundary_status: str
    rights_status: str
    split: str


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


def collect_markdown_files(input_dir: Path) -> list[Path]:
    """收集训练来源 Markdown，排除脚本和运行目录。"""

    if not input_dir.is_dir():
        raise PipelineError(f"训练文本目录不存在：{input_dir}")
    paths = []
    for path in input_dir.rglob("*.md"):
        relative_parts = path.relative_to(input_dir).parts
        if len(relative_parts) < 2 or "script" in relative_parts or "work" in relative_parts:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(input_dir).as_posix())


def heading_candidates(text: str) -> list[dict[str, Any]]:
    """列出 Markdown 标题作为人工边界候选，不自动声称它们是完整故事。"""

    headings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = HEADING_RE.match(line)
        if match:
            headings.append(
                {"line": line_number, "level": len(match.group(1)), "title": match.group(2).strip()}
            )
    return headings


def build_inventory(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构建来源清单和供人工填写的故事边界候选。"""

    inventory: list[dict[str, Any]] = []
    boundary_template: list[dict[str, Any]] = []
    for path in collect_markdown_files(input_dir):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(input_dir).as_posix()
        headings = heading_candidates(text)
        inventory.append(
            {
                "source_path": relative,
                "sha256": sha256_text(text),
                "bytes": path.stat().st_size,
                "line_count": len(text.splitlines()),
                "heading_count": len(headings),
            }
        )
        for heading in headings:
            boundary_template.append(
                {
                    "source_path": relative,
                    "title": heading["title"],
                    "start_line": heading["line"],
                    "end_line": None,
                    "boundary_status": "needs_review",
                    "rights_status": "unknown",
                    "split": "auto",
                }
            )
    return inventory, boundary_template


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
    split = str(record.get("split", "auto"))
    if split not in ALLOWED_SPLITS:
        raise PipelineError(f"边界清单第 {line_number} 条 split 无效：{split}")
    return Boundary(
        source_path=str(record["source_path"]),
        title=str(record["title"]).strip(),
        start_line=start_line,
        end_line=end_line,
        boundary_status=str(record.get("boundary_status", "needs_review")),
        rights_status=str(record.get("rights_status", "unknown")),
        split=split,
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


def assign_automatic_splits(
    records: list[dict[str, Any]], blind_count: int, validation_count: int
) -> None:
    """按内容哈希确定性分配盲测、验证和训练集合。"""

    automatic = [
        record
        for record in records
        if record["split"] == "auto" and record["eligible_for_cloud"] and not record["duplicate_of"]
    ]
    automatic.sort(key=lambda record: (record["sha256"], record["source_id"]))
    for index, record in enumerate(automatic):
        if index < blind_count:
            record["split"] = "blind"
        elif index < blind_count + validation_count:
            record["split"] = "validation"
        else:
            record["split"] = "train"
    for record in records:
        if record["split"] == "auto":
            record["split"] = "train"


def mark_duplicates(records: list[dict[str, Any]], threshold: int) -> None:
    """标记精确重复和 SimHash 近重复，不删除任何来源证据。"""

    exact: dict[str, str] = {}
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for record in sorted(records, key=lambda item: item["source_id"]):
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
    blind_count: int,
    validation_count: int,
    simhash_threshold: int,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """根据经人工确认的边界提取、清洗并登记完整故事。"""

    raw_boundaries = read_jsonl(boundary_manifest)
    boundaries = [parse_boundary(record, index) for index, record in enumerate(raw_boundaries, 1)]
    approved_ranges: dict[str, list[Boundary]] = {}
    for boundary in boundaries:
        if boundary.boundary_status == "approved":
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
    existing_splits: dict[str, str] = {}
    existing_manifest = work_dir / "stories.jsonl"
    if existing_manifest.is_file():
        for record in read_jsonl(existing_manifest):
            source_id = record.get("source_id")
            split = record.get("split")
            if isinstance(source_id, str) and split in ALLOWED_SPLITS - {"auto"}:
                existing_splits[source_id] = str(split)
    for boundary in boundaries:
        if boundary.boundary_status != "approved":
            continue
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
        record: dict[str, Any] = {
            "source_id": source_id,
            "title": boundary.title,
            "source_path": boundary.source_path,
            "start_line": boundary.start_line,
            "end_line": boundary.end_line,
            "story_path": f"stories/{source_id}.md",
            "sha256": sha256_text(cleaned),
            "content_hash": content_hash,
            "simhash64": f"{simhash64(cleaned):016x}",
            "character_count": character_count,
            "name_candidates": extract_name_candidates(cleaned),
            "boundary_status": boundary.boundary_status,
            "rights_status": boundary.rights_status,
            "eligible_for_cloud": boundary.rights_status == APPROVED_RIGHTS_STATUS,
            "split": boundary.split,
            "duplicate_of": None,
            "duplicate_kind": None,
        }
        stories.append(record)
        story_texts[source_id] = cleaned
    for record in stories:
        if record["split"] == "auto" and record["source_id"] in existing_splits:
            record["split"] = existing_splits[record["source_id"]]
    mark_duplicates(stories, simhash_threshold)
    assign_automatic_splits(stories, blind_count, validation_count)
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


def relative_to_repo(path: Path) -> str:
    """返回相对仓库路径；运行数据必须位于仓库中才能被 Codex 只读访问。"""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise PipelineError(f"Codex 输入必须位于仓库内：{path}") from error


def codex_command(
    *,
    prompt: str,
    model: str,
    reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
    profile: str | None = None,
    local_provider: str | None = None,
) -> list[str]:
    """构造最小权限、非交互、结构化输出的 Codex CLI 命令。"""

    command = [
        "codex",
        "exec",
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
    if profile:
        command.extend(["--profile", profile])
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
    profile: str | None = None,
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
        profile=profile,
        local_provider=local_provider,
    )
    last_error = ""
    for attempt in range(retries + 1):
        if temporary_path.exists():
            temporary_path.unlink()
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            last_error = str(error)
        else:
            if completed.returncode == 0 and temporary_path.is_file():
                value = read_json(temporary_path)
                validator(value)
                temporary_path.unlink()
                return value
            stderr_tail = completed.stderr.strip()[-1000:]
            last_error = f"退出码 {completed.returncode}: {stderr_tail or '无错误输出'}"
        if attempt < retries:
            time.sleep(min(2**attempt, 8))
    raise PipelineError(f"Codex 任务失败（已尝试 {retries + 1} 次）：{last_error}")


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


def build_parser() -> argparse.ArgumentParser:
    """构造 Step 1 命令行。"""

    parser = argparse.ArgumentParser(description="清洗并按确认边界生成完整故事")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument(
        "--boundary-manifest",
        type=Path,
        help="人工确认的 JSONL 边界；省略时仅生成来源与标题候选清单",
    )
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--max-chars", type=int, default=50000)
    parser.add_argument("--blind-count", type=int, default=60)
    parser.add_argument("--validation-count", type=int, default=20)
    parser.add_argument("--simhash-threshold", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="只检查并打印统计，不写文件")
    parser.add_argument("--overwrite", action="store_true", help="允许替换已有 Step 1 清单")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Step 1。"""

    args = build_parser().parse_args(argv)
    if args.min_chars < 1 or args.max_chars < args.min_chars:
        raise PipelineError("字符数范围无效")
    if args.blind_count < 0 or args.validation_count < 0:
        raise PipelineError("集合数量不能小于 0")
    if not 0 <= args.simhash_threshold <= 16:
        raise PipelineError("simhash-threshold 必须在 0–16 之间")
    if args.boundary_manifest is None:
        inventory, template = build_inventory(args.input_dir)
        if not args.dry_run:
            inventory_path = args.work_dir / "source_inventory.jsonl"
            template_path = args.work_dir / "boundary_template.jsonl"
            if not args.overwrite and (inventory_path.exists() or template_path.exists()):
                raise PipelineError("来源清单已存在；确认后使用 --overwrite")
            write_jsonl(inventory_path, inventory)
            write_jsonl(template_path, template)
        print(f"来源 Markdown：{len(inventory)}；标题边界候选：{len(template)}")
        return 0
    manifest_path = args.work_dir / "stories.jsonl"
    if manifest_path.exists() and not args.overwrite and not args.dry_run:
        raise PipelineError("stories.jsonl 已存在；确认后使用 --overwrite")
    stories = prepare_stories(
        args.input_dir,
        args.work_dir,
        args.boundary_manifest,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        blind_count=args.blind_count,
        validation_count=args.validation_count,
        simhash_threshold=args.simhash_threshold,
        dry_run=args.dry_run,
    )
    eligible = sum(record["eligible_for_cloud"] for record in stories)
    duplicates = sum(record["duplicate_of"] is not None for record in stories)
    print(f"完整故事：{len(stories)}；云端授权：{eligible}；重复项：{duplicates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
