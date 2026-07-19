#!/usr/bin/env python3
"""Task 4 V3 原始结果生成三份双后端中文评价报告。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_neutral_v2_reports import (
    dense_ranks,
    format_models,
    group_audio,
    leaders,
    mean,
    metric_value,
    model_metric_means,
    pearson,
    read_jsonl,
    validate_results,
)


DEFAULT_RESULTS = PROJECT_ROOT / "tts-bench" / "reports" / "task4-2026-07-19-v3-r02"
DEFAULT_REPORTS = PROJECT_ROOT / "tts-bench" / "reports"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper_CER_V3评价报告.md",
    "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V3评价报告.md",
    "quality": "UTMOSv2&NISQA_V3评价报告.md",
}
ROLE_ORDER = {"旁白": 0, "小公主": 1, "三皇子": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    return parser.parse_args()


def rank_correlation(
    first: dict[str, int],
    second: dict[str, int],
) -> float:
    """计算两组稠密名次的 Pearson 相关（并列名次下的 Spearman 形式）。"""

    models = sorted(first, key=str.casefold)
    if set(models) != set(second):
        raise ValueError("两个后端的模型集合不一致")
    return pearson(
        [float(first[model]) for model in models],
        [float(second[model]) for model in models],
    )


def sorted_syntheses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按模型和 V3 角色固定顺序排列。"""

    unknown = {row["role"] for row in rows} - set(ROLE_ORDER)
    if unknown:
        raise ValueError(f"V3 结果包含未知角色：{sorted(unknown)}")
    return sorted(rows, key=lambda row: (row["model_id"].casefold(), ROLE_ORDER[row["role"]]))


def render_cer_report(audio_rows: list[dict[str, Any]], results_link: str) -> str:
    references, syntheses, _ = group_audio(audio_rows)
    metrics = ("sensevoice_cer", "whisper_cer")
    means = {metric: model_metric_means(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], higher_is_better=False) for metric in metrics}
    sense_leaders, sense_best = leaders(means["sensevoice_cer"], False)
    whisper_leaders, whisper_best = leaders(means["whisper_cer"], False)
    correlation = rank_correlation(ranks["sensevoice_cer"], ranks["whisper_cer"])
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references) for metric in metrics
    }
    largest_gap = max(
        syntheses,
        key=lambda row: abs(metric_value(row, "sensevoice_cer") - metric_value(row, "whisper_cer")),
    )

    lines = [
        "# SenseVoice CER 与 Whisper CER V3 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次以两个独立自动语音识别后端评价 8 个模型、3 个角色的 24 条 V3 克隆音频，"
        "并以 3 条原始参考音频检查后端自身偏差。27 条音频在两个后端均完整返回；"
        "CER（字符错误率）越低越好。",
        "",
        f"- SenseVoice 三角色宏平均最低为 **{sense_best:.4f}**，对应{format_models(sense_leaders)}。",
        f"- Whisper 三角色宏平均最低为 **{whisper_best:.4f}**，对应{format_models(whisper_leaders)}。",
        f"- 两组稠密名次的相关为 **{correlation:.3f}**。报告保留两套独立名次，不将 CER 简单平均为总分。",
        f"- 逐样本后端差异最大的是 **{largest_gap['model_id']} / {largest_gap['role']}**，"
        f"绝对差为 **{abs(metric_value(largest_gap, 'sensevoice_cer') - metric_value(largest_gap, 'whisper_cer')):.4f}**。",
        "",
        "## 模型宏平均",
        "",
        "| 模型 | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["sensevoice_cer"], key=str.casefold):
        lines.append(
            f"| {model} | {means['sensevoice_cer'][model]:.4f} | {ranks['sensevoice_cer'][model]} | "
            f"{means['whisper_cer'][model]:.4f} | {ranks['whisper_cer'][model]} |"
        )

    lines.extend(["", "## 原始参考音频基线", "", "| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |", "| --- | ---: | ---: |"])
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {metric_value(row, 'sensevoice_cer'):.4f} | {metric_value(row, 'whisper_cer'):.4f} |"
        )
    lines.append(
        f"| 三角色宏平均 | **{reference_means['sensevoice_cer']:.4f}** | **{reference_means['whisper_cer']:.4f}** |"
    )

    lines.extend(["", "## 逐角色结果", "", "| 模型 | 角色 | SenseVoice CER ↓ | Whisper CER ↓ |", "| --- | --- | ---: | ---: |"])
    for row in sorted_syntheses(syntheses):
        lines.append(
            f"| {row['model_id']} | {row['role']} | {metric_value(row, 'sensevoice_cer'):.4f} | {metric_value(row, 'whisper_cer'):.4f} |"
        )

    sense_text = largest_gap["metrics"]["sensevoice_cer"]["hypothesis_raw"]
    whisper_text = largest_gap["metrics"]["whisper_cer"]["hypothesis_raw"]
    lines.extend(
        [
            "",
            "## 后端差异与边界",
            "",
            f"最大差异样本的 SenseVoice 转写为 `{sense_text}`，Whisper 转写为 `{whisper_text}`。"
            "两侧统一使用 `zh-v1`：Unicode NFKC（兼容等价规范化）、小写化、删除空白和标点；"
            "不做繁简转换、数字读法归一或同音字容错。",
            "",
            "CER 同时受 TTS 可懂度和 ASR 语言模型偏差影响；本批仅三个短句，不能代替更大文本集与人工复核。",
            "",
            "## 可追溯证据",
            "",
            f"- 逐音频原始结果：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 完整覆盖与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)",
            "- 评测清单：[`task4-2026-07-19-v3.jsonl`](../manifests/task4-2026-07-19-v3.jsonl)",
            "",
        ]
    )
    return "\n".join(lines)


