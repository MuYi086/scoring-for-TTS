#!/usr/bin/env python3
"""批量计算已合成 TTS 音频的客观指标，并生成透明的模型排名。

本脚本只评估已经登记到 ``tts-bench/runs/*/synthesis.jsonl`` 的产物，
不会调用 TTS 合成模型。重型依赖均延迟导入：缺少模型、权重或可选包时，
会在逐样本结果中明确写入错误，而不会以缺失分数参与排名。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvaluationSample:
    """一次成功合成及其评估所需的冻结上下文。"""

    run_id: str
    model_id: str
    case_id: str
    audio_path: Path
    audio_sha256: str
    reference_audio_path: Path
    target_text: str
    duration_seconds: float
    wall_seconds: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "runs",
        help="包含多个 <run_id>/synthesis.jsonl 的目录。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "automated-evaluation.example.json",
        help="自动评估 JSON 配置。复制示例后再按校准集调整。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录；省略时按 UTC 时间写入 tts-bench/reports/。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=["audio_health", "wavlm", "asr", "utmosv2"],
        default=None,
        help="只运行指定指标；省略时运行配置中的全部指标。",
    )
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="允许 Hugging Face 评价模型首次下载；默认仅使用本地缓存。",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="任一完整样本缺少所选指标时以非零状态退出。结果文件仍会写出。",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到配置文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置不是有效 JSON：{path} ({exc})") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"配置顶层必须是对象：{path}")
    return loaded


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_relative_path(path: Path) -> str:
    """优先输出仓库相对路径；仓库外的用户数据则保留绝对路径。"""

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} 不是有效 JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number} 必须是 JSON 对象")
        yield record


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for case in read_jsonl(path):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"评测清单缺少 case_id：{path}")
        if case_id in cases:
            raise ValueError(f"评测清单有重复 case_id：{case_id} ({path})")
        cases[case_id] = case
    return cases


def discover_samples(runs_root: Path) -> tuple[list[EvaluationSample], list[dict[str, str]]]:
    """从全部运行记录构建待评估样本，不因单条脏数据终止整批运行。"""

    samples: list[EvaluationSample] = []
    errors: list[dict[str, str]] = []
    manifest_cache: dict[Path, dict[str, dict[str, Any]]] = {}

    for synthesis_path in sorted(runs_root.glob("*/synthesis.jsonl")):
        for record in read_jsonl(synthesis_path):
            if record.get("status") != "complete":
                continue
            run_id = str(record.get("run_id", ""))
            case_id = str(record.get("case_id", ""))
            try:
                audio = record["audio"]
                provenance = record["provenance"]
                manifest_path = project_path(provenance["manifest_path"])
                if manifest_path not in manifest_cache:
                    manifest_cache[manifest_path] = load_manifest(manifest_path)
                case = manifest_cache[manifest_path][case_id]
                reference = case["reference"]
                target = case["target"]
                audio_path = project_path(audio["path"])
                reference_audio_path = project_path(reference["audio_path"])
                if not audio_path.is_file():
                    raise ValueError(f"找不到合成音频：{audio_path}")
                if not reference_audio_path.is_file():
                    raise ValueError(f"找不到参考音频：{reference_audio_path}")
                samples.append(
                    EvaluationSample(
                        run_id=run_id,
                        model_id=str(record["model"]["id"]),
                        case_id=case_id,
                        audio_path=audio_path,
                        audio_sha256=str(audio["sha256"]),
                        reference_audio_path=reference_audio_path,
                        target_text=str(target["text"]),
                        duration_seconds=float(audio["duration_seconds"]),
                        wall_seconds=(
                            float(record["runtime"]["wall_seconds"])
                            if "runtime" in record and "wall_seconds" in record["runtime"]
                            else None
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(
                    {
                        "run_id": run_id or synthesis_path.parent.name,
                        "case_id": case_id or "unknown",
                        "error": str(exc),
                    }
                )

    if not samples and not errors:
        raise ValueError(f"在 {runs_root} 下未找到任何 synthesis.jsonl")
    return samples, errors


def normalize_zh_v1(text: str) -> str:
    """与 asr/normalization/zh-v1.md 一致的无依赖中文 CER 规范化。"""

    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def levenshtein_distance(reference: str, hypothesis: str) -> int:
    """返回两个字符序列的编辑距离，空间复杂度为 O(min(n, m))。"""

    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for ref_index, ref_char in enumerate(reference, 1):
        current = [ref_index]
        for hyp_index, hyp_char in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[hyp_index] + 1,
                    previous[hyp_index - 1] + (ref_char != hyp_char),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    if not reference:
        raise ValueError("规范化后的目标文本为空，无法计算 CER")
    return levenshtein_distance(reference, hypothesis) / len(reference)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def score_higher_is_better(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        raise ValueError("评分归一化的 upper 必须大于 lower")
    return 100 * clamp((value - lower) / (upper - lower), 0, 1)


def score_lower_is_better(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        raise ValueError("评分归一化的 upper 必须大于 lower")
    return 100 * (1 - clamp((value - lower) / (upper - lower), 0, 1))


def weighted_score(component_scores: dict[str, float], weights: dict[str, float]) -> float:
    if set(component_scores) != set(weights):
        raise ValueError("综合分组件与权重键必须完全一致")
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("综合分权重之和必须大于 0")
    return sum(component_scores[name] * weights[name] for name in weights) / total_weight


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lazy_import_audio_stack() -> tuple[Any, Any, Any]:
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError(
            "音频基础依赖缺失。请使用 audio_eval 环境安装 numpy、soundfile、torch、torchaudio。"
        ) from exc
    return np, sf, (torch, torchaudio)


def load_mono_audio(path: Path, target_sample_rate: int) -> tuple[Any, int]:
    np, sf, torch_audio = lazy_import_audio_stack()
    torch, torchaudio = torch_audio
    waveform, source_sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(waveform, axis=1)
    if source_sample_rate == target_sample_rate:
        return mono, source_sample_rate
    tensor = torch.from_numpy(mono).unsqueeze(0)
    resampled = torchaudio.functional.resample(tensor, source_sample_rate, target_sample_rate)
    return resampled.squeeze(0).cpu().numpy(), target_sample_rate


def audio_health(path: Path, config: dict[str, Any]) -> dict[str, float]:
    np, sf, _ = lazy_import_audio_stack()
    waveform, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(waveform, axis=1)
    if not len(mono):
        raise ValueError("音频为空")
    clipping_threshold = float(config["clipping_threshold"])
    clipping_ratio = float(np.mean(np.abs(mono) >= clipping_threshold))
    rms = float(np.sqrt(np.mean(np.square(mono))))
    rms_dbfs = 20 * math.log10(max(rms, 1e-12))
    peak_dbfs = 20 * math.log10(max(float(np.max(np.abs(mono))), 1e-12))
    return {
        "sample_rate_hz": float(sample_rate),
        "duration_seconds": len(mono) / sample_rate,
        "clipping_ratio": clipping_ratio,
        "rms_dbfs": rms_dbfs,
        "peak_dbfs": peak_dbfs,
    }


class WavLMSpeakerEvaluator:
    """用说话人验证版本的 WavLM 计算音色相似度与分窗稳定度。"""

    def __init__(self, config: dict[str, Any], allow_model_download: bool):
        try:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForAudioXVector
        except ImportError as exc:
            raise RuntimeError("WavLM 依赖缺失：需要 transformers、torch。") from exc

        requested_device = config["device"]
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("配置要求 CUDA，但当前 PyTorch 未检测到可用 CUDA。")
        self.torch = torch
        self.device = requested_device
        self.sample_rate_hz = int(config["sample_rate_hz"])
        model_id = str(config["model_id"])
        local_files_only = not allow_model_download
        try:
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(
                model_id, local_files_only=local_files_only
            )
            self.model = AutoModelForAudioXVector.from_pretrained(
                model_id, local_files_only=local_files_only
            ).to(self.device)
        except OSError as exc:
            mode = "本地缓存" if local_files_only else "下载或加载"
            raise RuntimeError(f"无法{mode} WavLM 模型 {model_id}：{exc}") from exc
        self.model.eval()

    def embedding(self, waveform: Any) -> Any:
        inputs = self.feature_extractor(
            waveform,
            sampling_rate=self.sample_rate_hz,
            return_tensors="pt",
            padding=True,
        )
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with self.torch.inference_mode():
            embeddings = self.model(**inputs).embeddings
            return self.torch.nn.functional.normalize(embeddings, dim=-1).squeeze(0).cpu()

    def similarity(self, reference_path: Path, synthesis_path: Path) -> float:
        reference, _ = load_mono_audio(reference_path, self.sample_rate_hz)
        synthesis, _ = load_mono_audio(synthesis_path, self.sample_rate_hz)
        reference_embedding = self.embedding(reference)
        synthesis_embedding = self.embedding(synthesis)
        return float(self.torch.dot(reference_embedding, synthesis_embedding))

    def stability(self, reference_path: Path, synthesis_path: Path, window_seconds: float) -> dict[str, float]:
        reference, _ = load_mono_audio(reference_path, self.sample_rate_hz)
        synthesis, _ = load_mono_audio(synthesis_path, self.sample_rate_hz)
        reference_embedding = self.embedding(reference)
        window_samples = max(1, round(window_seconds * self.sample_rate_hz))
        windows = [synthesis[start : start + window_samples] for start in range(0, len(synthesis), window_samples)]
        scores = [float(self.torch.dot(reference_embedding, self.embedding(window))) for window in windows if len(window)]
        if not scores:
            raise ValueError("无法从合成音频取得稳定度窗口")
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return {
            "window_count": float(len(scores)),
            "mean": mean,
            "min": min(scores),
            "std": math.sqrt(variance),
        }


class WhisperAsrEvaluator:
    """使用固定 ASR 模型产生转写；CER 由主流程按冻结规则计算。"""

    def __init__(self, config: dict[str, Any], allow_model_download: bool):
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("ASR 依赖缺失：需要 transformers、torch。") from exc
        device = 0 if config["device"] == "cuda" and torch.cuda.is_available() else -1
        if config["device"] == "cuda" and device < 0:
            raise RuntimeError("配置要求 CUDA，但当前 PyTorch 未检测到可用 CUDA。")
        model_id = str(config["model_id"])
        try:
            self.pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_id,
                device=device,
                model_kwargs={"local_files_only": not allow_model_download},
            )
        except Exception as exc:  # transformers 的异常类型随版本变化。
            mode = "本地缓存" if not allow_model_download else "下载或加载"
            raise RuntimeError(f"无法{mode} ASR 模型 {model_id}：{exc}") from exc
        self.generate_kwargs = {
            "language": str(config["language"]),
            "task": str(config["task"]),
        }

    def transcribe(self, audio_path: Path) -> str:
        result = self.pipeline(str(audio_path), generate_kwargs=self.generate_kwargs)
        text = result.get("text") if isinstance(result, dict) else None
        if not isinstance(text, str):
            raise RuntimeError("ASR 未返回 text 字段")
        return text


class UtmosV2Evaluator:
    """调用 UTMOSv2 的预训练自然度预测器。"""

    def __init__(self) -> None:
        try:
            import utmosv2
        except ImportError as exc:
            raise RuntimeError(
                "UTMOSv2 未安装。请先按 utmosv2/安装与使用说明.md 安装，再运行全量评估。"
            ) from exc
        self.model = utmosv2.create_model(pretrained=True)

    def predict(self, audio_path: Path) -> float:
        score = self.model.predict(input_path=str(audio_path))
        return float(score.item() if hasattr(score, "item") else score)


def make_metric_error(name: str, exc: Exception) -> dict[str, str]:
    return {"metric": name, "error": str(exc)}


def evaluate_sample(
    sample: EvaluationSample,
    selected_metrics: set[str],
    config: dict[str, Any],
    evaluators: dict[str, Any],
    allow_model_download: bool,
) -> dict[str, Any]:
    """计算一个样本的所有选择指标；每个指标独立失败。"""

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": sample.run_id,
        "model_id": sample.model_id,
        "case_id": sample.case_id,
        "audio": {
            "path": project_relative_path(sample.audio_path),
            "sha256": sample.audio_sha256,
        },
        "metrics": {},
        "errors": [],
    }

    if "audio_health" in selected_metrics:
        try:
            result["metrics"]["audio_health"] = audio_health(sample.audio_path, config["audio_health"])
        except Exception as exc:  # 单样本损坏不影响其他音频。
            result["errors"].append(make_metric_error("audio_health", exc))

    if "wavlm" in selected_metrics:
        try:
            evaluator = evaluators.get("wavlm")
            if evaluator is None:
                evaluator = WavLMSpeakerEvaluator(config["wavlm"], allow_model_download)
                evaluators["wavlm"] = evaluator
            result["metrics"]["wavlm"] = {
                "speaker_similarity": evaluator.similarity(
                    sample.reference_audio_path, sample.audio_path
                ),
                "stability": evaluator.stability(
                    sample.reference_audio_path,
                    sample.audio_path,
                    float(config["wavlm"]["window_seconds"]),
                ),
            }
        except Exception as exc:
            result["errors"].append(make_metric_error("wavlm", exc))

    if "asr" in selected_metrics:
        try:
            evaluator = evaluators.get("asr")
            if evaluator is None:
                evaluator = WhisperAsrEvaluator(config["asr"], allow_model_download)
                evaluators["asr"] = evaluator
            hypothesis_raw = evaluator.transcribe(sample.audio_path)
            reference_normalized = normalize_zh_v1(sample.target_text)
            hypothesis_normalized = normalize_zh_v1(hypothesis_raw)
            result["metrics"]["asr"] = {
                "reference_text": sample.target_text,
                "hypothesis_raw": hypothesis_raw,
                "normalization_id": "zh-v1",
                "reference_normalized": reference_normalized,
                "hypothesis_normalized": hypothesis_normalized,
                "cer": character_error_rate(reference_normalized, hypothesis_normalized),
            }
        except Exception as exc:
            result["errors"].append(make_metric_error("asr", exc))

    if "utmosv2" in selected_metrics:
        try:
            evaluator = evaluators.get("utmosv2")
            if evaluator is None:
                evaluator = UtmosV2Evaluator()
                evaluators["utmosv2"] = evaluator
            result["metrics"]["utmosv2"] = {"predicted_mos": evaluator.predict(sample.audio_path)}
        except Exception as exc:
            result["errors"].append(make_metric_error("utmosv2", exc))

    result["status"] = "complete" if not result["errors"] else "incomplete"
    return result


def ranking_components(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, float]:
    normalizers = config["ranking"]["normalizers"]
    health = metrics["audio_health"]
    return {
        "asr_cer": score_lower_is_better(
            float(metrics["asr"]["cer"]),
            float(normalizers["asr_cer"]["lower"]),
            float(normalizers["asr_cer"]["upper"]),
        ),
        "speaker_similarity": score_higher_is_better(
            float(metrics["wavlm"]["speaker_similarity"]),
            float(normalizers["speaker_similarity"]["lower"]),
            float(normalizers["speaker_similarity"]["upper"]),
        ),
        "utmosv2": score_higher_is_better(
            float(metrics["utmosv2"]["predicted_mos"]),
            float(normalizers["utmosv2"]["lower"]),
            float(normalizers["utmosv2"]["upper"]),
        ),
        "speaker_stability": score_higher_is_better(
            float(metrics["wavlm"]["stability"]["min"]),
            float(normalizers["speaker_stability"]["lower"]),
            float(normalizers["speaker_stability"]["upper"]),
        ),
        "audio_health": score_lower_is_better(
            float(health["clipping_ratio"]),
            float(normalizers["audio_health"]["lower"]),
            float(normalizers["audio_health"]["upper"]),
        ),
    }


def add_ranking(result: dict[str, Any], config: dict[str, Any]) -> None:
    if result["status"] != "complete":
        result["ranking"] = {"status": "missing_metric"}
        return
    try:
        components = ranking_components(result["metrics"], config)
        result["ranking"] = {
            "status": "complete",
            "component_scores": components,
            "configured_score": weighted_score(components, config["ranking"]["weights"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        result["status"] = "incomplete"
        result["errors"].append(make_metric_error("ranking", exc))
        result["ranking"] = {"status": "missing_metric"}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_summary(results: list[dict[str, Any]], input_errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[(result["run_id"], result["model_id"])].append(result)

    summary: list[dict[str, Any]] = []
    for (run_id, model_id), rows in sorted(grouped.items()):
        complete = [row for row in rows if row["status"] == "complete"]
        metric_rows = [row["metrics"] for row in complete]
        summary.append(
            {
                "run_id": run_id,
                "model_id": model_id,
                "case_count": len(rows),
                "complete_case_count": len(complete),
                "incomplete_case_count": len(rows) - len(complete),
                "wavlm_similarity_mean": mean(
                    [float(row["wavlm"]["speaker_similarity"]) for row in metric_rows]
                ),
                "wavlm_stability_min_mean": mean(
                    [float(row["wavlm"]["stability"]["min"]) for row in metric_rows]
                ),
                "asr_cer_mean": mean([float(row["asr"]["cer"]) for row in metric_rows]),
                "utmosv2_mos_mean": mean(
                    [float(row["utmosv2"]["predicted_mos"]) for row in metric_rows]
                ),
                "clipping_ratio_max": max(
                    [float(row["audio_health"]["clipping_ratio"]) for row in metric_rows], default=None
                ),
                "rtf_mean": mean(
                    [
                        row.get("runtime", {}).get("rtf")
                        for row in rows
                        if isinstance(row.get("runtime", {}).get("rtf"), float)
                    ]
                ),
                "configured_score_mean": mean(
                    [float(row["ranking"]["configured_score"]) for row in complete]
                ),
            }
        )
    return summary


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "run_id",
        "model_id",
        "case_count",
        "complete_case_count",
        "incomplete_case_count",
        "wavlm_similarity_mean",
        "wavlm_stability_min_mean",
        "asr_cer_mean",
        "utmosv2_mos_mean",
        "clipping_ratio_max",
        "rtf_mean",
        "configured_score_mean",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    if config.get("schema_version") != "1.0":
        raise ValueError("仅支持 schema_version 为 1.0 的自动评估配置")
    configured_metrics = set(config.get("enabled_metrics", []))
    selected_metrics = set(args.metrics) if args.metrics else configured_metrics
    if not selected_metrics:
        raise ValueError("至少需要启用一个评价指标")
    if not selected_metrics <= {"audio_health", "wavlm", "asr", "utmosv2"}:
        raise ValueError("配置含有不支持的评价指标")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or PROJECT_ROOT / "tts-bench" / "reports" / f"automated-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    samples, input_errors = discover_samples(args.runs_root)
    evaluators: dict[str, Any] = {}
    results: list[dict[str, Any]] = []

    for sample in samples:
        result = evaluate_sample(
            sample,
            selected_metrics,
            config,
            evaluators,
            args.allow_model_download,
        )
        if sample.wall_seconds is not None and sample.duration_seconds > 0:
            result["runtime"] = {"rtf": sample.wall_seconds / sample.duration_seconds}
        add_ranking(result, config)
        results.append(result)

    summary = build_summary(results, input_errors)
    summary.sort(
        key=lambda row: (
            row["configured_score_mean"] is None,
            -(row["configured_score_mean"] or 0),
            row["run_id"],
        )
    )
    write_jsonl(output_dir / "per_case.jsonl", results)
    write_jsonl(output_dir / "input_errors.jsonl", input_errors)
    write_summary_csv(output_dir / "model_summary.csv", summary)
    (output_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "runs_root": str(args.runs_root),
                "selected_metrics": sorted(selected_metrics),
                "allow_model_download": args.allow_model_download,
                "config": config,
                "sample_count": len(samples),
                "input_error_count": len(input_errors),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    incomplete = [result for result in results if result["status"] != "complete"]
    print(f"逐样本结果：{output_dir / 'per_case.jsonl'}")
    print(f"模型汇总：{output_dir / 'model_summary.csv'}")
    print(f"完成：{len(results) - len(incomplete)}/{len(results)}，输入错误：{len(input_errors)}")
    if args.strict and (incomplete or input_errors):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"自动评估失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
