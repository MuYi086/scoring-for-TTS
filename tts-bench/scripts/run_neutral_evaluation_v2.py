#!/usr/bin/env python3
"""以六个独立后端评价克隆音频，并保留原始参考音频与校准对照。

脚本只读取已经登记的合成记录，不调用 TTS 模型，也不计算跨指标加权总分。
所有评价模型必须从 ``HF_MIRROR_ROOT`` 离线加载。
"""

from __future__ import annotations

import argparse
import csv
import gc
import importlib.metadata
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_automated_evaluation import (  # noqa: E402
    SenseVoiceAsrEvaluator,
    UtmosV2Evaluator,
    WavLMSpeakerEvaluator,
    WhisperAsrEvaluator,
    character_error_rate,
    discover_samples,
    load_json,
    load_manifest,
    load_mono_audio,
    normalize_zh_v1,
    project_path,
    project_relative_path,
    resolve_mirrored_model,
    sha256_file,
)


METRICS = (
    "sensevoice_cer",
    "whisper_cer",
    "wavlm_sim",
    "speechbrain_ecapa_sim",
    "utmosv2",
    "nisqa",
)


@dataclass(frozen=True)
class AudioInput:
    """一条待评价音频及其冻结文本。"""

    audio_id: str
    kind: str
    model_id: str
    run_id: str | None
    case_id: str
    role: str
    path: Path
    sha256: str
    expected_text: str


class SpeechBrainEcapaEvaluator:
    """从本地 SpeechBrain ECAPA-TDNN 检查点提取归一化说话人嵌入。"""

    def __init__(self, config: dict[str, Any]) -> None:
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError as exc:
            raise RuntimeError("SpeechBrain ECAPA 依赖缺失：需要 speechbrain、torch。") from exc

        requested_device = str(config["device"])
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("配置要求 CUDA，但当前 PyTorch 未检测到可用 CUDA。")
        self.torch = torch
        self.sample_rate_hz = int(config["sample_rate_hz"])
        self.device = "cuda:0" if requested_device == "cuda" else requested_device
        model_id = str(config["model_id"])
        model_source = resolve_mirrored_model(model_id)
        savedir = Path(tempfile.gettempdir()) / "scoring-for-tts-speechbrain-ecapa"
        try:
            self.model = EncoderClassifier.from_hparams(
                source=model_source,
                savedir=str(savedir),
                run_opts={"device": self.device},
                overrides={"pretrained_path": model_source},
            )
        except Exception as exc:
            raise RuntimeError(f"无法加载本地 SpeechBrain ECAPA 模型 {model_id}：{exc}") from exc

    def embedding(self, waveform: Any) -> Any:
        tensor = self.torch.from_numpy(waveform).unsqueeze(0)
        with self.torch.inference_mode():
            embedding = self.model.encode_batch(tensor).squeeze()
        return self.torch.nn.functional.normalize(embedding, dim=-1).cpu()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "runs-v2",
        help="包含多个 <run_id>/synthesis.jsonl 的目录。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "config" / "neutral-evaluation-v2.json",
        help="V2 中立评测冻结配置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "tts-bench" / "reports" / "task3-2026-07-19-v2-r02",
        help="原始结果目录。",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=METRICS,
        default=list(METRICS),
        help="只运行指定后端；用于排错或断点续跑。",
    )
    parser.add_argument("--resume", action="store_true", help="从已有输出目录继续并覆盖所选后端。")
    parser.add_argument("--strict", action="store_true", help="所选后端存在任一缺失或错误时返回非零状态。")
    return parser.parse_args()