def render_similarity_report(
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    results_link: str,
) -> str:
    metrics = ("wavlm_sim", "speechbrain_ecapa_sim")
    means = {metric: model_metric_means(similarity_rows, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], higher_is_better=True) for metric in metrics}
    wavlm_leaders, wavlm_best = leaders(means["wavlm_sim"], True)
    ecapa_leaders, ecapa_best = leaders(means["speechbrain_ecapa_sim"], True)
    correlation = rank_correlation(ranks["wavlm_sim"], ranks["speechbrain_ecapa_sim"])
    controls: dict[str, dict[str, list[float]]] = {metric: defaultdict(list) for metric in metrics}
    for row in calibration_rows:
        for metric in metrics:
            controls[metric][row["control_type"]].append(metric_value(row, metric))

    lines = [
        "# WavLM SIM 与 SpeechBrain ECAPA SIM V3 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次将 24 条 V3 克隆音频逐一与同角色原始参考音频比较，并用两个独立说话人表征后端计算余弦相似度。"
        "另加入 3 个同说话人前后半段对照和 3 个跨角色原始音频对照，两个后端均完成 30/30 对；分数越高越好。",
        "",
        f"- WavLM 三角色宏平均最高为 **{wavlm_best:.4f}**，对应{format_models(wavlm_leaders)}。",
        f"- SpeechBrain ECAPA 三角色宏平均最高为 **{ecapa_best:.4f}**，对应{format_models(ecapa_leaders)}。",
        f"- 两组稠密名次的相关为 **{correlation:.3f}**；两种嵌入空间不共用量纲，不跨后端平均。",
        "",
        "## 模型宏平均",
        "",
        "| 模型 | WavLM SIM ↑ | 名次 | SpeechBrain ECAPA SIM ↑ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["wavlm_sim"], key=str.casefold):
        lines.append(
            f"| {model} | {means['wavlm_sim'][model]:.4f} | {ranks['wavlm_sim'][model]} | "
            f"{means['speechbrain_ecapa_sim'][model]:.4f} | {ranks['speechbrain_ecapa_sim'][model]} |"
        )

    lines.extend(["", "## 逐角色结果", "", "| 模型 | 角色 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |", "| --- | --- | ---: | ---: |"])
    for row in sorted_syntheses(similarity_rows):
        lines.append(
            f"| {row['model_id']} | {row['role']} | {metric_value(row, 'wavlm_sim'):.4f} | {metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )

    lines.extend(["", "## 原始音频校准对照", "", "| 对照 | 类型 | WavLM SIM | SpeechBrain ECAPA SIM |", "| --- | --- | ---: | ---: |"])
    for row in calibration_rows:
        lines.append(
            f"| {row['label']} | {row['control_type']} | {metric_value(row, 'wavlm_sim'):.4f} | {metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 校准解读与边界",
            "",
            f"WavLM 的同说话人分段均值为 **{mean(controls['wavlm_sim']['same_speaker_split_half']):.4f}**，"
            f"跨角色均值为 **{mean(controls['wavlm_sim']['different_speaker_reference_pair']):.4f}**；"
            f"ECAPA 对应为 **{mean(controls['speechbrain_ecapa_sim']['same_speaker_split_half']):.4f}** 和 "
            f"**{mean(controls['speechbrain_ecapa_sim']['different_speaker_reference_pair']):.4f}**。",
            "",
            "本批每个角色仅有一条参考音频；同说话人正例来自同一录音切分，跨角色负例仅三对。"
            "因此不将 SIM 解释为‘同一人概率’，也不设置未经更大校准集确认的通过阈值。",
            "",
            "## 可追溯证据",
            "",
            f"- 24 个克隆对：[`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- 6 个校准对：[`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- 完整覆盖与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)",
            "",
        ]
    )
    return "\n".join(lines)


def render_quality_report(
    audio_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    results_link: str,
) -> str:
    references, syntheses, references_by_case = group_audio(audio_rows)
    metrics = ("utmosv2", "nisqa")
    means = {metric: model_metric_means(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], higher_is_better=True) for metric in metrics}
    reference_means = {metric: mean(metric_value(row, metric) for row in references) for metric in metrics}
    deltas: dict[str, dict[str, float]] = {}
    for metric in metrics:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in syntheses:
            grouped[row["model_id"]].append(
                metric_value(row, metric) - metric_value(references_by_case[row["case_id"]], metric)
            )
        deltas[metric] = {model: mean(values) for model, values in grouped.items()}
    utmos_leaders, utmos_best = leaders(means["utmosv2"], True)
    nisqa_leaders, nisqa_best = leaders(means["nisqa"], True)
    correlation = rank_correlation(ranks["utmosv2"], ranks["nisqa"])
    utmos_config = metadata["config"]["utmosv2"]

    lines = [
        "# UTMOSv2 与 NISQA V3 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次使用 UTMOSv2 和 NISQA-TTS 两个无参考自然度预测器，评价 24 条 V3 克隆音频和 3 条原始参考音频。"
        "两个后端均完成 27/27，预测 MOS 越高越好。",
        "",
        f"- UTMOSv2 三角色宏平均最高为 **{utmos_best:.4f}**，对应{format_models(utmos_leaders)}。",
        f"- NISQA-TTS 三角色宏平均最高为 **{nisqa_best:.4f}**，对应{format_models(nisqa_leaders)}。",
        f"- 两组稠密名次的相关为 **{correlation:.3f}**；两后端保持独立名次，不跨量纲加权。",
        f"- 原始参考音频宏平均为 UTMOSv2 **{reference_means['utmosv2']:.4f}**、NISQA-TTS **{reference_means['nisqa']:.4f}**。",
        "",
        "## 模型宏平均与同角色基线差",
        "",
        "| 模型 | UTMOSv2 ↑ | 名次 | 相对原始 | NISQA-TTS ↑ | 名次 | 相对原始 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["utmosv2"], key=str.casefold):
        lines.append(
            f"| {model} | {means['utmosv2'][model]:.4f} | {ranks['utmosv2'][model]} | {deltas['utmosv2'][model]:+.4f} | "
            f"{means['nisqa'][model]:.4f} | {ranks['nisqa'][model]} | {deltas['nisqa'][model]:+.4f} |"
        )

    lines.extend(["", "## 原始参考音频基线", "", "| 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |", "| --- | ---: | ---: |"])
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(f"| {row['role']} | {metric_value(row, 'utmosv2'):.4f} | {metric_value(row, 'nisqa'):.4f} |")
    lines.append(f"| 三角色宏平均 | **{reference_means['utmosv2']:.4f}** | **{reference_means['nisqa']:.4f}** |")

    lines.extend(["", "## 逐角色结果", "", "| 模型 | 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |", "| --- | --- | ---: | ---: |"])
    for row in sorted_syntheses(syntheses):
        lines.append(f"| {row['model_id']} | {row['role']} | {metric_value(row, 'utmosv2'):.4f} | {metric_value(row, 'nisqa'):.4f} |")

    lines.extend(
        [
            "",
            "## 可复现策略与边界",
            "",
            f"UTMOSv2 固定随机种子 `{utmos_config['inference_seed']}`，每条音频执行 "
            f"{utmos_config['num_repetitions']} 次裁剪并取模型内置平均，静音移除为 `{str(utmos_config['remove_silent_section']).lower()}`。"
            "NISQA 使用面向合成语音的 `nisqa_tts.tar`（NISQA-TTS v1.0）离线整批推理。",
            "",
            "MOS 预测器没有在本 V3 数据集上用真人评分重新校准，绝对值不等于人工 MOS。"
            "自然度也不表示文本念对、音色相似或角色表演合适；应与双 CER、双 SIM 及人工盲听结合。",
            "",
            "## 可追溯证据",
            "",
            f"- 逐音频原始结果：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 完整覆盖、裁剪参数与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)",
            "",
        ]
    )
    return "\n".join(lines)


def build_reports(results_dir: Path, results_link: str | None = None) -> dict[str, str]:
    audio_rows = read_jsonl(results_dir / "per_audio.jsonl")
    similarity_rows = read_jsonl(results_dir / "speaker_similarity.jsonl")
    calibration_rows = read_jsonl(results_dir / "speaker_calibration.jsonl")
    try:
        metadata = json.loads((results_dir / "run_metadata.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到原始结果：{results_dir / 'run_metadata.json'}") from exc
    validate_results(audio_rows, similarity_rows, calibration_rows, metadata)
    if set(metadata.get("config", {}).get("case_labels", {}).values()) != set(ROLE_ORDER):
        raise ValueError("原始结果不是旁白、小公主、三皇子三角色 V3 矩阵")
    results_link = results_link or results_dir.name
    return {
        "cer": render_cer_report(audio_rows, results_link),
        "sim": render_similarity_report(similarity_rows, calibration_rows, results_link),
        "quality": render_quality_report(audio_rows, metadata, results_link),
    }


def main() -> int:
    args = parse_args()
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    results_link = Path(os.path.relpath(args.results_dir.resolve(), start=args.reports_dir.resolve())).as_posix()
    reports = build_reports(args.results_dir, results_link)
    for report_id, content in reports.items():
        path = args.reports_dir / REPORT_FILENAMES[report_id]
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"V3 报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
