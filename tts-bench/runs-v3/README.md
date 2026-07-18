# Task 4 V3 合成记录

本目录只登记 `cloneData/audio_v3/` 中 24 条本地大音频的路径、SHA-256 和 WAV 元数据，不存放音频本体。八个运行目录分别对应一个模型，共用合成冻结配置 [`synthesis-v3.json`](../config/synthesis-v3.json) 和评测清单 [`task4-2026-07-19-v3.jsonl`](../manifests/task4-2026-07-19-v3.jsonl)。

V3 评测时必须显式使用 `--runs-root tts-bench/runs-v3`，避免与 Task 3 V2 的不同文本和角色混合。