def write_jsonl_atomic(path: Path, records: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def metric_error(metric: str, exc: Exception) -> dict[str, str]:
    return {"metric": metric, "error": str(exc)}


def clear_metric_error(record: dict[str, Any], metric: str) -> None:
    record["errors"] = [error for error in record["errors"] if error.get("metric") != metric]


def release_model(model: Any) -> None:
    del model
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "2.0":
        raise ValueError("仅支持 schema_version 为 2.0 的中立评测配置")
    if config.get("policy", {}).get("normalization_id") != "zh-v1":
        raise ValueError("当前只实现 zh-v1 文本规范化")
    if not os.environ.get("HF_MIRROR_ROOT"):
        raise ValueError("必须设置 HF_MIRROR_ROOT，V2 评测不允许隐式联网下载")


def build_inputs(
    runs_root: Path,
    config: dict[str, Any],
) -> tuple[list[AudioInput], list[AudioInput]]:
    samples, input_errors = discover_samples(runs_root)
    if input_errors:
        raise ValueError(f"合成记录存在 {len(input_errors)} 条输入错误，拒绝静默略过")

    manifest_path = project_path(config["manifest_path"])
    cases = load_manifest(manifest_path)
    labels = config["case_labels"]
    if set(cases) != set(labels):
        raise ValueError("case_labels 必须与冻结清单中的 case_id 完全一致")

    models = {sample.model_id for sample in samples}
    expected_model_count = int(config["expected_model_count"])
    if len(models) != expected_model_count:
        raise ValueError(f"期望 {expected_model_count} 个模型，实际发现 {len(models)} 个")
    expected_pairs = {(model, case_id) for model in models for case_id in cases}
    actual_pairs = {(sample.model_id, sample.case_id) for sample in samples}
    if actual_pairs != expected_pairs or len(samples) != len(expected_pairs):
        raise ValueError("模型与 case 不是完整笛卡尔积，不能进行成对比较")

    references: list[AudioInput] = []
    for case_id, case in cases.items():
        reference = case["reference"]
        path = project_path(reference["audio_path"])
        if not path.is_file():
            raise ValueError(f"找不到原始参考音频：{path}")
        references.append(
            AudioInput(
                audio_id=f"reference:{case_id}",
                kind="reference",
                model_id="原始参考音频",
                run_id=None,
                case_id=case_id,
                role=str(labels[case_id]),
                path=path,
                sha256=sha256_file(path),
                expected_text=str(reference["transcript"]),
            )
        )

    syntheses: list[AudioInput] = []
    for sample in samples:
        actual_sha256 = sha256_file(sample.audio_path)
        if actual_sha256 != sample.audio_sha256:
            raise ValueError(f"合成音频哈希与登记值不一致：{sample.audio_path}")
        syntheses.append(
            AudioInput(
                audio_id=f"synthesis:{sample.run_id}:{sample.case_id}",
                kind="synthesis",
                model_id=sample.model_id,
                run_id=sample.run_id,
                case_id=sample.case_id,
                role=str(labels[sample.case_id]),
                path=sample.audio_path,
                sha256=actual_sha256,
                expected_text=sample.target_text,
            )
        )
    return references, syntheses


def base_audio_record(audio: AudioInput) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "audio_id": audio.audio_id,
        "kind": audio.kind,
        "model_id": audio.model_id,
        "run_id": audio.run_id,
        "case_id": audio.case_id,
        "role": audio.role,
        "audio": {"path": project_relative_path(audio.path), "sha256": audio.sha256},
        "expected_text": audio.expected_text,
        "metrics": {},
        "errors": [],
    }


def base_similarity_record(audio: AudioInput, reference: AudioInput) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "run_id": audio.run_id,
        "model_id": audio.model_id,
        "case_id": audio.case_id,
        "role": audio.role,
        "reference_audio": {
            "path": project_relative_path(reference.path),
            "sha256": reference.sha256,
        },
        "synthesis_audio": {
            "path": project_relative_path(audio.path),
            "sha256": audio.sha256,
        },
        "metrics": {},
        "errors": [],
    }


