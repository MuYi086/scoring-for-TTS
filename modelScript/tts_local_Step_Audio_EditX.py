"""使用 Step-Audio-EditX 官方推理工程进行零样本克隆或音频编辑。"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(
    os.environ.get(
        "STEP_AUDIO_EDITX_MODEL_PATH",
        "~/hf-mirror/stepfun-ai/Step-Audio-EditX",
    )
)
TOKENIZER_PATH = Path(
    os.environ.get("STEP_AUDIO_TOKENIZER_PATH", "~/hf-mirror/stepfun-ai/Step-Audio-Tokenizer")
)
CODE_PATH = Path(
    os.environ.get("STEP_AUDIO_EDITX_CODE_PATH", "~/tts-depency/Step-Audio-EditX")
)
VLLM_CODE_PATH = os.environ.get("VLLM_CODE_PATH")
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
PROMPT_AUDIO = Path(
    os.environ.get(
        "STEP_AUDIO_PROMPT_AUDIO",
        "~/tts-depency/Step-Audio-EditX/assets/test.wav",
    )
)
TEXT_FILE = SAMPLE_DIR / "第一章.md"
DEFAULT_GENERATED_TEXT = "你好，这是一个本地 Step-Audio-EditX 测试。"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Step-Audio-EditX synthesis")
    parser.add_argument("--code-path", type=Path, default=CODE_PATH, help="官方 Step-Audio-EditX 源码目录")
    parser.add_argument(
        "--vllm-code-path",
        type=Path,
        default=Path(VLLM_CODE_PATH).expanduser() if VLLM_CODE_PATH else None,
        help="可选的本地 vLLM 源码目录；默认使用已安装的预编译 vLLM wheel",
    )
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--tokenizer-path", type=Path, default=TOKENIZER_PATH)
    parser.add_argument("--prompt-audio", type=Path, default=PROMPT_AUDIO)
    parser.add_argument("--prompt-text", default="您好，很高兴能为您提供配音服务。选择您感兴趣的音色，让我们一起开启声音创作的奇幻之旅吧。")
    parser.add_argument("--generated-text", default=None)
    parser.add_argument("--text-file", type=Path, default=TEXT_FILE)
    parser.add_argument("--edit-type", choices=("clone", "emotion", "style", "vad", "denoise", "paralinguistic", "speed"), default="clone")
    parser.add_argument("--edit-info", default="")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DIR)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=3072)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--cosyvoice-dtype", choices=("float32", "bfloat16", "float16"), default="bfloat16")
    parser.add_argument("--enforce-eager", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cosyvoice-cuda-graph", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label}不存在：{path}")
    return path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    if not text:
        raise ValueError(f"文本文件为空：{path}")
    return text


def load_upstream(code_path: Path, vllm_code_path: Path | None = None):
    code_path = require_path(code_path, "Step-Audio-EditX 源码目录")
    if not (code_path / "tts.py").exists() or not (code_path / "tokenizer.py").exists():
        raise FileNotFoundError(
            f"{code_path} 不是完整的 Step-Audio-EditX 推理仓库，缺少 tts.py 或 tokenizer.py；"
            "请按安装指南克隆官方源码。"
        )
    if vllm_code_path is not None and vllm_code_path.expanduser().exists():
        sys.path.insert(0, str(vllm_code_path.expanduser().resolve()))
    sys.path.insert(0, str(code_path))
    try:
        import torch
        import torchaudio
        from tokenizer import StepAudioTokenizer
        from tts import StepAudioTTS
    except ImportError as exc:
        raise RuntimeError(
            f"Step-Audio-EditX 运行时不可导入，缺失：{exc.name or exc}。"
            "请在 Step-Audio-EditX 环境安装可运行的 vLLM wheel 及 pyproject.toml 依赖；"
            "仅有 vLLM GitHub 源码还不包含编译扩展。"
        ) from exc
    return StepAudioTokenizer, StepAudioTTS, torch, torchaudio


def synthesize(args: argparse.Namespace) -> Path:
    os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")
    StepAudioTokenizer, StepAudioTTS, torch, torchaudio = load_upstream(
        args.code_path, args.vllm_code_path
    )
    model_path = require_path(args.model_path, "Step-Audio-EditX 模型目录")
    tokenizer_path = require_path(args.tokenizer_path, "Step-Audio-Tokenizer 模型目录")
    prompt_audio = require_path(args.prompt_audio, "参考音频")
    if not torch.cuda.is_available():
        raise RuntimeError("Step-Audio-EditX 需要 CUDA GPU。")
    generated_text = args.generated_text
    if generated_text is None:
        if args.text_file.expanduser().exists():
            generated_text = read_text(args.text_file)
        else:
            generated_text = DEFAULT_GENERATED_TEXT

    print(f"code: {args.code_path.expanduser().resolve()}")
    print(f"model: {model_path}")
    print(f"tokenizer: {tokenizer_path}")
    print(f"edit_type: {args.edit_type}")
    tokenizer = StepAudioTokenizer(str(tokenizer_path), model_source="local")
    model = StepAudioTTS(
        str(model_path),
        tokenizer,
        model_source="local",
        quantization=None,
        tensor_parallel_size=1,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        enforce_eager=args.enforce_eager,
        dtype=args.dtype,
        max_num_seqs=args.max_num_seqs,
        cosyvoice_dtype=args.cosyvoice_dtype,
        cosyvoice_cuda_graph=args.cosyvoice_cuda_graph,
    )

    if args.edit_type == "clone":
        output_audio, output_sr = model.clone(
            prompt_wav_path=str(prompt_audio),
            prompt_text=args.prompt_text,
            target_text=generated_text,
        )
        label = "clone"
    else:
        output_audio, output_sr = model.edit(
            prompt_wav_path=str(prompt_audio),
            prompt_text=args.prompt_text,
            target_text=generated_text,
            edit_type=args.edit_type,
            edit_info=args.edit_info,
        )
        label = args.edit_type + (f"_{args.edit_info}" if args.edit_info else "")

    output_path = args.output.expanduser().resolve() if args.output else args.output_dir.expanduser().resolve() / f"Step-Audio-EditX_{label}.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_audio.ndim == 1:
        output_audio = output_audio.unsqueeze(0)
    torchaudio.save(str(output_path), output_audio.detach().cpu(), output_sr)
    print(f"sample_rate: {output_sr} Hz")
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
