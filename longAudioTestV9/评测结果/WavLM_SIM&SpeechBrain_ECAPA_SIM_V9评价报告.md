# WavLM SIM 与 SpeechBrain ECAPA SIM V9 评价报告

## 结论摘要

SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。

- WavLM 5 角色宏平均最高为 **0.9379**，对应**MOSS-TTS-Local-Transformer-v1.5**。
- ECAPA 5 角色宏平均最高为 **0.6781**，对应**OmniVoice**。
- 双后端名次相关为 **0.214**；两种嵌入空间不直接平均原始值。

## 模型 5 角色宏平均

| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9232 | 4 | 0.6463 | 5 |
| IndexTTS2 | 0.9210 | 5 | 0.6769 | 2 |
| LongCat-AudioDiT-1B | 0.9208 | 6 | 0.6691 | 4 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9379 | 1 | 0.6133 | 6 |
| OmniVoice | 0.9270 | 3 | 0.6781 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9175 | 7 | 0.5996 | 7 |
| VoxCPM2 | 0.9304 | 2 | 0.6722 | 3 |

## 逐角色结果

| 模型 | 角色 | 片段数 | 定位规则 | WavLM SIM ↑ | ECAPA SIM ↑ |
| --- | --- | ---: | --- | ---: | ---: |
| dots.tts-base | 旁白 | 5 | 标准 | 0.9626 | 0.7937 |
| dots.tts-base | 布罗迪 | 5 | 标准 | 0.7952 | 0.4293 |
| dots.tts-base | 我 | 5 | 标准 | 0.9103 | 0.5572 |
| dots.tts-base | 布罗迪姐姐 | 5 | 标准 | 0.9778 | 0.7401 |
| dots.tts-base | 教授 | 5 | 标准 | 0.9702 | 0.7111 |
| IndexTTS2 | 旁白 | 5 | 标准 | 0.9259 | 0.7528 |
| IndexTTS2 | 布罗迪 | 5 | 标准 | 0.7969 | 0.5479 |
| IndexTTS2 | 我 | 5 | 标准 | 0.9548 | 0.6081 |
| IndexTTS2 | 布罗迪姐姐 | 4 | 标准 | 0.9574 | 0.7714 |
| IndexTTS2 | 教授 | 5 | 标准 | 0.9702 | 0.7041 |
| LongCat-AudioDiT-1B | 旁白 | 5 | 标准 | 0.9762 | 0.8184 |
| LongCat-AudioDiT-1B | 布罗迪 | 5 | 标准 | 0.8134 | 0.4394 |
| LongCat-AudioDiT-1B | 我 | 5 | 标准 | 0.8864 | 0.6053 |
| LongCat-AudioDiT-1B | 布罗迪姐姐 | 4 | 标准 | 0.9830 | 0.7971 |
| LongCat-AudioDiT-1B | 教授 | 5 | 标准 | 0.9450 | 0.6852 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 5 | 标准 | 0.9576 | 0.7601 |
| MOSS-TTS-Local-Transformer-v1.5 | 布罗迪 | 5 | 标准 | 0.8873 | 0.5314 |
| MOSS-TTS-Local-Transformer-v1.5 | 我 | 5 | 标准 | 0.9138 | 0.4718 |
| MOSS-TTS-Local-Transformer-v1.5 | 布罗迪姐姐 | 4 | 标准 | 0.9809 | 0.7473 |
| MOSS-TTS-Local-Transformer-v1.5 | 教授 | 5 | 标准 | 0.9500 | 0.5557 |
| OmniVoice | 旁白 | 5 | 标准 | 0.9586 | 0.8108 |
| OmniVoice | 布罗迪 | 5 | 标准 | 0.8323 | 0.5183 |
| OmniVoice | 我 | 5 | 标准 | 0.9092 | 0.6242 |
| OmniVoice | 布罗迪姐姐 | 4 | 标准 | 0.9806 | 0.7578 |
| OmniVoice | 教授 | 5 | 标准 | 0.9540 | 0.6793 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 5 | 标准 | 0.9288 | 0.6251 |
| Qwen3-TTS-12Hz-1.7B-Base | 布罗迪 | 5 | 标准 | 0.7986 | 0.4309 |
| Qwen3-TTS-12Hz-1.7B-Base | 我 | 5 | 标准 | 0.9111 | 0.5387 |
| Qwen3-TTS-12Hz-1.7B-Base | 布罗迪姐姐 | 4 | 标准 | 0.9765 | 0.7272 |
| Qwen3-TTS-12Hz-1.7B-Base | 教授 | 5 | 标准 | 0.9725 | 0.6763 |
| VoxCPM2 | 旁白 | 5 | 标准 | 0.9698 | 0.8081 |
| VoxCPM2 | 布罗迪 | 5 | 标准 | 0.8060 | 0.4959 |
| VoxCPM2 | 我 | 5 | 标准 | 0.9346 | 0.5772 |
| VoxCPM2 | 布罗迪姐姐 | 4 | 标准 | 0.9713 | 0.7722 |
| VoxCPM2 | 教授 | 5 | 标准 | 0.9706 | 0.7075 |

## 原始音频校准与边界

- WavLM：同说话人分段均值 **0.9730**；跨角色均值 **0.8127**。
- ECAPA：同说话人分段均值 **0.6887**；跨角色均值 **0.5347**。
- WavLM 的跨角色均值 0.8127 低于模型宏平均 0.9175–0.9379。应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。
- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。
- 只有某角色完全没有达到标准精确匹配长度的候选时，才允许使用配置冻结且显式标记的短台词回退片段；其 SIM 稳定性更弱。
- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。

- 35 个模型/角色结果（7 个模型 × 5 个角色）：[`speaker_similarity.jsonl`](task10-v9-20260726T000000Z/speaker_similarity.jsonl)
- 15 个校准对：[`speaker_calibration.jsonl`](task10-v9-20260726T000000Z/speaker_calibration.jsonl)
- 冻结配置：`tts-bench/config/neutral-evaluation-v9.json`
