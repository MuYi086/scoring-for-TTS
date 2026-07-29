# tts-bench：通用实验基准

`tts-bench` 只保留早期通用、短样本实验基准的登记格式与自动评价器。它不是 Task 6、Task 7、Task 8 或 Task 9 的长音频公共评测入口；这些任务必须使用各自 `task-runner/task*/` 下的合成器、冻结契约、预检器、评测器和报告生成器。

已删除失效的 V2–V5 和旧七模型 V9 说明、配置及预检入口。它们依赖的运行器、清单或输入已不在仓库中，且其六后端指标与当前长音频双 ASR 规则不兼容。

## 保留内容

- `scripts/run_automated_evaluation.py`：对已登记的通用短样本运行执行音频健康、WavLM、ASR 和 UTMOSv2 自动评价；不调用 TTS 合成模型。
- `config/automated-evaluation*.json`：该通用评价器的示例与本地配置。
- `contracts/`、`templates/` 和 `datasets/README.md`：通用实验登记格式。
- `environment/`：该通用评价器的环境定义。

通用实验的本地音频、运行记录和派生结果不提交到仓库。

## 通用实验运行

在已登记 `tts-bench/runs/<run_id>/synthesis.jsonl` 的前提下，使用本地配置运行：

```bash
conda run -n audio_eval python tts-bench/scripts/run_automated_evaluation.py \
  --runs-root tts-bench/runs \
  --config tts-bench/config/automated-evaluation.json
```

该命令的 `configured_score`（配置化比较分）仅适用于同一通用实验配置，不能用于 Task 6–9，也不能替代人工试听。

## 当前长音频入口

| 任务 | 合成与评测入口 |
| --- | --- |
| Task 6 | `task-runner/task6/` |
| Task 7 | `task-runner/task7/` |
| Task 8 | `task-runner/task8/` |
| Task 9 | `task-runner/task9/` |

长音频任务只报告 SenseVoice CER 与 Whisper-large-v3-turbo CER 的独立名次，并使用最终 WAV 哈希绑定的逐段合成证据；不得复用本目录的 WavLM、UTMOSv2、综合分或旧长音频脚本。
