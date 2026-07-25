# WavLM SIM 与 SpeechBrain ECAPA SIM V7 评价报告

## 结论摘要

SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。

- WavLM 3 角色宏平均最高为 **0.9342**，对应**MOSS-TTS-Local-Transformer-v1.5**。
- ECAPA 3 角色宏平均最高为 **0.7049**，对应**OmniVoice**。
- 双后端名次相关为 **0.321**；两种嵌入空间不直接平均原始值。

## 模型 3 角色宏平均

| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.8627 | 5 | 0.6364 | 4 |
| IndexTTS2 | 0.8902 | 3 | 0.6246 | 6 |
| LongCat-AudioDiT-1B | 0.8266 | 7 | 0.6504 | 3 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9342 | 1 | 0.6788 | 2 |
| OmniVoice | 0.8919 | 2 | 0.7049 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.8697 | 4 | 0.5728 | 7 |
| VoxCPM2 | 0.8270 | 6 | 0.6316 | 5 |

## 逐角色结果

| 模型 | 角色 | 片段数 | 定位规则 | WavLM SIM ↑ | ECAPA SIM ↑ |
| --- | --- | ---: | --- | ---: | ---: |
| dots.tts-base | 旁白 | 5 | 标准 | 0.9789 | 0.7399 |
| dots.tts-base | 我 | 3 | 标准 | 0.9479 | 0.6480 |
| dots.tts-base | 警察 | 1 | 标准 | 0.6613 | 0.5214 |
| IndexTTS2 | 旁白 | 5 | 标准 | 0.9757 | 0.7646 |
| IndexTTS2 | 我 | 3 | 标准 | 0.9247 | 0.6049 |
| IndexTTS2 | 警察 | 1 | 标准 | 0.7701 | 0.5044 |
| LongCat-AudioDiT-1B | 旁白 | 5 | 标准 | 0.9826 | 0.7505 |
| LongCat-AudioDiT-1B | 我 | 3 | 标准 | 0.9534 | 0.6883 |
| LongCat-AudioDiT-1B | 警察 | 1 | 标准 | 0.5438 | 0.5124 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 5 | 标准 | 0.9851 | 0.7441 |
| MOSS-TTS-Local-Transformer-v1.5 | 我 | 3 | 标准 | 0.9485 | 0.6439 |
| MOSS-TTS-Local-Transformer-v1.5 | 警察 | 1 | 标准 | 0.8689 | 0.6485 |
| OmniVoice | 旁白 | 5 | 标准 | 0.9730 | 0.7857 |
| OmniVoice | 我 | 3 | 标准 | 0.9255 | 0.6510 |
| OmniVoice | 警察 | 1 | 标准 | 0.7773 | 0.6781 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 5 | 标准 | 0.9794 | 0.6832 |
| Qwen3-TTS-12Hz-1.7B-Base | 我 | 3 | 标准 | 0.9433 | 0.6188 |
| Qwen3-TTS-12Hz-1.7B-Base | 警察 | 2 | 短台词回退 | 0.6865 | 0.4163 |
| VoxCPM2 | 旁白 | 5 | 标准 | 0.9415 | 0.6761 |
| VoxCPM2 | 我 | 3 | 标准 | 0.9491 | 0.6613 |
| VoxCPM2 | 警察 | 1 | 标准 | 0.5905 | 0.5574 |

## 原始音频校准与边界

- WavLM：同说话人分段均值 **0.9520**；跨角色均值 **0.6771**。
- ECAPA：同说话人分段均值 **0.7672**；跨角色均值 **0.4610**。
- WavLM 的跨角色均值 0.6771 低于模型宏平均 0.8266–0.9342。应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。
- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。
- 只有某角色完全没有达到标准精确匹配长度的候选时，才允许使用配置冻结且显式标记的短台词回退片段；其 SIM 稳定性更弱。
- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。

- 21 个模型/角色结果（7 个模型 × 3 个角色）：[`speaker_similarity.jsonl`](task8-20260725-v7-r02/speaker_similarity.jsonl)
- 6 个校准对：[`speaker_calibration.jsonl`](task8-20260725-v7-r02/speaker_calibration.jsonl)
- 冻结配置：`tts-bench/config/neutral-evaluation-v7.json`
