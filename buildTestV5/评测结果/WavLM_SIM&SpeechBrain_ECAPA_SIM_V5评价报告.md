# WavLM SIM 与 SpeechBrain ECAPA SIM V5 评价报告

## 结论摘要

SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。

- WavLM 5 角色宏平均最高为 **0.9561**，对应**MOSS-TTS-Local-Transformer-v1.5**。
- ECAPA 5 角色宏平均最高为 **0.7194**，对应**IndexTTS2**。
- 双后端名次相关为 **0.786**；两种嵌入空间不直接平均原始值。

## 模型 5 角色宏平均

| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9338 | 6 | 0.6201 | 7 |
| IndexTTS2 | 0.9452 | 3 | 0.7194 | 1 |
| LongCat-AudioDiT-1B | 0.9484 | 2 | 0.7067 | 2 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9561 | 1 | 0.6882 | 3 |
| OmniVoice | 0.8850 | 7 | 0.6496 | 6 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9428 | 4 | 0.6512 | 5 |
| VoxCPM2 | 0.9374 | 5 | 0.6663 | 4 |

## 逐角色结果

| 模型 | 角色 | 片段数 | WavLM SIM ↑ | ECAPA SIM ↑ |
| --- | --- | ---: | ---: | ---: |
| dots.tts-base | 我 | 5 | 0.9373 | 0.6693 |
| dots.tts-base | 旁白 | 5 | 0.9357 | 0.6604 |
| dots.tts-base | 枯臂男子 | 5 | 0.9270 | 0.6231 |
| dots.tts-base | 老妇人 | 5 | 0.9338 | 0.5675 |
| dots.tts-base | 蒙眼罩的老人 | 3 | 0.9354 | 0.5802 |
| IndexTTS2 | 我 | 5 | 0.9420 | 0.7902 |
| IndexTTS2 | 旁白 | 5 | 0.9407 | 0.7833 |
| IndexTTS2 | 枯臂男子 | 5 | 0.9578 | 0.6836 |
| IndexTTS2 | 老妇人 | 5 | 0.9585 | 0.6377 |
| IndexTTS2 | 蒙眼罩的老人 | 5 | 0.9269 | 0.7022 |
| LongCat-AudioDiT-1B | 我 | 5 | 0.9415 | 0.7768 |
| LongCat-AudioDiT-1B | 旁白 | 5 | 0.9405 | 0.7163 |
| LongCat-AudioDiT-1B | 枯臂男子 | 5 | 0.9607 | 0.6971 |
| LongCat-AudioDiT-1B | 老妇人 | 5 | 0.9599 | 0.6222 |
| LongCat-AudioDiT-1B | 蒙眼罩的老人 | 5 | 0.9395 | 0.7210 |
| MOSS-TTS-Local-Transformer-v1.5 | 我 | 5 | 0.9565 | 0.7393 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 5 | 0.9658 | 0.7343 |
| MOSS-TTS-Local-Transformer-v1.5 | 枯臂男子 | 5 | 0.9512 | 0.6611 |
| MOSS-TTS-Local-Transformer-v1.5 | 老妇人 | 5 | 0.9576 | 0.6126 |
| MOSS-TTS-Local-Transformer-v1.5 | 蒙眼罩的老人 | 5 | 0.9493 | 0.6938 |
| OmniVoice | 我 | 5 | 0.9366 | 0.7216 |
| OmniVoice | 旁白 | 5 | 0.9467 | 0.7229 |
| OmniVoice | 枯臂男子 | 5 | 0.7502 | 0.5647 |
| OmniVoice | 老妇人 | 5 | 0.9231 | 0.6116 |
| OmniVoice | 蒙眼罩的老人 | 5 | 0.8686 | 0.6273 |
| Qwen3-TTS-12Hz-1.7B-Base | 我 | 5 | 0.9078 | 0.6995 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 5 | 0.9688 | 0.6976 |
| Qwen3-TTS-12Hz-1.7B-Base | 枯臂男子 | 5 | 0.9610 | 0.6315 |
| Qwen3-TTS-12Hz-1.7B-Base | 老妇人 | 5 | 0.9564 | 0.6117 |
| Qwen3-TTS-12Hz-1.7B-Base | 蒙眼罩的老人 | 5 | 0.9198 | 0.6156 |
| VoxCPM2 | 我 | 5 | 0.9320 | 0.7455 |
| VoxCPM2 | 旁白 | 5 | 0.9490 | 0.7367 |
| VoxCPM2 | 枯臂男子 | 5 | 0.9396 | 0.5881 |
| VoxCPM2 | 老妇人 | 5 | 0.9582 | 0.6179 |
| VoxCPM2 | 蒙眼罩的老人 | 5 | 0.9084 | 0.6433 |

## 原始音频校准与边界

- WavLM：同说话人分段均值 **0.9715**；跨角色均值 **0.8186**。
- ECAPA：同说话人分段均值 **0.8095**；跨角色均值 **0.5705**。
- WavLM 的跨角色均值 0.8186 低于模型宏平均 0.8850–0.9561。应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。
- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。
- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。

- 35 个模型/角色结果（7 个模型 × 5 个角色）：[`speaker_similarity.jsonl`](task6-20260724-v5-r01/speaker_similarity.jsonl)
- 15 个校准对：[`speaker_calibration.jsonl`](task6-20260724-v5-r01/speaker_calibration.jsonl)
- 冻结配置：`tts-bench/config/neutral-evaluation-v5.json`