def build_calibration_records(references: list[AudioInput]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reference in references:
        rows.append(
            {
                "schema_version": "2.0",
                "control_type": "same_speaker_split_half",
                "left_case_id": reference.case_id,
                "right_case_id": reference.case_id,
                "label": f"{reference.role}原始音频前半段 ↔ 后半段",
                "metrics": {},
                "errors": [],
            }
        )
    for left, right in combinations(references, 2):
        rows.append(
            {
                "schema_version": "2.0",
                "control_type": "different_speaker_reference_pair",
                "left_case_id": left.case_id,
                "right_case_id": right.case_id,
                "label": f"{left.role}原始音频 ↔ {right.role}原始音频",
                "metrics": {},
                "errors": [],
            }
        )
    return rows


def restore_or_create_records(
    output_dir: Path,
    references: list[AudioInput],
    syntheses: list[AudioInput],
    resume: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    audio_path = output_dir / "per_audio.jsonl"
    similarity_path = output_dir / "speaker_similarity.jsonl"
    calibration_path = output_dir / "speaker_calibration.jsonl"
    if resume:
        audio_rows = read_jsonl(audio_path)
        similarity_rows = read_jsonl(similarity_path)
        calibration_rows = read_jsonl(calibration_path)
        if not audio_rows or not similarity_rows or not calibration_rows:
            raise ValueError("--resume 要求三份原始结果文件都已存在")
        return audio_rows, similarity_rows, calibration_rows

    reference_by_case = {item.case_id: item for item in references}
    audio_rows = [base_audio_record(item) for item in [*references, *syntheses]]
    similarity_rows = [
        base_similarity_record(item, reference_by_case[item.case_id]) for item in syntheses
    ]
    return audio_rows, similarity_rows, build_calibration_records(references)


def apply_asr_metric(
    metric: str,
    evaluator_factory: Callable[[], Any],
    inputs: dict[str, AudioInput],
    rows: list[dict[str, Any]],
) -> None:
    evaluator = evaluator_factory()
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, metric)
            try:
                hypothesis_raw = evaluator.transcribe(inputs[row["audio_id"]].path)
                reference_normalized = normalize_zh_v1(row["expected_text"])
                hypothesis_normalized = normalize_zh_v1(hypothesis_raw)
                row["metrics"][metric] = {
                    "hypothesis_raw": hypothesis_raw,
                    "normalization_id": "zh-v1",
                    "reference_normalized": reference_normalized,
                    "hypothesis_normalized": hypothesis_normalized,
                    "cer": character_error_rate(reference_normalized, hypothesis_normalized),
                }
            except Exception as exc:
                row["metrics"].pop(metric, None)
                row["errors"].append(metric_error(metric, exc))
            print(f"[{metric}] {index}/{len(rows)} {row['audio_id']}", flush=True)
    finally:
        release_model(evaluator)


def cosine(left: Any, right: Any) -> float:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("说话人相似度需要 torch。") from exc
    return float(torch.dot(left, right))


def apply_similarity_metric(
    metric: str,
    evaluator: Any,
    references: dict[str, AudioInput],
    syntheses: dict[tuple[str, str], AudioInput],
    rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> None:
    cache: dict[Path, Any] = {}

    def embedding_path(path: Path) -> Any:
        if path not in cache:
            waveform, _ = load_mono_audio(path, evaluator.sample_rate_hz)
            cache[path] = evaluator.embedding(waveform)
        return cache[path]

    for index, row in enumerate(rows, 1):
        clear_metric_error(row, metric)
        try:
            reference = references[row["case_id"]]
            synthesis = syntheses[(row["run_id"], row["case_id"])]
            row["metrics"][metric] = cosine(
                embedding_path(reference.path),
                embedding_path(synthesis.path),
            )
        except Exception as exc:
            row["metrics"].pop(metric, None)
            row["errors"].append(metric_error(metric, exc))
        print(f"[{metric}] {index}/{len(rows)} {row['model_id']} / {row['role']}", flush=True)

    for row in calibration_rows:
        clear_metric_error(row, metric)
        try:
            left = references[row["left_case_id"]]
            right = references[row["right_case_id"]]
            if row["control_type"] == "same_speaker_split_half":
                waveform, _ = load_mono_audio(left.path, evaluator.sample_rate_hz)
                midpoint = len(waveform) // 2
                if midpoint < evaluator.sample_rate_hz:
                    raise ValueError("原始音频过短，无法构造至少一秒的前后半段校准对")
                left_embedding = evaluator.embedding(waveform[:midpoint])
                right_embedding = evaluator.embedding(waveform[midpoint:])
            else:
                left_embedding = embedding_path(left.path)
                right_embedding = embedding_path(right.path)
            row["metrics"][metric] = cosine(left_embedding, right_embedding)
        except Exception as exc:
            row["metrics"].pop(metric, None)
            row["errors"].append(metric_error(metric, exc))


def apply_utmosv2(
    config: dict[str, Any],
    inputs: dict[str, AudioInput],
    rows: list[dict[str, Any]],
) -> None:
    evaluator = UtmosV2Evaluator(config)
    try:
        for index, row in enumerate(rows, 1):
            clear_metric_error(row, "utmosv2")
            try:
                row["metrics"]["utmosv2"] = {
                    "predicted_mos": evaluator.predict(inputs[row["audio_id"]].path)
                }
            except Exception as exc:
                row["metrics"].pop("utmosv2", None)
                row["errors"].append(metric_error("utmosv2", exc))
            print(f"[utmosv2] {index}/{len(rows)} {row['audio_id']}", flush=True)
    finally:
        release_model(evaluator)


def predict_nisqa_batch(config: dict[str, Any], inputs: list[AudioInput]) -> dict[str, float]:
    repository = Path(resolve_mirrored_model(str(config["repository_id"])))
    checkpoint = repository / str(config["checkpoint_path"])
    if not checkpoint.is_file():
        raise RuntimeError(f"找不到 NISQA-TTS 检查点：{checkpoint}")

    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib-task3"))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "numba-task3"))
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))
    try:
        from nisqa.NISQA_model import nisqaModel
    except ImportError as exc:
        raise RuntimeError("无法从本地 NISQA 仓库导入评价器。") from exc

    with tempfile.TemporaryDirectory(prefix="nisqa-task3-") as temporary_dir:
        temporary = Path(temporary_dir)
        csv_path = temporary / "inputs.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["audio_id", "audio_path"])
            writer.writeheader()
            for audio in inputs:
                writer.writerow({"audio_id": audio.audio_id, "audio_path": str(audio.path)})

        args = {
            "mode": "predict_csv",
            "pretrained_model": str(checkpoint),
            "data_dir": str(temporary),
            "csv_file": csv_path.name,
            "csv_deg": "audio_path",
            "num_workers": 0,
            "bs": int(config["batch_size"]),
            "ms_channel": None,
            "tr_bs_val": int(config["batch_size"]),
            "tr_num_workers": 0,
            "tr_device": str(config["device"]),
            "output_dir": None,
        }
        frame = nisqaModel(args).predict()
        return {
            str(row["audio_id"]): float(row["mos_pred"])
            for row in frame.to_dict(orient="records")
        }


