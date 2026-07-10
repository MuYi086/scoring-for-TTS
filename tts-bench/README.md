# tts-bench：基准事实源

`tts-bench` 是所有评估的唯一编排层，不运行模型。它解决的不是“如何算一个分数”，而是先确保每个模型面对的是同一份输入、同一条参考音频、同一份预处理约定，并且每个数字都能回溯到具体音频与配置。

## 目录职责

```text
tts-bench/
├── contracts/       # 机器可读的数据契约（JSON Schema）
├── datasets/        # 样本集说明；本地音频放 datasets/audio/，不提交
├── manifests/       # 冻结的 case 清单，JSON Lines（每行一个样本）
├── reports/         # 可提交的汇总报告与决策记录
├── runs/            # 每次模型运行的可追溯证据；其中音频不提交
└── templates/       # 新建运行和汇总时复制的模板
```

## 四种核心对象

| 对象 | 作用 | 存放位置 |
| --- | --- | --- |
| `case`（评测样本） | 固定参考音频、参考转写、待合成文本和考察维度。 | `manifests/*.jsonl` |
| `run`（一次运行） | 某模型、某配置、某个冻结清单的一次完整执行。 | `runs/<run_id>/` |
| `synthesis record`（合成记录） | 将一个 `case` 的输出音频、哈希、耗时和配置绑定。 | `runs/<run_id>/synthesis.jsonl` |
| `metric record`（指标记录） | 将一个评价器的逐样本结果绑定到合成记录。 | `runs/<run_id>/metrics/` |

`case_id` 与 `run_id` 是跨目录关联的主键。不要用文件名、显示名称或目录扫描顺序作为关联依据。

## 新建一次手工运行

1. 从 `templates/run.example.yaml` 复制为 `runs/<run_id>/run.yaml`，填写模型版本、配置快照和冻结的清单路径。
2. 由 `modelScript/` 中相应脚本手工合成，把原始 WAV 放在 `runs/<run_id>/audio/<case_id>.wav`。该目录被忽略，避免大音频进入 Git。
3. 以 `contracts/synthesis-record.schema.json` 为准，逐行填写 `synthesis.jsonl`。每条成功或失败的尝试都应留下记录。
4. 对同一批成功样本分别执行 WavLM、ASR、TTS-PRISM-7B 与人工盲听；评价器只写自己的输出文件，不改写原始合成音频。
5. 只在逐样本结果齐全后汇总；`templates/scorecard.csv` 只承载汇总展示，不能替代逐样本证据。

详细操作与停止条件见仓库根目录的 [`评估步骤指南.md`](../评估步骤指南.md)。
