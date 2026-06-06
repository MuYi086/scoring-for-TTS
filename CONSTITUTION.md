# 项目宪章 (Project Constitution)

版本：1.0.0  
批准日期：2026-05-24  
最后修订：2026-05-24

## 适用范围

本宪章适用于本仓库的代码、测试、音色库、生成资产、说明文档、提交说明、评审意见，以及自动化代理输出。若其他规则与本宪章冲突，优先遵循本宪章；若用户当次明确要求不同格式，则以用户要求为准。

## 核心原则

### 1. 中文优先 (Chinese First)

面向用户和贡献者的输出文档必须优先使用中文，包括 README、schema 说明、音色说明、任务总结、评审意见和 PR 描述。必须保留英文术语时，首次出现应写成 English term（中文说明），例如 voice casting（角色配音映射）。代码标识符、JSON 字段名、CLI 参数、第三方命令和机器可读输出保持原文，但应在说明文字中补充中文解释。

### 2. 音色库单一事实来源 (Single Source of Truth)

`src/timbre_design/data/voices_v2_106.json` 是音色结构化数据的唯一源文件。派生目录、试听音频、README、控制提示和下游映射都应从该 JSON 或代码逻辑生成，不应手工维护相互冲突的数据副本。

### 3. 可复现与可审计 (Reproducible and Auditable)

匹配、角色分配、VoxCPM2 控制提示和生成资产必须保留可追踪信息。涉及角色匹配质量、人工复核、低置信度兜底或空间音频摆位的变更，应输出清晰理由并配套测试。

### 4. 本地模型优先 (Local Model First)

本项目所有音频生成和合成必须使用本机 ModelScope 下载的 VoxCPM2 模型目录：`/persistent/home/muyi086/modelscope/VoxCPM2`。调用 `voxcpm`、项目脚本或其他 TTS（文本转语音）入口时，必须显式传入该目录作为 `--model-path` 或等价模型路径配置，并优先使用 `--local-files-only` 或等价离线选项，避免走默认远端模型、Hugging Face 下载或其他缓存模型。若因调试需要临时使用其他模型路径，必须在任务说明和结果总结中明确标注原因、路径和影响范围。

### 5. 一音色一目录 (One Voice per Directory)

每个音色的试听资产维护在 `samples/generated/<voice_id>/`。目录应包含 `voice.json`、`README.md`、`sample.txt`、`sample.voice.txt`、`sample.controls.json`，并在合成后包含 `sample.wav` 或 `sample.mp3`。大体积音频进入提交前必须明确确认。

### 6. 轻量、可测试、少依赖 (Lightweight and Testable)

本项目保持轻量 Python 包形态。新增逻辑优先写成可测试的小函数，避免引入 Web 框架、重型任务框架或不必要依赖。影响匹配、校验、资产生成、控制提示或导出格式的改动必须补充 pytest（Python 测试框架）用例。

## 文档规则

新增或修改 Markdown 文档时，默认使用中文标题和中文正文。必要英文标题、字段或术语后面应跟中文说明。示例命令可以保留英文命令本身，但命令用途、参数含义和注意事项必须用中文解释。

## 治理规则

修改本宪章时，需要在提交或 PR 中说明原因、影响范围和迁移要求。破坏既有音色 ID、JSON 字段、生成目录结构或中文优先规则的改动，必须被视为高风险变更并进行人工复核。
