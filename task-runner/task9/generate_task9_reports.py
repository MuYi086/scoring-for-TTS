#!/usr/bin/env python3
"""从 Task 9 原始结果生成公共任务规定的两份 V9 中文报告。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from run_task9_evaluation import PROJECT_ROOT


TASK_DIR = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "longAudioTestV9" / "评测结果"
CER_REPORT_NAME = "SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告.md"
AUTOMATED_REPORT_NAME = "音频交付与文本一致性_V9自动检查报告.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True, help="Task 9 本次原始结果目录")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="两份公共报告输出目录")
    return parser.parse_args(argv)


def escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def format_number(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def load_results(results_dir: Path) -> dict[str, Any]:
    path = results_dir.expanduser().resolve() / "task9_evaluation_results.json"
    try:
        results = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 Task 9 原始结果：{path}: {exc}") from exc
    validate_complete_results(results)
    return results


def validate_complete_results(results: dict[str, Any]) -> None:
    if results.get("schema_version") != "task9-v2" or results.get("version") != "V9":
        raise ValueError("结果不是 Task 9 V9 格式")
    contract = results.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("结果缺少冻结评测契约")
    expected = [item["model_id"] for item in contract.get("models", [])]
    actual = results.get("models", {})
    missing = [model_id for model_id in expected if model_id not in actual]
    if missing:
        raise ValueError("尚未完成全部模型，不能生成公共报告：" + "、".join(missing))
    for model_id in expected:
        record = actual[model_id]
        if record.get("status") != "complete":
            raise ValueError(f"{model_id} 评测未成功完成")
        for metric in ("sensevoice_cer", "whisper_large_v3_turbo_cer"):
            if record.get("metrics", {}).get(metric, {}).get("status") != "complete":
                raise ValueError(f"{model_id} 的 {metric} 未成功完成")


def ranked_models(results: dict[str, Any], metric: str) -> list[dict[str, Any]]:
    models = [
        item
        for item in results["models"].values()
        if item["metrics"][metric]["asr_health"]["ranking_eligible"]
    ]
    return sorted(models, key=lambda item: float(item["metrics"][metric]["cer"]))


def build_cer_report(results: dict[str, Any], results_link: str) -> str:
    contract = results["contract"]
    source = contract["source"]
    segment_manifest = results["inputs"]["segment_manifest"]
    segment_policy = segment_manifest["policy"]
    model_records = results["models"]
    sense_rank = ranked_models(results, "sensevoice_cer")
    whisper_rank = ranked_models(results, "whisper_large_v3_turbo_cer")
    lines = [
        "# SenseVoice CER 与 Whisper-large-v3-turbo CER V9 评价报告",
        "",
        "本报告衡量双 ASR 转写与实际合成台词的差异。全文参考严格为 `longAudioTestV9/text.md` 中实际参与合成、原始顺序固定的文本；未使用不存在的 `ai_deal.json`，也未复用旧 V9 字符统计。",
        "",
        f"- 规范化规则：`{source['normalization_id']}`；参考字符数：`{source['normalized_character_count']}`。",
        f"- 共享分段清单：{len(segment_manifest['segments'])} 段；按旁白参考语速估算，目标片段 `{segment_policy['target_seconds']}` 秒、最大 `{segment_policy['max_segment_seconds']}` 秒。",
        "- ASR 直接读取与最终 WAV 哈希绑定的逐段合成证据；严格汉字 CER 记录字面差异，拼音 CER 仅用于识别同音字造成的假阳性，二者均不等同于人工确认的朗读错误。",
        f"- 原始证据：[task9_evaluation_results.json]({results_link}/task9_evaluation_results.json)。",
        "- 两个后端独立排名，绝不平均为综合分；Whisper 名称完整标注为 Whisper-large-v3-turbo。",
        "",
        "## 双后端逐段文本指标与独立名次",
        "",
        "| 模型 | SenseVoice 严格汉字 CER | SenseVoice 拼音 CER | SenseVoice 健康 / 名次 | Whisper 严格汉字 CER | Whisper 拼音 CER | Whisper 健康 / 名次 |",
        "| --- | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    sense_places = {item["model_id"]: index for index, item in enumerate(sense_rank, start=1)}
    whisper_places = {item["model_id"]: index for index, item in enumerate(whisper_rank, start=1)}
    for record in model_records.values():
        sense_result = record["metrics"]["sensevoice_cer"]
        whisper_result = record["metrics"]["whisper_large_v3_turbo_cer"]
        sense = float(sense_result["cer"])
        whisper = float(whisper_result["cer"])
        sense_health = sense_result["asr_health"]
        whisper_health = whisper_result["asr_health"]
        sense_rank_label = str(sense_places[record["model_id"]]) if record["model_id"] in sense_places else "不排名"
        whisper_rank_label = str(whisper_places[record["model_id"]]) if record["model_id"] in whisper_places else "不排名"
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_cell(record["display_name"]),
                    format_number(sense),
                    format_number(float(sense_result["phonetic_cer"])),
                    escape_cell(f"{sense_health['status']} / {sense_rank_label}"),
                    format_number(whisper),
                    format_number(float(whisper_result["phonetic_cer"])),
                    escape_cell(f"{whisper_health['status']} / {whisper_rank_label}"),
                )
            )
            + " |"
        )
    lines.extend(["", "## 完整转写与字符错误位置", ""])
    backend_labels = (
        ("sensevoice_cer", "SenseVoice"),
        ("whisper_large_v3_turbo_cer", "Whisper-large-v3-turbo"),
    )
    for record in model_records.values():
        lines.extend([f"### {record['display_name']}", ""])
        for metric, label in backend_labels:
            result = record["metrics"][metric]
            lines.extend(
                [
                    f"#### {label}",
                    "",
                    f"- 严格汉字 CER：`{format_number(float(result['strict_character_cer']))}`；字符编辑数：`{result['character_errors']}`。",
                    f"- 拼音 CER：`{format_number(float(result['phonetic_cer']))}`；拼音 token 编辑数：`{result['phonetic_errors']}`。",
                    f"- ASR 健康：`{result['asr_health']['status']}`；不可靠片段：{', '.join(result['asr_health']['unreliable_segment_ids']) or '无'}；该后端{'参与' if result['asr_health']['ranking_eligible'] else '不参与'}名次。",
                    f"- 分段：按冻结合成证据的 {len(result['chunks'])} 个语义段逐段解码；解码参数已保存在原始证据。",
                    "",
                    "完整转写：",
                    "",
                    "```text",
                    result["full_transcription"],
                    "```",
                    "",
                ]
            )
            locations = result["error_locations"]
            if not locations:
                lines.extend(["字符错误位置：无。", ""])
                continue
            lines.extend(
                [
                    "严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：",
                    "",
                    "| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |",
                    "| --- | --- | --- | ---: | --- | ---: | --- |",
                ]
            )
            for error in locations:
                lines.append(
                    "| "
                    + " | ".join(
                        (
                            escape_cell(error.get("segment_id", "")),
                            escape_cell(error.get("classification", "")),
                            escape_cell(error["operation"]),
                            str(error["reference_index"]),
                            escape_cell(error["reference_character"] or "∅"),
                            str(error["hypothesis_index"]),
                            escape_cell(error["hypothesis_character"] or "∅"),
                        )
                    )
                    + " |"
                )
            lines.append("")
    lines.extend(["## 双后端分歧与 ASR 健康门控", ""])
    for record in model_records.values():
        sense = record["metrics"]["sensevoice_cer"]
        whisper = record["metrics"]["whisper_large_v3_turbo_cer"]
        sense_set = {
            (item["operation"], item["reference_index"], item["reference_character"], item["hypothesis_character"])
            for item in sense["error_locations"]
        }
        whisper_set = {
            (item["operation"], item["reference_index"], item["reference_character"], item["hypothesis_character"])
            for item in whisper["error_locations"]
        }
        lines.extend(
            [
                f"### {record['display_name']}",
                "",
                f"- 仅 SenseVoice 报告的错误：{len(sense_set - whisper_set)} 项。",
                f"- 仅 Whisper-large-v3-turbo 报告的错误：{len(whisper_set - sense_set)} 项。",
                f"- 两后端共同报告的错误：{len(sense_set & whisper_set)} 项。",
                f"- 同段转写共识健康：`{record['asr_consensus_health']['status']}`；分歧过大的片段：{', '.join(record['asr_consensus_health']['unreliable_segment_ids']) or '无'}。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def format_silence_regions(regions: list[dict[str, float]]) -> str:
    if not regions:
        return "无"
    return "；".join(
        f"{region['start_seconds']:.3f}s–{region['end_seconds']:.3f}s" for region in regions
    )


def build_automated_report(results: dict[str, Any], results_link: str) -> str:
    contract = results["contract"]
    source = contract["source"]
    measurement = contract["audio_measurement"]
    segment_manifest = results["inputs"]["segment_manifest"]
    segment_policy = segment_manifest["policy"]
    lines = [
        "# 音频交付与文本一致性 V9 自动检查报告",
        "",
        "本报告覆盖音频可解码性、格式、哈希、采样测量与双 ASR 全文一致性。它不对音色贴合、自然度、情绪或长时间听觉疲劳作自动评分。",
        "",
        f"- 唯一全文参考：`{source['text_path']}`，规范化字符数 `{source['normalized_character_count']}`。",
        f"- 原始证据：[task9_evaluation_results.json]({results_link}/task9_evaluation_results.json)。",
        f"- 交付契约状态：`{measurement['delivery_contract_status']}`。{measurement['delivery_contract_note']}",
        "",
        "## 音频交付原始测量",
        "",
        "| 模型 | 解码 | SHA-256 | 格式 / 位深 | 采样率 | 声道 | 时长（秒） | 削波占比 | 最大采样峰值 dBFS | DC 偏置 | 前导 / 尾部静音（秒） |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in results["models"].values():
        audio = record["audio_delivery"]
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_cell(record["display_name"]),
                    escape_cell(audio["decode_status"]),
                    f"`{audio['sha256']}`",
                    escape_cell(f"{audio['format']} / {audio['subtype']}"),
                    str(audio["sample_rate_hz"]),
                    str(audio["channels"]),
                    format_number(float(audio["duration_seconds"]), 3),
                    format_number(float(audio["clipping_ratio"]), 8),
                    format_number(float(audio["max_sample_peak_dbfs"]), 3),
                    format_number(float(audio["dc_offset"]), 8),
                    f"{audio['leading_silence_seconds']:.3f} / {audio['trailing_silence_seconds']:.3f}",
                )
            )
            + " |"
        )
    lines.extend(["", "长静音位置（仅测量，不判定异常）：", ""])
    for record in results["models"].values():
        audio = record["audio_delivery"]
        lines.append(f"- {record['display_name']}：{format_silence_regions(audio['long_silence_regions'])}。")
    lines.extend(["", "## 台词与结构完整性", ""])
    lines.extend(
        [
            "| 模型 | SenseVoice 严格 / 拼音 CER | SenseVoice 健康 | Whisper 严格 / 拼音 CER | Whisper 健康 | 全文转写记录 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in results["models"].values():
        sense = record["metrics"]["sensevoice_cer"]
        whisper = record["metrics"]["whisper_large_v3_turbo_cer"]
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_cell(record["display_name"]),
                    escape_cell(f"{sense['strict_character_cer']:.6f} / {sense['phonetic_cer']:.6f}"),
                    escape_cell(sense["asr_health"]["status"]),
                    escape_cell(f"{whisper['strict_character_cer']:.6f} / {whisper['phonetic_cer']:.6f}"),
                    escape_cell(whisper["asr_health"]["status"]),
                    "见 CER 报告及原始 JSON",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "全文覆盖、缺失、插入、重复和顺序风险均以双 ASR 的逐段原始转写及其字符差异呈现。严格汉字 CER、拼音 CER 和 ASR 健康状态均不代表音频质量、角色表现或人工确认的朗读错误。",
            "",
            "## 共享分段与拼接条件",
            "",
            f"两模型使用同一份冻结清单，共 `{len(segment_manifest['segments'])}` 段；清单 SHA-256 为 `{results['inputs']['segment_manifest_sha256']}`。",
            "",
            f"- 参考语速：{segment_manifest['reference_speech_rate']['characters_per_second']:.3f} 个规范化字符/秒。",
            f"- 时长预算：目标 {segment_policy['target_seconds']} 秒，最大 {segment_policy['max_segment_seconds']} 秒。",
            "- 边界停顿：强制切分 250ms、句末 500ms、段落 750ms；最后一段不额外插入静音。",
            f"- 上下文策略：{segment_policy['context_policy']}",
            "",
            "## 文本时间与读法合规",
            "",
            f"{contract['not_executed']['forced_alignment']}",
            "",
            "## 角色路由告警（非音色评分）",
            "",
            f"{contract['not_executed']['role_routing']}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(results_dir: Path, reports_dir: Path) -> tuple[Path, Path]:
    results = load_results(results_dir)
    reports_root = reports_dir.expanduser().resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    results_link = Path(os.path.relpath(results_dir.expanduser().resolve(), start=reports_root)).as_posix()
    cer_path = reports_root / CER_REPORT_NAME
    automated_path = reports_root / AUTOMATED_REPORT_NAME
    cer_path.write_text(build_cer_report(results, results_link), encoding="utf-8")
    automated_path.write_text(build_automated_report(results, results_link), encoding="utf-8")
    return cer_path, automated_path


def main() -> int:
    args = parse_args()
    try:
        cer_path, automated_path = write_reports(args.results_dir, args.reports_dir)
    except ValueError as error:
        print(f"Task 9 报告生成失败：{error}", file=sys.stderr)
        return 2
    print(cer_path)
    print(automated_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
