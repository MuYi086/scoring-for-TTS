"""
Run the full local TTS evaluation with GPU-backed neural metrics.

Outputs:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/模型合成音频完整评测.md
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/quality_scores.csv
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_transcripts/*.txt
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_diffs/*.md

Usage:
  conda run -n audio_eval python scripts/evaluate_tts_model_audio_full.py
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import evaluate_tts_model_audio as signal_eval


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REFERENCE_AUDIO = SAMPLE_DIR / "sample.wav"
FULL_REPORT_FILE = SAMPLE_DIR / "模型合成音频完整评测.md"
SCORES_CSV = SAMPLE_DIR / "quality_scores.csv"
TRANSCRIPT_DIR = SAMPLE_DIR / "asr_transcripts"
DIFF_DIR = SAMPLE_DIR / "asr_diffs"

SENSEVOICE_MODEL = Path("/home/muyi086/hf-mirror/FunAudioLLM/SenseVoiceSmall")
SPEECHBRAIN_MODEL = Path("/home/muyi086/hf-mirror/speechbrain/spkrec-ecapa-voxceleb")
NISQA_ROOT = Path("/home/muyi086/github/audio-eval-tools/NISQA")
DNSMOS_ROOT = Path("/home/muyi086/github/audio-eval-tools/DNS-Challenge/DNSMOS")


@dataclasses.dataclass(frozen=True)
class FullMetrics:
    signal: signal_eval.AudioMetrics
    transcript: str
    normalized_transcript: str
    cer: float
    insertions: int
    deletions: int
    substitutions: int
    nisqa_tts: float
    nisqa_mos: float
    nisqa_noisiness: float
    nisqa_discontinuity: float
    nisqa_coloration: float
    nisqa_loudness: float
    dnsmos_ovrl: float
    dnsmos_sig: float
    dnsmos_bak: float
    dnsmos_p808: float
    speaker_similarity: float
    content_score: float
    neural_score: float
    speaker_score: float
    signal_score: float
    total_score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full GPU-backed TTS evaluation")
    parser.add_argument("--sample-dir", type=Path, default=SAMPLE_DIR)
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE)
    parser.add_argument("--reference-audio", type=Path, default=REFERENCE_AUDIO)
    parser.add_argument("--full-output", type=Path, default=FULL_REPORT_FILE)
    parser.add_argument("--scores-csv", type=Path, default=SCORES_CSV)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--segment-seconds", type=float, default=25.0)
    parser.add_argument("--keep-work-dir", action="store_true")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def require_cuda() -> None:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "完整评测要求 GPU，但当前 PyTorch 看不到 CUDA。请用已授权的 "
            "`conda run -n audio_eval python ...` 运行，或先修复 GPU 权限。"
        )
    torch.zeros(1, device="cuda")
    print(f"GPU: {torch.cuda.get_device_name(0)}")


def read_source_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    return text.strip()


def normalize_text(text: str) -> str:
    text = re.sub(r"<\|[^>]+?\|>", "", text)
    chars = []
    for char in text:
        if "\u4e00" <= char <= "\u9fff" or char.isalnum():
            chars.append(char.lower())
    return "".join(chars)


def edit_counts(reference: str, hypothesis: str) -> tuple[int, int, int, int]:
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    dp: list[list[tuple[int, int, int, int]]] = [[(0, 0, 0, 0) for _ in range(cols)] for _ in range(rows)]
    for i in range(1, rows):
        cost, ins, dele, sub = dp[i - 1][0]
        dp[i][0] = (cost + 1, ins, dele + 1, sub)
    for j in range(1, cols):
        cost, ins, dele, sub = dp[0][j - 1]
        dp[0][j] = (cost + 1, ins + 1, dele, sub)
    for i in range(1, rows):
        for j in range(1, cols):
            if reference[i - 1] == hypothesis[j - 1]:
                keep = dp[i - 1][j - 1]
            else:
                cost, ins, dele, sub = dp[i - 1][j - 1]
                keep = (cost + 1, ins, dele, sub + 1)
            cost, ins, dele, sub = dp[i][j - 1]
            insert = (cost + 1, ins + 1, dele, sub)
            cost, ins, dele, sub = dp[i - 1][j]
            delete = (cost + 1, ins, dele + 1, sub)
            dp[i][j] = min(keep, insert, delete, key=lambda item: (item[0], item[3], item[2], item[1]))
    return dp[-1][-1]


def run_asr(model_paths: list[Path], device: str, reference_text: str) -> dict[str, dict[str, Any]]:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    model = AutoModel(
        model=str(SENSEVOICE_MODEL),
        device=device,
        hub="hf",
        disable_update=True,
    )
    reference_normalized = normalize_text(reference_text)
    results: dict[str, dict[str, Any]] = {}
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    DIFF_DIR.mkdir(exist_ok=True)

    for path in model_paths:
        model_name = signal_eval.model_name_from_path(path)
        raw = model.generate(input=str(path), language="zh", use_itn=True, batch_size_s=60)
        transcript = rich_transcription_postprocess(raw[0]["text"])
        normalized = normalize_text(transcript)
        distance, insertions, deletions, substitutions = edit_counts(reference_normalized, normalized)
        cer = distance / max(1, len(reference_normalized))
        (TRANSCRIPT_DIR / f"{model_name}.txt").write_text(transcript + "\n", encoding="utf-8")
        render_asr_diff(
            DIFF_DIR / f"{model_name}.md",
            model_name,
            reference_normalized,
            normalized,
            transcript,
            cer,
            insertions,
            deletions,
            substitutions,
        )
        results[model_name] = {
            "transcript": transcript,
            "normalized": normalized,
            "cer": cer,
            "insertions": insertions,
            "deletions": deletions,
            "substitutions": substitutions,
        }
    return results


def render_asr_diff(
    output: Path,
    model_name: str,
    reference: str,
    hypothesis: str,
    transcript: str,
    cer: float,
    insertions: int,
    deletions: int,
    substitutions: int,
) -> None:
    lines = [
        f"# {model_name} ASR 内容差异",
        "",
        f"- CER（字符错误率）：{cer:.4f}",
        f"- 插入：{insertions}",
        f"- 删除：{deletions}",
        f"- 替换：{substitutions}",
        "",
        "## ASR 转写",
        "",
        transcript,
        "",
        "## 归一化文本",
        "",
        f"- 参考长度：{len(reference)}",
        f"- 转写长度：{len(hypothesis)}",
        "",
        "```text",
        hypothesis,
        "```",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


def write_segments(model_paths: list[Path], work_dir: Path, seconds: float) -> Path:
    import soundfile as sf

    chunk_dir = work_dir / "nisqa_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for path in model_paths:
        model_name = safe_name(signal_eval.model_name_from_path(path))
        audio, sample_rate = sf.read(str(path), always_2d=False)
        chunk_size = int(sample_rate * seconds)
        total = len(audio)
        index = 0
        for start in range(0, total, chunk_size):
            chunk = audio[start : min(total, start + chunk_size)]
            if len(chunk) < sample_rate:
                continue
            sf.write(str(chunk_dir / f"{model_name}__{index:03d}.wav"), chunk, sample_rate)
            index += 1
    return chunk_dir


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def run_nisqa(chunk_dir: Path, work_dir: Path, weight_name: str, output_name: str) -> dict[str, dict[str, float]]:
    output_dir = work_dir / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "NUMBA_CACHE_DIR": str(work_dir / "numba_cache"),
            "MPLCONFIGDIR": str(work_dir / "mpl_cache"),
            "XDG_CACHE_HOME": str(work_dir / "xdg_cache"),
        }
    )
    command = [
        sys.executable,
        str(NISQA_ROOT / "run_predict.py"),
        "--mode",
        "predict_dir",
        "--pretrained_model",
        str(NISQA_ROOT / "weights" / weight_name),
        "--data_dir",
        str(chunk_dir),
        "--num_workers",
        "0",
        "--bs",
        "1",
        "--output_dir",
        str(output_dir),
    ]
    subprocess.run(command, check=True, env=env, cwd=str(NISQA_ROOT))
    csv_path = output_dir / "NISQA_results.csv"
    return average_nisqa_csv(csv_path)


def average_nisqa_csv(path: Path) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            model = row["deg"].split("__", 1)[0]
            grouped.setdefault(model, {})
            for key, value in row.items():
                if key in {"deg", "model"} or value == "":
                    continue
                grouped[model].setdefault(key, []).append(float(value))
    return {
        model: {key: sum(values) / len(values) for key, values in metrics.items()}
        for model, metrics in grouped.items()
    }


def run_dnsmos(model_paths: list[Path]) -> dict[str, dict[str, float]]:
    import librosa
    import numpy as np
    import numpy.polynomial.polynomial as poly
    import onnxruntime as ort
    import soundfile as sf

    sampling_rate = 16000
    input_length = 9.01
    primary = ort.InferenceSession(str(DNSMOS_ROOT / "DNSMOS/sig_bak_ovr.onnx"))
    p808 = ort.InferenceSession(str(DNSMOS_ROOT / "DNSMOS/model_v8.onnx"))

    def audio_melspec(audio):
        mel = librosa.feature.melspectrogram(
            y=audio, sr=sampling_rate, n_fft=321, hop_length=160, n_mels=120
        )
        return ((librosa.power_to_db(mel, ref=np.max) + 40) / 40).T

    def polyfit(sig, bak, ovr):
        p_ovr = np.poly1d([-0.06766283, 1.11546468, 0.04602535])
        p_sig = np.poly1d([-0.08397278, 1.22083953, 0.0052439])
        p_bak = np.poly1d([-0.13166888, 1.60915514, -0.39604546])
        return p_sig(sig), p_bak(bak), p_ovr(ovr)

    results: dict[str, dict[str, float]] = {}
    for path in model_paths:
        audio, input_rate = sf.read(str(path), always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if input_rate != sampling_rate:
            audio = librosa.resample(audio, orig_sr=input_rate, target_sr=sampling_rate)
        required = int(input_length * sampling_rate)
        while len(audio) < required:
            audio = np.append(audio, audio)
        hops = max(1, int(np.floor(len(audio) / sampling_rate) - input_length) + 1)
        values = {"OVRL": [], "SIG": [], "BAK": [], "P808_MOS": []}
        for index in range(hops):
            segment = audio[int(index * sampling_rate) : int((index + input_length) * sampling_rate)]
            if len(segment) < required:
                continue
            features = np.array(segment).astype("float32")[np.newaxis, :]
            p808_features = np.array(audio_melspec(segment[:-160])).astype("float32")[np.newaxis, :, :]
            p808_mos = float(p808.run(None, {"input_1": p808_features})[0][0][0])
            sig_raw, bak_raw, ovr_raw = primary.run(None, {"input_1": features})[0][0]
            sig, bak, ovr = polyfit(sig_raw, bak_raw, ovr_raw)
            values["OVRL"].append(float(ovr))
            values["SIG"].append(float(sig))
            values["BAK"].append(float(bak))
            values["P808_MOS"].append(p808_mos)
        results[signal_eval.model_name_from_path(path)] = {
            key: sum(items) / len(items) if items else 0.0 for key, items in values.items()
        }
    return results


def run_speaker_similarity(model_paths: list[Path], reference_audio: Path, device: str) -> dict[str, float]:
    import torch
    import torch.nn.functional as F
    from speechbrain.inference.speaker import EncoderClassifier

    classifier = EncoderClassifier.from_hparams(
        source=str(SPEECHBRAIN_MODEL),
        savedir=str(Path(tempfile.gettempdir()) / "speechbrain_ecapa_eval"),
        overrides={"pretrained_path": str(SPEECHBRAIN_MODEL)},
        run_opts={"device": device},
    )

    def embedding(path: Path):
        waveform = classifier.load_audio(str(path)).unsqueeze(0).to(device)
        with torch.inference_mode():
            return classifier.encode_batch(waveform).reshape(1, -1)

    reference_embedding = embedding(reference_audio)
    results = {}
    for path in model_paths:
        model_embedding = embedding(path)
        similarity = F.cosine_similarity(reference_embedding, model_embedding).item()
        results[signal_eval.model_name_from_path(path)] = similarity
    return results


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def score_full(
    signal: signal_eval.AudioMetrics,
    asr: dict[str, Any],
    nisqa_tts: dict[str, float],
    nisqa_quality: dict[str, float],
    dnsmos: dict[str, float],
    speaker_similarity: float,
) -> FullMetrics:
    cer = asr["cer"]
    content_score = 35.0 * clamp(1.0 - cer / 0.12)
    naturalness_norm = clamp((nisqa_tts.get("mos_pred", 1.0) - 1.0) / 4.0)
    nisqa_mos_norm = clamp((nisqa_quality.get("mos_pred", 1.0) - 1.0) / 4.0)
    dnsmos_norm = clamp((dnsmos.get("OVRL", 1.0) - 1.0) / 4.0)
    neural_score = 30.0 * (
        naturalness_norm * 0.50
        + dnsmos_norm * 0.30
        + nisqa_mos_norm * 0.20
    )
    speaker_score = 20.0 * clamp((speaker_similarity - 0.55) / 0.40)
    signal_score = 15.0 * clamp(
        (signal.technical_score + signal.completeness_score + signal.naturalness_score) / 75.0
    )
    total = content_score + neural_score + speaker_score + signal_score
    return FullMetrics(
        signal=signal,
        transcript=asr["transcript"],
        normalized_transcript=asr["normalized"],
        cer=cer,
        insertions=asr["insertions"],
        deletions=asr["deletions"],
        substitutions=asr["substitutions"],
        nisqa_tts=nisqa_tts.get("mos_pred", 0.0),
        nisqa_mos=nisqa_quality.get("mos_pred", 0.0),
        nisqa_noisiness=nisqa_quality.get("noi_pred", 0.0),
        nisqa_discontinuity=nisqa_quality.get("dis_pred", 0.0),
        nisqa_coloration=nisqa_quality.get("col_pred", 0.0),
        nisqa_loudness=nisqa_quality.get("loud_pred", 0.0),
        dnsmos_ovrl=dnsmos.get("OVRL", 0.0),
        dnsmos_sig=dnsmos.get("SIG", 0.0),
        dnsmos_bak=dnsmos.get("BAK", 0.0),
        dnsmos_p808=dnsmos.get("P808_MOS", 0.0),
        speaker_similarity=speaker_similarity,
        content_score=content_score,
        neural_score=neural_score,
        speaker_score=speaker_score,
        signal_score=signal_score,
        total_score=total,
    )


def write_scores_csv(path: Path, metrics: list[FullMetrics]) -> None:
    fields = [
        "model",
        "total_score",
        "content_score",
        "neural_score",
        "speaker_score",
        "signal_score",
        "cer",
        "insertions",
        "deletions",
        "substitutions",
        "nisqa_tts",
        "nisqa_mos",
        "nisqa_noisiness",
        "nisqa_discontinuity",
        "nisqa_coloration",
        "nisqa_loudness",
        "dnsmos_ovrl",
        "dnsmos_sig",
        "dnsmos_bak",
        "dnsmos_p808",
        "speaker_similarity",
        "duration",
        "rms_db",
        "active_ratio",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in metrics:
            writer.writerow(
                {
                    "model": item.signal.model_name,
                    "total_score": f"{item.total_score:.4f}",
                    "content_score": f"{item.content_score:.4f}",
                    "neural_score": f"{item.neural_score:.4f}",
                    "speaker_score": f"{item.speaker_score:.4f}",
                    "signal_score": f"{item.signal_score:.4f}",
                    "cer": f"{item.cer:.6f}",
                    "insertions": item.insertions,
                    "deletions": item.deletions,
                    "substitutions": item.substitutions,
                    "nisqa_tts": f"{item.nisqa_tts:.4f}",
                    "nisqa_mos": f"{item.nisqa_mos:.4f}",
                    "nisqa_noisiness": f"{item.nisqa_noisiness:.4f}",
                    "nisqa_discontinuity": f"{item.nisqa_discontinuity:.4f}",
                    "nisqa_coloration": f"{item.nisqa_coloration:.4f}",
                    "nisqa_loudness": f"{item.nisqa_loudness:.4f}",
                    "dnsmos_ovrl": f"{item.dnsmos_ovrl:.4f}",
                    "dnsmos_sig": f"{item.dnsmos_sig:.4f}",
                    "dnsmos_bak": f"{item.dnsmos_bak:.4f}",
                    "dnsmos_p808": f"{item.dnsmos_p808:.4f}",
                    "speaker_similarity": f"{item.speaker_similarity:.6f}",
                    "duration": f"{item.signal.duration:.2f}",
                    "rms_db": f"{item.signal.rms_db:.2f}",
                    "active_ratio": f"{item.signal.active_ratio:.4f}",
                }
            )


def render_report(metrics: list[FullMetrics], reference_text: str, device: str) -> str:
    ranked = sorted(metrics, key=lambda item: item.total_score, reverse=True)
    lines = [
        "# 模型合成音频评测",
        "",
        "## 结论",
        "",
    ]
    for rank, item in enumerate(ranked, start=1):
        lines.append(
            f"{rank}. **{item.signal.model_name}**：{item.total_score:.1f}/100，"
            f"内容准确率 {item.content_score:.1f}/35，神经质量 {item.neural_score:.1f}/30，"
            f"说话人相似度 {item.speaker_score:.1f}/20，信号健康度 {item.signal_score:.1f}/15。"
            f"CER {item.cer:.2%}，ECAPA 相似度 {item.speaker_similarity:.3f}。"
        )
    lines.extend(
        [
            "",
            "本次为局限补全后的完整评测。人工盲听已作为前置筛选完成，不参与本次打分；本次只比较剩余听觉难以区分的候选模型。",
            "",
            "## 流程说明",
            "",
            f"- 运行设备：`{device}`，脚本启动时强制检查 CUDA；GPU 不可用则失败。",
            "- 内容准确率：SenseVoiceSmall（Hugging Face 本地模型）转写后计算 CER（字符错误率）。",
            "- 神经质量：NISQA-TTS 自然度、NISQA v2 质量维度和 DNSMOS OVRL/SIG/BAK/P808。",
            "- 说话人相似度：SpeechBrain ECAPA-TDNN 提取参考音频和合成音频 embedding（嵌入向量），计算 cosine similarity（余弦相似度）。",
            "- 信号健康度：沿用本地 WAV 解析得到的响度、削波、静音、语速和动态范围指标。",
            f"- 合成正文归一化字符数：{len(normalize_text(reference_text))}。",
            "",
            "## 汇总评分",
            "",
            "| 排名 | 模型 | 总分 | 内容准确率 | 神经质量 | 说话人相似度 | 信号健康度 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, item in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | {item.signal.model_name} | {item.total_score:.1f} | "
            f"{item.content_score:.1f} | {item.neural_score:.1f} | "
            f"{item.speaker_score:.1f} | {item.signal_score:.1f} |"
        )
    lines.extend(
        [
            "",
            "## 关键指标",
            "",
            "| 模型 | CER | NISQA-TTS | NISQA MOS | DNSMOS OVRL | DNSMOS SIG | DNSMOS BAK | ECAPA 相似度 | 时长(s) | RMS(dBFS) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in ranked:
        lines.append(
            f"| {item.signal.model_name} | {item.cer:.2%} | {item.nisqa_tts:.3f} | "
            f"{item.nisqa_mos:.3f} | {item.dnsmos_ovrl:.3f} | {item.dnsmos_sig:.3f} | "
            f"{item.dnsmos_bak:.3f} | {item.speaker_similarity:.3f} | "
            f"{item.signal.duration:.2f} | {item.signal.rms_db:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            f"- `samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/quality_scores.csv`",
            f"- `samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_transcripts/`",
            f"- `samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/asr_diffs/`",
            f"- `samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/模型合成音频完整评测.md`",
            "",
            "## 复现命令",
            "",
            "```bash",
            "conda run -n audio_eval python scripts/evaluate_tts_model_audio_full.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    require_cuda()
    sample_dir = require_path(args.sample_dir, "sample dir")
    text_file = require_path(args.text_file, "text file")
    reference_audio = require_path(args.reference_audio, "reference audio")
    for path, label in [
        (SENSEVOICE_MODEL, "SenseVoiceSmall model"),
        (SPEECHBRAIN_MODEL, "SpeechBrain ECAPA model"),
        (NISQA_ROOT / "weights/nisqa_tts.tar", "NISQA-TTS weights"),
        (NISQA_ROOT / "weights/nisqa.tar", "NISQA weights"),
        (DNSMOS_ROOT / "DNSMOS/sig_bak_ovr.onnx", "DNSMOS primary model"),
        (DNSMOS_ROOT / "DNSMOS/model_v8.onnx", "DNSMOS P.808 model"),
    ]:
        require_path(path, label)

    reference_text = read_source_text(text_file)
    text_chars = signal_eval.read_synthesis_text_chars(text_file)
    reference_signal = signal_eval.analyze_audio(
        signal_eval.read_wav(reference_audio), text_chars, "参考音频"
    )
    model_paths = signal_eval.discover_model_wavs(sample_dir, None)
    signal_metrics = {
        signal_eval.model_name_from_path(path): signal_eval.score_metrics(
            signal_eval.analyze_audio(signal_eval.read_wav(path), text_chars, signal_eval.model_name_from_path(path)),
            reference_signal,
        )
        for path in model_paths
    }

    asr_results = run_asr(model_paths, args.device, reference_text)
    dnsmos_results = run_dnsmos(model_paths)
    speaker_results = run_speaker_similarity(model_paths, reference_audio, args.device)

    work_dir = Path(tempfile.mkdtemp(prefix="tts_audio_eval_"))
    try:
        chunk_dir = write_segments(model_paths, work_dir, args.segment_seconds)
        nisqa_tts_results = run_nisqa(chunk_dir, work_dir, "nisqa_tts.tar", "nisqa_tts")
        nisqa_quality_results = run_nisqa(chunk_dir, work_dir, "nisqa.tar", "nisqa_quality")
    finally:
        if args.keep_work_dir:
            print(f"kept work dir: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)

    full_metrics = []
    for path in model_paths:
        model_name = signal_eval.model_name_from_path(path)
        safe = safe_name(model_name)
        full_metrics.append(
            score_full(
                signal_metrics[model_name],
                asr_results[model_name],
                nisqa_tts_results.get(safe, {}),
                nisqa_quality_results.get(safe, {}),
                dnsmos_results.get(model_name, {}),
                speaker_results.get(model_name, 0.0),
            )
        )

    write_scores_csv(args.scores_csv, full_metrics)
    report = render_report(full_metrics, reference_text, args.device)
    args.full_output.write_text(report, encoding="utf-8")
    for item in sorted(full_metrics, key=lambda metric: metric.total_score, reverse=True):
        print(f"{item.signal.model_name}: {item.total_score:.1f}/100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
