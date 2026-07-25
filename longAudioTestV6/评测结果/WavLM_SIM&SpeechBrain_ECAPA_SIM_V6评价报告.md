# WavLM SIM 与 SpeechBrain ECAPA SIM V6 评价报告

## 结论摘要

SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。

- WavLM 4 角色宏平均最高为 **0.9465**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- ECAPA 4 角色宏平均最高为 **0.7036**，对应**OmniVoice**。
- 双后端名次相关为 **-0.107**；两种嵌入空间不直接平均原始值。

## 模型 4 角色宏平均

| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9251 | 7 | 0.6320 | 6 |
| IndexTTS2 | 0.9340 | 6 | 0.6698 | 4 |
| LongCat-AudioDiT-1B | 0.9413 | 4 | 0.6855 | 2 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9407 | 5 | 0.6796 | 3 |
| OmniVoice | 0.9446 | 3 | 0.7036 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9465 | 1 | 0.5951 | 7 |
| VoxCPM2 | 0.9452 | 2 | 0.6598 | 5 |

## 逐角色结果

| 模型 | 角色 | 片段数 | WavLM SIM ↑ | ECAPA SIM ↑ |
| --- | --- | ---: | ---: | ---: |
| dots.tts-base | 旁白 | 5 | 0.9321 | 0.7041 |
| dots.tts-base | 三皇子 | 2 | 0.9520 | 0.4801 |
| dots.tts-base | 小公主 | 5 | 0.8996 | 0.6782 |
| dots.tts-base | 辰南 | 5 | 0.9169 | 0.6658 |
| IndexTTS2 | 旁白 | 5 | 0.9479 | 0.7300 |
| IndexTTS2 | 三皇子 | 2 | 0.9149 | 0.6331 |
| IndexTTS2 | 小公主 | 5 | 0.9239 | 0.6361 |
| IndexTTS2 | 辰南 | 5 | 0.9495 | 0.6802 |
| LongCat-AudioDiT-1B | 旁白 | 5 | 0.9504 | 0.7139 |
| LongCat-AudioDiT-1B | 三皇子 | 3 | 0.9631 | 0.6375 |
| LongCat-AudioDiT-1B | 小公主 | 5 | 0.8939 | 0.6998 |
| LongCat-AudioDiT-1B | 辰南 | 5 | 0.9579 | 0.6910 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 5 | 0.9675 | 0.6986 |
| MOSS-TTS-Local-Transformer-v1.5 | 三皇子 | 2 | 0.9634 | 0.6701 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 5 | 0.8858 | 0.6531 |
| MOSS-TTS-Local-Transformer-v1.5 | 辰南 | 5 | 0.9461 | 0.6968 |
| OmniVoice | 旁白 | 5 | 0.9366 | 0.7322 |
| OmniVoice | 三皇子 | 1 | 0.9794 | 0.6696 |
| OmniVoice | 小公主 | 5 | 0.9377 | 0.7424 |
| OmniVoice | 辰南 | 5 | 0.9248 | 0.6701 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 5 | 0.9401 | 0.6374 |
| Qwen3-TTS-12Hz-1.7B-Base | 三皇子 | 3 | 0.9551 | 0.4614 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 5 | 0.9362 | 0.6833 |
| Qwen3-TTS-12Hz-1.7B-Base | 辰南 | 5 | 0.9545 | 0.5985 |
| VoxCPM2 | 旁白 | 5 | 0.9415 | 0.6819 |
| VoxCPM2 | 三皇子 | 2 | 0.9500 | 0.6200 |
| VoxCPM2 | 小公主 | 5 | 0.9403 | 0.6937 |
| VoxCPM2 | 辰南 | 5 | 0.9489 | 0.6435 |

## 原始音频校准与边界

- WavLM：同说话人分段均值 **0.9523**；跨角色均值 **0.7655**。
- ECAPA：同说话人分段均值 **0.5830**；跨角色均值 **0.3285**。
- WavLM 的跨角色均值 0.7655 低于模型宏平均 0.9251–0.9465。应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。
- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。
- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。

- 28 个模型/角色结果（7 个模型 × 4 个角色）：[`speaker_similarity.jsonl`](task7-20260725-v6-r01/speaker_similarity.jsonl)
- 10 个校准对：[`speaker_calibration.jsonl`](task7-20260725-v6-r01/speaker_calibration.jsonl)
- 冻结配置：`tts-bench/config/neutral-evaluation-v6.json`
