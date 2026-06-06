"""Synthesize one sample WAV from a generated voice asset directory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import soundfile as sf
from voxcpm.core import VoxCPM


DEFAULT_MODEL_PATH = Path("/persistent/home/muyi086/modelscope/VoxCPM2")


def main() -> int:
    args = parse_args()
    directory = args.directory
    if not directory.is_dir():
        raise SystemExit(f"目录不存在：{directory}")

    output_wav = directory / args.output_name
    if output_wav.exists() and not args.overwrite:
        raise SystemExit(f"输出文件已存在，如需覆盖请加 --overwrite：{output_wav}")

    text = (directory / "sample.txt").read_text(encoding="utf-8").strip()
    prompt = (directory / "sample.voice.txt").read_text(encoding="utf-8").strip()
    controls = read_controls(directory / "sample.controls.json")
    provider = provider_overrides(controls)
    cfg_value = args.cfg_value if args.cfg_value is not None else float(provider.get("cfg_value", 2.0))
    inference_timesteps = (
        args.inference_timesteps
        if args.inference_timesteps is not None
        else int(provider.get("inference_timesteps", 10))
    )
    normalize = args.normalize or bool(provider.get("normalize", False))
    final_text = f"({prompt}){text}" if prompt else text

    if args.dry_run:
        print(f"model_path={args.model_path}")
        print(f"output_wav={output_wav}")
        print(f"cfg_value={cfg_value}")
        print(f"inference_timesteps={inference_timesteps}")
        print(f"normalize={normalize}")
        print(final_text)
        return 0

    model = VoxCPM(
        voxcpm_model_path=str(args.model_path),
        zipenhancer_model_path=None,
        enable_denoiser=False,
        optimize=args.optimize,
        device=args.device,
    )
    audio_array = model.generate(
        text=final_text,
        cfg_value=cfg_value,
        inference_timesteps=inference_timesteps,
        normalize=normalize,
        denoise=False,
    )
    tmp_wav = output_wav.with_suffix(".tmp.wav")
    sf.write(str(tmp_wav), audio_array, model.tts_model.sample_rate)
    tmp_wav.replace(output_wav)
    print(f"已生成 {output_wav}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按目录内 sample.txt、sample.voice.txt、sample.controls.json 合成单个 WAV。"
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output-name", default="sample.3.wav")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--cfg-value", type=float)
    parser.add_argument("--inference-timesteps", type=int)
    parser.add_argument("--normalize", action="store_true")
    parser.add_argument("--optimize", action="store_true", help="启用 torch.compile 预热优化。")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_controls(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"控制参数 JSON 无效：{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"控制参数 JSON 顶层必须是对象：{path}")
    return payload


def provider_overrides(controls: dict[str, Any]) -> dict[str, Any]:
    overrides = controls.get("provider_overrides", {})
    if not isinstance(overrides, dict):
        return {}
    voxcpm2 = overrides.get("voxcpm2", {})
    return voxcpm2 if isinstance(voxcpm2, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
