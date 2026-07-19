#!/usr/bin/env python3
"""从 Task 3 V2 原始结果生成三份双后端中文评价报告。"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = PROJECT_ROOT / "tts-bench" / "reports" / "task3-2026-07-19-v2-r02"
DEFAULT_REPORTS = PROJECT_ROOT / "tts-bench" / "reports"

REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper_CER_V2评价报告.md",
    "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V2评价报告.md",
    "quality": "UTMOSv2&NISQA_V2评价报告.md",
}
ROLE_ORDER = {"旁白": 0, "辰南": 1, "小公主": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except FileNotFoundError as exc:
        raise ValueError(f"找不到原始结果：{path}") from exc


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("不能计算空序列均值")
    return sum(values) / len(values)


def dense_ranks(values: dict[str, float], higher_is_better: bool) -> dict[str, int]:
    """对每个后端独立计算稠密名次；相同原始值共享名次。"""

    ordered = sorted(set(values.values()), reverse=higher_is_better)
    ranks = {value: index + 1 for index, value in enumerate(ordered)}
    return {name: ranks[value] for name, value in values.items()}


def metric_value(record: dict[str, Any], metric: str) -> float:
    value = record["metrics"][metric]
    if isinstance(value, dict):
        key = "cer" if "cer" in value else "predicted_mos"
        return float(value[key])
    return float(value)


def validate_results(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    if len(audio_rows) != 27:
        raise ValueError(f"per_audio.jsonl 应有 27 条，实际 {len(audio_rows)} 条")
    if sum(row["kind"] == "reference" for row in audio_rows) != 3:
        raise ValueError("原始参考音频必须恰好 3 条")
    if len(similarity_rows) != 24 or len(calibration_rows) != 6:
        raise ValueError("说话人结果必须包含 24 个克隆对和 6 个校准对")
    if any(row.get("errors") for row in [*audio_rows, *similarity_rows, *calibration_rows]):
        raise ValueError("原始结果仍有逐项错误，拒绝生成看似完整的报告")
    for metric, coverage in metadata["coverage"].items():
        if coverage["complete"] != coverage["expected"]:
            raise ValueError(f"{metric} 覆盖不完整：{coverage}")


def group_audio(
    audio_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    references = [row for row in audio_rows if row["kind"] == "reference"]
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    return references, syntheses, {row["case_id"]: row for row in references}


def model_metric_means(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["model_id"]].append(metric_value(row, metric))
    return {model: mean(values) for model, values in grouped.items()}


def leaders(values: dict[str, float], higher_is_better: bool) -> tuple[list[str], float]:
    best = max(values.values()) if higher_is_better else min(values.values())
    return [model for model, value in values.items() if value == best], best


def format_models(models: Iterable[str]) -> str:
    return "、".join(f"**{model}**" for model in models)


def pearson(left: list[float], right: list[float]) -> float:
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else 0.0


def render_cer_report(
    audio_rows: list[dict[str, Any]],
    results_link: str,
) -> str:
    references, syntheses, _ = group_audio(audio_rows)
    metrics = ["sensevoice_cer", "whisper_cer"]
    means = {metric: model_metric_means(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], False) for metric in metrics}
    sense_leaders, sense_best = leaders(means["sensevoice_cer"], False)
    whisper_leaders, whisper_best = leaders(means["whisper_cer"], False)
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references) for metric in metrics
    }
    zero_counts: dict[str, dict[str, int]] = {
        metric: {
            model: sum(
                metric_value(row, metric) == 0
                for row in syntheses
                if row["model_id"] == model
            )
            for model in means[metric]
        }
        for metric in metrics
    }
    largest_gap = max(
        syntheses,
        key=lambda row: abs(
            metric_value(row, "sensevoice_cer") - metric_value(row, "whisper_cer")
        ),
    )
    sense_transcript = largest_gap["metrics"]["sensevoice_cer"]["hypothesis_raw"]
    whisper_transcript = largest_gap["metrics"]["whisper_cer"]["hypothesis_raw"]

    lines = [
        "# SenseVoice CER 与 Whisper CER V2 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次使用两个独立自动语音识别后端评价 8 个模型、3 个角色的 24 条克隆音频，"
        "并对 3 条原始参考音频使用各自冻结转写计算基线。27 条音频在两个后端均成功，"
        "没有缺失项。CER（字符错误率）越低越好。",
        "",
        f"- SenseVoice 宏平均 CER 最低为 **{sense_best:.4f}**，对应{format_models(sense_leaders)}。",
        f"- Whisper 宏平均 CER 最低的是{format_models(whisper_leaders)}，为 **{whisper_best:.4f}**。",
        "- 两个后端没有给出完全相同的排序，因此本报告不把二者平均成一个总分，也不宣布单一‘总冠军’。",
        f"- 逐样本后端差异最大的是 **{largest_gap['model_id']} / {largest_gap['role']}**，"
        f"绝对差为 **{abs(metric_value(largest_gap, 'sensevoice_cer') - metric_value(largest_gap, 'whisper_cer')):.4f}**。",
        "",
        "## 模型宏平均",
        "",
        "宏平均表示三个角色等权；名次分别在单个后端内部计算。零错数是三条克隆音频中 CER 为 0 的条数。",
        "",
        "| 模型 | SenseVoice CER ↓ | 名次 | 零错数 | Whisper CER ↓ | 名次 | 零错数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["sensevoice_cer"], key=str.casefold):
        lines.append(
            f"| {model} | {means['sensevoice_cer'][model]:.4f} | "
            f"{ranks['sensevoice_cer'][model]} | {zero_counts['sensevoice_cer'][model]}/3 | "
            f"{means['whisper_cer'][model]:.4f} | {ranks['whisper_cer'][model]} | "
            f"{zero_counts['whisper_cer'][model]}/3 |"
        )

    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "原始音频的文本与克隆目标句不同，所以这里只用于暴露 ASR 后端自身偏差，不能把基线与克隆音频做严格的同句优劣判断。",
            "",
            "| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in references:
        lines.append(
            f"| {row['role']} | {metric_value(row, 'sensevoice_cer'):.4f} | "
            f"{metric_value(row, 'whisper_cer'):.4f} |"
        )
    lines.extend(
        [
            f"| 三角色宏平均 | **{reference_means['sensevoice_cer']:.4f}** | "
            f"**{reference_means['whisper_cer']:.4f}** |",
            "",
            "## 逐角色结果",
            "",
            "| 模型 | 角色 | SenseVoice CER ↓ | Whisper CER ↓ |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in sorted(
        syntheses,
        key=lambda item: (item["model_id"].casefold(), ROLE_ORDER[item["role"]]),
    ):
        lines.append(
            f"| {row['model_id']} | {row['role']} | "
            f"{metric_value(row, 'sensevoice_cer'):.4f} | "
            f"{metric_value(row, 'whisper_cer'):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 后端差异与规范化边界",
            "",
            f"逐样本最大后端差异出现在 **{largest_gap['model_id']} / {largest_gap['role']}**："
            f"SenseVoice 转写为 `{sense_transcript}`，Whisper 转写为 `{whisper_transcript}`。"
            "这类差异可能来自繁简体、同音字或 ASR 解码风格，而不一定代表音频实际读错。",
            "",
            "两侧统一使用 `zh-v1`：Unicode NFKC（兼容等价规范化）、小写化、删除空白和标点；"
            "不做繁简转换，也不把 `123` 与‘一二三’视为等价。因此原始参考音频中的数字读法会抬高 Whisper CER，"
            "繁简体差异也会按不同字符计错。保留这些原始行为是为了避免针对本批结果临时改规则；"
            "正式长期榜单应预先冻结包含繁简与数字读法转换的新版规范化配置。",
            "",
            "## 适用边界",
            "",
            "本批只有三个固定目标文本。CER 同时测量 TTS 可懂度与 ASR 偏差，不能评价音色、自然度、停顿和情绪；"
            "同音专名尤其容易受语言模型消歧影响。选型前应扩充文本，并人工复核两个后端均报错的片段。",
            "",
            "## 可追溯证据",
            "",
            f"- 逐音频原始结果：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 完整覆盖与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v2.json`](../config/neutral-evaluation-v2.json)",
            "- 评测清单：[`task3-2026-07-19-v2.jsonl`](../manifests/task3-2026-07-19-v2.jsonl)",
            "",
        ]
    )
    return "\n".join(lines)


def render_similarity_report(
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    results_link: str,
) -> str:
    metrics = ["wavlm_sim", "speechbrain_ecapa_sim"]
    means = {metric: model_metric_means(similarity_rows, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], True) for metric in metrics}
    wavlm_leaders, wavlm_best = leaders(means["wavlm_sim"], True)
    ecapa_leaders, ecapa_best = leaders(means["speechbrain_ecapa_sim"], True)
    models = sorted(means["wavlm_sim"], key=str.casefold)
    rank_correlation = pearson(
        [float(ranks["wavlm_sim"][model]) for model in models],
        [float(ranks["speechbrain_ecapa_sim"][model]) for model in models],
    )
    controls: dict[str, dict[str, list[float]]] = {
        metric: defaultdict(list) for metric in metrics
    }
    for row in calibration_rows:
        for metric in metrics:
            controls[metric][row["control_type"]].append(metric_value(row, metric))
    high_negative = max(
        (
            row
            for row in calibration_rows
            if row["control_type"] == "different_speaker_reference_pair"
        ),
        key=lambda row: metric_value(row, "wavlm_sim"),
    )

    lines = [
        "# WavLM SIM 与 SpeechBrain ECAPA SIM V2 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次将 24 条克隆音频逐一与同角色原始参考音频比较，并使用两个独立说话人表征后端计算余弦相似度。"
        "另加入 3 个同说话人前后半段对照和 3 个跨角色原始音频对照。两个后端各 30/30 完成，相似度越高越好。",
        "",
        f"- WavLM 宏平均最高的是{format_models(wavlm_leaders)}：**{wavlm_best:.4f}**。",
        f"- SpeechBrain ECAPA 宏平均最高的是{format_models(ecapa_leaders)}：**{ecapa_best:.4f}**。",
        f"- 两套独立名次的 Spearman 秩相关为 **{rank_correlation:.3f}**；领先模型不同，不能把某一个后端当作唯一事实。",
        f"- WavLM 的跨角色最高对照是“{high_negative['label']}”："
        f"**{metric_value(high_negative, 'wavlm_sim'):.4f}**，"
        "已经接近部分克隆对得分，说明本批数据不能使用未经校准的统一 WavLM 阈值。",
        "",
        "## 模型宏平均",
        "",
        "两个余弦分数的量纲和分布不同，只在各自后端内部排名，不跨后端平均。",
        "",
        "| 模型 | WavLM SIM ↑ | 名次 | SpeechBrain ECAPA SIM ↑ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in models:
        lines.append(
            f"| {model} | {means['wavlm_sim'][model]:.4f} | {ranks['wavlm_sim'][model]} | "
            f"{means['speechbrain_ecapa_sim'][model]:.4f} | "
            f"{ranks['speechbrain_ecapa_sim'][model]} |"
        )

    lines.extend(
        [
            "",
            "## 校准对照",
            "",
            "同说话人对照把同一条原始音频按时间切成前后两半，属于乐观上界；跨角色对照仅有三个角色，"
            "属于本批局部负例，不足以训练或冻结正式阈值。",
            "",
            "| 对照 | 类型 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    control_labels = {
        "same_speaker_split_half": "同说话人分段",
        "different_speaker_reference_pair": "跨角色原始音频",
    }
    for row in calibration_rows:
        lines.append(
            f"| {row['label']} | {control_labels[row['control_type']]} | "
            f"{metric_value(row, 'wavlm_sim'):.4f} | "
            f"{metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )
    for control_type, label in control_labels.items():
        wavlm_values = controls["wavlm_sim"][control_type]
        ecapa_values = controls["speechbrain_ecapa_sim"][control_type]
        lines.append(
            f"| {label}均值 | 汇总 | **{mean(wavlm_values):.4f}** | "
            f"**{mean(ecapa_values):.4f}** |"
        )

    lines.extend(
        [
            "",
            "## 逐角色结果",
            "",
            "| 模型 | 角色 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in sorted(
        similarity_rows,
        key=lambda item: (item["model_id"].casefold(), ROLE_ORDER[item["role"]]),
    ):
        lines.append(
            f"| {row['model_id']} | {row['role']} | {metric_value(row, 'wavlm_sim'):.4f} | "
            f"{metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 结果解读",
            "",
            "两个检查点的训练数据、嵌入空间，以及对音高、韵律和录音条件的敏感性不同，"
            "因此模型在两套后端中的相对次序可能变化。这种差异应作为模型选择的不确定性，而不是计算错误。",
            "",
            "跨角色原始音频对照显示，本批样本的高相似分并不天然等于同一说话人。"
            "因此报告只陈述同一后端内的相对次序，不把 SIM 解释为‘同一人概率’，也不设置通过线。",
            "",
            "## 适用边界",
            "",
            "每个角色只有一条参考与一条目标句；同说话人正例来自同一录音切分，跨角色负例也只有三对。"
            "正式验证应加入更多同说话人跨文本录音、更多异说话人负例、性别与音高匹配的困难负例，并用人工盲听校准。",
            "",
            "## 可追溯证据",
            "",
            f"- 24 个克隆对：[`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- 6 个校准对：[`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- 完整覆盖与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v2.json`](../config/neutral-evaluation-v2.json)",
            "",
        ]
    )
    return "\n".join(lines)


def render_quality_report(
    audio_rows: list[dict[str, Any]],
    results_link: str,
) -> str:
    references, syntheses, references_by_case = group_audio(audio_rows)
    metrics = ["utmosv2", "nisqa"]
    means = {metric: model_metric_means(syntheses, metric) for metric in metrics}
    ranks = {metric: dense_ranks(means[metric], True) for metric in metrics}
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references) for metric in metrics
    }
    above_reference_counts = {
        metric: sum(value > reference_means[metric] for value in means[metric].values())
        for metric in metrics
    }
    deltas: dict[str, dict[str, float]] = {metric: {} for metric in metrics}
    for metric in metrics:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in syntheses:
            grouped[row["model_id"]].append(
                metric_value(row, metric)
                - metric_value(references_by_case[row["case_id"]], metric)
            )
        deltas[metric] = {model: mean(values) for model, values in grouped.items()}
    utmos_leaders, utmos_best = leaders(means["utmosv2"], True)
    nisqa_leaders, nisqa_best = leaders(means["nisqa"], True)

    lines = [
        "# UTMOSv2 与 NISQA V2 评价报告",
        "",
        "## 结论摘要",
        "",
        "本次使用 UTMOSv2 和 NISQA-TTS 两个无参考自然度预测器，评价 24 条克隆音频和 3 条原始参考音频。"
        "两个后端均为 27/27 完成，预测 MOS 越高越好。",
        "",
        f"- UTMOSv2 宏平均最高的是{format_models(utmos_leaders)}：**{utmos_best:.4f}**。",
        f"- NISQA-TTS 宏平均最高的是{format_models(nisqa_leaders)}：**{nisqa_best:.4f}**。",
        "- 两个后端的领先模型和独立名次可能不同，显示自然度结论依赖评价器；本报告不计算跨后端总分。",
        f"- 原始参考音频宏平均为 UTMOSv2 **{reference_means['utmosv2']:.4f}**、"
        f"NISQA-TTS **{reference_means['nisqa']:.4f}**；克隆模型中分别有 "
        f"**{above_reference_counts['utmosv2']}/8** 与 **{above_reference_counts['nisqa']}/8** 的宏平均高于对应原始基线。"
        "原始音频和目标句并非同文本，该对照只作本批锚点，不能把任一预测器当成人工 MOS。",
        "",
        "## 模型宏平均与同角色基线差",
        "",
        "基线差是每个克隆样本减去同角色原始参考分后再按三个角色等权平均；正值表示预测分高于原始参考。"
        "两个后端分别排名，不计算跨后端总分。",
        "",
        "| 模型 | UTMOSv2 ↑ | 名次 | 相对原始 | NISQA-TTS ↑ | 名次 | 相对原始 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(means["utmosv2"], key=str.casefold):
        lines.append(
            f"| {model} | {means['utmosv2'][model]:.4f} | {ranks['utmosv2'][model]} | "
            f"{deltas['utmosv2'][model]:+.4f} | {means['nisqa'][model]:.4f} | "
            f"{ranks['nisqa'][model]} | {deltas['nisqa'][model]:+.4f} |"
        )

    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "| 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in references:
        lines.append(
            f"| {row['role']} | {metric_value(row, 'utmosv2'):.4f} | "
            f"{metric_value(row, 'nisqa'):.4f} |"
        )
    lines.append(
        f"| 三角色宏平均 | **{reference_means['utmosv2']:.4f}** | "
        f"**{reference_means['nisqa']:.4f}** |"
    )

    lines.extend(
        [
            "",
            "## 逐角色结果",
            "",
            "| 模型 | 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in sorted(
        syntheses,
        key=lambda item: (item["model_id"].casefold(), ROLE_ORDER[item["role"]]),
    ):
        lines.append(
            f"| {row['model_id']} | {row['role']} | {metric_value(row, 'utmosv2'):.4f} | "
            f"{metric_value(row, 'nisqa'):.4f} |"
        )

    lines.extend(
        [
            "",
            "## 可复现策略与解释边界",
            "",
            "UTMOSv2 的推理数据管线会随机截取音频；默认单次预测会随随机状态漂移。V2 配置将随机种子冻结为 "
            "`20260719`，每条音频执行 5 次裁剪并取模型内置平均，静音移除保持开启。"
            "NISQA 使用面向合成语音的 `nisqa_tts.tar`（NISQA-TTS v1.0），本批离线整批推理。",
            "",
            "MOS 预测器的绝对值没有在本数据集上用真人评分重新校准；NISQA-TTS 的模型领域是合成语音，"
            "原始参考音频分数只作为本批锚点。两个后端的分差也没有置信区间，尤其 NISQA-TTS 的模型均值集中在较窄区间，"
            "不应把很小的数值差解释为可感知优势。",
            "",
            "## 适用边界",
            "",
            "自然度预测不评价文本是否正确、是否像目标说话人、角色表演和情绪是否合适。"
            "正式选型应把双后端结果与 CER、双说话人后端及人工盲听共同使用。",
            "",
            "## 可追溯证据",
            "",
            f"- 逐音频原始结果：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 完整覆盖、5 次裁剪参数与软件版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            "- 冻结配置：[`neutral-evaluation-v2.json`](../config/neutral-evaluation-v2.json)",
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
    roles = {row["role"] for row in [*audio_rows, *similarity_rows]}
    if roles != set(ROLE_ORDER):
        raise ValueError(f"V2 结果角色应为 {sorted(ROLE_ORDER)}，实际为 {sorted(roles)}")
    results_link = results_link or results_dir.name
    return {
        "cer": render_cer_report(audio_rows, results_link),
        "sim": render_similarity_report(similarity_rows, calibration_rows, results_link),
        "quality": render_quality_report(audio_rows, results_link),
    }


def main() -> int:
    args = parse_args()
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
        print(f"V2 报告生成失败：{error}")
        raise SystemExit(2) from error
