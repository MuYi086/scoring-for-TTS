"""使用本地 MOSS-VoiceGenerator 按自然语言描述设计音色并合成语音。

MOSS-VoiceGenerator 不使用参考音频；它需要额外的 MOSS-Audio-Tokenizer-v2
目录（或可联网下载的模型 ID）作为音频解码器。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "MOSS_VOICEGENERATOR_MODEL_PATH",
        "~/hf-mirror/OpenMOSS-Team/MOSS-VoiceGenerator",
    )
)
CODEC_PATH = os.environ.get(
    "MOSS_AUDIO_TOKENIZER_PATH",
    "~/hf-mirror/openmoss/MOSS-Audio-Tokenizer-v2",
)
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local MOSS-VoiceGenerator synthesis")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--codec-path", default=CODEC_PATH, help="MOSS-Audio-Tokenizer-v2 路径或 Hugging Face ID")
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE)
    parser.add_argument("--text", default=None, help="直接传入文本；传入后优先于 --text-file")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR)
    parser.add_argument(
        "--instruction",
        default="低沉、沉稳、成熟的中文男声，像深夜电台主持一样自然、克制地叙述。",
    )
    parser.add_argument("--max-chars-per-chunk", type=int, default=0, help="0 表示整段生成")
    parser.add_argument("--pause-ms", type=int, default=250)
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--audio-temperature", type=float, default=1.5)
    parser.add_argument("--audio-top-p", type=float, default=0.6)
    parser.add_argument("--audio-top-k", type=int, default=50)
    parser.add_argument("--audio-repetition-penalty", type=float, default=1.1)
    parser.add_argument("--dtype", choices=("auto", "float16", "bfloat16", "float32"), default="auto")
    parser.add_argument("--attn-implementation", choices=("auto", "flash_attention_2", "sdpa", "eager"), default="auto")
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label}不存在：{path}")
    return path


def read_text(path: Path, direct_text: str | None = None) -> str:
    if direct_text is not None and direct_text.strip():
        return direct_text.strip()
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def split_long_sentence(text: str, max_chars: int) -> list[str]:
    parts = re.findall(r".+?[，,、：:]|.+$", text, flags=re.S)
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(part[i : i + max_chars] for i in range(0, len(part), max_chars))
            continue
        candidate = current + part
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = part
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    sentences = re.findall(r".+?[。！？；;!?]|.+$", text, flags=re.S)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_sentence(sentence, max_chars))
            continue
        candidate = current + sentence
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def import_runtime():
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio
        import transformers
        from transformers import AutoModel, AutoProcessor
    except ImportError as exc:
        raise RuntimeError(f"MOSS-VoiceGenerator 运行时不可导入，缺失：{exc.name or exc}") from exc
    return AutoModel, AutoProcessor, np, sf, torch, torchaudio, transformers


def resolve_dtype(torch, requested: str):
    if requested == "auto":
        return torch.bfloat16
    return {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}[requested]


def resolve_attention(torch, requested: str, dtype) -> str:
    torch.backends.cuda.enable_cudnn_sdp(False)
    torch.backends.cuda.enable_flash_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(True)
    if requested != "auto":
        return requested
    if importlib.util.find_spec("flash_attn") is not None and dtype in {torch.float16, torch.bfloat16}:
        major, _minor = torch.cuda.get_device_capability()
        if major >= 8:
            return "flash_attention_2"
    return "sdpa"


def join_waveforms(waveforms: list, sample_rate: int, pause_ms: int, np, torch):
    if not waveforms:
        raise RuntimeError("MOSS-VoiceGenerator 未返回音频。")
    segments = []
    for waveform in waveforms:
        if isinstance(waveform, torch.Tensor):
            audio = waveform.detach().float().cpu().numpy()
        else:
            audio = np.asarray(waveform, dtype=np.float32)
        if audio.ndim == 2:
            audio = audio.mean(axis=0 if audio.shape[0] <= 2 else 1)
        segments.append(audio.reshape(-1).astype(np.float32, copy=False))
    pause = np.zeros(int(sample_rate * max(pause_ms, 0) / 1000), dtype=np.float32)
    joined: list = []
    for index, segment in enumerate(segments):
        joined.append(segment)
        if index + 1 < len(segments) and len(pause):
            joined.append(pause)
    return np.concatenate(joined)


def decode_message(processor, outputs, torch):
    messages = processor.decode(outputs)
    if not messages:
        raise RuntimeError("MOSS-VoiceGenerator 解码结果为空。")
    message = messages[0]
    if message is None or not message.audio_codes_list:
        raise RuntimeError("MOSS-VoiceGenerator 解码结果不包含音频。")
    return message.audio_codes_list[0]


def synthesize(args: argparse.Namespace) -> Path:
    AutoModel, AutoProcessor, np, sf, torch, torchaudio, transformers = import_runtime()
    model_path = require_path(args.model_path, "模型目录")
    text_file = None if args.text is not None and args.text.strip() else require_path(args.text_file, "文本文件")
    if not torch.cuda.is_available():
        raise RuntimeError("MOSS-VoiceGenerator 需要 CUDA GPU。")
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        codec_path = require_path(Path(args.codec_path), "本地音频 tokenizer 目录")
        codec_path = str(codec_path)
    else:
        codec_path = args.codec_path

    # Transformers 4.x 没有该映射；MOSS 远程处理器只需要一个可写映射。
    from transformers import processing_utils

    if not hasattr(processing_utils, "MODALITY_TO_BASE_CLASS_MAPPING"):
        processing_utils.MODALITY_TO_BASE_CLASS_MAPPING = {}

    text_chunks = split_text(read_text(text_file, args.text), args.max_chars_per_chunk)
    dtype = resolve_dtype(torch, args.dtype)
    attention = resolve_attention(torch, args.attn_implementation, dtype)
    print(f"model: {model_path}")
    print(f"codec: {codec_path}")
    print(f"chunks: {len(text_chunks)}; transformers: {transformers.__version__}; attention: {attention}")
    started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        normalize_inputs=True,
        codec_path=codec_path,
    )
    processor.audio_tokenizer = processor.audio_tokenizer.to("cuda")
    model = AutoModel.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        attn_implementation=attention,
        dtype=dtype,
        local_files_only=args.local_files_only,
    ).to("cuda")
    model.eval()

    sample_rate = int(processor.model_config.sampling_rate)
    waveforms = []
    for index, chunk in enumerate(text_chunks, start=1):
        print(f"synthesizing chunk {index}/{len(text_chunks)}")
        conversation = [[processor.build_user_message(text=chunk, instruction=args.instruction)]]
        batch = processor(conversation, mode="generation")
        input_ids = batch["input_ids"].to("cuda")
        attention_mask = batch["attention_mask"].to("cuda")
        with torch.inference_mode():
            outputs = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=args.max_new_tokens,
                audio_temperature=args.audio_temperature,
                audio_top_p=args.audio_top_p,
                audio_top_k=args.audio_top_k,
                audio_repetition_penalty=args.audio_repetition_penalty,
            )
        waveforms.append(decode_message(processor, outputs, torch))

    waveform = join_waveforms(waveforms, sample_rate, args.pause_ms, np, torch)
    elapsed = time.perf_counter() - started
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{model_path.name}_{elapsed:.2f}s_{sample_rate // 1000}khz.wav"
    sf.write(str(output_path), waveform, sample_rate)
    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample_rate: {sample_rate} Hz")
    print(f"output: {output_path}")
    return output_path


def main() -> int:
    try:
        synthesize(parse_args())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
