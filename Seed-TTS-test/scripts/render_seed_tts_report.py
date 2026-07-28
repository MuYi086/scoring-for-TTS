#!/usr/bin/env python3
"""从冻结元数据和官方原始 WER/SIM 输出生成 Seed-TTS 中文基准报告。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from seed_tts_runner import CONFIG_PATH, SeedTtsError, load_json, sha256_file


SCRIPT_DIR = Path(__file__).resolve().parent
SEED_TTS_ROOT = SCRIPT_DIR.parent
DEFAULT_REPORT_ROOT = SEED_TTS_ROOT / "report"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-run", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def require_formal_result(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    metadata = load_json(run_dir / "freeze" / "run_metadata.json")
    if metadata.get("mode") != "formal" or metadata.get("status") != "complete" or metadata.get("limit") is not None:
        raise SeedTtsError("只允许为已完成、未限制条数的正式运行生成报告。")
    if metadata.get("split_selection") != ["meta", "hardcase"]:
        raise SeedTtsError("正式报告必须包含 meta 与 hardcase 两个完整分集。")
    for split, spec in config["dataset_splits"].items():
        actual = len(list((run_dir / split).glob("*.wav")))
        if actual != spec["expected_count"]:
            raise SeedTtsError(f"{split} WAV 覆盖数不正确：实际 {actual}，应为 {spec['expected_count']}。")
    return metadata


def parse_wer(path: Path, expected_count: int) -> tuple[float, int]:
    if not path.is_file():
        raise SeedTtsError(f"缺少官方 WER 原始输出：{path}")
    score: float | None = None
    records = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("WER:"):
            score = float(line.split(":", 1)[1].strip().rstrip("%"))
        elif not line.startswith("utt\t") and line.count("\t") >= 6:
            records += 1
    if score is None or records != expected_count:
        raise SeedTtsError(f"WER 原始输出不完整：{path}（逐条 {records}/{expected_count}，汇总 {score}）")
    return score, records


def parse_sim(path: Path, expected_count: int) -> tuple[float, float, int]:
    if not path.is_file():
        raise SeedTtsError(f"缺少官方 SIM 原始输出：{path}")
    score: float | None = None
    variance: float | None = None
    records = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASV:"):
            score = float(line.split(":", 1)[1].strip())
        elif line.startswith("ASV-var:"):
            variance = float(line.split(":", 1)[1].strip())
        elif "\t" in line:
            records += 1
    if score is None or variance is None or records != expected_count:
        raise SeedTtsError(f"SIM 原始输出不完整：{path}（逐条 {records}/{expected_count}，汇总 {score}）")
    return score, variance, records


def report_text(metadata: dict[str, Any], rows: list[dict[str, Any]], result_link: str) -> str:
    table = "\n".join(
        f"| {row['split']} | {row['count']} | {row['wer']:.3f}% | {row['sim']:.3f} | {row['variance']:.3f} |"
        for row in rows
    )
    return f"""# Seed-TTS 中文 WER 与 WavLM-large-SV SIM 标准基准报告

## 结论口径

本报告仅代表冻结模型版本 `{metadata['model_display_name']}` 在 Seed-TTS-Eval 官方中文外部基准上的表现；它不推断小说长音频的自然度、情绪、角色区分度或最终生产排名。Seed-TTS 中文 WER（逐字 token）和 WavLM-large-SV SIM（说话人相似度）是独立指标，**未合成为总分或总排名**。

| 分集 | 生成覆盖 | Seed-TTS 中文 WER | WavLM-large-SV SIM | SIM 方差 |
| --- | ---: | ---: | ---: | ---: |
{table}

## 冻结信息

- 模型：`{metadata['model_display_name']}`（脚本标识：`{metadata['model_id']}`）
- 运行标识：`{metadata['run_id']}`
- 合成完成时间：`{metadata.get('completed_at', '未记录')}`
- 模型权重与关键文件哈希、推理参数、随机种子策略、数据清单哈希、Python 包版本：[`freeze/run_metadata.json`]({result_link}/freeze/run_metadata.json)
- 合成逐条证据（音频 SHA-256、耗时、格式与种子）：[`synthesis.jsonl`]({result_link}/synthesis.jsonl)
- 官方输入映射（参考音频、参考文本、目标文本）：[`inputs.jsonl`]({result_link}/inputs.jsonl)

## 原始官方评分输出

- `meta`：[`WER`](raw/meta.wer.tsv) 与 [`SIM`](raw/meta.sim.tsv)
- `hardcase`：[`WER`](raw/hardcase.wer.tsv) 与 [`SIM`](raw/hardcase.sim.tsv)

评分报告目录还应保留两个评分环境的 `pip freeze`、GPU/驱动信息、Paraformer 文件 SHA-256、WavLM 权重 SHA-256 与 Seed-TTS-Eval 补丁冻结记录；这些环境证据不得用未登记的机器改动替代。
"""


def main() -> int:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    run_dir = args.result_run.expanduser().resolve()
    metadata = require_formal_result(run_dir, config)
    if args.validate_only:
        print("正式合成覆盖完整，可进入官方 WER/SIM 评分。")
        return 0
    report_dir = args.report_dir.expanduser().resolve()
    rows = []
    for split, spec in config["dataset_splits"].items():
        raw_dir = report_dir / "raw"
        wer, wer_count = parse_wer(raw_dir / f"{split}.wer.tsv", spec["expected_count"])
        sim, variance, sim_count = parse_sim(raw_dir / f"{split}.sim.tsv", spec["expected_count"])
        rows.append({"split": split, "count": spec["expected_count"], "wer": wer, "wer_records": wer_count, "sim": sim, "variance": variance, "sim_records": sim_count})
    report_dir.mkdir(parents=True, exist_ok=True)
    result_link = Path(os.path.relpath(run_dir, start=report_dir)).as_posix()
    report_path = report_dir / "Seed-TTS_ZH_WER&WavLM-large-SV_SIM_标准基准报告.md"
    report_path.write_text(report_text(metadata, rows, result_link), encoding="utf-8")
    manifest = {"result_run": str(run_dir), "result_run_metadata_sha256": sha256_file(run_dir / "freeze" / "run_metadata.json"), "rows": rows, "report_sha256": sha256_file(report_path)}
    (report_dir / "report_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成报告：{report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SeedTtsError as exc:
        print(f"错误：{exc}", file=__import__("sys").stderr)
        raise SystemExit(2)
