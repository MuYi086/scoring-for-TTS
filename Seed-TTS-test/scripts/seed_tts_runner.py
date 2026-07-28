#!/usr/bin/env python3
"""逐条串行生成 Seed-TTS-Eval 中文基准音频。

本文件只负责编排：每次进程只加载一个模型，并在模型常驻期间按官方清单的
原始顺序逐条写入 ``<utt>.wav``。它不下载模型、不启动评分，也不会读取本任务
明确排除的参考项目 Python 代码；IndexTTS2 和 LongCat 必须显式提供各自独立的
官方源码目录。
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import hashlib
import importlib.metadata
import json
import os
import random
import shutil
import sys
import time
import traceback
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
SEED_TTS_ROOT = SCRIPT_DIR.parent
DEFAULT_RESULT_ROOT = SEED_TTS_ROOT / "result"
CONFIG_PATH = SCRIPT_DIR / "model-config.json"


class SeedTtsError(RuntimeError):
    """可读的运行前置条件或合成失败错误。"""


@dataclass(frozen=True)
class SeedItem:
    split: str
    utt: str
    prompt_text: str
    prompt_wav: Path
    infer_text: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_dump_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedTtsError(f"缺少配置文件：{path}") from exc
    if not isinstance(value, dict):
        raise SeedTtsError(f"配置文件不是 JSON 对象：{path}")
    return value


def require_directory(value: str | None, label: str) -> Path:
    if not value:
        raise SeedTtsError(f"必须设置 {label}，不能隐式猜测机器路径。")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SeedTtsError(f"{label} 不是存在的目录：{path}")
    return path


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SeedTtsError(f"{label}不存在：{resolved}")
    return resolved


def assert_valid_utt(utt: str, source: Path, line_number: int) -> None:
    if not utt or Path(utt).name != utt or utt.endswith(".wav") or "/" in utt or "\\" in utt or utt in {".", ".."}:
        raise SeedTtsError(f"{source}:{line_number} 的 utt 非法：{utt!r}")


def parse_meta_list(data_root: Path, split: str, list_name: str) -> list[SeedItem]:
    list_path = require_file(data_root / list_name, f"{split} 官方清单")
    entries: list[SeedItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(list_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) != 4:
            raise SeedTtsError(f"{list_path}:{line_number} 应为四列 utt|参考文本|参考音频|目标文本，实际为 {len(fields)} 列。")
        utt, prompt_text, prompt_rel, infer_text = fields
        assert_valid_utt(utt, list_path, line_number)
        if utt in seen:
            raise SeedTtsError(f"{list_path}:{line_number} 的 utt 重复：{utt}")
        if not prompt_text or not infer_text:
            raise SeedTtsError(f"{list_path}:{line_number} 的参考文本或目标文本为空。")
        prompt_wav = (list_path.parent / prompt_rel).resolve()
        if not prompt_wav.is_file():
            raise SeedTtsError(f"{list_path}:{line_number} 的参考音频不存在：{prompt_wav}")
        seen.add(utt)
        entries.append(SeedItem(split, utt, prompt_text, prompt_wav, infer_text))
    if not entries:
        raise SeedTtsError(f"官方清单为空：{list_path}")
    return entries


def wav_info(path: Path) -> dict[str, int]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SeedTtsError(f"未生成有效 WAV 文件：{path}")
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as reader:
            frame_rate = reader.getframerate()
            frame_count = reader.getnframes()
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
    except (wave.Error, EOFError) as exc:
        raise SeedTtsError(f"输出不是可读取的 RIFF WAV：{path}（{exc}）") from exc
    if frame_rate <= 0 or frame_count <= 0 or channels <= 0 or sample_width <= 0:
        raise SeedTtsError(f"输出 WAV 元数据无效：{path}")
    return {
        "sample_rate": frame_rate,
        "frames": frame_count,
        "channels": channels,
        "sample_width": sample_width,
        "duration_ms": round(frame_count * 1000 / frame_rate),
    }


def stable_item_seed(base_seed: int, utt: str) -> int:
    """让断点续跑与从头运行在同一 utt 上使用相同的随机种子。"""
    offset = int.from_bytes(hashlib.sha256(utt.encode("utf-8")).digest()[:4], "big")
    return (base_seed + offset) % 2_147_483_647


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def source_revision(path: Path | None) -> str | None:
    if path is None:
        return None
    git_dir = path / ".git"
    if not git_dir.exists():
        return None
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = git_dir / value[5:]
        return ref.read_text(encoding="utf-8").strip() if ref.is_file() else None
    return value


def resolve_dtype(torch: Any, name: str) -> Any:
    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    try:
        return mapping[name]
    except KeyError as exc:
        raise SeedTtsError(f"不支持的 dtype：{name}") from exc


def require_cuda(torch: Any, model_name: str) -> str:
    if not torch.cuda.is_available():
        raise SeedTtsError(f"{model_name} 要求可用的 CUDA GPU；请在可访问 GPU 的终端运行。")
    return "cuda"


def set_torch_seed(torch: Any, seed: int, *, numpy_module: Any | None = None) -> None:
    random.seed(seed)
    if numpy_module is not None:
        numpy_module.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def to_mono_float32(audio: Any, numpy_module: Any) -> Any:
    waveform = numpy_module.asarray(audio, dtype=numpy_module.float32)
    if waveform.ndim == 2:
        waveform = waveform.mean(axis=0 if waveform.shape[0] <= 2 else 1)
    return waveform.reshape(-1)


class Backend:
    """一次运行只加载一次的模型后端。"""

    def __init__(self, model_path: Path, code_path: Path | None, parameters: dict[str, Any], cache_dir: Path):
        self.model_path = model_path
        self.code_path = code_path
        self.parameters = parameters
        self.cache_dir = cache_dir

    def load(self) -> None:
        raise NotImplementedError

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        raise NotImplementedError

    def close(self) -> None:
        gc.collect()
        torch = getattr(self, "torch", None)
        if torch is not None and torch.cuda.is_available():
            with contextlib.suppress(Exception):
                torch.cuda.synchronize()
            with contextlib.suppress(Exception):
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()


class DotsBackend(Backend):
    def load(self) -> None:
        try:
            import numpy as np
            import soundfile as sf
            import torch
            from dots_tts.runtime import DotsTtsRuntime
            from dots_tts.utils.logging import configure_logging
            from dots_tts.utils.util import seed_everything
        except ImportError as exc:
            raise SeedTtsError(f"dots.tts 运行时不可导入：{exc}") from exc
        require_cuda(torch, "dots.tts-base")
        configure_logging()
        self.np, self.sf, self.torch, self.seed_everything = np, sf, torch, seed_everything
        self.runtime = DotsTtsRuntime.from_pretrained(
            str(self.model_path),
            precision=self.parameters["precision"],
            max_generate_length=self.parameters["max_generate_length"],
        )

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        self.seed_everything(seed)
        result = self.runtime.generate(
            text=item.infer_text,
            prompt_audio_path=str(item.prompt_wav),
            prompt_text=item.prompt_text,
            language=self.parameters["language"],
            template_name=None,
            ode_method=self.parameters["ode_method"],
            num_steps=self.parameters["num_steps"],
            guidance_scale=self.parameters["guidance_scale"],
            speaker_scale=self.parameters["speaker_scale"],
            normalize_text=False,
            profile_inference=False,
        )
        self.sf.write(str(destination), result["audio"].float().cpu().squeeze().numpy(), int(self.runtime.sample_rate))


class IndexTtsBackend(Backend):
    def load(self) -> None:
        if self.code_path is None or not (self.code_path / "indextts").is_dir():
            raise SeedTtsError("IndexTTS2 必须设置 SEED_TTS_INDEXTTS_CODE_PATH，且目录内必须有官方 indextts 包。")
        if str(self.code_path) not in sys.path:
            sys.path.insert(0, str(self.code_path))
        try:
            import torch
            from indextts.infer_v2 import IndexTTS2
        except ImportError as exc:
            raise SeedTtsError(f"IndexTTS2 官方运行时不可导入：{exc}") from exc
        require_cuda(torch, "IndexTTS2")
        self.torch = torch
        aux_dir = self.model_path / "hf_cache"
        self.model = IndexTTS2(
            model_dir=str(self.model_path),
            cfg_path=str(self.model_path / "config.yaml"),
            aux_paths={
                "w2v_bert": str(aux_dir / "w2v-bert-2.0"),
                "semantic_codec": str(aux_dir / "semantic_codec_model.safetensors"),
                "campplus": str(aux_dir / "campplus_cn_common.bin"),
                "bigvgan": str(aux_dir / "bigvgan"),
            },
            device=None,
            use_fp16=self.parameters["use_fp16"],
            use_cuda_kernel=self.parameters["use_cuda_kernel"],
            use_deepspeed=self.parameters["use_deepspeed"],
            use_accel=self.parameters["use_accel"],
            use_torch_compile=self.parameters["use_torch_compile"],
        )

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed)
        self.model.infer(
            spk_audio_prompt=str(item.prompt_wav),
            text=item.infer_text,
            output_path=str(destination),
            emo_audio_prompt=None,
            emo_alpha=1.0,
            emo_vector=None,
            use_emo_text=False,
            emo_text=None,
            interval_silence=self.parameters["interval_silence"],
            max_text_tokens_per_segment=self.parameters["max_text_tokens_per_segment"],
            num_beams=self.parameters["num_beams"],
            verbose=True,
        )


class LongCatBackend(Backend):
    def load(self) -> None:
        if self.code_path is None or not (self.code_path / "audiodit").is_dir():
            raise SeedTtsError("LongCat 必须设置 SEED_TTS_LONGCAT_CODE_PATH，且目录内必须有官方 audiodit 包。")
        if str(self.code_path) not in sys.path:
            sys.path.insert(0, str(self.code_path))
        try:
            import librosa
            import numpy as np
            import soundfile as sf
            import torch
            import torch.nn.functional as F
            import audiodit  # noqa: F401
            from audiodit import AudioDiTModel
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise SeedTtsError(f"LongCat-AudioDiT 官方运行时不可导入：{exc}") from exc
        device = require_cuda(torch, "LongCat-AudioDiT-1B")
        self.np, self.sf, self.torch, self.F, self.librosa, self.device = np, sf, torch, F, librosa, device
        torch.backends.cudnn.benchmark = False
        self.model = AudioDiTModel.from_pretrained(str(self.model_path), local_files_only=True).to(device)
        if self.parameters["vae_dtype"] == "float16" and hasattr(self.model.vae, "to_half"):
            self.model.vae.to_half()
        else:
            self.model.vae.to(resolve_dtype(torch, self.parameters["vae_dtype"]))
        self.model.eval()
        tokenizer_source = self.model.config.text_encoder_model
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, local_files_only=True, fix_mistral_regex=True)
        except TypeError:
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, local_files_only=True)
        self.sample_rate = int(self.model.config.sampling_rate)
        self.full_hop = int(self.model.config.latent_hop)
        self.max_duration = float(self.model.config.max_wav_duration)

    @staticmethod
    def _normalize(text: str) -> str:
        import re

        return re.sub(r"\s+", " ", re.sub(r"[\"“”‘’]", " ", text.lower())).strip()

    @staticmethod
    def _approx_duration(text: str, max_duration: float) -> float:
        compact = "".join(text.split())
        zh = sum("\u4e00" <= char <= "\u9fff" for char in compact)
        en = sum(char.isalpha() for char in compact)
        other = len(compact) - zh - en
        return min(max_duration, (zh + other if zh > en else en + other) * (0.21 if zh > en else 0.082))

    def _prompt_audio(self, path: Path) -> tuple[Any, int]:
        audio, _ = self.librosa.load(str(path), sr=self.sample_rate, mono=True)
        prompt = self.torch.from_numpy(audio).float().unsqueeze(0).unsqueeze(0)
        with self.torch.inference_mode():
            encoded = self.model.vae.encode(prompt.to(self.device))
        return prompt, int(encoded.shape[-1])

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed, numpy_module=self.np)
        prompt_audio, prompt_frames = self._prompt_audio(item.prompt_wav)
        target = self._normalize(item.infer_text)
        prompt_text = self._normalize(item.prompt_text)
        inputs = self.tokenizer([f"{prompt_text} {target}"], padding="longest", return_tensors="pt")
        estimated = self._approx_duration(target, self.max_duration) * self.parameters["duration_scale"]
        duration = max(prompt_frames + 1, int(round(estimated * self.sample_rate / self.full_hop)) + prompt_frames)
        duration = min(duration, int(self.max_duration * self.sample_rate / self.full_hop))
        with self.torch.inference_mode():
            output = self.model(
                input_ids=inputs.input_ids.to(self.device),
                attention_mask=inputs.attention_mask.to(self.device),
                prompt_audio=prompt_audio,
                duration=duration,
                steps=self.parameters["nfe"],
                cfg_strength=self.parameters["guidance_strength"],
                guidance_method=self.parameters["guidance_method"],
            )
        self.sf.write(str(destination), output.waveform.squeeze().detach().cpu().numpy(), self.sample_rate)


class MossBackend(Backend):
    def load(self) -> None:
        codec_path = require_directory(os.environ.get("SEED_TTS_MOSS_CODEC_PATH"), "SEED_TTS_MOSS_CODEC_PATH")
        try:
            import torch
            import torchaudio
            import transformers.processing_utils as processing_utils
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:
            raise SeedTtsError(f"MOSS-TTS 运行时不可导入：{exc}") from exc
        if not hasattr(processing_utils, "MODALITY_TO_BASE_CLASS_MAPPING"):
            raise SeedTtsError("MOSS-TTS 需要含 MODALITY_TO_BASE_CLASS_MAPPING 的 Transformers 版本。")
        device = require_cuda(torch, "MOSS-TTS-Local-Transformer-v1.5")
        self.torch, self.torchaudio, self.device = torch, torchaudio, device
        self._patch_torch_compat()
        self.processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True, codec_path=str(codec_path))
        self.processor.audio_tokenizer = self.processor.audio_tokenizer.to(device)
        self.model = AutoModel.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            attn_implementation=self.parameters["attn_implementation"],
            dtype=resolve_dtype(torch, self.parameters["dtype"]),
            local_files_only=True,
        ).to(device)
        self.model.eval()

    def _patch_torch_compat(self) -> None:
        original_pad = self.torch.nn.utils.rnn.pad_sequence
        if "padding_side" not in __import__("inspect").signature(original_pad).parameters:
            def pad_sequence_compat(sequences: Any, batch_first: bool = False, padding_value: float = 0.0, padding_side: str = "right") -> Any:
                if padding_side == "right":
                    return original_pad(sequences, batch_first=batch_first, padding_value=padding_value)
                if padding_side != "left":
                    raise ValueError(f"未知 padding_side：{padding_side}")
                padded = original_pad([item.flip(0) for item in sequences], batch_first=batch_first, padding_value=padding_value)
                return padded.flip(1 if batch_first else 0)
            self.torch.nn.utils.rnn.pad_sequence = pad_sequence_compat
        original_autocast = self.torch.is_autocast_enabled
        try:
            original_autocast("cuda")
        except TypeError:
            self.torch.is_autocast_enabled = lambda device_type=None: original_autocast()

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed)
        conversation = [self.processor.build_user_message(text=item.infer_text, reference=[str(item.prompt_wav)], language=self.parameters["language"])]
        batch = self.processor([conversation], mode="generation")
        kwargs = {
            "max_new_tokens": self.parameters["max_new_tokens"],
            "audio_temperature": self.parameters["audio_temperature"],
            "audio_top_p": self.parameters["audio_top_p"],
            "audio_top_k": self.parameters["audio_top_k"],
            "audio_repetition_penalty": self.parameters["audio_repetition_penalty"],
        }
        with self.torch.inference_mode():
            output = self.model.generate(input_ids=batch["input_ids"].to(self.device), attention_mask=batch["attention_mask"].to(self.device), **kwargs)
            decoded = self.processor.decode(output)
        audio_parts = []
        for message in decoded:
            if message is not None:
                audio_parts.extend(audio.to(self.torch.float32).cpu() for audio in message.audio_codes_list if audio is not None)
        if not audio_parts:
            raise SeedTtsError("MOSS-TTS 未返回解码后的音频。")
        waveform = self.torch.cat([item.unsqueeze(0) if item.ndim == 1 else item for item in audio_parts], dim=-1)
        self.torchaudio.save(str(destination), waveform, int(self.processor.model_config.sampling_rate))


class OmniVoiceBackend(Backend):
    def load(self) -> None:
        try:
            import numpy as np
            import soundfile as sf
            import torch
            from omnivoice import OmniVoice
        except ImportError as exc:
            raise SeedTtsError(f"OmniVoice 运行时不可导入：{exc}") from exc
        require_cuda(torch, "OmniVoice")
        self.np, self.sf, self.torch = np, sf, torch
        self.model = OmniVoice.from_pretrained(str(self.model_path), device_map="cuda:0", dtype=resolve_dtype(torch, self.parameters["dtype"]), local_files_only=True)
        self.sample_rate = int(getattr(self.model, "sampling_rate", 24000))

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed, numpy_module=self.np)
        prompt = self.model.create_voice_clone_prompt(ref_audio=str(item.prompt_wav), ref_text=item.prompt_text, preprocess_prompt=self.parameters["preprocess_prompt"])
        generated = self.model.generate(
            text=item.infer_text,
            language=self.parameters["language"],
            voice_clone_prompt=prompt,
            instruct=None,
            num_step=self.parameters["num_step"],
            guidance_scale=self.parameters["guidance_scale"],
            speed=self.parameters["speed"],
            duration=None,
            t_shift=self.parameters["t_shift"],
            denoise=self.parameters["denoise"],
            postprocess_output=self.parameters["postprocess_output"],
            layer_penalty_factor=self.parameters["layer_penalty_factor"],
            position_temperature=self.parameters["position_temperature"],
            class_temperature=self.parameters["class_temperature"],
            audio_chunk_duration=self.parameters["audio_chunk_duration"],
            audio_chunk_threshold=self.parameters["audio_chunk_threshold"],
            pad_duration=self.parameters["pad_duration"],
            fade_duration=self.parameters["fade_duration"],
        )
        if not generated:
            raise SeedTtsError("OmniVoice 未返回音频。")
        self.sf.write(str(destination), to_mono_float32(generated[0], self.np), self.sample_rate)


class Qwen3Backend(Backend):
    def load(self) -> None:
        try:
            import numpy as np
            import soundfile as sf
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise SeedTtsError(f"Qwen3-TTS 运行时不可导入：{exc}") from exc
        require_cuda(torch, "Qwen3-TTS")
        self.np, self.sf, self.torch = np, sf, torch
        self.model = Qwen3TTSModel.from_pretrained(
            str(self.model_path), device_map="cuda:0", dtype=resolve_dtype(torch, self.parameters["dtype"]), attn_implementation=self.parameters["attn_implementation"], local_files_only=True
        )

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed, numpy_module=self.np)
        prompt = self.model.create_voice_clone_prompt(ref_audio=str(item.prompt_wav), ref_text=item.prompt_text, x_vector_only_mode=False)
        wavs, sample_rate = self.model.generate_voice_clone(
            text=item.infer_text,
            language=self.parameters["language"],
            voice_clone_prompt=prompt,
            max_new_tokens=self.parameters["max_new_tokens"],
        )
        waveform = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        self.sf.write(str(destination), to_mono_float32(waveform, self.np), int(sample_rate))


class VoxCpm2Backend(Backend):
    def load(self) -> None:
        try:
            import inspect
            import numpy as np
            import soundfile as sf
            import torch
            from voxcpm import VoxCPM
        except ImportError as exc:
            raise SeedTtsError(f"VoxCPM2 运行时不可导入：{exc}") from exc
        require_cuda(torch, "VoxCPM2")
        self.inspect, self.np, self.sf, self.torch, self.VoxCPM = inspect, np, sf, torch, VoxCPM
        signature = inspect.signature(VoxCPM.from_pretrained)
        supported = set(signature.parameters)
        kwargs = {"load_denoiser": self.parameters["load_denoiser"], "local_files_only": True, "optimize": self.parameters["optimize"]}
        if not any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
            kwargs = {name: value for name, value in kwargs.items() if name in supported}
        self.model = VoxCPM.from_pretrained(str(self.model_path), **kwargs)
        self.sample_rate = int(self.model.tts_model.sample_rate)

    def synthesize(self, item: SeedItem, destination: Path, seed: int) -> None:
        set_torch_seed(self.torch, seed, numpy_module=self.np)
        signature = self.inspect.signature(self.model.generate)
        kwargs: dict[str, Any] = {
            "text": item.infer_text,
            "reference_wav_path": str(item.prompt_wav),
            "cfg_value": self.parameters["cfg_value"],
            "inference_timesteps": self.parameters["inference_timesteps"],
            "prompt_text": item.prompt_text,
            "prompt_wav_path": str(item.prompt_wav),
        }
        if not any(parameter.kind == self.inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
            kwargs = {name: value for name, value in kwargs.items() if name in signature.parameters}
        with self.torch.inference_mode():
            generated = self.model.generate(**kwargs)
        self.sf.write(str(destination), to_mono_float32(generated, self.np), self.sample_rate)


BACKENDS = {
    "dots_tts": DotsBackend,
    "indextts2": IndexTtsBackend,
    "longcat_audiodit": LongCatBackend,
    "moss_tts": MossBackend,
    "omnivoice": OmniVoiceBackend,
    "qwen3_tts": Qwen3Backend,
    "voxcpm2": VoxCpm2Backend,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=sorted(BACKENDS), help="固定模型脚本标识")
    parser.add_argument("--run-id", required=True, help="本次唯一运行标识；正式运行不得复用已有目录")
    parser.add_argument("--data-root", type=Path, default=os.environ.get("SEED_TTS_DATA_ROOT"), help="seedtts_testset 根目录；默认读取 SEED_TTS_DATA_ROOT")
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT, help="结果根目录，默认 Seed-TTS-test/result")
    parser.add_argument("--split", choices=("all", "meta", "hardcase"), default="all", help="要合成的官方分集")
    parser.add_argument("--resume", action="store_true", help="只继续同一未完成 run-id；会跳过已校验的 WAV")
    parser.add_argument("--limit", type=int, default=None, help="仅用于独立 smoke run；正式评分目录禁止此参数")
    return parser.parse_args()


def preflight_model(config: dict[str, Any], model_id: str) -> tuple[Path, Path | None]:
    model = config["models"][model_id]
    model_path = require_directory(os.environ.get(model["model_path_env"]), model["model_path_env"])
    missing = [name for name in model["required_files"] if not (model_path / name).is_file()]
    if missing:
        raise SeedTtsError(f"{model['display_name']} 的离线模型文件缺失：{', '.join(missing)}")
    code_path = None
    if "code_path_env" in model:
        code_path = require_directory(os.environ.get(model["code_path_env"]), model["code_path_env"])
    return model_path, code_path


def make_metadata(args: argparse.Namespace, config: dict[str, Any], data_root: Path, model_path: Path, code_path: Path | None, selected_splits: Iterable[str]) -> dict[str, Any]:
    model = config["models"][args.model]
    split_list = list(selected_splits)
    lists = {
        split: {
            "path": str((data_root / config["dataset_splits"][split]["list_name"]).resolve()),
            "sha256": sha256_file(data_root / config["dataset_splits"][split]["list_name"]),
            "expected_count": config["dataset_splits"][split]["expected_count"],
        }
        for split in split_list
    }
    required_hashes = {name: sha256_file(model_path / name) for name in model["required_files"]}
    return {
        "schema_version": 1,
        "benchmark": config["benchmark"],
        "created_at": utc_now(),
        "model_id": args.model,
        "model_display_name": model["display_name"],
        "run_id": args.run_id,
        "mode": "smoke" if args.limit is not None else ("formal" if len(split_list) == 2 else "partial"),
        "split_selection": split_list,
        "limit": args.limit,
        "data_lists": lists,
        "model_path": str(model_path),
        "model_required_file_sha256": required_hashes,
        "model_code_path": str(code_path) if code_path else None,
        "model_code_revision": source_revision(code_path),
        "parameters": model["parameters"],
        "seed_policy": "base_seed + sha256(utt) 前四字节，模 2147483647",
        "offline": {"HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"), "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE")},
        "runner_sha256": sha256_file(Path(__file__)),
        "model_config_sha256": sha256_file(CONFIG_PATH),
        "python": sys.version,
        "packages": {name: package_version(name) for name in ("torch", "transformers", "dots-tts", "qwen-tts", "omnivoice", "voxcpm")},
        "status": "running",
    }


def assert_resume_compatible(existing: dict[str, Any], current: dict[str, Any]) -> None:
    keys = ("model_id", "run_id", "mode", "limit", "split_selection", "data_lists", "model_required_file_sha256", "model_code_revision", "parameters", "runner_sha256", "model_config_sha256")
    changed = [key for key in keys if existing.get(key) != current.get(key)]
    if changed:
        raise SeedTtsError("断点续跑的冻结项不一致，必须创建新的 run-id：" + "、".join(changed))


def write_input_manifest(run_dir: Path, items_by_split: dict[str, list[SeedItem]]) -> None:
    manifest = run_dir / "inputs.jsonl"
    if manifest.exists():
        return
    for split, items in items_by_split.items():
        for item in items:
            append_jsonl(manifest, {"split": split, "utt": item.utt, "prompt_text": item.prompt_text, "prompt_wav": str(item.prompt_wav), "infer_text": item.infer_text})


def output_path_for(run_dir: Path, item: SeedItem) -> Path:
    return run_dir / item.split / f"{item.utt}.wav"


def run(args: argparse.Namespace) -> int:
    if not args.run_id or any(part in args.run_id for part in ("/", "\\", "..")):
        raise SeedTtsError("--run-id 必须是安全的单层目录名。")
    if args.limit is not None and args.limit <= 0:
        raise SeedTtsError("--limit 必须为正整数。")
    config = load_json(CONFIG_PATH)
    model_path, code_path = preflight_model(config, args.model)
    data_root = require_directory(str(args.data_root) if args.data_root else None, "SEED_TTS_DATA_ROOT 或 --data-root")
    selected_splits = ["meta", "hardcase"] if args.split == "all" else [args.split]
    items_by_split = {split: parse_meta_list(data_root, split, config["dataset_splits"][split]["list_name"]) for split in selected_splits}
    for split, items in items_by_split.items():
        expected = config["dataset_splits"][split]["expected_count"]
        if len(items) != expected:
            raise SeedTtsError(f"{split} 清单条数错误：实际 {len(items)}，应为 {expected}。")
        if args.limit is not None:
            items_by_split[split] = items[: args.limit]
    run_dir = args.result_root.expanduser().resolve() / config["models"][args.model]["output_dir"] / args.run_id
    metadata_path = run_dir / "freeze" / "run_metadata.json"
    current_metadata = make_metadata(args, config, data_root, model_path, code_path, selected_splits)
    if run_dir.exists():
        if not args.resume:
            raise SeedTtsError(f"结果目录已存在：{run_dir}。只能对同一次未完成运行添加 --resume；否则使用新的 --run-id。")
        existing = load_json(metadata_path)
        assert_resume_compatible(existing, current_metadata)
        current_metadata["created_at"] = existing["created_at"]
        current_metadata["resumed_at"] = utc_now()
    else:
        run_dir.mkdir(parents=True)
    for split in selected_splits:
        (run_dir / split).mkdir(parents=True, exist_ok=True)
    write_input_manifest(run_dir, items_by_split)
    json_dump_atomic(metadata_path, current_metadata)
    model_config = config["models"][args.model]
    cache_dir = run_dir / "runtime-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))
    os.environ.setdefault("HF_MODULES_CACHE", str(cache_dir / "hf_modules"))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_dir / "numba"))
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir / "xdg"))
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True,max_split_size_mb:128")
    backend = BACKENDS[args.model](model_path, code_path, model_config["parameters"], cache_dir)
    state_path = run_dir / "synthesis.jsonl"
    base_seed = int(model_config["parameters"].get("seed", 0))
    try:
        print(f"[Seed-TTS] 加载 {model_config['display_name']}；合成严格串行，不会并发占用显存。")
        backend.load()
        for split, items in items_by_split.items():
            for index, item in enumerate(items, start=1):
                destination = output_path_for(run_dir, item)
                if destination.exists():
                    if not args.resume:
                        raise SeedTtsError(f"发现已有输出但未传 --resume：{destination}")
                    wav_info(destination)
                    continue
                temporary = destination.with_name(f".{item.utt}.part.wav")
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
                seed = stable_item_seed(base_seed, item.utt)
                started = time.perf_counter()
                try:
                    backend.synthesize(item, temporary, seed)
                    temporary.replace(destination)
                    info = wav_info(destination)
                except Exception:
                    with contextlib.suppress(FileNotFoundError):
                        temporary.unlink()
                    raise
                append_jsonl(state_path, {"at": utc_now(), "split": split, "utt": item.utt, "output": str(destination), "sha256": sha256_file(destination), "seed": seed, "elapsed_seconds": round(time.perf_counter() - started, 3), **info})
                print(f"[Seed-TTS] {model_config['display_name']} {split} {index}/{len(items)}: {item.utt}")
        coverage = {split: sum(path.is_file() for path in (run_dir / split).glob("*.wav")) for split in selected_splits}
        expected = {split: len(items) for split, items in items_by_split.items()}
        if coverage != expected:
            raise SeedTtsError(f"覆盖数不完整：实际 {coverage}，应为 {expected}")
        current_metadata["status"] = "complete"
        current_metadata["completed_at"] = utc_now()
        current_metadata["generated_coverage"] = coverage
        json_dump_atomic(metadata_path, current_metadata)
        print(f"[Seed-TTS] 合成完成：{run_dir}")
        return 0
    except Exception:
        current_metadata["status"] = "interrupted"
        current_metadata["interrupted_at"] = utc_now()
        current_metadata["traceback"] = traceback.format_exc()
        json_dump_atomic(metadata_path, current_metadata)
        raise
    finally:
        backend.close()


def main() -> int:
    try:
        return run(parse_args())
    except SeedTtsError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
