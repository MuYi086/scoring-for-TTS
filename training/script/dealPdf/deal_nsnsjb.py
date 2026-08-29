#!/usr/bin/env python3
"""用 MinerU 将《男生女生（金版）》PDF 批量转换为 Markdown。

默认读取 Windows 的 ``C:\\Downloads\\男生女生金版2002-2015``（在 WSL 中自动映射为
``/mnt/c/Downloads/男生女生金版2002-2015``），并将同名 ``.md`` 写入本仓库的
``training/男生女生金版``。脚本按 MinerU 批量接口提交并并发上传，已生成的非空 Markdown 会被
跳过，因此可安全重跑。

运行前请仅在本机环境中设置 MinerU API Token：

    export MINEU_API_KEY='...'
    python training/script/dealPdf/deal_nsnsjb.py

先检查待处理列表而不访问 MinerU：

    python training/script/dealPdf/deal_nsnsjb.py --dry-run
"""

from __future__ import annotations

import argparse
from concurrent.futures import as_completed, FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


API_BASE = "https://mineru.net/api/v4"
MODEL_VERSION = "vlm"
LANGUAGE = "ch"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 900
MAX_BATCH_SIZE = 50
DEFAULT_UPLOAD_WORKERS = 4
DEFAULT_DOWNLOAD_WORKERS = 4
UPLOAD_TIMEOUT_SECONDS = 300
UPLOAD_MAX_ATTEMPTS = 3
UPLOAD_RETRY_DELAY_SECONDS = 2
PROGRESS_HEARTBEAT_SECONDS = 30
UPLOAD_LOW_SPEED_LIMIT_BYTES = 1024
UPLOAD_LOW_SPEED_TIME_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_UPLOAD_SIZE_BYTES = 200 * 1024 * 1024
WINDOWS_SOURCE_DIR = Path(r"C:\Downloads\男生女生金版2002-2015")
WSL_SOURCE_DIR = Path("/mnt/c/Downloads/男生女生金版2002-2015")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "training" / "男生女生金版"
API_TOKEN_ENVIRONMENT_VARIABLE = "MINEU_API_KEY"


@dataclass(frozen=True)
class RunSummary:
    """一次转换运行的统计数据。"""

    total: int
    succeeded: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class BatchItem:
    """批量任务中的一个 PDF 及其本地输出映射。"""

    data_id: str
    pdf_path: Path
    output_path: Path

    @property
    def error_path(self) -> Path:
        """返回本文件的错误标记路径。"""
        return self.output_path.with_suffix(self.output_path.suffix + ".error")


@dataclass(frozen=True)
class SubmittedBatch:
    """已经获得 batch_id 且上传成功的文件集合。"""

    batch_id: str
    items: tuple[BatchItem, ...]


class MinerUConnectionError(RuntimeError):
    """无法连接 MinerU 或其签名存储服务时抛出，调用方应停止本批次。"""


class MinerUAuthenticationError(RuntimeError):
    """MinerU 拒绝认证信息时抛出，且不会在异常中暴露 Token。"""


def log(message: str) -> None:
    """输出带时间的进度日志。"""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def default_source_dir() -> Path:
    """返回当前系统可访问的默认 PDF 目录。"""
    if WINDOWS_SOURCE_DIR.exists():
        return WINDOWS_SOURCE_DIR
    return WSL_SOURCE_DIR


