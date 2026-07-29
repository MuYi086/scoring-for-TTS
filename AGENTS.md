# Repository Guidelines

## 宪章与语言 (Constitution & Language)

修改代码、数据、文档或生成资产前，先阅读 [CONSTITUTION.md](CONSTITUTION.md)。本项目面向用户和贡献者的文档、总结、评审意见和代理输出默认中文优先。必须保留英文术语时，首次出现应补中文说明，例如 `voice casting`（角色配音映射）。

## 安全与配置提示 (Security)

不要提交密钥、本地环境文件或机器专属路径。大体积音频资产提交前必须单独确认，因为会显著增加仓库体积。

## 评测复现规则 (Evaluation Reproduction)

修改 Task 6–9 的评测环境、模型版本、输入发现、指标计算或报告导出前，先阅读 [公共评测任务.md](公共评测任务.md) 和对应 `task*.md`。权威入口是对应 `task-runner/task*/` 目录中的冻结契约、合成器、预检器、评测器和报告生成器；不得将 `tts-bench` 的通用短样本评价器用于这些长音频任务。

- 不要假设 GitHub 克隆包含 `cloneData/*.wav` 或 `hf-mirror`；前者被忽略，后者始终在仓库外。
- 正式评分前必须运行对应任务的 `check_task*_evaluation_setup.py`，确认冻结文本、共享分段清单、候选成品、哈希绑定逐段证据、双 ASR、CUDA 与环境版本。
- 每次复测使用新的 `--output-dir`；只有继续同一次未完成运行时才能使用 `--resume`。
- 不得把不同后端或不同量纲的原始值直接平均；长音频报告保持 SenseVoice 与 Whisper-large-v3-turbo 的独立名次、原始转写和健康门控。
- 更新环境变量、依赖版本、模型 revision 或复测命令时，同步更新对应 `task*.md`、[公共评测任务.md](公共评测任务.md) 和相关 `task-runner/task*/README.md`；如改动通用短样本基准，再同步更新 `tts-bench/README.md`。
