# WavLM SIM 与 SpeechBrain ECAPA SIM V3 评价报告

## 结论摘要

本次将 24 条 V3 克隆音频逐一与同角色原始参考音频比较，并用两个独立说话人表征后端计算余弦相似度。另加入 3 个同说话人前后半段对照和 3 个跨角色原始音频对照，两个后端均完成 30/30 对；分数越高越好。

- WavLM 三角色宏平均最高为 **0.9675**，对应**LongCat-AudioDiT-1B**。
- SpeechBrain ECAPA 三角色宏平均最高为 **0.7507**，对应**IndexTTS2**。
- 两组稠密名次的相关为 **0.571**；两种嵌入空间不共用量纲，不跨后端平均。

## 模型宏平均

| 模型 | WavLM SIM ↑ | 名次 | SpeechBrain ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9420 | 8 | 0.6833 | 5 |
| IndexTTS2 | 0.9558 | 3 | 0.7507 | 1 |
| LongCat-AudioDiT-1B | 0.9675 | 1 | 0.6975 | 4 |
| mimo-v2.5-tts-voiceclone | 0.9481 | 6 | 0.6291 | 8 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9451 | 7 | 0.6443 | 6 |
| OmniVoice | 0.9553 | 4 | 0.7430 | 2 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9543 | 5 | 0.6361 | 7 |
| VoxCPM2 | 0.9651 | 2 | 0.7257 | 3 |

## 逐角色结果

| 模型 | 角色 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 0.9293 | 0.8285 |
| dots.tts-base | 小公主 | 0.9784 | 0.4195 |
| dots.tts-base | 辰南 | 0.9182 | 0.8018 |
| IndexTTS2 | 旁白 | 0.9354 | 0.8512 |
| IndexTTS2 | 小公主 | 0.9761 | 0.6133 |
| IndexTTS2 | 辰南 | 0.9558 | 0.7876 |
| LongCat-AudioDiT-1B | 旁白 | 0.9824 | 0.8703 |
| LongCat-AudioDiT-1B | 小公主 | 0.9587 | 0.4892 |
| LongCat-AudioDiT-1B | 辰南 | 0.9614 | 0.7329 |
| mimo-v2.5-tts-voiceclone | 旁白 | 0.9437 | 0.7004 |
| mimo-v2.5-tts-voiceclone | 小公主 | 0.9334 | 0.5543 |
| mimo-v2.5-tts-voiceclone | 辰南 | 0.9673 | 0.6327 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 0.9721 | 0.7305 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 0.9619 | 0.4435 |
| MOSS-TTS-Local-Transformer-v1.5 | 辰南 | 0.9014 | 0.7590 |
| OmniVoice | 旁白 | 0.9781 | 0.8560 |
| OmniVoice | 小公主 | 0.9666 | 0.6502 |
| OmniVoice | 辰南 | 0.9213 | 0.7226 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 0.9673 | 0.6464 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 0.9539 | 0.5252 |
| Qwen3-TTS-12Hz-1.7B-Base | 辰南 | 0.9416 | 0.7369 |
| VoxCPM2 | 旁白 | 0.9611 | 0.8712 |
| VoxCPM2 | 小公主 | 0.9801 | 0.5045 |
| VoxCPM2 | 辰南 | 0.9542 | 0.8012 |

## 原始音频校准对照

| 对照 | 类型 | WavLM SIM | SpeechBrain ECAPA SIM |
| --- | --- | ---: | ---: |
| 旁白原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9675 | 0.7431 |
| 小公主原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9852 | 0.8956 |
| 辰南原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9647 | 0.8533 |
| 旁白原始音频 ↔ 小公主原始音频 | different_speaker_reference_pair | 0.4960 | 0.2211 |
| 旁白原始音频 ↔ 辰南原始音频 | different_speaker_reference_pair | 0.9570 | 0.6584 |
| 小公主原始音频 ↔ 辰南原始音频 | different_speaker_reference_pair | 0.5345 | 0.2691 |

## 校准解读与边界

WavLM 的同说话人分段均值为 **0.9724**，跨角色均值为 **0.6625**；ECAPA 对应为 **0.8307** 和 **0.3828**。

本批每个角色仅有一条参考音频；同说话人正例来自同一录音切分，跨角色负例仅三对。因此不将 SIM 解释为‘同一人概率’，也不设置未经更大校准集确认的通过阈值。

## 可追溯证据

- 24 个克隆对：[`speaker_similarity.jsonl`](task4-2026-07-19-v3/speaker_similarity.jsonl)
- 6 个校准对：[`speaker_calibration.jsonl`](task4-2026-07-19-v3/speaker_calibration.jsonl)
- 完整覆盖与软件版本：[`run_metadata.json`](task4-2026-07-19-v3/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
