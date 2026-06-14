"""
Evaluate cloned TTS WAV files with reproducible local signal metrics.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/模型合成音频评测.md

This script intentionally uses only the Python standard library. It supports
PCM WAV, IEEE-float WAV, and common WAVE_FORMAT_EXTENSIBLE wrappers.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import re
import statistics
import struct
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
REFERENCE_AUDIO = SAMPLE_DIR / "sample.wav"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REPORT_FILE = SAMPLE_DIR / "模型合成音频评测.md"
DEFAULT_MODEL_PATTERNS = (
    "dots.tts-base_*.wav",
    "MOSS-TTS-Local-Transformer_*.wav",
    "Qwen3-TTS-12Hz-1.7B-Base_*.wav",
    "VoxCPM2_*.wav",
)

MIN_DB = -120.0
TARGET_TEXT_CPS_LOW = 3.2
TARGET_TEXT_CPS_HIGH = 6.2
TARGET_ACTIVE_CPS_LOW = 4.0
TARGET_ACTIVE_CPS_HIGH = 8.0


@dataclasses.dataclass(frozen=True)
class WavAudio:
    path: Path
    sample_rate: int
    channels: int
    bits_per_sample: int
    format_tag: int
    format_name: str
    samples: list[float]

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate if self.sample_rate else 0.0


@dataclasses.dataclass(frozen=True)
class AudioMetrics:
    path: Path
    model_name: str
    sample_rate: int
    channels: int
    bits_per_sample: int
    format_name: str
    duration: float
    peak: float
    rms_db: float
    crest_db: float
    dc_offset: float
    clipping_percent: float
    active_duration: float
    active_ratio: float
    silence_ratio: float
    leading_silence: float
    trailing_silence: float
    pause_count: int
    pause_total: float
    pause_median: float
    frame_dynamic_range_db: float
    zcr_per_second: float
    high_freq_proxy_db: float
    f0_median: float | None
    f0_iqr: float | None
    voiced_frame_ratio: float
    chars_per_second: float
    active_chars_per_second: float
    technical_score: float = 0.0
    completeness_score: float = 0.0
    clone_proxy_score: float = 0.0
    naturalness_score: float = 0.0
    total_score: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cloned TTS WAV files.")
    parser.add_argument("--sample-dir", type=Path, default=SAMPLE_DIR, help="Directory containing WAV files")
    parser.add_argument("--reference-audio", type=Path, default=REFERENCE_AUDIO, help="Reference voice WAV")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE, help="Synthesized source text")
    parser.add_argument("--output", type=Path, default=REPORT_FILE, help="Markdown report path")
    parser.add_argument(
        "--model-wav",
        type=Path,
        action="append",
        default=None,
        help="Model WAV to evaluate. Can be provided multiple times. Defaults to known files.",
    )
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def read_wav(path: Path) -> WavAudio:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"not a RIFF/WAVE file: {path}")

    fmt_chunk: bytes | None = None
    data_chunk: bytes | None = None
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", data, pos + 4)[0]
        start = pos + 8
        end = start + chunk_size
        if end > len(data):
            raise ValueError(f"invalid WAV chunk size in {path}")
        if chunk_id == b"fmt ":
            fmt_chunk = data[start:end]
        elif chunk_id == b"data":
            data_chunk = data[start:end]
        pos = end + (chunk_size % 2)

    if fmt_chunk is None or data_chunk is None:
        raise ValueError(f"missing fmt or data chunk: {path}")
    if len(fmt_chunk) < 16:
        raise ValueError(f"invalid fmt chunk: {path}")

    format_tag, channels, sample_rate, _, block_align, bits = struct.unpack_from(
        "<HHIIHH", fmt_chunk, 0
    )
    effective_tag = format_tag
    if format_tag == 65534 and len(fmt_chunk) >= 40:
        effective_tag = struct.unpack_from("<H", fmt_chunk, 24)[0]

    samples = decode_samples(data_chunk, effective_tag, channels, bits, block_align, path)
    return WavAudio(
        path=path,
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits,
        format_tag=effective_tag,
        format_name=format_name(effective_tag),
        samples=samples,
    )


def format_name(format_tag: int) -> str:
    if format_tag == 1:
        return "PCM"
    if format_tag == 3:
        return "IEEE float"
    return f"unknown({format_tag})"


def decode_samples(
    data: bytes, format_tag: int, channels: int, bits: int, block_align: int, path: Path
) -> list[float]:
    if channels <= 0 or block_align <= 0:
        raise ValueError(f"invalid channel or block alignment in {path}")

    bytes_per_sample = bits // 8
    if bytes_per_sample * channels > block_align:
        raise ValueError(f"invalid bits/block alignment in {path}")

    frame_count = len(data) // block_align
    samples: list[float] = []

    for frame_index in range(frame_count):
        frame_start = frame_index * block_align
        channel_values = []
        for channel in range(channels):
            offset = frame_start + channel * bytes_per_sample
            channel_values.append(decode_one_sample(data, offset, format_tag, bits, path))
        samples.append(sum(channel_values) / len(channel_values))

    return samples


def decode_one_sample(data: bytes, offset: int, format_tag: int, bits: int, path: Path) -> float:
    if format_tag == 1:
        if bits == 8:
            return (data[offset] - 128) / 128.0
        if bits == 16:
            return struct.unpack_from("<h", data, offset)[0] / 32768.0
        if bits == 24:
            raw = data[offset : offset + 3]
            value = int.from_bytes(raw + (b"\xff" if raw[2] & 0x80 else b"\x00"), "little", signed=True)
            return value / 8388608.0
        if bits == 32:
            return struct.unpack_from("<i", data, offset)[0] / 2147483648.0
    elif format_tag == 3:
        if bits == 32:
            return float(struct.unpack_from("<f", data, offset)[0])
        if bits == 64:
            return float(struct.unpack_from("<d", data, offset)[0])
    raise ValueError(f"unsupported WAV format in {path}: tag={format_tag}, bits={bits}")


def read_synthesis_text_chars(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def db(value: float) -> float:
    if value <= 0:
        return MIN_DB
    return 20.0 * math.log10(value)


def amp(db_value: float) -> float:
    return 10.0 ** (db_value / 20.0)


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.median(values)


def iqr(values: list[float]) -> float:
    if not values:
        return 0.0
    return percentile(values, 75) - percentile(values, 25)


def frame_rms_values(samples: list[float], sample_rate: int, frame_ms: int = 50) -> list[float]:
    frame_size = max(1, int(sample_rate * frame_ms / 1000))
    values = []
    for start in range(0, len(samples), frame_size):
        frame = samples[start : start + frame_size]
        if not frame:
            continue
        values.append(math.sqrt(sum(sample * sample for sample in frame) / len(frame)))
    return values


def silence_runs(active_flags: list[bool], frame_seconds: float) -> list[tuple[float, int, int]]:
    runs = []
    start: int | None = None
    for index, active in enumerate(active_flags):
        if not active and start is None:
            start = index
        elif active and start is not None:
            runs.append(((index - start) * frame_seconds, start, index - 1))
            start = None
    if start is not None:
        runs.append(((len(active_flags) - start) * frame_seconds, start, len(active_flags) - 1))
    return runs


def estimate_f0(samples: list[float], sample_rate: int, active_flags: list[bool]) -> tuple[float | None, float | None, float]:
    if not samples or not active_flags:
        return None, None, 0.0

    target_rate = 8000
    stride = max(1, round(sample_rate / target_rate))
    effective_rate = sample_rate / stride
    downsampled = samples[::stride]
    frame_ms = 30
    hop_ms = 50
    frame_size = max(1, int(effective_rate * frame_ms / 1000))
    hop_size = max(1, int(effective_rate * hop_ms / 1000))
    min_lag = max(1, int(effective_rate / 300))
    max_lag = max(min_lag + 1, int(effective_rate / 55))
    source_frame_seconds = 0.05

    f0_values: list[float] = []
    tested = 0
    for start in range(0, max(0, len(downsampled) - frame_size), hop_size):
        source_flag_index = int((start / effective_rate) / source_frame_seconds)
        if source_flag_index >= len(active_flags) or not active_flags[source_flag_index]:
            continue
        frame = downsampled[start : start + frame_size]
        mean_value = sum(frame) / len(frame)
        centered = [value - mean_value for value in frame]
        energy = sum(value * value for value in centered)
        if energy <= 1e-8:
            continue
        tested += 1
        best_lag = 0
        best_corr = -1.0
        max_frame_lag = min(max_lag, len(centered) - 2)
        for lag in range(min_lag, max_frame_lag + 1):
            numerator = 0.0
            delayed_energy = 0.0
            for index in range(0, len(centered) - lag):
                a = centered[index]
                b = centered[index + lag]
                numerator += a * b
                delayed_energy += b * b
            if delayed_energy <= 1e-8:
                continue
            corr = numerator / math.sqrt(energy * delayed_energy)
            if corr > best_corr:
                best_corr = corr
                best_lag = lag
        if best_lag and best_corr >= 0.35:
            f0_values.append(effective_rate / best_lag)

    if not f0_values:
        return None, None, 0.0
    voiced_ratio = len(f0_values) / tested if tested else 0.0
    return median(f0_values), iqr(f0_values), voiced_ratio


def zcr_per_second(samples: list[float], duration: float) -> float:
    if len(samples) < 2 or duration <= 0:
        return 0.0
    changes = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous >= 0 > sample):
            changes += 1
        previous = sample
    return changes / duration


def high_freq_proxy_db(samples: list[float]) -> float:
    if len(samples) < 2:
        return MIN_DB
    energy = sum(sample * sample for sample in samples) / len(samples)
    diff_energy = sum((samples[index] - samples[index - 1]) ** 2 for index in range(1, len(samples))) / (
        len(samples) - 1
    )
    if energy <= 0:
        return MIN_DB
    return db(math.sqrt(diff_energy / energy))


def analyze_audio(audio: WavAudio, text_chars: int, model_name: str) -> AudioMetrics:
    samples = audio.samples
    sample_count = len(samples)
    duration = audio.duration
    peak = max((abs(sample) for sample in samples), default=0.0)
    rms = math.sqrt(sum(sample * sample for sample in samples) / sample_count) if sample_count else 0.0
    dc_offset = sum(samples) / sample_count if sample_count else 0.0
    clipping_percent = (
        100.0 * sum(1 for sample in samples if abs(sample) >= 0.999) / sample_count if sample_count else 0.0
    )
    frame_values = frame_rms_values(samples, audio.sample_rate)
    noise_floor = percentile(frame_values, 10)
    active_threshold = max(noise_floor * 4.0, amp(-45.0))
    active_flags = [value >= active_threshold for value in frame_values]
    frame_seconds = 0.05
    active_frames = sum(1 for flag in active_flags if flag)
    active_duration = min(duration, active_frames * frame_seconds)
    active_ratio = active_duration / duration if duration > 0 else 0.0
    silence_ratio = 1.0 - active_ratio

    runs = silence_runs(active_flags, frame_seconds)
    pause_runs = [seconds for seconds, start, end in runs if seconds >= 0.25 and start > 0 and end < len(active_flags) - 1]
    leading_silence = 0.0
    trailing_silence = 0.0
    if runs and runs[0][1] == 0:
        leading_silence = runs[0][0]
    if runs and runs[-1][2] == len(active_flags) - 1:
        trailing_silence = runs[-1][0]

    active_frame_db = [db(value) for value, active in zip(frame_values, active_flags) if active]
    frame_dynamic_range_db = percentile(active_frame_db, 95) - percentile(active_frame_db, 10)
    f0_median, f0_iqr, voiced_frame_ratio = estimate_f0(samples, audio.sample_rate, active_flags)

    return AudioMetrics(
        path=audio.path,
        model_name=model_name,
        sample_rate=audio.sample_rate,
        channels=audio.channels,
        bits_per_sample=audio.bits_per_sample,
        format_name=audio.format_name,
        duration=duration,
        peak=peak,
        rms_db=db(rms),
        crest_db=db(peak / rms) if rms > 0 else 0.0,
        dc_offset=dc_offset,
        clipping_percent=clipping_percent,
        active_duration=active_duration,
        active_ratio=active_ratio,
        silence_ratio=silence_ratio,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
        pause_count=len(pause_runs),
        pause_total=sum(pause_runs),
        pause_median=median(pause_runs),
        frame_dynamic_range_db=frame_dynamic_range_db,
        zcr_per_second=zcr_per_second(samples, duration),
        high_freq_proxy_db=high_freq_proxy_db(samples),
        f0_median=f0_median,
        f0_iqr=f0_iqr,
        voiced_frame_ratio=voiced_frame_ratio,
        chars_per_second=text_chars / duration if duration > 0 else 0.0,
        active_chars_per_second=text_chars / active_duration if active_duration > 0 else 0.0,
    )


def score_range(value: float, low: float, high: float, tolerance: float) -> float:
    if low <= value <= high:
        return 1.0
    if value < low:
        return max(0.0, 1.0 - (low - value) / tolerance)
    return max(0.0, 1.0 - (value - high) / tolerance)


def score_similarity(value: float, reference: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(value - reference) / tolerance)


def optional_value(value: float | None, fallback: float = 0.0) -> float:
    return value if value is not None else fallback


def score_metrics(metrics: AudioMetrics, reference: AudioMetrics) -> AudioMetrics:
    sample_rate_score = min(1.0, metrics.sample_rate / 24000.0)
    channels_score = 1.0 if metrics.channels == 1 else 0.8
    loudness_score = score_range(metrics.rms_db, -26.0, -14.0, 12.0)
    peak_score = score_range(metrics.peak, 0.08, 0.98, 0.25)
    clipping_score = max(0.0, 1.0 - metrics.clipping_percent / 0.1)
    dc_score = max(0.0, 1.0 - abs(metrics.dc_offset) / 0.02)
    crest_score = score_range(metrics.crest_db, 6.0, 24.0, 8.0)
    technical = 25.0 * weighted_average(
        [
            (sample_rate_score, 0.15),
            (channels_score, 0.05),
            (loudness_score, 0.22),
            (peak_score, 0.18),
            (clipping_score, 0.22),
            (dc_score, 0.08),
            (crest_score, 0.10),
        ]
    )

    total_speed_score = score_range(metrics.chars_per_second, TARGET_TEXT_CPS_LOW, TARGET_TEXT_CPS_HIGH, 2.0)
    active_speed_score = score_range(
        metrics.active_chars_per_second, TARGET_ACTIVE_CPS_LOW, TARGET_ACTIVE_CPS_HIGH, 3.0
    )
    active_ratio_score = score_range(metrics.active_ratio, 0.62, 0.94, 0.18)
    edge_silence_score = max(0.0, 1.0 - (metrics.leading_silence + metrics.trailing_silence) / 3.0)
    completeness = 25.0 * weighted_average(
        [
            (total_speed_score, 0.34),
            (active_speed_score, 0.26),
            (active_ratio_score, 0.25),
            (edge_silence_score, 0.15),
        ]
    )

    ref_f0 = optional_value(reference.f0_median, optional_value(metrics.f0_median, 120.0))
    ref_iqr = optional_value(reference.f0_iqr, optional_value(metrics.f0_iqr, 20.0))
    f0_score = score_similarity(optional_value(metrics.f0_median, ref_f0 + 80), ref_f0, 55.0)
    f0_iqr_score = score_similarity(optional_value(metrics.f0_iqr, ref_iqr + 30), ref_iqr, 45.0)
    zcr_score = score_similarity(metrics.zcr_per_second, reference.zcr_per_second, 1100.0)
    brightness_score = score_similarity(metrics.high_freq_proxy_db, reference.high_freq_proxy_db, 10.0)
    loudness_ref_score = score_similarity(metrics.rms_db, reference.rms_db, 12.0)
    clone_proxy = 25.0 * weighted_average(
        [
            (f0_score, 0.32),
            (f0_iqr_score, 0.18),
            (zcr_score, 0.16),
            (brightness_score, 0.16),
            (loudness_ref_score, 0.18),
        ]
    )

    pause_rate = metrics.pause_count / max(metrics.duration / 60.0, 0.01)
    pause_rate_score = score_range(pause_rate, 2.0, 12.0, 7.0)
    pause_total_score = score_range(metrics.pause_total / metrics.duration, 0.02, 0.22, 0.16)
    dynamic_score = score_range(metrics.frame_dynamic_range_db, 8.0, 28.0, 10.0)
    voiced_score = score_range(metrics.voiced_frame_ratio, 0.40, 0.92, 0.25)
    natural_speed_score = score_range(metrics.chars_per_second, 3.4, 5.8, 1.8)
    naturalness = 25.0 * weighted_average(
        [
            (pause_rate_score, 0.20),
            (pause_total_score, 0.20),
            (dynamic_score, 0.22),
            (voiced_score, 0.18),
            (natural_speed_score, 0.20),
        ]
    )

    total = technical + completeness + clone_proxy + naturalness
    return dataclasses.replace(
        metrics,
        technical_score=technical,
        completeness_score=completeness,
        clone_proxy_score=clone_proxy,
        naturalness_score=naturalness,
        total_score=total,
    )


def weighted_average(items: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in items)
    if total_weight <= 0:
        return 0.0
    return sum(max(0.0, min(1.0, value)) * weight for value, weight in items) / total_weight


def discover_model_wavs(sample_dir: Path, explicit: list[Path] | None) -> list[Path]:
    if explicit:
        return [require_path(path, "model wav") for path in explicit]

    paths: list[Path] = []
    for pattern in DEFAULT_MODEL_PATTERNS:
        matches = sorted(sample_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
        if not matches:
            raise FileNotFoundError(f"no WAV matches pattern {pattern} in {sample_dir}")
        paths.append(matches[0].resolve())
    return paths


def model_name_from_path(path: Path) -> str:
    match = re.match(r"(.+)_\d+(?:\.\d+)?s_\d+(?:\.\d+)?khz\.wav$", path.name)
    if match:
        return match.group(1)
    return path.stem


def format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def format_optional(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "未检出"
    return f"{value:.{digits}f}"


def metric_warning(metrics: AudioMetrics, rank: int) -> str:
    warnings = []
    if metrics.clipping_percent > 0.01:
        warnings.append("存在削波风险")
    if metrics.rms_db < -30:
        warnings.append("整体响度偏低")
    if metrics.rms_db > -12:
        warnings.append("整体响度偏高")
    if metrics.chars_per_second < TARGET_TEXT_CPS_LOW:
        warnings.append("语速偏慢")
    if metrics.chars_per_second > TARGET_TEXT_CPS_HIGH:
        warnings.append("语速偏快或疑似缺字")
    if metrics.active_ratio < 0.55:
        warnings.append("静音占比偏高")
    if abs(metrics.dc_offset) > 0.02:
        warnings.append("DC 偏移偏高")
    if not warnings:
        warnings.append("主要硬指标正常")
    return f"第 {rank} 名；" + "，".join(warnings)


def render_report(reference: AudioMetrics, metrics: list[AudioMetrics], text_chars: int) -> str:
    ranked = sorted(metrics, key=lambda item: item.total_score, reverse=True)
    lines = [
        "# 模型合成音频评测",
        "",
        "## 结论",
        "",
    ]
    for rank, item in enumerate(ranked, start=1):
        lines.append(
            f"{rank}. **{item.model_name}**：{item.total_score:.1f}/100，"
            f"技术质量 {item.technical_score:.1f}，完整性/语速 {item.completeness_score:.1f}，"
            f"参考音色代理匹配 {item.clone_proxy_score:.1f}，叙事自然度 {item.naturalness_score:.1f}。"
            f"{metric_warning(item, rank)}。"
        )

    lines.extend(
        [
            "",
            "本次评测建议优先试听排名靠前的模型；客观分数用于筛掉明显的响度、削波、停顿、语速和参考音色偏离问题，不能替代最终人工听评。",
            "",
            "## 流程说明",
            "",
            "- 参考标准：语音质量的权威流程通常以 ITU-T P.800 主观 MOS（平均意见分）为金标准；PESQ/POLQA/STOI 等客观指标需要干净参考语音或授权实现。本任务只有短参考音色和长合成文本，因此采用可本地复现的无参考信号指标加参考音色代理距离。",
            "- 输入：参考音频 `sample.wav`，合成文本 `第一章.md`，合成正文字符数 "
            f"{text_chars}。",
            "- 评分：总分 100 分，由技术质量、完整性/语速、参考音色代理匹配、叙事自然度四项各 25 分组成。",
            "- 时长口径：报告中的时长从 WAV `data` chunk（音频数据块）计算；文件名里的 `xxs` 是合成耗时，不用于语速或质量评分。",
            "- 局限：脚本不做 ASR（自动语音识别）逐字核对，也不做神经 MOS 预测；如需上线级结论，应补充盲听 ABX、MOS 打分表和人工错漏字标注。",
            "",
            "## 汇总评分",
            "",
            "| 排名 | 模型 | 总分 | 技术质量 | 完整性/语速 | 参考音色代理匹配 | 叙事自然度 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, item in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | {item.model_name} | {item.total_score:.1f} | {item.technical_score:.1f} | "
            f"{item.completeness_score:.1f} | {item.clone_proxy_score:.1f} | {item.naturalness_score:.1f} |"
        )

    lines.extend(
        [
            "",
            "## 关键客观指标",
            "",
            "| 模型 | 时长(s) | 采样率(Hz) | 格式 | RMS(dBFS) | 峰值 | 削波(%) | 语速(字/s) | 有声占比 | 停顿数 | 基频中位(Hz) | 动态范围(dB) |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in ranked:
        lines.append(
            f"| {item.model_name} | {item.duration:.2f} | {item.sample_rate} | "
            f"{item.format_name}/{item.bits_per_sample}bit | {item.rms_db:.2f} | {item.peak:.3f} | "
            f"{item.clipping_percent:.4f} | {item.chars_per_second:.2f} | {item.active_ratio:.2f} | "
            f"{item.pause_count} | {format_optional(item.f0_median)} | {item.frame_dynamic_range_db:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 参考音频指标",
            "",
            f"- 文件：`{reference.path.relative_to(REPO_ROOT)}`",
            f"- 时长：{reference.duration:.2f}s；采样率：{reference.sample_rate}Hz；格式：{reference.format_name}/{reference.bits_per_sample}bit",
            f"- RMS：{reference.rms_db:.2f} dBFS；峰值：{reference.peak:.3f}；基频中位：{format_optional(reference.f0_median)} Hz；过零率：{reference.zcr_per_second:.1f}/s",
            "",
            "## 文件清单",
            "",
        ]
    )
    for item in ranked:
        lines.append(f"- `{item.path.relative_to(REPO_ROOT)}`")
    lines.extend(
        [
            "",
            "## 复现命令",
            "",
            "```bash",
            "python scripts/evaluate_tts_model_audio.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    sample_dir = require_path(args.sample_dir, "sample dir")
    reference_path = require_path(args.reference_audio, "reference audio")
    text_file = require_path(args.text_file, "text file")
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text_chars = read_synthesis_text_chars(text_file)
    reference = analyze_audio(read_wav(reference_path), text_chars, "参考音频")
    model_paths = discover_model_wavs(sample_dir, args.model_wav)
    scored = [
        score_metrics(analyze_audio(read_wav(path), text_chars, model_name_from_path(path)), reference)
        for path in model_paths
    ]
    report = render_report(reference, scored, text_chars)
    output_path.write_text(report, encoding="utf-8")
    print(f"wrote report: {output_path}")
    for item in sorted(scored, key=lambda metric: metric.total_score, reverse=True):
        print(f"{item.model_name}: {item.total_score:.1f}/100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
