# Repository Guidelines

## 项目结构

- `modelScript/`：本地或云端 TTS（文本转语音）模型脚本及安装说明。
- `task-runner/task6/` 至 `task-runner/task9/`：长音频合成、预检、评测和报告生成的权威入口。
- `longAudioTestV6/` 至 `longAudioTestV9/`：各任务的冻结文本、参考音频和报告目录；音频、分段清单、证据及运行结果通常被忽略，不应提交。
- `asr/`：ASR（自动语音识别）规范化规则、配置示例和数据契约；`tests/`：pytest（Python 测试框架）测试。
- `pyproject.toml`、`CONSTITUTION.md`、`公共评测任务.md`：依赖、项目原则和公共评测契约。

## 开发与测试命令

```bash
python -m pytest -q                         # 运行全部无模型测试
python -m pytest tests/test_task9_evaluation.py -q
ruff check .                                # 执行静态检查（若已安装 Ruff）
```

长音频任务先阅读对应 `task*.md` 和 `公共评测任务.md`。以 Task 9 为例，先执行 `python task-runner/task9/run_task9_clone.py --dry-run`，再运行对应 `check_task9_evaluation_setup.py`；正式评分每次使用新的 `--output-dir`，仅对同一次未完成运行使用 `--resume`。

## 编码与命名

使用 Python 3.11、4 个空格缩进和不超过 100 字符的行宽；函数与变量使用 `snake_case`，测试文件命名为 `tests/test_*.py`。新增逻辑应拆成小型、可测试函数，避免无必要的重型依赖。Markdown 文档和贡献说明中文优先，首次出现的英文术语附中文解释。

## 评测与测试规范

影响匹配、校验、合成证据、控制提示或报告格式的改动必须补充 pytest 用例。Task 6–9 只能按冻结输入串行评测 IndexTTS2 与 VoxCPM2；正式评分前必须通过任务预检。SenseVoice 与 Whisper-large-v3-turbo 的结果分别报告，禁止跨后端或跨量纲平均，也不得用 `tts-bench` 通用短样本评价器替代长音频运行器。

## 提交与 PR

提交信息沿用简短的 Conventional Commits（约定式提交）风格，例如 `feat: 增加模型脚本`、`fix: 修复评测路径`。PR 应说明变更范围、验证命令及评测影响；涉及任务契约、模型版本、环境变量或命令时，同时更新相关任务文档和 README。不要提交密钥、`.env`、机器专属路径或未经确认的大体积音频资产。
