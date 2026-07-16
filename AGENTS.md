# Repository Guidelines

## 宪章与语言 (Constitution & Language)

修改代码、数据、文档或生成资产前，先阅读 [CONSTITUTION.md](CONSTITUTION.md)。本项目面向用户和贡献者的文档、总结、评审意见和代理输出默认中文优先。必须保留英文术语时，首次出现应补中文说明，例如 `voice casting`（角色配音映射）。

## 安全与配置提示 (Security)

不要提交密钥、本地环境文件或机器专属路径。大体积音频资产提交前必须单独确认，因为会显著增加仓库体积。

## 评测复现规则 (Evaluation Reproduction)

修改评测环境、模型版本、输入发现、指标计算或报告导出前，先阅读 [跨电脑复测指南](docs/跨电脑复测指南.md)。V2 权威入口是 `tts-bench/config/neutral-evaluation-v2.json`、`tts-bench/config/evaluation-assets-v2.json` 和 `tts-bench/scripts/run_neutral_evaluation_v2.py`。

- 不要假设 GitHub 克隆包含 `cloneData/*.wav` 或 `hf-mirror`；前者被忽略，后者始终在仓库外。
- 正式评分前必须运行 `check_neutral_evaluation_setup.py`，确认八模型乘三角色矩阵、登记哈希、评价权重和环境版本。
- 每次复测使用新的 `--output-dir`；只有继续同一次未完成运行时才能使用 `--resume`。
- 不得把六个后端的原始值跨量纲直接平均；报告保持双后端独立名次、原始音频基线和校准对照。
- 更新环境变量、依赖版本、模型 revision 或复测命令时，同步更新根 `README.md`、跨电脑复测指南和 `tts-bench/README.md`。
