#!/usr/bin/env python3
"""从 Task 5 V4 原始结果生成三份双后端中文评价报告。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_RESULTS = PROJECT_ROOT / "longAudioTest" / "评测结果" / "task5-v4-raw"
DEFAULT_REPORTS = PROJECT_ROOT / "longAudioTest" / "评测结果"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper_CER_V4评价报告.md",
    "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V4评价报告.md",
    "quality": "UTMOSv2&NISQA_V4评价报告.md",
}
ROLE_ORDER = {"旁白": 0, "辰南": 1, "见习魔法师": 2, "女侍卫": 3, "侍卫": 4, "小公主": 5}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_neutral_v2_reports import (  # noqa: E402
    dense_ranks,
    format_models,
    leaders,
    mean,
    pearson,
    read_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--model-id",
        help="只生成一个已完成模型的独立报告；省略时要求全部模型完成并生成三份最终报告。",
    )
    return parser.parse_args()


def metric_value(row: dict[str, Any], metric: str) -> float:
    value = row["metrics"][metric]
    if isinstance(value, dict):
        if "cer" in value:
            return float(value["cer"])
        if "mean" in value:
            return float(value["mean"])
    return float(value)


def rank_correlation(first: dict[str, int], second: dict[str, int]) -> float:
    models = sorted(first, key=str.casefold)
    if set(models) != set(second):
        raise ValueError("两个后端的模型集合不一致")
    return pearson(
        [float(first[model]) for model in models],
        [float(second[model]) for model in models],
    )


def model_values(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    return {row["model_id"]: metric_value(row, metric) for row in rows}


def model_role_means(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["model_id"]].append(metric_value(row, metric))
    return {model: mean(values) for model, values in grouped.items()}


def control_means(
    rows: list[dict[str, Any]], metric: str
) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["control_type"]].append(metric_value(row, metric))
    return {control_type: mean(values) for control_type, values in grouped.items()}


def validate_results(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    if len(audio_rows) != 13:
        raise ValueError(f"per_audio.jsonl 应有 13 条，实际 {len(audio_rows)} 条")
    if sum(row.get("kind") == "reference" for row in audio_rows) != 6:
        raise ValueError("V4 原始参考音频必须恰好 6 条")
    if sum(row.get("kind") == "synthesis" for row in audio_rows) != 7:
        raise ValueError("V4 模型长音频必须恰好 7 条")
    if len(similarity_rows) != 42:
        raise ValueError(f"speaker_similarity.jsonl 应有 42 条，实际 {len(similarity_rows)} 条")
    if len(calibration_rows) != 21:
        raise ValueError(f"speaker_calibration.jsonl 应有 21 条，实际 {len(calibration_rows)} 条")
    all_rows = [*audio_rows, *similarity_rows, *calibration_rows]
    if any(row.get("errors") for row in all_rows):
        raise ValueError("原始结果仍有逐项错误，拒绝生成看似完整的报告")
    for metric, coverage in metadata.get("coverage", {}).items():
        if coverage["complete"] != coverage["expected"]:
            raise ValueError(f"{metric} 覆盖不完整：{coverage}")
    roles = {row["role"] for row in similarity_rows}
    if roles != set(ROLE_ORDER):
        raise ValueError(f"V4 SIM 角色应为 {sorted(ROLE_ORDER)}，实际 {sorted(roles)}")
    models = {row["model_id"] for row in audio_rows if row["kind"] == "synthesis"}
    if len(models) != 7 or any(
        {row["role"] for row in similarity_rows if row["model_id"] == model} != set(ROLE_ORDER)
        for model in models
    ):
        raise ValueError("V4 双 SIM 不是完整的 7 模型 × 6 角色矩阵")


def validate_model_results(
    model_id: str,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """校验单模型六后端及共享原始音频基线已经完整。"""

    references = [row for row in audio_rows if row.get("kind") == "reference"]
    syntheses = [
        row
        for row in audio_rows
        if row.get("kind") == "synthesis" and row.get("model_id") == model_id
    ]
    model_similarity = [row for row in similarity_rows if row.get("model_id") == model_id]
    if len(references) != 6:
        raise ValueError(f"单模型报告要求 6 条原始参考音频，实际 {len(references)} 条")
    if len(syntheses) != 1:
        raise ValueError(f"找不到唯一模型结果：{model_id}")
    if {row.get("role") for row in model_similarity} != set(ROLE_ORDER):
        raise ValueError(f"{model_id} 的双 SIM 不是完整六角色结果")
    if len(calibration_rows) != 21:
        raise ValueError(f"原始音频校准对应该有 21 条，实际 {len(calibration_rows)} 条")

    audio_metrics = {"sensevoice_cer", "whisper_cer", "utmosv2", "nisqa"}
    similarity_metrics = {"wavlm_sim", "speechbrain_ecapa_sim"}
    relevant_rows = [*references, syntheses[0], *model_similarity, *calibration_rows]
    if any(row.get("errors") for row in relevant_rows):
        raise ValueError(f"{model_id} 或共享原始音频基线仍有逐项错误")
    for row in [*references, syntheses[0]]:
        missing = audio_metrics - set(row.get("metrics", {}))
        if missing:
            raise ValueError(f"{row.get('audio_id')} 缺少后端：{', '.join(sorted(missing))}")
    for row in [*model_similarity, *calibration_rows]:
        missing = similarity_metrics - set(row.get("metrics", {}))
        if missing:
            raise ValueError(f"{row.get('label', row.get('role'))} 缺少后端：{', '.join(sorted(missing))}")
    return references, syntheses[0], model_similarity


def render_model_report(
    model_id: str,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    results_link: str,
) -> str:
    """渲染不跨后端合分的单模型六后端报告。"""

    references, synthesis, model_similarity = validate_model_results(
        model_id,
        audio_rows,
        similarity_rows,
        calibration_rows,
    )
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references)
        for metric in ("sensevoice_cer", "whisper_cer", "utmosv2", "nisqa")
    }
    similarity_means = {
        metric: mean(metric_value(row, metric) for row in model_similarity)
        for metric in ("wavlm_sim", "speechbrain_ecapa_sim")
    }
    controls = {
        metric: control_means(calibration_rows, metric)
        for metric in ("wavlm_sim", "speechbrain_ecapa_sim")
    }
    alignment = synthesis["metrics"]["whisper_cer"].get("alignment_summary", {})
    utmos = synthesis["metrics"]["utmosv2"]
    nisqa = synthesis["metrics"]["nisqa"]

    lines = [
        f"# {model_id} V4 独立评价报告",
        "",
        "## 六后端结果",
        "",
        "本报告只评价这一条模型长音频，并与六条角色原始音频基线或校准对照比较。六个后端保持独立量纲，"
        "不计算跨后端加权总分，也不把未经本批真人标注校准的数值解释为通过阈值。",
        "",
        "| 维度 | 后端 | 模型结果 | 原始音频对照 | 方向 |",
        "| --- | --- | ---: | ---: | --- |",
        f"| 全文可懂度 | SenseVoice CER | {metric_value(synthesis, 'sensevoice_cer'):.4f} | "
        f"六角色宏平均 {reference_means['sensevoice_cer']:.4f} | 越低越好 |",
        f"| 全文可懂度 | Whisper CER | {metric_value(synthesis, 'whisper_cer'):.4f} | "
        f"六角色宏平均 {reference_means['whisper_cer']:.4f} | 越低越好 |",
        f"| 角色音色 | WavLM SIM | {similarity_means['wavlm_sim']:.4f} | "
        f"同人分段 {controls['wavlm_sim']['same_speaker_split_half']:.4f}；"
        f"跨角色 {controls['wavlm_sim']['different_speaker_reference_pair']:.4f} | 越高越好 |",
        f"| 角色音色 | ECAPA SIM | {similarity_means['speechbrain_ecapa_sim']:.4f} | "
        f"同人分段 {controls['speechbrain_ecapa_sim']['same_speaker_split_half']:.4f}；"
        f"跨角色 {controls['speechbrain_ecapa_sim']['different_speaker_reference_pair']:.4f} | 越高越好 |",
        f"| 自然度 | UTMOSv2 | {utmos['mean']:.4f} | 六角色宏平均 "
        f"{reference_means['utmosv2']:.4f} | 越高越好 |",
        f"| 自然度 | NISQA-TTS | {nisqa['mean']:.4f} | 六角色宏平均 "
        f"{reference_means['nisqa']:.4f} | 越高越好 |",
        "",
        "原始参考音频与长音频不是同文本、也不是同混音条件；CER 与自然度对照只用于显示后端在本批原始录音上的锚点，"
        "不能把两者差值直接归因为音色克隆损失。",
        "",
        "## 角色音色明细",
        "",
        "| 角色 | 对齐片段数 | WavLM SIM ↑ | ECAPA SIM ↑ |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in sorted(model_similarity, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {len(row['alignment_excerpts'])} | "
            f"{metric_value(row, 'wavlm_sim'):.4f} | "
            f"{metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 长音频覆盖信息",
            "",
            f"- 音频时长：**{synthesis['audio']['duration_seconds']:.2f} 秒**。",
            f"- Whisper 时间戳块：**{alignment.get('chunk_count', 0)}** 个；精确对齐 "
            f"**{alignment.get('exact_matched_characters', 0)} / "
            f"{alignment.get('expected_characters', 0)}** 个规范化字符，"
            f"对齐率 **{alignment.get('exact_alignment_ratio_to_expected', 0.0):.4f}**。",
            f"- 自然度窗口：UTMOSv2 **{utmos['count']}** 个、NISQA-TTS **{nisqa['count']}** 个；"
            f"每窗 {metadata['config']['quality_sampling']['window_seconds']:.0f} 秒，按全长等距冻结。",
            "",
            "## 解释边界与证据",
            "",
            "双 CER 同时受背景音乐、音效和长音频 ASR 解码影响；双 SIM 使用 Whisper 对齐后的纯角色片段；"
            "双自然度预测器未在本批中文多角色长音频上用真人 MOS 重新校准。正式选择仍应结合人工盲听。",
            "",
            f"- 逐音频结果：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 逐角色片段与双 SIM：[`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- 原始音频校准对：[`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- 配置、版本与覆盖：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "",
        ]
    )
    return "\n".join(lines)


def model_report_filename(model_id: str) -> str:
    safe_model_id = re.sub(r"[^0-9A-Za-z._-]+", "_", model_id).strip("._")
    if not safe_model_id:
        raise ValueError(f"model_id 无法生成安全文件名：{model_id!r}")
    return f"{safe_model_id}_V4评价报告.md"


def render_cer_report(audio_rows: list[dict[str, Any]], results_link: str) -> str:
    references = [row for row in audio_rows if row["kind"] == "reference"]
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    metrics = ("sensevoice_cer", "whisper_cer")
    values = {metric: model_values(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(values[metric], higher_is_better=False) for metric in metrics}
    sense_leaders, sense_best = leaders(values["sensevoice_cer"], False)
    whisper_leaders, whisper_best = leaders(values["whisper_cer"], False)
    correlation = rank_correlation(ranks["sensevoice_cer"], ranks["whisper_cer"])
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references) for metric in metrics
    }
    largest_gap = max(
        syntheses,
        key=lambda row: abs(metric_value(row, "sensevoice_cer") - metric_value(row, "whisper_cer")),
    )

    lines = [
        "# SenseVoice CER 与 Whisper CER V4 评价报告",
        "",
        "## 结论摘要",
        "",
        "- **主要评测什么**：SenseVoice 与 Whisper 是两套独立 ASR（自动语音识别）后端；本报告用 "
        "CER（字符错误率）衡量小说台词是否被完整、正确、清楚地说出，包括错字、漏字和多字，CER 越低越好。",
        "- **对小说有声化的重要度：极高，建议作为第一道生产硬门槛。** 台词错误、漏句或重复会直接改变剧情，"
        "并带来最高的返工定位成本；优先选择两个 CER 都低且结论一致的模型，再进入音色和听感比较。",
        "- **不能代表什么**：CER 不评价角色是否像目标音色、情绪表演或声音自然度；背景音乐、音效和 ASR 偏差也会影响结果。"
        "六条角色原始音频只用于暴露 ASR 后端基线偏差。",
        "",
        f"- SenseVoice 全文 CER 最低为 **{sense_best:.4f}**，对应{format_models(sense_leaders)}。",
        f"- Whisper 全文 CER 最低为 **{whisper_best:.4f}**，对应{format_models(whisper_leaders)}。",
        f"- 两组独立稠密名次相关为 **{correlation:.3f}**；不把两个 CER 简单平均为总分。",
        f"- 两后端差异最大的是 **{largest_gap['model_id']}**，绝对差为 "
        f"**{abs(metric_value(largest_gap, 'sensevoice_cer') - metric_value(largest_gap, 'whisper_cer')):.4f}**。",
        "",
        "## 模型全文结果",
        "",
        "| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        model = row["model_id"]
        lines.append(
            f"| {model} | {row['audio']['duration_seconds']:.2f} | "
            f"{values['sensevoice_cer'][model]:.4f} | {ranks['sensevoice_cer'][model]} | "
            f"{values['whisper_cer'][model]:.4f} | {ranks['whisper_cer'][model]} |"
        )

    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "参考音频与有声书不是同文本，因此不能把两者 CER 数值直接解释为模型相对原始音频的退化幅度。",
            "",
            "| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {metric_value(row, 'sensevoice_cer'):.4f} | "
            f"{metric_value(row, 'whisper_cer'):.4f} |"
        )
    lines.append(
        f"| 六角色宏平均 | **{reference_means['sensevoice_cer']:.4f}** | "
        f"**{reference_means['whisper_cer']:.4f}** |"
    )

    alignment_rows = []
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        summary = row["metrics"]["whisper_cer"].get("alignment_summary", {})
        alignment_rows.append((row["model_id"], summary))
    lines.extend(
        [
            "",
            "## 文本与长音频边界",
            "",
            "目录中的 `text.md` 与 `ai_deal.json` 不是同一段小说：成品开头经双 ASR 抽检与 `ai_deal.json` 一致，"
            "冻结哈希和正文也显示两者不同。因此本报告以 148 段 `dialogue` 的台词顺序拼接为全文 CER 参考；"
            "若误用 `text.md`，CER 会主要反映文本错配。统一规范化仍为 `zh-v1`：Unicode NFKC、"
            "小写化并删除空白和标点，不做繁简、数字读法或同音字等价。",
            "",
            "Whisper 时间戳同时用于后续角色片段定位。下表的精确对齐率只衡量 ASR 文本与冻结台词的精确字符匹配，"
            "不进入 CER，也不与 SenseVoice 分数混合。",
            "",
            "| 模型 | Whisper 时间戳块 | 精确对齐字符 / 参考字符 | 精确对齐率 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for model, summary in alignment_rows:
        lines.append(
            f"| {model} | {summary.get('chunk_count', 0)} | "
            f"{summary.get('exact_matched_characters', 0)} / {summary.get('expected_characters', 0)} | "
            f"{summary.get('exact_alignment_ratio_to_expected', 0.0):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 解释边界与证据",
            "",
            "全文 CER 同时受 TTS 可懂度、背景音乐/音效、ASR 语言模型和长音频解码影响，不能评价音色、自然度或表演。"
            "模型时长差异很大，删句会表现为 CER 删除错误，因此不应以更短时长本身推断效率优势。",
            "",
            f"- 逐音频结果与完整转写：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 覆盖、版本与冻结配置快照：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 配置事实源：`tts-bench/config/neutral-evaluation-v4.json`",
            "- 台词事实源：`longAudioTest/ai_deal.json`；原始但未被本批成品使用的文本：`longAudioTest/text.md`",
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
    means = {metric: model_role_means(similarity_rows, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], higher_is_better=True) for metric in metrics}
    wavlm_leaders, wavlm_best = leaders(means["wavlm_sim"], True)
    ecapa_leaders, ecapa_best = leaders(means["speechbrain_ecapa_sim"], True)
    correlation = rank_correlation(ranks["wavlm_sim"], ranks["speechbrain_ecapa_sim"])
    controls = {metric: control_means(calibration_rows, metric) for metric in metrics}

    lines = [
        "# WavLM SIM 与 SpeechBrain ECAPA SIM V4 评价报告",
        "",
        "## 结论摘要",
        "",
        "- **主要评测什么**：WavLM 与 SpeechBrain ECAPA 是两套独立说话人嵌入后端；本报告用 "
        "SIM（余弦相似度）衡量每个角色的合成片段是否接近其目标参考音色，SIM 越高越好。",
        "- **对小说有声化的重要度：高，是多角色作品的核心选型维度。** 它关系到 voice casting（角色配音映射）"
        "是否准确、角色是否容易混淆以及跨章节音色是否连续；建议在台词正确性通过后，重点比较六角色宏平均和逐角色短板。",
        "- **不能代表什么**：SIM 不评价台词是否完整、语气情绪或整体自然度，也不是“同一人概率”；稀有角色片段少，"
        "背景音乐和音效也可能影响嵌入结果。",
        "",
        "技术上先将 Whisper 时间戳块与 148 段冻结台词做单调精确字符对齐，再为每个模型、每个角色按全文位置"
        "等距选取至多 5 段纯角色片段。两后端分别与同角色原始音频比较，片段内等权平均、六角色再等权宏平均。",
        "",
        f"- WavLM 六角色宏平均最高为 **{wavlm_best:.4f}**，对应{format_models(wavlm_leaders)}。",
        f"- ECAPA 六角色宏平均最高为 **{ecapa_best:.4f}**，对应{format_models(ecapa_leaders)}。",
        f"- 两组独立名次相关为 **{correlation:.3f}**；两种嵌入空间不共用量纲，不跨后端平均。",
        "",
        "## 模型六角色宏平均",
        "",
        "| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["wavlm_sim"], key=str.casefold):
        lines.append(
            f"| {model} | {means['wavlm_sim'][model]:.4f} | {ranks['wavlm_sim'][model]} | "
            f"{means['speechbrain_ecapa_sim'][model]:.4f} | "
            f"{ranks['speechbrain_ecapa_sim'][model]} |"
        )

    lines.extend(
        [
            "",
            "## 逐角色结果",
            "",
            "| 模型 | 角色 | 片段数 | WavLM SIM ↑ | ECAPA SIM ↑ |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(
        similarity_rows,
        key=lambda item: (item["model_id"].casefold(), ROLE_ORDER[item["role"]]),
    ):
        lines.append(
            f"| {row['model_id']} | {row['role']} | {len(row['alignment_excerpts'])} | "
            f"{metric_value(row, 'wavlm_sim'):.4f} | "
            f"{metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )

    labels = {
        "same_speaker_split_half": "同说话人分段",
        "different_speaker_reference_pair": "跨角色原始音频",
    }
    lines.extend(
        [
            "",
            "## 原始音频校准对照",
            "",
            "六个同说话人前后半段对照是偏乐观的正例，十五个跨角色对是本批局部负例；它们只用于解释分布，"
            "不据此设置通过阈值。",
            "",
            "| 对照 | 类型 | WavLM SIM | ECAPA SIM |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in calibration_rows:
        lines.append(
            f"| {row['label']} | {labels[row['control_type']]} | "
            f"{metric_value(row, 'wavlm_sim'):.4f} | "
            f"{metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )
    for control_type, label in labels.items():
        lines.append(
            f"| {label}均值 | 汇总 | **{controls['wavlm_sim'][control_type]:.4f}** | "
            f"**{controls['speechbrain_ecapa_sim'][control_type]:.4f}** |"
        )

    lines.extend(
        [
            "",
            "## 对齐与适用边界",
            "",
            "角色片段不是原始合成中间文件，而是由 Whisper 时间戳和冻结文本自动定位；每段至少 4 个精确匹配字符、"
            "块内匹配率至少 0.50、角色纯度至少 0.85；跨角色块按精确匹配字符的角色连续区间切分，"
            "并按规范化字符位置线性估算块内时间边界。片段时长限制为 0.5–20 秒，筛选规则在评分前冻结，"
            "片段按时间等距选择，不按 SIM 高低挑选。背景音乐和音效仍可能降低说话人嵌入的可比性。",
            "",
            "稀有角色只有少量台词，片段数小于 5 时方差更大；每个角色只有一条校准录音，SIM 也不是‘同一人概率’。"
            "正式角色定版仍需听取报告列出的片段并进行人工盲听。",
            "",
            "## 可追溯证据",
            "",
            f"- 42 个模型/角色结果及片段时间：[`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- 21 个原始音频校准对：[`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- Whisper 对齐摘要与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：`tts-bench/config/neutral-evaluation-v4.json`",
            "",
        ]
    )
    return "\n".join(lines)


def render_quality_report(
    audio_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    results_link: str,
) -> str:
    references = [row for row in audio_rows if row["kind"] == "reference"]
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    metrics = ("utmosv2", "nisqa")
    values = {metric: model_values(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(values[metric], higher_is_better=True) for metric in metrics}
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references) for metric in metrics
    }
    utmos_leaders, utmos_best = leaders(values["utmosv2"], True)
    nisqa_leaders, nisqa_best = leaders(values["nisqa"], True)
    correlation = rank_correlation(ranks["utmosv2"], ranks["nisqa"])
    sampling = metadata["config"]["quality_sampling"]

    lines = [
        "# UTMOSv2 与 NISQA V4 评价报告",
        "",
        "## 结论摘要",
        "",
        "- **主要评测什么**：UTMOSv2 与 NISQA-TTS 是两套独立的无参考语音质量预测器；本报告预测音频的"
        "自然度、清晰度和伪影程度，以 MOS（平均意见分）形式给分，分数越高越好。",
        "- **对小说有声化的重要度：高，是成品听感的体验门槛。** 它直接关系到长时间收听的疲劳感和交付品质；"
        "建议在台词正确、角色音色可接受后用于淘汰听感明显不稳的模型，并结合人工盲听决定最终生产方案。",
        "- **不能代表什么**：预测 MOS 不检查漏句、错字、角色是否对应或情绪是否合适，也未针对本批中文多角色长音频做真人 MOS 校准；"
        "背景音乐、响度和混音都会影响分数。",
        "",
        f"技术上每条长音频按全长等距取至多 {sampling['window_count']} 个 {sampling['window_seconds']:.0f} 秒窗口，"
        "下混单声道后分别预测并对窗口等权平均；短参考音频按可容纳的不重叠窗口数取样。",
        "",
        f"- UTMOSv2 窗口均值最高为 **{utmos_best:.4f}**，对应{format_models(utmos_leaders)}。",
        f"- NISQA-TTS 窗口均值最高为 **{nisqa_best:.4f}**，对应{format_models(nisqa_leaders)}。",
        f"- 两组独立名次相关为 **{correlation:.3f}**；不跨预测器加权。",
        f"- 六条原始参考音频宏平均为 UTMOSv2 **{reference_means['utmosv2']:.4f}**、"
        f"NISQA-TTS **{reference_means['nisqa']:.4f}**，只作为录音条件锚点。",
        "",
        "## 模型长音频窗口汇总",
        "",
        "| 模型 | 窗口数 | UTMOSv2 均值 ↑ | 最低 | 标准差 | 名次 | NISQA 均值 ↑ | 最低 | 标准差 | 名次 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        model = row["model_id"]
        utmos = row["metrics"]["utmosv2"]
        nisqa = row["metrics"]["nisqa"]
        lines.append(
            f"| {model} | {utmos['count']} | {utmos['mean']:.4f} | {utmos['min']:.4f} | "
            f"{utmos['std']:.4f} | {ranks['utmosv2'][model]} | {nisqa['mean']:.4f} | "
            f"{nisqa['min']:.4f} | {nisqa['std']:.4f} | {ranks['nisqa'][model]} |"
        )

    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "| 角色 | 窗口数 | UTMOSv2 ↑ | NISQA-TTS ↑ |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {row['metrics']['utmosv2']['count']} | "
            f"{metric_value(row, 'utmosv2'):.4f} | {metric_value(row, 'nisqa'):.4f} |"
        )
    lines.append(
        f"| 六角色宏平均 | — | **{reference_means['utmosv2']:.4f}** | "
        f"**{reference_means['nisqa']:.4f}** |"
    )

    lines.extend(
        [
            "",
            "## 可复现策略与边界",
            "",
            f"UTMOSv2 固定随机种子 `{metadata['config']['utmosv2']['inference_seed']}`，每个时间窗执行 "
            f"{metadata['config']['utmosv2']['num_repetitions']} 次模型内裁剪平均，并开启静音移除。"
            "NISQA 使用 NISQA-TTS v1.0 对同一组时间窗整批离线推理。具体窗口起止时间和逐窗分数保存在原始结果中。",
            "",
            "两个预测器都不是在本批中文多角色、有背景音乐和音效的长音频上用真人 MOS 重新校准的；"
            "背景层、响度和混音会影响分数，绝对值不能等同人工 MOS。原始参考音频是干声且文本不同，"
            "所以只提供锚点，不把模型与原始均值之差解释为纯 TTS 自然度损失。",
            "",
            "自然度分数不评价台词是否完整、是否像目标角色、情绪是否正确。模型选择必须与双 CER、双 SIM 和人工盲听结合。",
            "",
            "## 可追溯证据",
            "",
            f"- 逐音频、逐窗口分数：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 覆盖、采样参数和软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：`tts-bench/config/neutral-evaluation-v4.json`",
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
    results_link = results_link or results_dir.name
    return {
        "cer": render_cer_report(audio_rows, results_link),
        "sim": render_similarity_report(similarity_rows, calibration_rows, results_link),
        "quality": render_quality_report(audio_rows, metadata, results_link),
    }


def build_model_report(
    results_dir: Path,
    model_id: str,
    results_link: str | None = None,
) -> str:
    audio_rows = read_jsonl(results_dir / "per_audio.jsonl")
    similarity_rows = read_jsonl(results_dir / "speaker_similarity.jsonl")
    calibration_rows = read_jsonl(results_dir / "speaker_calibration.jsonl")
    try:
        metadata = json.loads((results_dir / "run_metadata.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到原始结果：{results_dir / 'run_metadata.json'}") from exc
    return render_model_report(
        model_id,
        audio_rows,
        similarity_rows,
        calibration_rows,
        metadata,
        results_link or results_dir.name,
    )


def write_model_report(results_dir: Path, reports_dir: Path, model_id: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_link = Path(
        os.path.relpath(results_dir.resolve(), start=reports_dir.resolve())
    ).as_posix()
    content = build_model_report(results_dir, model_id, results_link)
    path = reports_dir / model_report_filename(model_id)
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    if args.model_id:
        print(write_model_report(args.results_dir, args.reports_dir, args.model_id))
        return 0
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    results_link = Path(
        os.path.relpath(args.results_dir.resolve(), start=args.reports_dir.resolve())
    ).as_posix()
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
        print(f"V4 报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
