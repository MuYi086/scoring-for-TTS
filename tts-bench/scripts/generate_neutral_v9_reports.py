#!/usr/bin/env python3
"""从 Task 9 V9 受限公共评测原始结果生成中文报告。"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from public_evaluation_v9 import PUBLIC_METRICS, read_jsonl  # noqa: E402


DEFAULT_REPORTS = PROJECT_ROOT / "longAudioTestV9" / "评测结果"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md",
    "delivery": "音频交付与文本一致性_V9自动检查报告.md",
}
ROLE_ORDER = {"旁白": 0, "布罗迪": 1, "我": 2, "布罗迪姐姐": 3, "教授": 4}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True, help="已完成的公共 V9 原始结果目录。")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    return parser.parse_args()


def dense_ranks(values: dict[str, float]) -> dict[str, int]:
    """对越低越好的 CER 计算并列密集名次。"""

    result: dict[str, int] = {}
    rank = 0
    previous: float | None = None
    for model, value in sorted(values.items(), key=lambda item: (item[1], item[0].casefold())):
        if previous is None or value != previous:
            rank += 1
            previous = value
        result[model] = rank
    return result


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("无法计算空集合均值")
    return sum(values) / len(values)


def load_results(results_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_jsonl(results_dir / "per_audio.jsonl")
    try:
        metadata = json.loads((results_dir / "run_metadata.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到原始结果：{results_dir / 'run_metadata.json'}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("run_metadata.json 顶层必须是对象")
    return rows, metadata


def validate_results(rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    """拒绝把不完整、越界或失败的原始结果渲染成正式报告。"""

    config = metadata.get("config", {})
    if metadata.get("schema_version") != "9.0" or config.get("schema_version") != "9.0":
        raise ValueError("原始结果不是冻结的 V9 配置")
    if metadata.get("evaluation_profile") != "public-task-restricted":
        raise ValueError("原始结果不是公共评测受限入口产生的结果")
    if tuple(metadata.get("long_audio_metrics", ())) != PUBLIC_METRICS:
        raise ValueError("原始结果包含非公共长音频指标")
    if metadata.get("cross_metric_weighted_score") is not False:
        raise ValueError("公共评测不得生成跨指标综合分")
    expected_count = int(config.get("expected_model_count", -1)) + int(
        config.get("expected_reference_count", -1)
    )
    if len(rows) != expected_count:
        raise ValueError(f"per_audio.jsonl 数量不正确：实际 {len(rows)}，应为 {expected_count}")
    if any(row.get("errors") for row in rows):
        raise ValueError("原始结果仍有逐项错误，拒绝生成看似完整的正式报告")
    coverage = metadata.get("coverage", {})
    for metric in PUBLIC_METRICS:
        item = coverage.get(metric, {})
        if item.get("complete") != item.get("expected") or item.get("expected") != len(rows):
            raise ValueError(f"{metric} 覆盖不完整：{item}")
    if {row.get("role") for row in rows if row.get("kind") == "reference"} != set(ROLE_ORDER):
        raise ValueError("原始参考角色集合与 V9 冻结配置不一致")


def synthesis_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["kind"] == "synthesis"]


def reference_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["kind"] == "reference"]


def cer(row: dict[str, Any], metric: str) -> float:
    return float(row["metrics"][metric]["cer"])


def error_locations(reference: str, hypothesis: str, limit: int = 80) -> list[str]:
    """输出可复核的规范化文本差异位置，避免在报告中复制整段转写。"""

    matcher = difflib.SequenceMatcher(a=reference, b=hypothesis, autojunk=False)
    locations: list[str] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        reference_part = reference[left_start:left_end] or "∅"
        hypothesis_part = hypothesis[right_start:right_end] or "∅"
        locations.append(
            f"{tag}：参考[{left_start}:{left_end}]「{reference_part}」→ 转写[{right_start}:{right_end}]「{hypothesis_part}」"
        )
        if len(locations) >= limit:
            locations.append(f"其余差异已省略；完整转写见 `per_audio.jsonl`。")
            break
    return locations or ["无差异。"]


def render_cer_report(rows: list[dict[str, Any]], metadata: dict[str, Any], link: str) -> str:
    syntheses = synthesis_rows(rows)
    references = reference_rows(rows)
    sense_values = {row["model_id"]: cer(row, "sensevoice_cer") for row in syntheses}
    whisper_values = {row["model_id"]: cer(row, "whisper_cer") for row in syntheses}
    sense_ranks = dense_ranks(sense_values)
    whisper_ranks = dense_ranks(whisper_values)
    source = metadata["config"]["source"]
    sense_best = min(sense_values.values())
    whisper_best = min(whisper_values.values())
    sense_leaders = [model for model, value in sense_values.items() if value == sense_best]
    whisper_leaders = [model for model, value in whisper_values.items() if value == whisper_best]
    lines = [
        "# SenseVoice CER 与 Whisper-large-v3-turbo CER V9 评价报告",
        "",
        "## 结论摘要",
        "",
        "CER（字符错误率）仅衡量台词文本保真，越低越好；它不评价音色、情绪、表演或自然度。"
        "SenseVoice 与 Whisper-large-v3-turbo 是独立后端，分别排名，绝不平均成总分。",
        "",
        f"- SenseVoice 最低 CER：**{sense_best:.4f}**，对应 **{'、'.join(sorted(sense_leaders, key=str.casefold))}**。",
        f"- Whisper-large-v3-turbo 最低 CER：**{whisper_best:.4f}**，对应 **{'、'.join(sorted(whisper_leaders, key=str.casefold))}**。",
        "",
        "## 模型全文 CER",
        "",
        "| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper-large-v3-turbo CER ↓ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        delivery = row["metrics"]["audio_delivery"]
        model = row["model_id"]
        lines.append(
            f"| {model} | {delivery['format']['duration_seconds']:.2f} | {sense_values[model]:.4f} | "
            f"{sense_ranks[model]} | {whisper_values[model]:.4f} | {whisper_ranks[model]} |"
        )
    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "参考音频与完整有声书的文本、混音和时长不同，以下结果仅用于观察 ASR 偏差，不参与模型名次。",
            "",
            "| 角色 | SenseVoice CER ↓ | Whisper-large-v3-turbo CER ↓ |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(f"| {row['role']} | {cer(row, 'sensevoice_cer'):.4f} | {cer(row, 'whisper_cer'):.4f} |")
    lines.extend(
        [
            "",
            "## 台词边界与错误位置",
            "",
            f"成品按 `longAudioTestV9/ai_deal.json` 的 **{source['dialogue_count']} 段**实际台词合成；"
            f"全文 CER 固定使用其 **{source['normalized_character_count']}** 个 `zh-v1` 规范化字符。"
            f"`text.md` 有 {source['raw_text_normalized_character_count']} 个规范化字符，{source['raw_text_relation']}",
            "",
            "以下位置基于规范化文本差异，用于定位复核；完整的两后端转写、连续 30 秒分段和原始 CER 均保存在原始结果。",
        ]
    )
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        lines.extend(["", f"### {row['model_id']}", ""])
        for metric, label in (
            ("sensevoice_cer", "SenseVoice"),
            ("whisper_cer", "Whisper-large-v3-turbo"),
        ):
            value = row["metrics"][metric]
            lines.append(f"- {label}（CER {value['cer']:.4f}）：")
            lines.extend(f"  - {item}" for item in error_locations(value["reference_normalized"], value["hypothesis_normalized"]))
    lines.extend(
        [
            "",
            "## 可复核证据",
            "",
            f"- 完整转写、分段和逐条错误：[`per_audio.jsonl`]({link}/per_audio.jsonl)",
            f"- 冻结配置、环境、权重与覆盖：[`run_metadata.json`]({link}/run_metadata.json)",
            "",
        ]
    )
    return "\n".join(lines)


def delivery_summary(row: dict[str, Any]) -> tuple[str, str, str]:
    delivery = row["metrics"]["audio_delivery"]
    silence = delivery["silence"]
    interior = [
        item
        for item in silence["runs"]
        if item["start_seconds"] > 0 and item["end_seconds"] < delivery["format"]["duration_seconds"]
    ]
    return (
        f"{delivery['format']['sample_rate_hz']} Hz / {delivery['format']['channels']} ch / {delivery['format']['subtype']}",
        f"{delivery['clipping']['ratio']:.8f}（阈值 {delivery['clipping']['measurement_threshold']:.3f}）",
        f"首 {silence['leading_seconds']:.2f}s；尾 {silence['trailing_seconds']:.2f}s；中间 {len(interior)} 段",
    )


def render_delivery_report(rows: list[dict[str, Any]], metadata: dict[str, Any], link: str) -> str:
    syntheses = synthesis_rows(rows)
    checks = metadata["unexecuted_checks"]
    source = metadata["config"]["source"]
    lines = [
        "# 音频交付与文本一致性 V9 自动检查报告",
        "",
        "## 结论边界",
        "",
        "本任务没有冻结目标发布渠道、格式契约或响度阈值。因此本报告只记录可解码性、文件哈希、"
        "格式、采样峰值、样本削波比例、直流偏置和静音位置；**不判定通过、失败或优劣**。"
        "采样峰值不是最大真峰值，响度与最大真峰值因缺少目标渠道规范而未执行。",
        "",
        "## 成品交付原始测量",
        "",
        "| 模型 | 格式 | 时长（秒） | 采样峰值（dBFS） | 样本削波比例 | 直流偏置 | 静音观测 |",
        "| --- | --- | ---: | ---: | --- | ---: | --- |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        delivery = row["metrics"]["audio_delivery"]
        format_value, clipping, silence = delivery_summary(row)
        lines.append(
            f"| {row['model_id']} | {format_value} | {delivery['format']['duration_seconds']:.2f} | "
            f"{delivery['sample_peak_dbfs']:.2f} | {clipping} | {delivery['dc_offset']:.8f} | {silence} |"
        )
    lines.extend(
        [
            "",
            "## 静音区间与异常位置",
            "",
            "下列区间以冻结的 100 ms RMS 窗和 -60 dBFS 静音阈值观测，持续至少 0.5 秒；"
            "它们不是未冻结交付标准下的自动失败判定。",
        ]
    )
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        runs = row["metrics"]["audio_delivery"]["silence"]["runs"]
        lines.append("")
        lines.append(f"### {row['model_id']}")
        if runs:
            for item in runs:
                lines.append(
                    f"- {item['start_seconds']:.2f}–{item['end_seconds']:.2f} 秒（{item['duration_seconds']:.2f} 秒）"
                )
        else:
            lines.append("- 未观测到持续至少 0.5 秒的静音区间。")
    lines.extend(
        [
            "",
            "## 台词与结构完整性",
            "",
            f"全文以 `longAudioTestV9/ai_deal.json` 的 {source['dialogue_count']} 段、"
            f"{source['normalized_character_count']} 个规范化字符为唯一参考；"
            "SenseVoice 与 Whisper-large-v3-turbo 的全文 CER、完整转写和错误位置见同批 CER 报告。"
            "两个后端均按固定连续、不重叠的 30 秒分段顺序转写。",
            "",
            "## 未执行的配置项",
            "",
            f"- 强制对齐与读法合规：**未执行**。{checks['forced_alignment']['reason']}",
            f"- 角色路由告警：**未执行**。{checks['role_routing']['reason']}",
            "",
            "## 可复核证据",
            "",
            f"- 逐音频格式、哈希、静音、两后端转写：[`per_audio.jsonl`]({link}/per_audio.jsonl)",
            f"- 测量参数、未冻结契约与环境快照：[`run_metadata.json`]({link}/run_metadata.json)",
            "",
        ]
    )
    return "\n".join(lines)


def build_reports(results_dir: Path, results_link: str | None = None) -> dict[str, str]:
    rows, metadata = load_results(results_dir)
    validate_results(rows, metadata)
    link = results_link or results_dir.name
    return {
        "cer": render_cer_report(rows, metadata, link),
        "delivery": render_delivery_report(rows, metadata, link),
    }


def main() -> int:
    args = parse_args()
    reports = build_reports(args.results_dir)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    link = Path(os.path.relpath(args.results_dir.resolve(), start=args.reports_dir.resolve())).as_posix()
    reports = build_reports(args.results_dir, link)
    for report_id, content in reports.items():
        path = args.reports_dir / REPORT_FILENAMES[report_id]
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"V9 公共报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
