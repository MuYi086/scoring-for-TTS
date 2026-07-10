# 清单格式

清单使用 JSON Lines（每行一个 JSON 对象），以便追加、审阅和逐行定位。新实验先复制 `case.example.jsonl`，人工核对后再冻结为一个带日期或版本的清单，例如 `cases-2026-07-v1.jsonl`。

每个样本必须有稳定且不复用的 `case_id`。一旦清单用于 `holdout`（保留集），不得修改其文本、参考音频或评分维度；需要变更时新建版本。

完整字段约束见 [`../contracts/benchmark-case.schema.json`](../contracts/benchmark-case.schema.json)。
