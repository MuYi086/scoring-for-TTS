"""Batch synthesize sample.1.wav files from generated voice asset folders."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import soundfile as sf
from voxcpm.core import VoxCPM


DEFAULT_ASSET_ROOT = Path("samples/generated")
DEFAULT_MODEL_PATH = Path("/persistent/home/muyi086/modelscope/VoxCPM2")
DEFAULT_LOG_FILE = DEFAULT_ASSET_ROOT / "sample1_generation.jsonl"


@dataclass(frozen=True)
class SampleJob:
    directory: Path
    text_file: Path
    control_file: Path
    controls_file: Path
    output_wav: Path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    jobs = select_jobs(args.root, limit=args.limit, start_after=args.start_after)
    if not jobs:
        print("没有找到可合成的 sample 目录。", file=sys.stderr)
        return 1

    pending = [
        job for job in jobs if args.overwrite or not job.output_wav.exists()
    ]
    print(
        f"发现目录 {len(jobs)} 个，待生成 {len(pending)} 个，"
        f"已存在跳过 {len(jobs) - len(pending)} 个。",
        flush=True,
    )
    if args.dry_run:
        for job in pending:
            print(job.output_wav)
        return 0
    if not pending:
        return 0

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    model = VoxCPM(
        voxcpm_model_path=str(args.model_path),
        zipenhancer_model_path=None,
        enable_denoiser=False,
        optimize=args.optimize,
        device=args.device,
    )

    ok = 0
    failed = 0
    started = time.monotonic()
    with args.log_file.open("a", encoding="utf-8") as log:
        for index, job in enumerate(pending, 1):
            item_started = time.monotonic()
            try:
                generated = synthesize_job(
                    model,
                    job,
                    cfg_value=args.cfg_value,
                    inference_timesteps=args.inference_timesteps,
                    normalize=args.normalize,
                )
            except Exception as exc:  # noqa: BLE001 - keep the batch resumable.
                failed += 1
                elapsed = time.monotonic() - item_started
                write_log(
                    log,
                    {
                        "status": "failed",
                        "directory": str(job.directory),
                        "output_wav": str(job.output_wav),
                        "error": str(exc),
                        "elapsed_seconds": round(elapsed, 3),
                    },
                )
                print(
                    f"[{index}/{len(pending)}] 失败 {job.directory.name}: {exc}",
                    flush=True,
                )
                continue

            ok += 1
            elapsed = time.monotonic() - item_started
            write_log(
                log,
                {
                    "status": "generated",
                    "directory": str(job.directory),
                    "output_wav": str(generated),
                    "elapsed_seconds": round(elapsed, 3),
                    "size_bytes": generated.stat().st_size,
                },
            )
            print(
                f"[{index}/{len(pending)}] 已生成 {generated} "
                f"({elapsed:.1f}s)",
                flush=True,
            )

    total_elapsed = time.monotonic() - started
    print(
        f"完成：成功 {ok}，失败 {failed}，耗时 {total_elapsed / 60:.1f} 分钟。",
        flush=True,
    )
    return 0 if failed == 0 else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 samples/generated/*/sample.txt 和 sample.voice.txt 合成 sample.1.wav。"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ASSET_ROOT)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-after", help="跳过排序中该目录名及之前的目录。")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--optimize", action="store_true", help="启用 torch.compile 预热优化。")
    parser.add_argument("--cfg-value", type=float)
    parser.add_argument("--inference-timesteps", type=int)
    parser.add_argument("--normalize", action="store_true")
    return parser.parse_args(argv)


def select_jobs(root: Path, *, limit: int | None, start_after: str | None) -> list[SampleJob]:
    jobs: list[SampleJob] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if start_after and directory.name <= start_after:
            continue
        text_file = directory / "sample.txt"
        control_file = directory / "sample.voice.txt"
        controls_file = directory / "sample.controls.json"
        if not text_file.is_file() or not control_file.is_file() or not controls_file.is_file():
            continue
        jobs.append(
            SampleJob(
                directory=directory,
                text_file=text_file,
                control_file=control_file,
                controls_file=controls_file,
                output_wav=directory / "sample.1.wav",
            )
        )
        if limit is not None and len(jobs) >= limit:
            break
    return jobs


def synthesize_job(
    model: VoxCPM,
    job: SampleJob,
    *,
    cfg_value: float | None,
    inference_timesteps: int | None,
    normalize: bool,
) -> Path:
    text = job.text_file.read_text(encoding="utf-8").strip()
    control = job.control_file.read_text(encoding="utf-8").strip()
    controls = read_controls(job.controls_file)
    provider = provider_overrides(controls)
    resolved_cfg = cfg_value if cfg_value is not None else float(provider.get("cfg_value", 2.0))
    resolved_steps = (
        inference_timesteps
        if inference_timesteps is not None
        else int(provider.get("inference_timesteps", 10))
    )
    resolved_normalize = normalize or bool(provider.get("normalize", False))
    final_text = f"({control}){text}" if control else text
    audio_array = model.generate(
        text=final_text,
        cfg_value=resolved_cfg,
        inference_timesteps=resolved_steps,
        normalize=resolved_normalize,
        denoise=False,
    )
    tmp_wav = job.directory / "sample.1.tmp.wav"
    sf.write(str(tmp_wav), audio_array, model.tts_model.sample_rate)
    tmp_wav.replace(job.output_wav)
    return job.output_wav


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


def write_log(log, payload: dict[str, Any]) -> None:
    log.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    log.flush()


if __name__ == "__main__":
    raise SystemExit(main())
