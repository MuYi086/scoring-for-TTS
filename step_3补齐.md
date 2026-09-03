# Step 3 阻断故事补齐操作手册

本手册处理 `work/training-pipeline-fear-v1/` 中被 Step 2 边界门禁拦下的故事。当前状态为：

```text
Step 2：413 / 413 completed
Step 3 可用候选：329 / 329 completed
Step 3 边界阻断：125（incomplete 93、uncertain 32）
```

这里的“补齐”不是让 Step 3 忽略门禁。只有完整、连续、可追溯的文学稿 A 才能生成教师答案 B。
所有命令均从仓库根目录执行。

## 0. 三条不可违反的规则

1. **不要修改 `training/原始资源/`。** 该目录受 Step 0 冻结哈希保护；直接修改会使当前 v1
   数据集失效。
2. **不要对 125 项使用 `--overwrite` 强行执行 Step 3。** `--overwrite` 只会覆盖已经合格的
   改写结果，不能将 `incomplete` 或 `uncertain` 变成可训练样本。
3. **单一起止行只能修复连续区间。** 若存在内部串页、缺失段落或多个不连续片段，不能把它伪装成
   一个连续故事；必须走第 3 节的人工清洗/流水线扩展路径。

## 1. 盘点与定位

先建立一个本次人工复核目录，并备份会被 `--overwrite` 重建的边界清单。此备份只用于审计和回退比较。

```bash
RUN_ID="manual-boundary-$(date +%Y%m%d-%H%M%S)"
REVIEW_DIR="work/training-pipeline-fear-v1/manual_review/${RUN_ID}"
mkdir -p "$REVIEW_DIR"

cp work/training-pipeline-fear-v1/boundaries.repaired.jsonl \
  "$REVIEW_DIR/boundaries.repaired.before.jsonl"
cp work/training-pipeline-fear-v1/boundary_repair_queue.jsonl \
  "$REVIEW_DIR/boundary_repair_queue.before.jsonl"
```

输出阻断统计和带“实际行号变化”的候选。`none` 和 `same_range` 不是可直接应用的修复。

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

