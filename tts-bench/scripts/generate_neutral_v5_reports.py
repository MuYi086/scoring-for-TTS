#!/usr/bin/env python3
"""从 Task 6 V5 原始结果生成单模型、三维度和综合中文评价报告。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_RESULTS = PROJECT_ROOT / "buildTestV5" / "评测结果" / "task6-v5-raw"
DEFAULT_REPORTS = PROJECT_ROOT / "buildTestV5" / "评测结果"
REPORT_VERSION = "V5"
SCHEMA_VERSION = "5.0"
SOURCE_DISPLAY_PATH = "buildTestV5/ai_deal.json"
CONFIG_DISPLAY_PATH = "tts-bench/config/neutral-evaluation-v5.json"
REPORT_FILENAMES = {
    "cer": "SenseVoice_CER&Whisper_CER_V5评价报告.md",
    "sim": "WavLM_SIM&SpeechBrain_ECAPA_SIM_V5评价报告.md",
    "quality": "UTMOSv2&NISQA_V5评价报告.md",
    "comprehensive": "小说转有声TTS_V5综合评价报告.md",
}
ROLE_ORDER = {
    "我": 0,
    "旁白": 1,
    "枯臂男子": 2,
    "老妇人": 3,
    "蒙眼罩的老人": 4,
}
METRIC_LABELS = {
    "sensevoice_cer": "SenseVoice CER",
    "whisper_cer": "Whisper CER",
    "wavlm_sim": "WavLM SIM",
    "speechbrain_ecapa_sim": "ECAPA SIM",
    "utmosv2": "UTMOSv2",
    "nisqa": "NISQA-TTS",
}
HIGHER_IS_BETTER = {
    "sensevoice_cer": False,
    "whisper_cer": False,
    "wavlm_sim": True,
    "speechbrain_ecapa_sim": True,
    "utmosv2": True,
    "nisqa": True,
}
DIMENSIONS = {
    "台词正确性": ("sensevoice_cer", "whisper_cer"),
    "角色音色": ("wavlm_sim", "speechbrain_ecapa_sim"),
    "自然听感": ("utmosv2", "nisqa"),
}
DEFAULT_WEIGHTS = {"台词正确性": 0.50, "角色音色": 0.30, "自然听感": 0.20}

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
        help="只生成一个已完成模型的独立报告；省略时要求全部模型完成并生成四份最终报告。",
    )
    return parser.parse_args()


def metric_value(row: dict[str, Any], metric: str) -> float:
    value = row["metrics"][metric]
    if isinstance(value, dict):
        for key in ("cer", "mean", "predicted_mos"):
            if key in value:
                return float(value[key])
    return float(value)


def grouped_means(rows: Iterable[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["model_id"]].append(metric_value(row, metric))
    return {model: mean(values) for model, values in grouped.items()}


def control_means(rows: list[dict[str, Any]], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["control_type"]].append(metric_value(row, metric))
    return {control_type: mean(values) for control_type, values in grouped.items()}


def rank_correlation(first: dict[str, int], second: dict[str, int]) -> float:
    models = sorted(first, key=str.casefold)
    if set(models) != set(second):
        raise ValueError("两个后端的模型集合不一致")
    return pearson(
        [float(first[model]) for model in models],
        [float(second[model]) for model in models],
    )


def load_results(
    results_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    audio_rows = read_jsonl(results_dir / "per_audio.jsonl")
    similarity_rows = read_jsonl(results_dir / "speaker_similarity.jsonl")
    calibration_rows = read_jsonl(results_dir / "speaker_calibration.jsonl")
    try:
        metadata = json.loads((results_dir / "run_metadata.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到原始结果：{results_dir / 'run_metadata.json'}") from exc
    return audio_rows, similarity_rows, calibration_rows, metadata


def validate_results(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    config = metadata.get("config", {})
    model_count = int(config.get("expected_model_count", -1))
    role_count = len(config.get("references", []))
    calibration_count = role_count + len(list(combinations(range(role_count), 2)))
    if (
        metadata.get("schema_version") != SCHEMA_VERSION
        or config.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError(f"原始结果不是冻结的 {REPORT_VERSION} 配置")
    if len(audio_rows) != model_count + role_count:
        raise ValueError(f"per_audio.jsonl 数量不正确：实际 {len(audio_rows)}")
    if len(similarity_rows) != model_count * role_count:
        raise ValueError(f"speaker_similarity.jsonl 数量不正确：实际 {len(similarity_rows)}")
    if len(calibration_rows) != calibration_count:
        raise ValueError(f"speaker_calibration.jsonl 数量不正确：实际 {len(calibration_rows)}")
    configured_roles = {item["role"] for item in config.get("references", [])}
    if configured_roles != set(ROLE_ORDER):
        raise ValueError(f"{REPORT_VERSION} 报告角色顺序与冻结配置不一致")
    if {row["role"] for row in similarity_rows} != configured_roles:
        raise ValueError(f"{REPORT_VERSION} SIM 角色集合与冻结配置不一致")
    all_rows = [*audio_rows, *similarity_rows, *calibration_rows]
    if any(row.get("errors") for row in all_rows):
        raise ValueError("原始结果仍有逐项错误，拒绝生成看似完整的报告")
    for metric, coverage in metadata.get("coverage", {}).items():
        if coverage["complete"] != coverage["expected"]:
            raise ValueError(f"{metric} 覆盖不完整：{coverage}")


def validate_model_results(
    model_id: str,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    references = [row for row in audio_rows if row.get("kind") == "reference"]
    syntheses = [
        row
        for row in audio_rows
        if row.get("kind") == "synthesis" and row.get("model_id") == model_id
    ]
    model_similarity = [row for row in similarity_rows if row.get("model_id") == model_id]
    if len(references) != len(ROLE_ORDER) or len(syntheses) != 1:
        raise ValueError(f"{model_id} 的参考音频或长音频结果不完整")
    if {row.get("role") for row in model_similarity} != set(ROLE_ORDER):
        raise ValueError(f"{model_id} 的双 SIM 不是完整五角色结果")
    calibration_count = len(ROLE_ORDER) + len(list(combinations(ROLE_ORDER, 2)))
    if len(calibration_rows) != calibration_count:
        raise ValueError(f"原始音频校准对应该有 {calibration_count} 条")
    audio_metrics = {"sensevoice_cer", "whisper_cer", "utmosv2", "nisqa"}
    sim_metrics = {"wavlm_sim", "speechbrain_ecapa_sim"}
    relevant = [*references, syntheses[0], *model_similarity, *calibration_rows]
    if any(row.get("errors") for row in relevant):
        raise ValueError(f"{model_id} 或共享基线仍有逐项错误")
    for row in [*references, syntheses[0]]:
        if audio_metrics - set(row.get("metrics", {})):
            raise ValueError(f"{row.get('audio_id')} 的四项音频指标不完整")
    for row in [*model_similarity, *calibration_rows]:
        if sim_metrics - set(row.get("metrics", {})):
            raise ValueError(f"{row.get('label', row.get('role'))} 的双 SIM 不完整")
    return references, syntheses[0], model_similarity


def model_report_filename(model_id: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", model_id).strip("._")
    if not safe:
        raise ValueError(f"model_id 无法生成安全文件名：{model_id!r}")
    return f"{safe}_{REPORT_VERSION}评价报告.md"


def render_model_report(
    model_id: str,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    results_link: str,
) -> str:
    references, synthesis, model_similarity = validate_model_results(
        model_id, audio_rows, similarity_rows, calibration_rows
    )
    reference_means = {
        metric: mean(metric_value(row, metric) for row in references)
        for metric in ("sensevoice_cer", "whisper_cer", "utmosv2", "nisqa")
    }
    sim_means = {
        metric: mean(metric_value(row, metric) for row in model_similarity)
        for metric in ("wavlm_sim", "speechbrain_ecapa_sim")
    }
    controls = {
        metric: control_means(calibration_rows, metric)
        for metric in ("wavlm_sim", "speechbrain_ecapa_sim")
    }
    alignment = synthesis["metrics"]["whisper_cer"].get("alignment_summary", {})
    role_count = len(references)
    fallback_roles = [
        row["role"]
        for row in model_similarity
        if any(
            excerpt.get("selection_tier") == "short_role_fallback"
            for excerpt in row["alignment_excerpts"]
        )
    ]
    lines = [
        f"# {model_id} {REPORT_VERSION} 独立评价报告",
        "",
        "## 六后端结果",
        "",
        "本报告只评价这一条模型长音频。六个后端保持独立量纲，不在单模型报告中跨后端合分；"
        "原始音频基线与成品并非同文本、同混音条件，只作为本批解释锚点。",
        "",
        "| 维度 | 后端 | 模型结果 | 原始音频或校准对照 | 方向 |",
        "| --- | --- | ---: | ---: | --- |",
        f"| 台词正确性 | SenseVoice CER | {metric_value(synthesis, 'sensevoice_cer'):.4f} | {role_count} 角色宏平均 {reference_means['sensevoice_cer']:.4f} | 越低越好 |",
        f"| 台词正确性 | Whisper CER | {metric_value(synthesis, 'whisper_cer'):.4f} | {role_count} 角色宏平均 {reference_means['whisper_cer']:.4f} | 越低越好 |",
        f"| 角色音色 | WavLM SIM | {sim_means['wavlm_sim']:.4f} | 同人 {controls['wavlm_sim']['same_speaker_split_half']:.4f}；跨角色 {controls['wavlm_sim']['different_speaker_reference_pair']:.4f} | 越高越好 |",
        f"| 角色音色 | ECAPA SIM | {sim_means['speechbrain_ecapa_sim']:.4f} | 同人 {controls['speechbrain_ecapa_sim']['same_speaker_split_half']:.4f}；跨角色 {controls['speechbrain_ecapa_sim']['different_speaker_reference_pair']:.4f} | 越高越好 |",
        f"| 自然听感 | UTMOSv2 | {metric_value(synthesis, 'utmosv2'):.4f} | {role_count} 角色宏平均 {reference_means['utmosv2']:.4f} | 越高越好 |",
        f"| 自然听感 | NISQA-TTS | {metric_value(synthesis, 'nisqa'):.4f} | {role_count} 角色宏平均 {reference_means['nisqa']:.4f} | 越高越好 |",
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
            "## 覆盖与解释边界",
            "",
            f"- 成品时长：**{synthesis['audio']['duration_seconds']:.2f} 秒**。",
            f"- Whisper 精确对齐：**{alignment.get('exact_matched_characters', 0)} / {alignment.get('expected_characters', 0)}** 个规范化字符，对齐率 **{alignment.get('exact_alignment_ratio_to_expected', 0.0):.4f}**。",
            f"- 自然度窗口：UTMOSv2 **{synthesis['metrics']['utmosv2']['count']}** 个、NISQA-TTS **{synthesis['metrics']['nisqa']['count']}** 个。",
            (
                "- 短台词定位回退：**"
                + "、".join(fallback_roles)
                + "** 未找到达到标准精确匹配长度的候选，SIM 使用原始结果中显式标记的短台词精确匹配片段；短片段嵌入稳定性较弱，必须结合人工盲听。"
                if fallback_roles
                else "- 短台词定位回退：未触发。"
            ),
            "- 双 CER 会受背景音乐、音效和 ASR 偏差影响；双 SIM 依赖自动时间戳对齐；双自然度没有本批真人 MOS 校准。正式选型仍需人工盲听。",
            "",
            "## 可追溯证据",
            "",
            f"- [`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- [`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- [`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- [`run_metadata.json`]({results_link}/run_metadata.json)",
            "",
        ]
    )
    return "\n".join(lines)


def render_cer_report(
    audio_rows: list[dict[str, Any]], metadata: dict[str, Any], results_link: str
) -> str:
    references = [row for row in audio_rows if row["kind"] == "reference"]
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    values = {
        metric: {row["model_id"]: metric_value(row, metric) for row in syntheses}
        for metric in ("sensevoice_cer", "whisper_cer")
    }
    ranks = {metric: dense_ranks(values[metric], False) for metric in values}
    sense_models, sense_best = leaders(values["sensevoice_cer"], False)
    whisper_models, whisper_best = leaders(values["whisper_cer"], False)
    correlation = rank_correlation(ranks["sensevoice_cer"], ranks["whisper_cer"])
    sense_order = sorted(values["sensevoice_cer"], key=lambda model: ranks["sensevoice_cer"][model])
    whisper_order = sorted(values["whisper_cer"], key=lambda model: ranks["whisper_cer"][model])
    if sense_order == whisper_order:
        divergence = "两个 ASR 后端给出相同排序，但仍应核对完整转写与原始 CER。"
    elif correlation < 0:
        divergence = "两个 ASR 后端排序呈负相关，不能用单一后端结论替代双后端核验。"
    else:
        divergence = "两个 ASR 后端排序不完全一致，应核对分歧模型的完整转写。"
    source = metadata["config"]["source"]
    raw_count = int(source["raw_text_normalized_character_count"])
    dialogue_count = int(source["normalized_character_count"])
    raw_text_relation = str(
        source.get(
            "raw_text_relation",
            f"`text.md` 有 {raw_count} 个规范化字符，其中相对实际合成台词串多出的 "
            f"{raw_count - dialogue_count} 个字符不进入本批 CER。",
        )
    )
    lines = [
        f"# SenseVoice CER 与 Whisper CER {REPORT_VERSION} 评价报告",
        "",
        "## 结论摘要",
        "",
        "CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；"
        "它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。",
        "",
        f"- SenseVoice 最低 CER 为 **{sense_best:.4f}**，对应{format_models(sense_models)}。",
        f"- Whisper 最低 CER 为 **{whisper_best:.4f}**，对应{format_models(whisper_models)}。",
        f"- 双后端名次相关为 **{correlation:.3f}**。",
        f"- SenseVoice 的顺序是 {'、'.join(sense_order)}；Whisper 的顺序是 {'、'.join(whisper_order)}。{divergence}",
        "",
        "## 模型全文结果",
        "",
        "| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        model = row["model_id"]
        alignment = row["metrics"]["whisper_cer"].get("alignment_summary", {})
        lines.append(
            f"| {model} | {row['audio']['duration_seconds']:.2f} | {values['sensevoice_cer'][model]:.4f} | "
            f"{ranks['sensevoice_cer'][model]} | {values['whisper_cer'][model]:.4f} | "
            f"{ranks['whisper_cer'][model]} | {alignment.get('exact_alignment_ratio_to_expected', 0.0):.4f} |"
        )
    lines.extend(
        [
            "",
            "## 原始参考音频基线",
            "",
            "| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {metric_value(row, 'sensevoice_cer'):.4f} | {metric_value(row, 'whisper_cer'):.4f} |"
        )
    lines.extend(
        [
            "",
            "## 文本边界与证据",
            "",
            f"成品按 `{SOURCE_DISPLAY_PATH}` 合成，故以其中 {source['dialogue_count']} 段台词、"
            f"{dialogue_count} 个规范化字符计算 CER。{raw_text_relation}"
            "若直接使用小说原文作为参考，会把输入差异误计为模型错误。"
            "规范化为 `zh-v1`，不做同音字或数字读法等价。",
            "",
            "原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。"
            "成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。",
            "",
            f"- 完整转写：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 覆盖与配置：[`run_metadata.json`]({results_link}/run_metadata.json)",
            f"- 冻结配置：`{CONFIG_DISPLAY_PATH}`",
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
    values = {metric: grouped_means(similarity_rows, metric) for metric in metrics}
    ranks = {metric: dense_ranks(values[metric], True) for metric in metrics}
    wavlm_models, wavlm_best = leaders(values["wavlm_sim"], True)
    ecapa_models, ecapa_best = leaders(values["speechbrain_ecapa_sim"], True)
    correlation = rank_correlation(ranks["wavlm_sim"], ranks["speechbrain_ecapa_sim"])
    controls = {metric: control_means(calibration_rows, metric) for metric in metrics}
    wavlm_model_min = min(values["wavlm_sim"].values())
    wavlm_model_max = max(values["wavlm_sim"].values())
    role_count = len({row["role"] for row in similarity_rows})
    model_count = len(values["wavlm_sim"])
    calibration_count = len(calibration_rows)
    similarity_count = len(similarity_rows)
    wavlm_cross = controls["wavlm_sim"]["different_speaker_reference_pair"]
    if wavlm_model_min <= wavlm_cross <= wavlm_model_max:
        wavlm_calibration = (
            f"WavLM 的跨角色均值 {wavlm_cross:.4f} 落在模型宏平均 "
            f"{wavlm_model_min:.4f}–{wavlm_model_max:.4f} 内，绝对值的角色区分度有限。"
        )
    elif wavlm_cross < wavlm_model_min:
        wavlm_calibration = (
            f"WavLM 的跨角色均值 {wavlm_cross:.4f} 低于模型宏平均 "
            f"{wavlm_model_min:.4f}–{wavlm_model_max:.4f}。"
        )
    else:
        wavlm_calibration = (
            f"WavLM 的跨角色均值 {wavlm_cross:.4f} 高于模型宏平均 "
            f"{wavlm_model_min:.4f}–{wavlm_model_max:.4f}，自动 SIM 的区分证据较弱。"
        )
    lines = [
        f"# WavLM SIM 与 SpeechBrain ECAPA SIM {REPORT_VERSION} 评价报告",
        "",
        "## 结论摘要",
        "",
        "SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。"
        "它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。",
        "",
        f"- WavLM {role_count} 角色宏平均最高为 **{wavlm_best:.4f}**，对应{format_models(wavlm_models)}。",
        f"- ECAPA {role_count} 角色宏平均最高为 **{ecapa_best:.4f}**，对应{format_models(ecapa_models)}。",
        f"- 双后端名次相关为 **{correlation:.3f}**；两种嵌入空间不直接平均原始值。",
        "",
        f"## 模型 {role_count} 角色宏平均",
        "",
        "| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in sorted(values["wavlm_sim"], key=str.casefold):
        lines.append(
            f"| {model} | {values['wavlm_sim'][model]:.4f} | {ranks['wavlm_sim'][model]} | "
            f"{values['speechbrain_ecapa_sim'][model]:.4f} | {ranks['speechbrain_ecapa_sim'][model]} |"
        )
    lines.extend(
        [
            "",
            "## 逐角色结果",
            "",
        "| 模型 | 角色 | 片段数 | 定位规则 | WavLM SIM ↑ | ECAPA SIM ↑ |",
        "| --- | --- | ---: | --- | ---: | ---: |",
        ]
    )
    for row in sorted(
        similarity_rows,
        key=lambda item: (item["model_id"].casefold(), ROLE_ORDER[item["role"]]),
    ):
        fallback = any(
            excerpt.get("selection_tier") == "short_role_fallback"
            for excerpt in row["alignment_excerpts"]
        )
        lines.append(
            f"| {row['model_id']} | {row['role']} | {len(row['alignment_excerpts'])} | "
            f"{'短台词回退' if fallback else '标准'} | "
            f"{metric_value(row, 'wavlm_sim'):.4f} | {metric_value(row, 'speechbrain_ecapa_sim'):.4f} |"
        )
    lines.extend(
        [
            "",
            "## 原始音频校准与边界",
            "",
            f"- WavLM：同说话人分段均值 **{controls['wavlm_sim']['same_speaker_split_half']:.4f}**；跨角色均值 **{controls['wavlm_sim']['different_speaker_reference_pair']:.4f}**。",
            f"- ECAPA：同说话人分段均值 **{controls['speechbrain_ecapa_sim']['same_speaker_split_half']:.4f}**；跨角色均值 **{controls['speechbrain_ecapa_sim']['different_speaker_reference_pair']:.4f}**。",
            f"- {wavlm_calibration}应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。",
            "- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。",
            "- 只有某角色完全没有达到标准精确匹配长度的候选时，才允许使用配置冻结且显式标记的短台词回退片段；其 SIM 稳定性更弱。",
            "- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。",
            "",
            f"- {similarity_count} 个模型/角色结果（{model_count} 个模型 × {role_count} 个角色）：[`speaker_similarity.jsonl`]({results_link}/speaker_similarity.jsonl)",
            f"- {calibration_count} 个校准对：[`speaker_calibration.jsonl`]({results_link}/speaker_calibration.jsonl)",
            f"- 冻结配置：`{CONFIG_DISPLAY_PATH}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_quality_report(
    audio_rows: list[dict[str, Any]], metadata: dict[str, Any], results_link: str
) -> str:
    references = [row for row in audio_rows if row["kind"] == "reference"]
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    values = {
        metric: {row["model_id"]: metric_value(row, metric) for row in syntheses}
        for metric in ("utmosv2", "nisqa")
    }
    ranks = {metric: dense_ranks(values[metric], True) for metric in values}
    utmos_models, utmos_best = leaders(values["utmosv2"], True)
    nisqa_models, nisqa_best = leaders(values["nisqa"], True)
    correlation = rank_correlation(ranks["utmosv2"], ranks["nisqa"])
    sampling = metadata["config"]["quality_sampling"]
    if set(utmos_models) == set(nisqa_models):
        predictor_agreement = (
            f"{format_models(utmos_models)} 在两个预测器上均列第 1，"
            "是本批自动自然听感结果最一致的候选。"
        )
    else:
        predictor_agreement = "两个预测器的第 1 名不同，自动自然听感结论存在明显分歧。"
    lines = [
        f"# UTMOSv2 与 NISQA {REPORT_VERSION} 评价报告",
        "",
        "## 结论摘要",
        "",
        "两套无参考语音质量预测器以 MOS（平均意见分）形式衡量自然度、清晰度和伪影，越高越好。"
        "它们不检查错字、漏句、角色对应或情绪，也未针对本批中文多角色混音做真人 MOS 校准。",
        "",
        f"- UTMOSv2 最高均值为 **{utmos_best:.4f}**，对应{format_models(utmos_models)}。",
        f"- NISQA-TTS 最高均值为 **{nisqa_best:.4f}**，对应{format_models(nisqa_models)}。",
        f"- 双预测器名次相关为 **{correlation:.3f}**；不直接平均原始 MOS。",
        f"- {predictor_agreement}",
        f"- 每条长音频按全长等距取 {sampling['window_count']} 个 {sampling['window_seconds']:.0f} 秒窗口。",
        "",
        "## 模型窗口汇总",
        "",
        "| 模型 | UTMOSv2 均值 ↑ | 最低 | 标准差 | 名次 | NISQA 均值 ↑ | 最低 | 标准差 | 名次 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(syntheses, key=lambda item: item["model_id"].casefold()):
        model = row["model_id"]
        utmos = row["metrics"]["utmosv2"]
        nisqa = row["metrics"]["nisqa"]
        lines.append(
            f"| {model} | {utmos['mean']:.4f} | {utmos['min']:.4f} | {utmos['std']:.4f} | "
            f"{ranks['utmosv2'][model]} | {nisqa['mean']:.4f} | {nisqa['min']:.4f} | "
            f"{nisqa['std']:.4f} | {ranks['nisqa'][model]} |"
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
    for row in sorted(references, key=lambda item: ROLE_ORDER[item["role"]]):
        lines.append(
            f"| {row['role']} | {metric_value(row, 'utmosv2'):.4f} | {metric_value(row, 'nisqa'):.4f} |"
        )
    lines.extend(
        [
            "",
            "## 解释边界与证据",
            "",
            "原始参考是干声且文本不同，只提供录音条件锚点。背景层、响度、停顿和混音都会影响预测器；"
            "长时间疲劳感、表演自然度与情绪适配仍需连续盲听确认。",
            "",
            f"- 逐窗口分数：[`per_audio.jsonl`]({results_link}/per_audio.jsonl)",
            f"- 采样参数与版本：[`run_metadata.json`]({results_link}/run_metadata.json)",
            f"- 冻结配置：`{CONFIG_DISPLAY_PATH}`",
            "",
        ]
    )
    return "\n".join(lines)


def metric_values_for_models(
    audio_rows: list[dict[str, Any]], similarity_rows: list[dict[str, Any]]
) -> dict[str, dict[str, float]]:
    syntheses = [row for row in audio_rows if row["kind"] == "synthesis"]
    values = {
        metric: {row["model_id"]: metric_value(row, metric) for row in syntheses}
        for metric in ("sensevoice_cer", "whisper_cer", "utmosv2", "nisqa")
    }
    values["wavlm_sim"] = grouped_means(similarity_rows, "wavlm_sim")
    values["speechbrain_ecapa_sim"] = grouped_means(
        similarity_rows, "speechbrain_ecapa_sim"
    )
    return values


def score_models(
    values: dict[str, dict[str, float]], weights: dict[str, float]
) -> tuple[dict[str, dict[str, float]], dict[str, float], dict[str, dict[str, int]]]:
    metric_ranks = {
        metric: dense_ranks(metric_values, HIGHER_IS_BETTER[metric])
        for metric, metric_values in values.items()
    }
    models = sorted(next(iter(values.values())), key=str.casefold)
    denominator = max(len(models) - 1, 1)
    dimension_scores: dict[str, dict[str, float]] = {model: {} for model in models}
    for model in models:
        for dimension, metrics in DIMENSIONS.items():
            points = [
                (len(models) - metric_ranks[metric][model]) / denominator * 100.0
                for metric in metrics
            ]
            dimension_scores[model][dimension] = mean(points)
    totals = {
        model: sum(dimension_scores[model][dimension] * weight for dimension, weight in weights.items())
        for model in models
    }
    return dimension_scores, totals, metric_ranks


def render_comprehensive_report(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    results_link: str,
) -> str:
    values = metric_values_for_models(audio_rows, similarity_rows)
    dimensions, totals, ranks = score_models(values, DEFAULT_WEIGHTS)
    ordered = sorted(totals, key=lambda model: (-totals[model], model.casefold()))
    top = ordered[0]
    last_rank = len(ordered)
    rank_summaries = []
    for model in ordered:
        leading = [METRIC_LABELS[metric] for metric in METRIC_LABELS if ranks[metric][model] == 1]
        trailing = [
            METRIC_LABELS[metric]
            for metric in METRIC_LABELS
            if ranks[metric][model] == last_rank
        ]
        strengths = "、".join(leading) + "列第 1" if leading else "没有单后端第 1"
        weaknesses = "、".join(trailing) + f"列第 {last_rank}" if trailing else "没有单后端末位"
        rank_summaries.append(f"**{model}**：{strengths}；{weaknesses}。")
    scenarios = {
        "生产默认": DEFAULT_WEIGHTS,
        "内容优先": {"台词正确性": 0.60, "角色音色": 0.25, "自然听感": 0.15},
        "三维较均衡": {"台词正确性": 0.40, "角色音色": 0.30, "自然听感": 0.30},
        "角色音色优先": {"台词正确性": 0.35, "角色音色": 0.45, "自然听感": 0.20},
        "自然听感优先": {"台词正确性": 0.35, "角色音色": 0.20, "自然听感": 0.45},
    }
    lines = [
        f"# 小说转有声 TTS {REPORT_VERSION} 综合评价报告",
        "",
        "## 最终结论",
        "",
        "按照小说转有声生产工作流的默认权重——台词正确性 **50%**、角色音色 **30%**、自然听感 **20%**——本批排序如下：",
        "",
    ]
    for index, model in enumerate(ordered, start=1):
        lines.append(f"{index}. **{model}：{totals[model]:.2f} 分**")
    lines.extend(
        [
            "",
            f"默认主生产候选为 **{top}**。该结论是本批 {len(ordered)} 个模型内的相对生产优先级，不是跨项目绝对质量分。"
            "正式定版前仍需核对双后端分歧、逐角色短板和连续长段盲听。",
            "",
            " ".join(rank_summaries),
            "",
            "## 权重与统一尺度",
            "",
            "| 生产维度 | 后端 | 权重 | 工作流依据 |",
            "| --- | --- | ---: | --- |",
            "| 台词正确性 | SenseVoice CER + Whisper CER | **50%** | 错字、漏句和重复会改变剧情并产生最高返工成本。 |",
            "| 角色音色 | WavLM SIM + ECAPA SIM | **30%** | 多角色小说依赖稳定、可区分的角色配音映射。 |",
            "| 自然听感 | UTMOSv2 + NISQA-TTS | **20%** | 影响长听疲劳和交付品质，但部分混音问题可后期修复。 |",
            "",
            "六个后端原始值跨量纲，不能直接平均。本报告先在每个后端内独立排名，再统一转换为名次分：",
            "",
            "```text",
            "单后端名次分 = (模型数 - 该后端名次) / (模型数 - 1) × 100",
            "维度分       = 该维度两个后端名次分的平均值",
            "综合分       = 台词正确性分 × 50% + 角色音色分 × 30% + 自然听感分 × 20%",
            "```",
            "",
            "## 加权排序明细",
            "",
            "| 综合名次 | 模型 | 台词正确性分 | 50% 贡献 | 角色音色分 | 30% 贡献 | 自然听感分 | 20% 贡献 | 综合分 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for index, model in enumerate(ordered, start=1):
        d = dimensions[model]
        lines.append(
            f"| {index} | **{model}** | {d['台词正确性']:.2f} | {d['台词正确性'] * 0.5:.2f} | "
            f"{d['角色音色']:.2f} | {d['角色音色'] * 0.3:.2f} | {d['自然听感']:.2f} | "
            f"{d['自然听感'] * 0.2:.2f} | **{totals[model]:.2f}** |"
        )
    lines.extend(
        [
            "",
            "## 六后端名次依据",
            "",
            "| 模型 | SenseVoice CER | Whisper CER | WavLM SIM | ECAPA SIM | UTMOSv2 | NISQA-TTS |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for model in sorted(totals, key=str.casefold):
        lines.append(
            f"| {model} | {ranks['sensevoice_cer'][model]} | {ranks['whisper_cer'][model]} | "
            f"{ranks['wavlm_sim'][model]} | {ranks['speechbrain_ecapa_sim'][model]} | "
            f"{ranks['utmosv2'][model]} | {ranks['nisqa'][model]} |"
        )
    lines.extend(
        [
            "",
            "## 权重敏感性",
            "",
            "| 场景 | 台词 / 音色 / 听感 | "
            + " | ".join(f"第 {index} 名" for index in range(1, len(ordered) + 1))
            + " |",
            "| --- | --- | " + " | ".join("---" for _ in ordered) + " |",
        ]
    )
    for name, weights in scenarios.items():
        _, scenario_totals, _ = score_models(values, weights)
        scenario_order = sorted(
            scenario_totals, key=lambda model: (-scenario_totals[model], model.casefold())
        )
        weight_label = " / ".join(f"{weights[key]:.0%}" for key in DIMENSIONS)
        placements = [f"{model} {scenario_totals[model]:.2f}" for model in scenario_order]
        lines.append(f"| {name} | {weight_label} | " + " | ".join(placements) + " |")
    lines.extend(
        [
            "",
            "## 生产建议与边界",
            "",
            f"1. 先用 **{top}** 做一章试生产，逐句核对漏句、角色切换、停顿和异常重音。",
            f"2. 对 {len(ROLE_ORDER)} 个有参考音频的角色做人工盲听，核对角色区分度与一致性。",
            "3. 至少连续听取 10–15 分钟，检查机械感、伪影、背景层干扰和听觉疲劳。",
            "4. 不因单一后端第一直接定版；背景音乐和音效会共同影响 ASR、说话人嵌入和质量预测器。",
            "",
            "## 数据来源",
            "",
            f"- [SenseVoice CER 与 Whisper CER {REPORT_VERSION} 评价报告]({REPORT_FILENAMES['cer']})",
            f"- [WavLM SIM 与 SpeechBrain ECAPA SIM {REPORT_VERSION} 评价报告]({REPORT_FILENAMES['sim']})",
            f"- [UTMOSv2 与 NISQA {REPORT_VERSION} 评价报告]({REPORT_FILENAMES['quality']})",
            f"- [{REPORT_VERSION} 完整覆盖与配置快照]({results_link}/run_metadata.json)",
            "",
        ]
    )
    return "\n".join(lines)


def build_reports(results_dir: Path, results_link: str | None = None) -> dict[str, str]:
    audio_rows, similarity_rows, calibration_rows, metadata = load_results(results_dir)
    validate_results(audio_rows, similarity_rows, calibration_rows, metadata)
    link = results_link or results_dir.name
    return {
        "cer": render_cer_report(audio_rows, metadata, link),
        "sim": render_similarity_report(similarity_rows, calibration_rows, link),
        "quality": render_quality_report(audio_rows, metadata, link),
        "comprehensive": render_comprehensive_report(audio_rows, similarity_rows, link),
    }


def build_model_report(
    results_dir: Path, model_id: str, results_link: str | None = None
) -> str:
    audio_rows, similarity_rows, calibration_rows, metadata = load_results(results_dir)
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
    path = reports_dir / model_report_filename(model_id)
    path.write_text(
        build_model_report(results_dir, model_id, results_link), encoding="utf-8"
    )
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
    for report_id, content in build_reports(args.results_dir, results_link).items():
        path = args.reports_dir / REPORT_FILENAMES[report_id]
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"{REPORT_VERSION} 报告生成失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
