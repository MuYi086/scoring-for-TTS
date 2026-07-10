# 输入映射

TTS-PRISM-7B 的待诊断音频来自 `tts-bench/runs/<run_id>/synthesis.jsonl` 中 `status=complete` 的记录。不要复制或移动原始音频；若官方推理需要特定采样率，生成派生文件并在结果中记录其来源哈希及预处理标识。

对每个输入至少带上 `run_id`、`case_id`、音频路径、合成音频 SHA-256、语言与目标文本。目标文本用于人工复核和建立上下文，最终应以官方推理接口所需字段为准。