work = Path("work/training-pipeline-fear-v1")
items = [
    json.loads(line)
    for line in (work / "boundary_repair_queue.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

print(f"修复队列：{len(items)}")
print("状态：", dict(sorted(Counter(item["status"] for item in items).items())))
print("\n有实际行号变更的候选：")
for item in items:
    start = item.get("suggested_start_line")
    end = item.get("suggested_end_line")
    changed = (
        start not in (None, item["current_start_line"])
        or end not in (None, item["current_end_line"])
    )
    if changed:
        print(
            f"{item['source_id']}\t{item['status']}\t{item['source_path']}\t"
            f"{item['current_start_line']}–{item['current_end_line']} -> "
            f"{start or item['current_start_line']}–{end or item['current_end_line']}"
        )
PY
```

查看单项的 Step 2 判断和原始行号上下文。把 `ID` 替换为上一步的 `source_id`；此命令只读。

```bash
ID='story_02b41ea93c5ba92d'

python - "$ID" <<'PY'
import json
import sys
from pathlib import Path

work = Path("work/training-pipeline-fear-v1")
source_id = sys.argv[1]
queue = [
    json.loads(line)
    for line in (work / "boundary_repair_queue.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
item = next((item for item in queue if item["source_id"] == source_id), None)
if item is None:
    raise SystemExit(f"当前修复队列中不存在：{source_id}")

print(json.dumps(item, ensure_ascii=False, indent=2))
context = work / "boundary_context" / f"{source_id}.txt"
if context.is_file():
    print(f"\n--- {context} ---")
    print(context.read_text(encoding="utf-8"))
else:
    print(f"\n缺少边界上下文：{context}；先执行第 2 节的 Step 2 续跑。")
PY
```

只有同时满足下面四项才可以批准：

- 新范围包含完整开头、完整结局；
- 新范围内没有相邻故事、广告、编辑文字或 OCR 串页；
- 新范围是一个连续区间；
- 建议范围和当前 `boundaries.repaired.jsonl` 中的范围精确匹配。

## 2. 连续边界修复（现有脚本可直接完成）

### 2.1 人工记录批准的 ID

完成逐条复核后，将**仅确认安全**的 ID 填入下列命令的 `approved_ids` 集合。不要填入：

- `suggested_start_line` 和 `suggested_end_line` 都是 `null` 的项；
- 建议与当前范围相同的项；
- 问题中出现“内部串页”“提取污染”“缺少结局”“无法用单一连续边界”的项。

```bash
REVIEW_DIR="$(find work/training-pipeline-fear-v1/manual_review -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"

python - "$REVIEW_DIR" <<'PY'
import sys
from pathlib import Path

review_dir = Path(sys.argv[1])

# 只保留已从原文上下文确认安全的 ID。空集合会安全退出，不会写任何修复清单。
approved_ids = {
    # "story_0123456789abcdef",
}

if not approved_ids:
    raise SystemExit("approved_ids 为空：请先完成逐项人工复核。")

(review_dir / "approved_ids.txt").write_text(
    "".join(f"{source_id}\n" for source_id in sorted(approved_ids)),
    encoding="utf-8",
)
print(review_dir / "approved_ids.txt")
PY
```

从当前队列生成仅含批准项目的修复清单，并确认它们仍能精确匹配当前边界。若出现
`未匹配`，说明队列或边界清单已经在别的轮次重建；停止，不要套用旧行号，回到第 1 节重新盘点。

```bash
REVIEW_DIR="$(find work/training-pipeline-fear-v1/manual_review -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"

python - "$REVIEW_DIR" <<'PY'
import json
import sys
from pathlib import Path

work = Path("work/training-pipeline-fear-v1")
review_dir = Path(sys.argv[1])
approved_ids = {
    line.strip()
    for line in (review_dir / "approved_ids.txt").read_text(encoding="utf-8").splitlines()
    if line.strip()
}
queue = [
    json.loads(line)
    for line in (work / "boundary_repair_queue.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
by_id = {item["source_id"]: item for item in queue}
unknown = sorted(approved_ids - by_id.keys())
if unknown:
    raise SystemExit(f"批准 ID 不在当前队列：{unknown}")

selected = [by_id[source_id] for source_id in sorted(approved_ids)]
boundaries = [
    json.loads(line)
    for line in (work / "boundaries.repaired.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
boundary_keys = {
    (item["source_path"], item["start_line"], item["end_line"])
    for item in boundaries
}
unmatched = [
    item["source_id"]
    for item in selected
    if (item["source_path"], item["current_start_line"], item["current_end_line"])
    not in boundary_keys
]
if unmatched:
    raise SystemExit(f"建议与当前边界不匹配，禁止应用：{unmatched}")

output = review_dir / "approved_repairs.jsonl"
output.write_text(
    "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in selected),
    encoding="utf-8",
)
print(f"已写入 {output}：{len(selected)} 项")
PY
```

应用这一小批已经确认的连续范围。此命令重建 `stories.jsonl`，因此 `--overwrite` 是必需且仅在此处允许的。

```bash
REVIEW_DIR="$(find work/training-pipeline-fear-v1/manual_review -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"

python training/script/step_1_prepare_stories.py \
  --apply-boundary-repairs \
  --boundary-manifest work/training-pipeline-fear-v1/boundaries.repaired.jsonl \
  --repair-manifest "$REVIEW_DIR/approved_repairs.jsonl" \
  --overwrite
```

随后重新分析新增/变化的故事。每批最多 20 项；输出仍显示待处理时，重复同一条命令。明确出现额度耗尽时停止，额度恢复后再重复。

```bash
python training/script/step_2_analyze_stories.py \
  --limit 20 --workers 2 --continue-on-error
```

当 Step 2 显示 `Luna 待处理：0` 后，续跑 Step 3：

```bash
python training/script/step_3_rewrite_stories.py \
  --variant teacher --limit 20 --workers 2 --continue-on-error
```

再次执行第 1 节的盘点命令。所有新变为 `complete` 且置信度至少 0.80、`issues=[]` 的故事会自动进入
Step 3；无需手动移动或复制任何改写文件。

## 3. 内部串页、缺段和非连续正文（需要扩展流水线）

以下情形**不能**使用第 2 节：

- 故事中间插入另一篇故事、栏目或广告；
- 开头/结局在当前授权原文中缺失；
- 正文由两个或更多不连续行段组成；
- 唯一建议仍是当前起止行，或没有建议行号。

当前脚本的边界模型只支持：

```text
source_path + start_line + end_line
```

它无法表达“保留 100–200 行和 230–350 行、跳过中间串页”的内容。因此不要手工编辑
`work/.../stories/<source_id>.md`：下一次 `prepare_stories` 会覆盖它，且其 SHA-256 与审计链也会失真。

正确做法是新增一个“人工清洗覆盖（manual cleaned override）”能力，并在新数据集版本 v2 中运行。实施
这项代码改造前，先建立分支并运行现有无模型测试：

```bash
git switch -c feat/manual-cleaned-story-overrides
python -m pytest -q
```

改造必须满足以下数据契约：

1. 保留原始冻结文件不变；人工清洗文本写入独立目录，例如
   `work/training-pipeline-fear-v2/manual_cleaned_stories/<source_id>.md`。
2. 建立版本化的 `manual_cleaned_overrides.jsonl`；每条至少记录 `source_id`、原 `source_path`、
   原始 SHA-256、保留的多个 `[start_line, end_line]` 段、清洗后文本 SHA-256、人工理由和审核者。
3. 增加一个专用脚本，将多个已审核段按原顺序拼成 A，并拒绝重叠段、倒序段、空段、未授权来源或
   缺少审核理由的记录。
4. `stories.jsonl` 中应标记 `boundary_source=manual_cleaned_override`，并让 Step 2、Step 3 的
   provenance 同时记录覆盖清单哈希和清洗后文本哈希。
5. 为以下情况补 pytest：连续单段、两段拼接、重叠拒绝、乱序拒绝、源哈希漂移拒绝、覆盖文本哈希
   变化后使旧 Step 2/3 结果失效。
6. 清洗后重新从 Step 2 开始；不得复用旧分析或旧改写。

代码实现完成并通过测试后，才创建新的 v2 计划和独立工作目录。不要把 v2 的结果混入当前
`work/training-pipeline-fear-v1/`。

## 4. 完成标准与后续阶段

对当前 v1，Step 3 的完成标准是：

```text
teacher 待改写：0
progress/step_3_teacher_train_validation.json：status=completed
```

这两项当前已经满足。125 个阻断项只有在边界/清洗问题解决并经 Step 2 重新判为 `complete` 后，才会
增加到 Step 3 的候选总数。

当 Step 3 续跑后再次显示 `待改写：0`，继续执行：

```bash
python training/script/step_4_review_rewrites.py \
  --variant teacher --limit 20 --workers 2 --continue-on-error

python training/script/step_5_adjudicate_stories.py \
  --variant teacher --limit 20 --workers 2 --continue-on-error

python training/script/step_6_export_datasets.py \
  --variant teacher --auto-approve-passed --overwrite
```

