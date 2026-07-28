#!/usr/bin/env python3
"""只读检查 Seed-TTS 中文基准的资源、补丁和结果布局，不加载 TTS 模型。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from seed_tts_runner import (
    BACKENDS,
    CONFIG_PATH,
    SeedTtsError,
    load_json,
    parse_meta_list,
    preflight_model,
    require_directory,
    require_file,
    sha256_file,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SEED_TTS_ROOT = SCRIPT_DIR.parent
DEFAULT_RESULT_ROOT = SEED_TTS_ROOT / "result"
PATCH_PATH = SCRIPT_DIR / "patches" / "0001-seed-tts-local-offline.patch"


class Report:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def show(self) -> None:
        for label, lines in (("通过", self.passed), ("警告", self.warnings), ("错误", self.errors)):
            for line in lines:
                print(f"[{label}] {line}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(BACKENDS), help="只检查一个模型；省略时检查全部七个")
    parser.add_argument("--data-root", type=Path, default=os.environ.get("SEED_TTS_DATA_ROOT"))
    parser.add_argument("--eval-root", type=Path, default=os.environ.get("SEED_TTS_EVAL_ROOT"))
    parser.add_argument("--wavlm-ckpt", type=Path, default=os.environ.get("SEED_TTS_WAVLM_CKPT"))
    parser.add_argument("--paraformer-dir", type=Path, default=os.environ.get("SEED_TTS_PARAFORMER_DIR"))
    parser.add_argument("--result-run", type=Path, help="额外检查某次合成结果是否恰好覆盖两个正式分集")
    return parser.parse_args()


def check_conda_envs(report: Report, config: dict[str, Any], model_ids: list[str]) -> None:
    try:
        completed = subprocess.run(["conda", "env", "list", "--json"], check=True, capture_output=True, text=True)
        environments = {Path(value).name for value in json.loads(completed.stdout).get("envs", [])}
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        report.errors.append(f"无法读取 Conda 环境列表：{exc}")
        return
    required = {"seed_tts_eval", "seed_tts_sim"} | {config["models"][model_id]["conda_env"] for model_id in model_ids}
    missing = sorted(required - environments)
    if missing:
        report.errors.append("缺少隔离 Conda 环境：" + "、".join(missing))
    else:
        report.passed.append("已找到两个评分环境和所选模型的隔离 Conda 环境。")
    for model_id in model_ids:
        model = config["models"][model_id]
        distribution = model.get("runtime_distribution")
        if not distribution or model["conda_env"] not in environments:
            continue
        command = [
            "conda",
            "run",
            "-n",
            model["conda_env"],
            "python",
            "-c",
            "import importlib.metadata as m, sys; m.version(sys.argv[1])",
            distribution,
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode:
            report.errors.append(
                f"{model['display_name']} 的运行时发行包缺失：{distribution}；"
                "请按该模型的官方环境同步脚本补齐后再运行预检。"
            )
        else:
            report.passed.append(f"{model['display_name']} 运行时发行包已登记：{distribution}。")


def check_data(report: Report, config: dict[str, Any], data_root: Path) -> None:
    try:
        root = require_directory(str(data_root), "SEED_TTS_DATA_ROOT 或 --data-root")
        counts = {}
        for split, spec in config["dataset_splits"].items():
            items = parse_meta_list(root, split, spec["list_name"])
            if len(items) != spec["expected_count"]:
                raise SeedTtsError(f"{split} 条数为 {len(items)}，应为 {spec['expected_count']}")
            counts[split] = len(items)
        report.passed.append(f"官方中文清单与全部参考音频存在：meta {counts['meta']} 条，hardcase {counts['hardcase']} 条。")
    except SeedTtsError as exc:
        report.errors.append(str(exc))


def check_models(report: Report, config: dict[str, Any], model_ids: list[str]) -> None:
    for model_id in model_ids:
        try:
            model_path, code_path = preflight_model(config, model_id)
            text = f"{config['models'][model_id]['display_name']} 离线权重完整"
            if code_path is not None:
                text += f"；官方源码路径已指定（{code_path.name}）"
            report.passed.append(text + "。")
        except SeedTtsError as exc:
            report.errors.append(f"{model_id}：{exc}")


def check_required_executables(report: Report, config: dict[str, Any], model_ids: list[str]) -> None:
    for model_id in model_ids:
        model = config["models"][model_id]
        executable_env = model.get("required_executable_env")
        if not executable_env:
            continue
        raw_path = os.environ.get(executable_env)
        path = Path(raw_path).expanduser() if raw_path else None
        if path is None or not path.is_file() or not os.access(path, os.X_OK):
            report.errors.append(
                f"{model['display_name']} 必须设置 {executable_env} 为可执行文件；"
                "该运行时需要 SoX 处理参考音频。"
            )
            continue
        report.passed.append(f"{model['display_name']} 的外部音频工具可用：{path.name}。")


def check_evaluator(report: Report, eval_root: Path, wavlm_ckpt: Path, paraformer_dir: Path) -> None:
    try:
        root = require_directory(str(eval_root), "SEED_TTS_EVAL_ROOT 或 --eval-root")
        require_file(wavlm_ckpt, "SEED_TTS_WAVLM_CKPT 或 --wavlm-ckpt")
        require_directory(str(paraformer_dir), "SEED_TTS_PARAFORMER_DIR 或 --paraformer-dir")
    except SeedTtsError as exc:
        report.errors.append(str(exc))
        return
    requirements = {
        "cal_wer.sh": ("prepare_ckpt.py", "sudo split"),
        "cal_sim.sh": ("sudo split",),
        "run_wer.py": (),
    }
    for filename, forbidden in requirements.items():
        path = root / filename
        if not path.is_file():
            report.errors.append(f"补丁工作副本缺少 {filename}：{root}")
            continue
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in content:
                report.errors.append(f"{filename} 仍含未允许的运行依赖：{token}")
    run_wer = root / "run_wer.py"
    if run_wer.is_file():
        content = run_wer.read_text(encoding="utf-8")
        if "SEED_TTS_PARAFORMER_DIR" not in content or 'hub="hf"' not in content:
            report.errors.append("run_wer.py 未固定本地 Paraformer（SEED_TTS_PARAFORMER_DIR + hub=hf）。")
    speaker_dir = root / "thirdparty" / "UniSpeech" / "downstreams" / "speaker_verification"
    if not (speaker_dir / "select_speakers.py").is_file() or (speaker_dir / "select.py").exists():
        report.errors.append("UniSpeech 的 select.py 重命名补丁未正确应用。")
    manifest = root / "freeze-patch.json"
    if not manifest.is_file():
        report.errors.append("缺少 freeze-patch.json；请使用 prepare_seed_tts_evaluator.sh 创建补丁工作副本。")
    else:
        try:
            payload = load_json(manifest)
            if payload.get("patch_sha256") != sha256_file(PATCH_PATH):
                report.errors.append("补丁 SHA-256 与仓库冻结补丁不一致。")
        except (SeedTtsError, OSError) as exc:
            report.errors.append(f"无法校验补丁冻结记录：{exc}")
    if not report.errors:
        report.passed.append("评分工作副本已应用本地 Paraformer、普通 split 与 select 重命名补丁。")


def check_result_run(report: Report, config: dict[str, Any], run_dir: Path) -> None:
    metadata_path = run_dir / "freeze" / "run_metadata.json"
    try:
        metadata = load_json(metadata_path)
    except SeedTtsError as exc:
        report.errors.append(str(exc))
        return
    if metadata.get("mode") != "formal" or metadata.get("status") != "complete" or metadata.get("limit") is not None:
        report.errors.append("结果目录不是已完成的正式运行（不得为 smoke、受限 --limit 或中断状态）。")
    if metadata.get("split_selection") != ["meta", "hardcase"]:
        report.errors.append("结果目录未同时生成 meta 与 hardcase，不能进行正式评分。")
    for split, spec in config["dataset_splits"].items():
        wavs = list((run_dir / split).glob("*.wav"))
        if len(wavs) != spec["expected_count"]:
            report.errors.append(f"{split} WAV 覆盖数不正确：实际 {len(wavs)}，应为 {spec['expected_count']}。")
    if not report.errors:
        report.passed.append("结果目录为完整的正式合成：2,020 条 meta 与 400 条 hardcase WAV。")


def main() -> int:
    args = parse_args()
    report = Report()
    config = load_json(CONFIG_PATH)
    model_ids = [args.model] if args.model else list(config["models"])
    if os.environ.get("ARNOLD_WORKER_GPU") != "1":
        report.errors.append("必须设置 ARNOLD_WORKER_GPU=1；Seed-TTS 单卡评分不得启动多个进程抢占同一 GPU。")
    if args.data_root is None:
        report.errors.append("必须设置 SEED_TTS_DATA_ROOT 或传入 --data-root。")
    else:
        check_data(report, config, args.data_root)
    check_models(report, config, model_ids)
    check_required_executables(report, config, model_ids)
    check_conda_envs(report, config, model_ids)
    if args.eval_root is None or args.wavlm_ckpt is None or args.paraformer_dir is None:
        report.errors.append("必须设置 SEED_TTS_EVAL_ROOT、SEED_TTS_WAVLM_CKPT 与 SEED_TTS_PARAFORMER_DIR。")
    else:
        check_evaluator(report, args.eval_root, args.wavlm_ckpt, args.paraformer_dir)
    if args.result_run is not None:
        check_result_run(report, config, args.result_run.expanduser().resolve())
    report.show()
    return 2 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
