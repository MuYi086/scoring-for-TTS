"""
Use MiMo-V2.5-TTS cloud API to synthesize the public-domain book sample.

Default output:
samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/mimo-v2.5-tts-voiceclone_${t}_${k}khz.wav

Usage:
  export MIMO_API_KEY=...
  python modelScript/tts_cloud_mimo.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import wave
from io import BytesIO
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "samples/v_zh_046_电台主持-低沉_沉稳_沉浸式"
TEXT_FILE = SAMPLE_DIR / "第一章.md"
REF_AUDIO = SAMPLE_DIR / "sample.wav"
BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5-tts-voiceclone"
DEFAULT_INSTRUCTION = "低沉、沉稳、沉浸式，像电台主持一样自然叙述。"
DEFAULT_VOICE = "mimo_default"
MAX_VOICE_BASE64_BYTES = 10 * 1024 * 1024
MODELS = (
    "mimo-v2.5-tts",
    "mimo-v2.5-tts-voiceclone",
    "mimo-v2.5-tts-voicedesign",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MiMo-V2.5-TTS cloud voice synthesis")
    parser.add_argument(
        "--api-key",
        default=None,
        help="MiMo API Key. Defaults to MIMO_API_KEY env var",
    )
    parser.add_argument("--base-url", default=BASE_URL, help="MiMo OpenAI-compatible API base URL")
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL, help="MiMo TTS model id")
    parser.add_argument(
        "--text-file",
        type=Path,
        default=TEXT_FILE,
        help="Text/Markdown file to synthesize",
    )
    parser.add_argument(
        "--ref-audio",
        type=Path,
        default=REF_AUDIO,
        help="Reference audio for mimo-v2.5-tts-voiceclone",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="Built-in voice id for mimo-v2.5-tts, such as mimo_default, 冰糖, 茉莉, 苏打 or 白桦",
    )
    parser.add_argument(
        "--instruction",
        default=DEFAULT_INSTRUCTION,
        help=(
            "User-role instruction. For voiceclone/built-in voices it controls style; "
            "for voicedesign it describes the target voice."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SAMPLE_DIR,
        help="Directory for output wav when --output is not set",
    )
    parser.add_argument("--output", type=Path, default=None, help="Exact output wav path")
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=120,
        help="Maximum text characters per synthesis chunk. 0 disables chunking.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=250,
        help="Silence inserted between synthesized chunks",
    )
    parser.add_argument(
        "--optimize-text-preview",
        action="store_true",
        help="Pass optimize_text_preview=true for mimo-v2.5-tts-voicedesign",
    )
    parser.add_argument(
        "--auth-header",
        choices=("api-key", "bearer", "both"),
        default="api-key",
        help="Authentication header style. Official curl examples use api-key.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print chunk/request summary without calling MiMo",
    )
    return parser.parse_args()


def require_path(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return path


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    return re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)


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


def resolve_api_key(args: argparse.Namespace) -> str:
    api_key = args.api_key or os.environ.get("MIMO_API_KEY")
    if not api_key:
        raise RuntimeError("MiMo API key is required. Pass --api-key or set MIMO_API_KEY.")
    return api_key


def audio_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".wav":
        return "audio/wav"
    if ext == ".mp3":
        return "audio/mpeg"
    raise ValueError(f"MiMo voiceclone only supports wav/mp3 reference audio, got: {path}")


def encode_reference_audio(path: Path) -> str:
    audio_bytes = path.read_bytes()
    encoded = base64.b64encode(audio_bytes)
    if len(encoded) > MAX_VOICE_BASE64_BYTES:
        raise ValueError(
            "Base64 encoded reference audio exceeds MiMo's 10 MB voiceclone limit: "
            f"{len(encoded) / 1024 / 1024:.2f} MB"
        )
    return f"data:{audio_mime_type(path)};base64,{encoded.decode('utf-8')}"


def build_messages(instruction: str, chunk: str) -> list[dict[str, str]]:
    return [
        {"role": "user", "content": instruction.strip()},
        {"role": "assistant", "content": chunk},
    ]


def build_audio_payload(args: argparse.Namespace, ref_audio: Path | None) -> dict[str, Any]:
    audio: dict[str, Any] = {"format": "wav"}
    if args.model == "mimo-v2.5-tts":
        audio["voice"] = args.voice
    elif args.model == "mimo-v2.5-tts-voiceclone":
        if ref_audio is None:
            raise RuntimeError("reference audio is required for mimo-v2.5-tts-voiceclone")
        audio["voice"] = encode_reference_audio(ref_audio)
    elif args.model == "mimo-v2.5-tts-voicedesign":
        if args.optimize_text_preview:
            audio["optimize_text_preview"] = True
    else:
        raise ValueError(f"unsupported model: {args.model}")
    return audio


def request_headers(api_key: str, auth_header: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if auth_header in {"api-key", "both"}:
        headers["api-key"] = api_key
    if auth_header in {"bearer", "both"}:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiMo HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiMo request failed: {exc.reason}") from exc

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"MiMo returned non-JSON response: {response_body[:500]}") from exc


def extract_audio_bytes(response: dict[str, Any]) -> bytes:
    try:
        encoded = response["choices"][0]["message"]["audio"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        message = f"MiMo response does not contain choices[0].message.audio.data: {response}"
        raise RuntimeError(message) from exc
    return base64.b64decode(encoded)


def read_wav_params(audio_bytes: bytes) -> wave._wave_params:
    with wave.open(BytesIO(audio_bytes), "rb") as reader:
        params = reader.getparams()
    if params.comptype != "NONE":
        raise RuntimeError(f"compressed wav is not supported for chunk joining: {params.comptype}")
    return params


def join_wav_bytes(chunks: list[bytes], pause_ms: int) -> tuple[bytes, int]:
    if not chunks:
        raise RuntimeError("MiMo returned no audio chunks.")

    first_params = read_wav_params(chunks[0])
    sample_rate = int(first_params.framerate)
    frame_size = first_params.nchannels * first_params.sampwidth
    pause_frames = max(0, int(sample_rate * pause_ms / 1000))
    pause = b"\x00" * pause_frames * frame_size

    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams(first_params)
        for index, chunk in enumerate(chunks):
            with wave.open(BytesIO(chunk), "rb") as reader:
                params = reader.getparams()
                if params[:3] != first_params[:3] or params[4:] != first_params[4:]:
                    raise RuntimeError(
                        "all MiMo wav chunks must share channels, sample width and sample rate; "
                        f"chunk 1={first_params}, chunk {index + 1}={params}"
                    )
                writer.writeframes(reader.readframes(reader.getnframes()))
            if index < len(chunks) - 1 and pause:
                writer.writeframes(pause)

    return output.getvalue(), sample_rate


def khz_from_sample_rate(sample_rate: int) -> str:
    khz = sample_rate / 1000
    return f"{khz:g}"


def elapsed_label(seconds: float) -> str:
    return f"{seconds:.2f}s"


def resolve_output_path(args: argparse.Namespace, elapsed: float, sample_rate: int) -> Path:
    if args.output is not None:
        return args.output.expanduser().resolve()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = (
        f"{args.model}_{elapsed_label(elapsed)}_"
        f"{khz_from_sample_rate(sample_rate)}khz.wav"
    )
    return output_dir / output_name


def synthesize(args: argparse.Namespace) -> Path | None:
    api_key = "" if args.dry_run else resolve_api_key(args)
    text_file = require_path(args.text_file, "text file")
    ref_audio = None
    if args.model == "mimo-v2.5-tts-voiceclone":
        ref_audio = require_path(args.ref_audio, "reference audio")

    text = read_text(text_file)
    chunks = split_text(text, args.max_chars_per_chunk)
    audio_payload = build_audio_payload(args, ref_audio)

    print(f"model: {args.model}")
    print(f"text: {text_file} ({len(text)} chars)")
    print(
        "chunks: "
        + ", ".join(
            f"{index + 1}/{len(chunks)}:{len(chunk)} chars"
            for index, chunk in enumerate(chunks)
        )
    )
    if ref_audio is not None:
        print(f"reference audio: {ref_audio}")
    elif args.model == "mimo-v2.5-tts":
        print(f"voice: {args.voice}")
    print(f"instruction: {args.instruction or 'empty'}")
    print(f"base_url: {args.base_url}")

    if args.dry_run:
        print("dry_run: true; skip MiMo request")
        return None

    url = chat_completions_url(args.base_url)
    headers = request_headers(api_key, args.auth_header)
    started = time.perf_counter()
    audio_chunks = []

    for index, chunk in enumerate(chunks, start=1):
        print(f"synthesizing chunk {index}/{len(chunks)} ({len(chunk)} chars)")
        payload = {
            "model": args.model,
            "messages": build_messages(args.instruction, chunk),
            "audio": audio_payload,
        }
        response = post_json(url, payload, headers, args.timeout)
        audio_chunks.append(extract_audio_bytes(response))

    wav_bytes, sample_rate = join_wav_bytes(audio_chunks, args.pause_ms)
    elapsed = time.perf_counter() - started
    output_path = resolve_output_path(args, elapsed, sample_rate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wav_bytes)

    print(f"elapsed: {elapsed:.2f}s")
    print(f"sample rate: {sample_rate} Hz ({khz_from_sample_rate(sample_rate)} kHz)")
    print(f"output: {output_path}")
    return output_path


def main() -> int:
    args = parse_args()
    try:
        synthesize(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