def build_parser(
    *,
    collection_name: str = "《男生女生（金版）》",
    windows_source_dir: Path = WINDOWS_SOURCE_DIR,
    wsl_source_dir: Path = WSL_SOURCE_DIR,
    default_output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> argparse.ArgumentParser:
    """为指定刊物创建命令行参数解析器。"""
    source_dir = windows_source_dir if windows_source_dir.exists() else wsl_source_dir
    parser = argparse.ArgumentParser(
        description=f"使用 MinerU 将{collection_name} PDF 批量转换为 Markdown"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=source_dir,
        help=f"待转换 PDF 目录；Windows 默认是 {windows_source_dir}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=f"Markdown 输出目录；默认是 {default_output_dir}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="即使已有同名且非空 Markdown 也重新调用 MinerU",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅列出待处理、跳过的文件，不读取密钥或访问 MinerU",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL_SECONDS,
        help=f"轮询间隔秒数，默认 {POLL_INTERVAL_SECONDS}",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=POLL_TIMEOUT_SECONDS,
        help=f"每批结果的最长等待秒数，默认 {POLL_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAX_BATCH_SIZE,
        help=f"每个 MinerU 批次的文件数，默认及上限均为 {MAX_BATCH_SIZE}",
    )
    parser.add_argument(
        "--upload-workers",
        type=int,
        default=DEFAULT_UPLOAD_WORKERS,
        help=f"并发上传数，默认 {DEFAULT_UPLOAD_WORKERS}",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help=f"并发下载结果数，默认 {DEFAULT_DOWNLOAD_WORKERS}",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    """验证路径和轮询参数，避免运行中才发现不可恢复的配置错误。"""
    if not args.source_dir.is_dir():
        raise FileNotFoundError(f"PDF 源目录不存在或不是目录: {args.source_dir}")
    if args.poll_interval <= 0:
        raise ValueError("--poll-interval 必须大于 0")
    if args.poll_timeout <= 0:
        raise ValueError("--poll-timeout 必须大于 0")
    if not 1 <= args.batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"--batch-size 必须在 1 到 {MAX_BATCH_SIZE} 之间")
    if args.upload_workers <= 0:
        raise ValueError("--upload-workers 必须大于 0")
    if args.download_workers <= 0:
        raise ValueError("--download-workers 必须大于 0")
    if args.output_dir.exists() and not args.output_dir.is_dir():
        raise NotADirectoryError(f"Markdown 输出路径不是目录: {args.output_dir}")


def collect_pdf_files(source_dir: Path) -> list[Path]:
    """递归收集 PDF，并以相对路径排序以保证运行顺序稳定。"""
    return sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.relative_to(source_dir).as_posix().casefold(),
    )


def output_path_for(pdf_path: Path, output_dir: Path) -> Path:
    """生成与 PDF 同名、扩展名改为 .md 的扁平化输出路径。"""
    return output_dir / f"{pdf_path.stem}.md"


def ensure_unique_output_paths(pdf_files: list[Path], output_dir: Path) -> None:
    """在上传前拒绝会映射到同一 Markdown 文件的输入，防止静默覆盖。"""
    duplicates: dict[Path, list[Path]] = {}
    for pdf_path in pdf_files:
        output_path = output_path_for(pdf_path, output_dir)
        duplicates.setdefault(output_path, []).append(pdf_path)
    collisions = [paths for paths in duplicates.values() if len(paths) > 1]
    if collisions:
        formatted = "; ".join(", ".join(str(path) for path in paths) for paths in collisions)
        raise ValueError(f"存在同名 PDF，无法保持输出文件名不变: {formatted}")


def ensure_within_upload_size_limit(pdf_files: list[Path]) -> None:
    """在上传前执行 MinerU 精准解析 API 的 200 MB 单文件大小限制检查。"""
    oversized_files = [
        pdf_path for pdf_path in pdf_files if pdf_path.stat().st_size > MAX_UPLOAD_SIZE_BYTES
    ]
    if oversized_files:
        formatted = "; ".join(str(pdf_path) for pdf_path in oversized_files)
        raise ValueError(
            "以下 PDF 超过 MinerU 的 200 MB 单文件限制，请拆分后再转换: "
            f"{formatted}"
        )


def should_skip(output_path: Path, overwrite: bool) -> bool:
    """判断既有、非空 Markdown 是否可作为已完成的断点。"""
    return not overwrite and output_path.is_file() and output_path.stat().st_size > 0