def apply_nisqa(
    config: dict[str, Any],
    inputs: list[AudioInput],
    rows: list[dict[str, Any]],
) -> None:
    try:
        scores = predict_nisqa_batch(config, inputs)
    except Exception as exc:
        for row in rows:
            clear_metric_error(row, "nisqa")
            row["metrics"].pop("nisqa", None)
            row["errors"].append(metric_error("nisqa", exc))
        return

    for row in rows:
        clear_metric_error(row, "nisqa")
        try:
            row["metrics"]["nisqa"] = {
                "predicted_mos": scores[row["audio_id"]],
                "model": str(config["model_name"]),
            }
        except KeyError as exc:
            row["metrics"].pop("nisqa", None)
            row["errors"].append(metric_error("nisqa", exc))


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in ["torch", "torchaudio", "transformers", "funasr", "speechbrain", "utmosv2"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def metric_coverage(
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for metric in ["sensevoice_cer", "whisper_cer", "utmosv2", "nisqa"]:
        coverage[metric] = {
            "complete": sum(metric in row["metrics"] for row in audio_rows),
            "expected": len(audio_rows),
        }
    for metric in ["wavlm_sim", "speechbrain_ecapa_sim"]:
        combined = [*similarity_rows, *calibration_rows]
        coverage[metric] = {
            "complete": sum(metric in row["metrics"] for row in combined),
            "expected": len(combined),
        }
    return coverage


def save_state(
    output_dir: Path,
    audio_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
    config: dict[str, Any],
    selected_metrics: list[str],
) -> None:
    write_jsonl_atomic(output_dir / "per_audio.jsonl", audio_rows)
    write_jsonl_atomic(output_dir / "speaker_similarity.jsonl", similarity_rows)
    write_jsonl_atomic(output_dir / "speaker_calibration.jsonl", calibration_rows)
    metadata = {
        "schema_version": "2.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "selected_metrics_this_invocation": selected_metrics,
        "offline": True,
        "cross_metric_weighted_score": False,
        "audio_count": len(audio_rows),
        "synthesis_pair_count": len(similarity_rows),
        "calibration_pair_count": len(calibration_rows),
        "coverage": metric_coverage(audio_rows, similarity_rows, calibration_rows),
        "package_versions": package_versions(),
        "config": config,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> int:
    """使用已解析参数执行一次六后端评测。"""

    config = load_json(args.config)
    validate_config(config)
    selected_metrics = list(dict.fromkeys(args.metrics))

    if args.output_dir.exists() and not args.resume:
        raise ValueError(f"输出目录已存在；如需续跑请增加 --resume：{args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=args.resume)

    references, syntheses = build_inputs(args.runs_root, config)
    all_inputs = [*references, *syntheses]
    inputs_by_id = {item.audio_id: item for item in all_inputs}
    references_by_case = {item.case_id: item for item in references}
    syntheses_by_key = {(str(item.run_id), item.case_id): item for item in syntheses}
    audio_rows, similarity_rows, calibration_rows = restore_or_create_records(
        args.output_dir,
        references,
        syntheses,
        args.resume,
    )

    for metric in selected_metrics:
        print(f"开始评价：{metric}", flush=True)
        if metric == "sensevoice_cer":
            apply_asr_metric(
                metric,
                lambda: SenseVoiceAsrEvaluator(config["sensevoice"]),
                inputs_by_id,
                audio_rows,
            )
        elif metric == "whisper_cer":
            apply_asr_metric(
                metric,
                lambda: WhisperAsrEvaluator(config["whisper"], allow_model_download=False),
                inputs_by_id,
                audio_rows,
            )
        elif metric in {"wavlm_sim", "speechbrain_ecapa_sim"}:
            evaluator = (
                WavLMSpeakerEvaluator(config["wavlm"], allow_model_download=False)
                if metric == "wavlm_sim"
                else SpeechBrainEcapaEvaluator(config["speechbrain_ecapa"])
            )
            try:
                apply_similarity_metric(
                    metric,
                    evaluator,
                    references_by_case,
                    syntheses_by_key,
                    similarity_rows,
                    calibration_rows,
                )
            finally:
                release_model(evaluator)
        elif metric == "utmosv2":
            apply_utmosv2(config["utmosv2"], inputs_by_id, audio_rows)
        elif metric == "nisqa":
            apply_nisqa(config["nisqa"], all_inputs, audio_rows)
        save_state(
            args.output_dir,
            audio_rows,
            similarity_rows,
            calibration_rows,
            config,
            selected_metrics,
        )

    coverage = metric_coverage(audio_rows, similarity_rows, calibration_rows)
    print(json.dumps(coverage, ensure_ascii=False, indent=2), flush=True)
    incomplete_selected = [
        metric
        for metric in selected_metrics
        if coverage[metric]["complete"] != coverage[metric]["expected"]
    ]
    if args.strict and incomplete_selected:
        print(f"以下后端结果不完整：{', '.join(incomplete_selected)}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"V2 中立评测失败：{error}", file=sys.stderr)
        raise SystemExit(2) from error
