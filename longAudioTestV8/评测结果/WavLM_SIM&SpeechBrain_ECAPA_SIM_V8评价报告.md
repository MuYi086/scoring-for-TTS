# WavLM SIM 与 SpeechBrain ECAPA SIM V8 评价报告

## 结论摘要

SIM（说话人嵌入余弦相似度）衡量自动定位的角色片段与目标参考音色的接近程度，越高越好。它是 voice casting（角色配音映射）的量化辅助，不是同一人概率，也不评价台词或自然度。

- WavLM 4 角色宏平均最高为 **0.9275**，对应**LongCat-AudioDiT-1B**。
- ECAPA 4 角色宏平均最高为 **0.6514**，对应**LongCat-AudioDiT-1B**。
- 双后端名次相关为 **0.429**；两种嵌入空间不直接平均原始值。

## 模型 4 角色宏平均

| 模型 | WavLM SIM ↑ | 名次 | ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.8725 | 7 | 0.5966 | 6 |
| IndexTTS2 | 0.8841 | 6 | 0.5972 | 5 |
| LongCat-AudioDiT-1B | 0.9275 | 1 | 0.6514 | 1 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9129 | 2 | 0.5736 | 7 |
| OmniVoice | 0.9062 | 4 | 0.6377 | 2 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9087 | 3 | 0.6119 | 3 |
| VoxCPM2 | 0.8984 | 5 | 0.6039 | 4 |

## 逐角色结果

| 模型 | 角色 | 片段数 | 定位规则 | WavLM SIM ↑ | ECAPA SIM ↑ |
| --- | --- | ---: | --- | ---: | ---: |
| dots.tts-base | 我 | 5 | 标准 | 0.8802 | 0.5389 |
| dots.tts-base | 旁白 | 5 | 标准 | 0.9440 | 0.7414 |
| dots.tts-base | 姐姐 | 5 | 标准 | 0.8057 | 0.5275 |
| dots.tts-base | 神秘声音 | 2 | 标准 | 0.8601 | 0.5787 |
| IndexTTS2 | 我 | 5 | 标准 | 0.8815 | 0.4343 |
| IndexTTS2 | 旁白 | 5 | 标准 | 0.9061 | 0.7293 |
| IndexTTS2 | 姐姐 | 5 | 标准 | 0.8619 | 0.6410 |
| IndexTTS2 | 神秘声音 | 2 | 标准 | 0.8867 | 0.5841 |
| LongCat-AudioDiT-1B | 我 | 5 | 标准 | 0.8911 | 0.5444 |
| LongCat-AudioDiT-1B | 旁白 | 5 | 标准 | 0.9516 | 0.7697 |
| LongCat-AudioDiT-1B | 姐姐 | 5 | 标准 | 0.9056 | 0.6020 |
| LongCat-AudioDiT-1B | 神秘声音 | 2 | 标准 | 0.9618 | 0.6896 |
| MOSS-TTS-Local-Transformer-v1.5 | 我 | 5 | 标准 | 0.9165 | 0.4931 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 5 | 标准 | 0.9614 | 0.6683 |
| MOSS-TTS-Local-Transformer-v1.5 | 姐姐 | 5 | 标准 | 0.8571 | 0.5756 |
| MOSS-TTS-Local-Transformer-v1.5 | 神秘声音 | 3 | 标准 | 0.9166 | 0.5575 |
| OmniVoice | 我 | 5 | 标准 | 0.8841 | 0.4811 |
| OmniVoice | 旁白 | 5 | 标准 | 0.9479 | 0.7511 |
| OmniVoice | 姐姐 | 4 | 标准 | 0.8813 | 0.6487 |
| OmniVoice | 神秘声音 | 2 | 标准 | 0.9114 | 0.6700 |
| Qwen3-TTS-12Hz-1.7B-Base | 我 | 5 | 标准 | 0.8864 | 0.5146 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 5 | 标准 | 0.9780 | 0.6862 |
| Qwen3-TTS-12Hz-1.7B-Base | 姐姐 | 5 | 标准 | 0.8723 | 0.5978 |
| Qwen3-TTS-12Hz-1.7B-Base | 神秘声音 | 2 | 标准 | 0.8981 | 0.6492 |
| VoxCPM2 | 我 | 5 | 标准 | 0.8748 | 0.5093 |
| VoxCPM2 | 旁白 | 5 | 标准 | 0.9082 | 0.6666 |
| VoxCPM2 | 姐姐 | 5 | 标准 | 0.9093 | 0.6281 |
| VoxCPM2 | 神秘声音 | 2 | 标准 | 0.9010 | 0.6115 |

## 原始音频校准与边界

- WavLM：同说话人分段均值 **0.9241**；跨角色均值 **0.6849**。
- ECAPA：同说话人分段均值 **0.6634**；跨角色均值 **0.3721**。
- WavLM 的跨角色均值 0.6849 低于模型宏平均 0.8725–0.9275。应结合 ECAPA、逐角色结果和人工盲听，不设置未经校准的通过阈值。
- 角色片段由 Whisper 时间戳与冻结台词单调对齐，按全文位置等距选择，不按 SIM 高低挑片段。
- 只有某角色完全没有达到标准精确匹配长度的候选时，才允许使用配置冻结且显式标记的短台词回退片段；其 SIM 稳定性更弱。
- 背景音乐、音效、自动对齐误差和多人齐声都会影响嵌入；正式角色定版必须结合片段盲听。

- 28 个模型/角色结果（7 个模型 × 4 个角色）：[`speaker_similarity.jsonl`](task9-20260726-v8-r01/speaker_similarity.jsonl)
- 10 个校准对：[`speaker_calibration.jsonl`](task9-20260726-v8-r01/speaker_calibration.jsonl)
- 冻结配置：`tts-bench/config/neutral-evaluation-v8.json`