def get_api_token() -> str:
    """从 MINEU_API_KEY 环境变量读取 Token。"""
    value = os.environ.get(API_TOKEN_ENVIRONMENT_VARIABLE)
    if not value:
        raise ValueError(
            "未设置 MinerU Token。请在当前终端执行 "
            "export MINEU_API_KEY='...'；Token 不要写入代码或文件。"
        )
    return normalize_api_token(value)


def normalize_api_token(api_token: str) -> str:
    """去除复制 Token 时常见的外围格式，不修改 Token 本体。"""
    normalized_token = api_token.strip()
    if len(normalized_token) >= 2 and normalized_token[0] == normalized_token[-1] in {"'", '"'}:
        normalized_token = normalized_token[1:-1].strip()
    if normalized_token.lower().startswith("bearer "):
        normalized_token = normalized_token[7:].strip()
    if not normalized_token:
        raise ValueError("MinerU Token 不能为空。")
    return normalized_token


def api_headers(api_key: str) -> dict[str, str]:
    """返回 MinerU JSON API 的认证请求头。"""
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def request_json(request: Request, timeout: float) -> dict[str, Any]:
    """执行 JSON 请求并返回对象，保留 HTTP 错误上下文。"""
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 401:
            raise MinerUAuthenticationError(
                "MinerU HTTP 401：认证失败。请在 API 管理页新建 Token，并在同一终端执行 "
                "export MINEU_API_KEY='新Token' 后重新运行；不要把 'Bearer ' 或引号复制到值中。"
            ) from error
        raise RuntimeError(f"MinerU HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        reason = error.reason if isinstance(error, URLError) else str(error)
        raise MinerUConnectionError(f"无法连接 MinerU: {reason}") from error

    try:
        result = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("MinerU 返回的不是有效 JSON") from error
    if not isinstance(result, dict):
        raise RuntimeError("MinerU 返回的 JSON 不是对象")
    return result


def split_batches(items: list[BatchItem], batch_size: int) -> list[list[BatchItem]]:
    """按 MinerU 的单批上限切分待处理文件。"""
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def get_batch_upload_urls(items: list[BatchItem], api_key: str) -> tuple[str, list[str]]:
    """一次申请一批 PDF 的 MinerU 签名上传地址。"""
    if not items:
        raise ValueError("不能为空批次申请上传地址")
    if len(items) > MAX_BATCH_SIZE:
        raise ValueError(f"单批文件数不能超过 {MAX_BATCH_SIZE}")

    payload = json.dumps(
        {
            "files": [
                {"name": item.pdf_path.name, "data_id": item.data_id} for item in items
            ],
            "model_version": MODEL_VERSION,
            "language": LANGUAGE,
        }
    ).encode("utf-8")
    request = Request(
        f"{API_BASE}/file-urls/batch",
        data=payload,
        headers=api_headers(api_key),
        method="POST",
    )
    result = request_json(request, timeout=30)
    if result.get("code") != 0:
        raise RuntimeError(f"申请上传地址失败: {result.get('msg', result)}")

    try:
        data = result["data"]
        batch_id = data["batch_id"]
        upload_urls = data["file_urls"]
    except (KeyError, TypeError) as error:
        raise RuntimeError(f"MinerU 上传地址响应缺少必要字段: {result}") from error
    if not isinstance(batch_id, str) or not isinstance(upload_urls, list):
        raise RuntimeError(f"MinerU 上传地址响应字段类型错误: {result}")
    if len(upload_urls) != len(items) or not all(isinstance(url, str) for url in upload_urls):
        raise RuntimeError(
            f"MinerU 返回 {len(upload_urls)} 个上传地址，但本批有 {len(items)} 个文件"
        )
    return batch_id, upload_urls


def upload_file(pdf_path: Path, upload_url: str) -> None:
    """用 MinerU 官方推荐的 curl PUT 方式上传 PDF，并重试临时连接故障。"""
    command = [
        "curl",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--location",
        "--upload-file",
        str(pdf_path),
        "--connect-timeout",
        "30",
        "--max-time",
        str(UPLOAD_TIMEOUT_SECONDS),
        "--speed-limit",
        str(UPLOAD_LOW_SPEED_LIMIT_BYTES),
        "--speed-time",
        str(UPLOAD_LOW_SPEED_TIME_SECONDS),
        "--output",
        os.devnull,
        "--write-out",
        "%{http_code}",
        upload_url,
    ]

    for attempt in range(1, UPLOAD_MAX_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "未找到 curl。请先安装 curl；MinerU 官方使用 curl -T 上传本地文件。"
            ) from error

        http_status = result.stdout.strip()
        if result.returncode == 0 and http_status in {"200", "201"}:
            return

        safe_detail = result.stderr.strip().replace(upload_url, "[签名上传地址]")
        if http_status and http_status != "000":
            error = RuntimeError(
                f"上传失败，HTTP {http_status}"
                + (f"：{safe_detail}" if safe_detail else "")
            )
            retryable = http_status.startswith("5")
        else:
            error = MinerUConnectionError(
                f"上传时无法连接存储服务（curl 退出码 {result.returncode}）"
                + (f"：{safe_detail}" if safe_detail else "")
            )
            retryable = True

        if not retryable or attempt == UPLOAD_MAX_ATTEMPTS:
            raise error

        delay = UPLOAD_RETRY_DELAY_SECONDS * attempt
        log(
            f"  {pdf_path.name} 上传连接中断，第 {attempt}/{UPLOAD_MAX_ATTEMPTS} 次失败，"
            f"{delay} 秒后重试..."
        )
        time.sleep(delay)


def upload_batch(
    items: list[BatchItem],
    upload_urls: list[str],
    workers: int,
) -> tuple[tuple[BatchItem, ...], list[tuple[BatchItem, Exception]]]:
    """并发上传一批文件，分别返回成功项和失败项。"""
    completed_items: set[str] = set()
    failures: list[tuple[BatchItem, Exception]] = []
    worker_count = min(workers, len(items))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_items = {
            executor.submit(upload_file, item.pdf_path, upload_url): item
            for item, upload_url in zip(items, upload_urls, strict=True)
        }
        pending_futures = set(future_items)
        completed_count = 0
        while pending_futures:
            done, pending_futures = wait(
                pending_futures,
                timeout=PROGRESS_HEARTBEAT_SECONDS,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                log(
                    f"  上传仍在进行：已结束 {completed_count}/{len(items)}，"
                    f"尚有 {len(pending_futures)} 个未结束"
                )
                continue
            for future in done:
                completed_count += 1
                item = future_items[future]
                try:
                    future.result()
                except Exception as error:
                    failures.append((item, error))
                    log(
                        f"  [上传失败 {completed_count}/{len(items)}] "
                        f"{item.pdf_path.name}: {error}"
                    )
                else:
                    completed_items.add(item.data_id)
                    log(
                        f"  上传完成 [{completed_count}/{len(items)}] "
                        f"{item.pdf_path.name}"
                    )

    uploaded = tuple(item for item in items if item.data_id in completed_items)
    return uploaded, failures


def submit_batch(items: list[BatchItem], api_key: str, workers: int) -> tuple[SubmittedBatch, int]:
    """申请一批上传地址并并发上传，返回可轮询批次和上传失败数。"""
    batch_id, upload_urls = get_batch_upload_urls(items, api_key)
    log(f"  batch_id: {batch_id}，开始并发上传 {len(items)} 个文件")
    uploaded, failures = upload_batch(items, upload_urls, workers)
    for item, error in failures:
        write_error(item.error_path, error)
    return SubmittedBatch(batch_id, uploaded), len(failures)


def get_batch_results(batch_id: str, api_key: str) -> list[dict[str, Any]]:
    """查询一次 MinerU 批量解析结果。"""
    request_url = f"{API_BASE}/extract-results/batch/{batch_id}"
    request = Request(request_url, headers=api_headers(api_key))
    result = request_json(request, timeout=30)
    if result.get("code") != 0:
        raise RuntimeError(f"查询解析结果失败: {result.get('msg', result)}")
    try:
        extract_results = result["data"]["extract_result"]
    except (KeyError, TypeError) as error:
        raise RuntimeError(f"MinerU 批量结果响应缺少必要字段: {result}") from error
    if not isinstance(extract_results, list) or not all(
        isinstance(item, dict) for item in extract_results
    ):
        raise RuntimeError(f"MinerU 批量结果 extract_result 不是对象列表: {result}")
    return extract_results


def match_batch_results(
    items: tuple[BatchItem, ...],
    extract_results: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """优先按 data_id、其次按唯一文件名匹配批量结果。"""
    expected_ids = {item.data_id for item in items}
    ids_by_filename = {item.pdf_path.name: item.data_id for item in items}
    matched: dict[str, dict[str, Any]] = {}
    for result_item in extract_results:
        data_id = result_item.get("data_id")
        if data_id not in expected_ids:
            data_id = ids_by_filename.get(result_item.get("file_name"))
        if data_id in expected_ids:
            matched[data_id] = result_item
    return matched


def download_zip(zip_url: str) -> bytes:
    """下载 MinerU 的解析结果 ZIP。"""
    try:
        with urlopen(zip_url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"下载结果失败，HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        reason = error.reason if isinstance(error, URLError) else str(error)
        raise MinerUConnectionError(f"下载结果时无法连接存储服务: {reason}") from error


def markdown_from_zip(zip_content: bytes) -> str:
    """优先从结果 ZIP 的 full.md 中读取 Markdown，兼容仅含一个 Markdown 的结果。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_content))
    except zipfile.BadZipFile as error:
        raise RuntimeError("MinerU 返回的结果不是有效 ZIP 文件") from error

    markdown_names = [name for name in archive.namelist() if name.lower().endswith(".md")]
    full_markdown = next(
        (name for name in markdown_names if name.rsplit("/", 1)[-1] == "full.md"),
        None,
    )
    selected_name = full_markdown or (markdown_names[0] if markdown_names else None)
    if selected_name is None:
        raise RuntimeError("MinerU 结果 ZIP 中未找到 Markdown 文件")
    with archive.open(selected_name) as markdown_file:
        return markdown_file.read().decode("utf-8", errors="replace")


def write_text_atomically(output_path: Path, content: str) -> None:
    """以原子替换写入 Markdown，避免中断留下半个输出文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_error(error_path: Path, error: Exception) -> None:
    """保存失败原因，便于重跑后核对；下次运行仍会重试该 PDF。"""
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")


def download_and_write_result(item: BatchItem, zip_url: str) -> None:
    """下载一个解析结果并原子写入对应 Markdown。"""
    markdown = markdown_from_zip(download_zip(zip_url))
    write_text_atomically(item.output_path, markdown)


def collect_batch_results(
    batch: SubmittedBatch,
    api_key: str,
    poll_interval: float,
    poll_timeout: float,
    download_workers: int,
) -> tuple[int, int]:
    """轮询一批任务，将每轮新完成的结果立即并发下载并写入。"""
    if not batch.items:
        return 0, 0

    remaining = {item.data_id: item for item in batch.items}
    started_at = time.monotonic()
    last_progress: tuple[int, int, tuple[tuple[str, int], ...]] | None = None
    last_log_at = started_at - PROGRESS_HEARTBEAT_SECONDS
    succeeded = 0
    failed = 0

    while remaining:
        elapsed = time.monotonic() - started_at
        if elapsed >= poll_timeout:
            unfinished = [item.pdf_path.name for item in remaining.values()]
            preview = "、".join(unfinished[:5])
            if len(unfinished) > 5:
                preview += f" 等 {len(unfinished)} 个文件"
            raise TimeoutError(
                f"等待 MinerU 批量解析超时（{poll_timeout:g} 秒）：{preview}"
            )

        matched = match_batch_results(
            batch.items,
            get_batch_results(batch.batch_id, api_key),
        )
        downloadable: list[tuple[BatchItem, str]] = []
        for data_id, item in list(remaining.items()):
            result_item = matched.get(data_id)
            if result_item is None:
                continue
            state = result_item.get("state")
            if state == "failed":
                error = RuntimeError(
                    f"MinerU 解析失败: {result_item.get('err_msg') or 'unknown'}"
                )
                write_error(item.error_path, error)
                log(f"  [解析失败] {item.pdf_path.name}: {error}")
                failed += 1
                del remaining[data_id]
                continue
            if state != "done":
                continue

            zip_url = result_item.get("full_zip_url")
            if not isinstance(zip_url, str) or not zip_url:
                error = RuntimeError("MinerU 已完成但未返回 full_zip_url")
                write_error(item.error_path, error)
                log(f"  [结果失败] {item.pdf_path.name}: {error}")
                failed += 1
                del remaining[data_id]
                continue
            downloadable.append((item, zip_url))

        if downloadable:
            worker_count = min(download_workers, len(downloadable))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_items = {
                    executor.submit(download_and_write_result, item, zip_url): item
                    for item, zip_url in downloadable
                }
                for future in as_completed(future_items):
                    item = future_items[future]
                    try:
                        future.result()
                    except Exception as error:
                        write_error(item.error_path, error)
                        log(f"  [下载失败] {item.pdf_path.name}: {error}")
                        failed += 1
                    else:
                        succeeded += 1
                        if item.error_path.exists():
                            item.error_path.unlink()
                        log(f"  [OK] 已保存: {item.output_path}")
                    del remaining[item.data_id]

        state_counts: dict[str, int] = {}
        for data_id in remaining:
            state = matched.get(data_id, {}).get("state", "not-returned")
            state_counts[state] = state_counts.get(state, 0) + 1
        state_summary = tuple(sorted(state_counts.items()))
        progress = (succeeded, failed, state_summary)
        now = time.monotonic()
        if progress != last_progress or now - last_log_at >= PROGRESS_HEARTBEAT_SECONDS:
            formatted = ", ".join(
                f"{state}={count}" for state, count in state_summary
            ) or "无待处理文件"
            log(
                f"  本批进度：已保存 {succeeded}，失败 {failed}，"
                f"剩余 {len(remaining)}（{formatted}）"
            )
            last_progress = progress
            last_log_at = now

        if remaining:
            time.sleep(poll_interval)
    return succeeded, failed


def run(args: argparse.Namespace) -> RunSummary:
    """按参数执行转换，返回可用于测试和命令行退出码的汇总。"""
    validate_args(args)
    pdf_files = collect_pdf_files(args.source_dir)
    ensure_unique_output_paths(pdf_files, args.output_dir)

    pending_files: list[tuple[Path, Path]] = []
    skipped = 0
    for pdf_path in pdf_files:
        output_path = output_path_for(pdf_path, args.output_dir)
        if should_skip(output_path, args.overwrite):
            skipped += 1
        else:
            pending_files.append((pdf_path, output_path))

    ensure_within_upload_size_limit([pdf_path for pdf_path, _ in pending_files])

    log(f"发现 PDF {len(pdf_files)} 个，待处理 {len(pending_files)} 个，已跳过 {skipped} 个")
    if args.dry_run:
        for pdf_path, output_path in pending_files:
            log(f"[DRY-RUN] {pdf_path} -> {output_path}")
        return RunSummary(len(pdf_files), 0, 0, skipped)
    if not pending_files:
        return RunSummary(len(pdf_files), 0, 0, skipped)

    api_key = get_api_token()
    batch_items = [
        BatchItem(
            data_id=f"document-{index:06d}",
            pdf_path=pdf_path,
            output_path=output_path,
        )
        for index, (pdf_path, output_path) in enumerate(pending_files, start=1)
    ]
    batches = split_batches(batch_items, args.batch_size)
    log(
        f"将待处理文件拆为 {len(batches)} 批，每批最多 {args.batch_size} 个；"
        f"上传并发数 {args.upload_workers}"
    )

    succeeded = 0
    failed = 0
    for batch_index, items in enumerate(batches, start=1):
        log(f"[提交批次 {batch_index}/{len(batches)}] {len(items)} 个文件")
        try:
            submitted_batch, upload_failures = submit_batch(
                items, api_key, args.upload_workers
            )
        except Exception as error:
            for item in items:
                write_error(item.error_path, error)
            log(f"  [ERR] 批次提交失败: {error}")
            log("检测到批次级错误，停止提交；修复后重新运行会跳过已有 Markdown。")
            raise
        failed += upload_failures
        if not submitted_batch.items:
            log(f"[批次 {batch_index}/{len(batches)} 完成] 本批文件全部上传失败")
            continue

        log(
            f"[收取批次 {batch_index}/{len(batches)}] "
            f"batch_id={submitted_batch.batch_id}，"
            f"等待 {len(submitted_batch.items)} 个已上传文件"
        )
        try:
            batch_succeeded, batch_failed = collect_batch_results(
                submitted_batch,
                api_key,
                args.poll_interval,
                args.poll_timeout,
                args.download_workers,
            )
        except Exception as error:
            for item in submitted_batch.items:
                if not item.output_path.exists():
                    write_error(item.error_path, error)
            log(f"  [ERR] 批次结果收取失败: {error}")
            log("检测到批次级错误，停止收取；修复后重新运行会跳过已有 Markdown。")
            raise
        succeeded += batch_succeeded
        failed += batch_failed
        log(
            f"[批次 {batch_index}/{len(batches)} 完成] "
            f"成功 {batch_succeeded}，失败 {upload_failures + batch_failed}；"
            "开始下一批"
        )

    return RunSummary(len(pdf_files), succeeded, failed, skipped)


def run_cli(args: argparse.Namespace) -> int:
    """运行已解析的命令行参数，并在有失败文件时返回非零状态。"""
    try:
        summary = run(args)
    except KeyboardInterrupt:
        log("用户中断；已完成的 Markdown 可在下次运行时自动跳过。")
        return 130
    except Exception as error:
        log(f"脚本异常退出: {error}")
        return 1

    log(
        f"处理完毕: 共 {summary.total}，成功 {summary.succeeded}，"
        f"失败 {summary.failed}，跳过 {summary.skipped}"
    )
    return 1 if summary.failed else 0


def main_for_collection(
    argv: list[str] | None = None,
    *,
    collection_name: str,
    windows_source_dir: Path,
    wsl_source_dir: Path,
    default_output_dir: Path,
) -> int:
    """使用共享 MinerU 流程运行一个指定刊物的数据集。"""
    args = build_parser(
        collection_name=collection_name,
        windows_source_dir=windows_source_dir,
        wsl_source_dir=wsl_source_dir,
        default_output_dir=default_output_dir,
    ).parse_args(argv)
    return run_cli(args)


def main(argv: list[str] | None = None) -> int:
    """运行《男生女生（金版）》命令行入口。"""
    return main_for_collection(
        argv,
        collection_name="《男生女生（金版）》",
        windows_source_dir=WINDOWS_SOURCE_DIR,
        wsl_source_dir=WSL_SOURCE_DIR,
        default_output_dir=DEFAULT_OUTPUT_DIR,
    )


if __name__ == "__main__":
    sys.exit(main())
