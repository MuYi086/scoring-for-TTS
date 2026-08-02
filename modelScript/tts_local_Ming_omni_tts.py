"""使用 Ming-omni-tts-0.5B 本地权重进行语音生成、音色设计或零样本克隆。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "MING_OMNI_TTS_MODEL_PATH",
        "~/hf-mirror/inclusionAI/Ming-omni-tts-0.5B",
    )
)
CODE_PATH = Path(
    os.environ.get("MING_OMNI_TTS_CODE_PATH", "~/tts-depency/Ming-omni-tts")
)
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Ming-omni-tts synthesis")
    parser.add_argument("--code-path", type=Path, default=CODE_PATH, help="官方 Ming-omni-tts 源码目录")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE)
    parser.add_argument("--text", default=None)
    parser.add_argument("--prompt", default="Please generate speech based on the following description.\n")
    parser.add_argument("--ref-audio", type=Path, default=None)
    parser.add_argument("--ref-text", default=None)
    parser.add_argument("--instruction-json", default=None, help="完整控制 JSON，或只传控制字段 JSON")
    parser.add_argument("--style", default=None, help="音色/风格描述，例如 ASMR 耳语")
    parser.add_argument("--emotion", default=None)
    parser.add_argument("--dialect", default=None)
    parser.add_argument("--speed", default=None)
    parser.add_argument("--pitch", default=None)
    parser.add_argument("--volume", default=None)
    parser.add_argument("--output", type=Path, default=SAMPLE_DIR / "Ming-omni-tts-0.5B.wav")
    parser.add_argument("--max-decode-steps", type=int, default=200)
    parser.add_argument("--cfg", type=float, default=2.0)
    parser.add_argument("--sigma", type=float, default=0.25)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label}不存在：{path}")
    return path


def read_text(args: argparse.Namespace) -> str:
    if args.text is not None and args.text.strip():
        return args.text.strip()
    path = require_path(args.text_file, "文本文件")
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def load_upstream(code_path: Path):
    code_path = require_path(code_path, "Ming-omni-tts 源码目录")
    required = ("modeling_bailingmm.py", "spkemb_extractor.py", "audio_tokenizer", "fm")
    missing = [name for name in required if not (code_path / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"{code_path} 不是完整的 Ming-omni-tts 推理仓库，缺少 {', '.join(missing)}；"
            "请按安装指南克隆官方源码。"
        )
    sys.path.insert(0, str(code_path))
    try:
        import torch
        import torchaudio
        from transformers import AutoTokenizer
        from modeling_bailingmm import BailingMMNativeForConditionalGeneration
        from spkemb_extractor import SpkembExtractor
    except ImportError as exc:
        raise RuntimeError(f"Ming-omni-tts 运行时不可导入，缺失：{exc.name or exc}") from exc
    return BailingMMNativeForConditionalGeneration, SpkembExtractor, AutoTokenizer, torch, torchaudio


def build_instruction(args: argparse.Namespace) -> str | None:
    values = {}
    if args.instruction_json:
        try:
            values.update(json.loads(args.instruction_json))
        except json.JSONDecodeError as exc:
            raise ValueError(f"--instruction-json 不是合法 JSON：{exc}") from exc
    for key, value in (
        ("风格", args.style),
        ("情感", args.emotion),
        ("方言", args.dialect),
        ("语速", args.speed),
        ("基频", args.pitch),
        ("音量", args.volume),
    ):
        if value is not None:
            values[key] = value
    if not values:
        return None
    if "audio_sequence" in values:
        return json.dumps(values, ensure_ascii=False)
    item = {
        "序号": 1,
        "说话人": "speaker_1",
        "方言": None,
        "风格": None,
        "语速": None,
        "基频": None,
        "音量": None,
        "情感": None,
        "BGM": {"Genre": None, "Mood": None, "Instrument": None, "Theme": None, "ENV": None, "SNR": None},
        "IP": None,
    }
    item.update({key: value for key, value in values.items() if key in item})
    return json.dumps({"audio_sequence": [item]}, ensure_ascii=False)


def prepare_prompt(torchaudio, torch, ref_audio: Path | None, sample_rate: int, spkemb_extractor):
    if ref_audio is None:
        return None, None, None
    waveform, source_rate = torchaudio.load(str(ref_audio))
    original = waveform
    if source_rate != sample_rate:
        waveform = torchaudio.transforms.Resample(source_rate, sample_rate)(waveform)
    if source_rate != 16000:
        original = torchaudio.transforms.Resample(source_rate, 16000)(original)
    speaker_embedding = spkemb_extractor(original)
    pad_align = int(1 / 12.5 * 4 * sample_rate)
    new_len = (waveform.size(-1) + pad_align - 1) // pad_align * pad_align
    if new_len != waveform.size(-1):
        padded = torch.zeros(1, new_len, dtype=waveform.dtype)
        padded[:, : waveform.size(-1)] = waveform
        waveform = padded
    return waveform, [speaker_embedding], speaker_embedding


def synthesize(args: argparse.Namespace) -> Path:
    if args.local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    BailingMMNativeForConditionalGeneration, SpkembExtractor, AutoTokenizer, torch, torchaudio = load_upstream(args.code_path)
    model_path = require_path(args.model_path, "Ming-omni-tts 模型目录")
    if not torch.cuda.is_available():
        raise RuntimeError("Ming-omni-tts 需要 CUDA GPU。")
    ref_audio = require_path(args.ref_audio, "参考音频") if args.ref_audio is not None else None
    model = BailingMMNativeForConditionalGeneration.from_pretrained(
        str(model_path), torch_dtype=torch.bfloat16, low_cpu_mem_usage=True, local_files_only=args.local_files_only
    ).eval().to(torch.bfloat16).to("cuda")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=args.local_files_only)
    model.tokenizer = tokenizer
    sample_rate = int(model.config.audio_tokenizer_config.sample_rate)
    extractor = None
    if ref_audio is not None:
        extractor = SpkembExtractor(str(model_path / "campplus.onnx"))
    prompt_waveform, speaker_embeddings, _ = prepare_prompt(torchaudio, torch, ref_audio, sample_rate, extractor)
    instruction = build_instruction(args)
    text = read_text(args)
    print(f"model: {model_path}")
    print(f"code: {args.code_path.expanduser().resolve()}")
    print(f"reference audio: {ref_audio or 'none; zero speaker embedding'}")
    with torch.inference_mode():
        waveform = model.generate(
            prompt=args.prompt,
            text=text,
            spk_emb=speaker_embeddings,
            instruction=instruction,
            prompt_waveform=prompt_waveform,
            prompt_text=args.ref_text,
            max_decode_steps=args.max_decode_steps,
            cfg=args.cfg,
            sigma=args.sigma,
            temperature=args.temperature,
            use_zero_spk_emb=ref_audio is None,
        )
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    torchaudio.save(str(output_path), waveform.detach().cpu(), sample_rate)
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
