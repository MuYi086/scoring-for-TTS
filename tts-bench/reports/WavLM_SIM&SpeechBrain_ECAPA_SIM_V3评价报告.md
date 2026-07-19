# WavLM SIM 与 SpeechBrain ECAPA SIM V3 评价报告

## 结论摘要

本次将 24 条 V3 克隆音频逐一与同角色原始参考音频比较，并用两个独立说话人表征后端计算余弦相似度。另加入 3 个同说话人前后半段对照和 3 个跨角色原始音频对照，两个后端均完成 30/30 对；分数越高越好。

- WavLM 三角色宏平均最高为 **0.9844**，对应**LongCat-AudioDiT-1B**。
- SpeechBrain ECAPA 三角色宏平均最高为 **0.8756**，对应**IndexTTS2**。
- 两组稠密名次的相关为 **0.310**；两种嵌入空间不共用量纲，不跨后端平均。

## 模型宏平均

| 模型 | WavLM SIM ↑ | 名次 | SpeechBrain ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9739 | 4 | 0.8132 | 5 |
| IndexTTS2 | 0.9726 | 5 | 0.8756 | 1 |
| LongCat-AudioDiT-1B | 0.9844 | 1 | 0.8607 | 4 |
| mimo-v2.5-tts-voiceclone | 0.9723 | 6 | 0.7857 | 6 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9669 | 8 | 0.7426 | 8 |
| OmniVoice | 0.9702 | 7 | 0.8731 | 3 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9797 | 3 | 0.7756 | 7 |
| VoxCPM2 | 0.9834 | 2 | 0.8746 | 2 |

## 逐角色结果

| 模型 | 角色 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 0.9751 | 0.8179 |
| dots.tts-base | 小公主 | 0.9901 | 0.8320 |
| dots.tts-base | 三皇子 | 0.9567 | 0.7898 |
| IndexTTS2 | 旁白 | 0.9747 | 0.8807 |
| IndexTTS2 | 小公主 | 0.9922 | 0.8868 |
| IndexTTS2 | 三皇子 | 0.9511 | 0.8594 |
| LongCat-AudioDiT-1B | 旁白 | 0.9843 | 0.8991 |
| LongCat-AudioDiT-1B | 小公主 | 0.9907 | 0.8284 |
| LongCat-AudioDiT-1B | 三皇子 | 0.9781 | 0.8547 |
| mimo-v2.5-tts-voiceclone | 旁白 | 0.9810 | 0.8576 |
| mimo-v2.5-tts-voiceclone | 小公主 | 0.9846 | 0.8254 |
| mimo-v2.5-tts-voiceclone | 三皇子 | 0.9512 | 0.6741 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 0.9403 | 0.7707 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 0.9843 | 0.8234 |
| MOSS-TTS-Local-Transformer-v1.5 | 三皇子 | 0.9761 | 0.6335 |
| OmniVoice | 旁白 | 0.9637 | 0.8709 |
| OmniVoice | 小公主 | 0.9859 | 0.8894 |
| OmniVoice | 三皇子 | 0.9611 | 0.8589 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 0.9795 | 0.7214 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 0.9831 | 0.8549 |
| Qwen3-TTS-12Hz-1.7B-Base | 三皇子 | 0.9764 | 0.7505 |
| VoxCPM2 | 旁白 | 0.9842 | 0.8751 |
| VoxCPM2 | 小公主 | 0.9875 | 0.8502 |
| VoxCPM2 | 三皇子 | 0.9786 | 0.8984 |

## 原始音频校准对照

| 对照 | 类型 | WavLM SIM | SpeechBrain ECAPA SIM |
| --- | --- | ---: | ---: |
| 旁白原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9675 | 0.7431 |
| 小公主原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9852 | 0.8956 |
| 三皇子原始音频前半段 ↔ 后半段 | same_speaker_split_half | 0.9854 | 0.7942 |
| 旁白原始音频 ↔ 小公主原始音频 | different_speaker_reference_pair | 0.4960 | 0.2211 |
| 旁白原始音频 ↔ 三皇子原始音频 | different_speaker_reference_pair | 0.9523 | 0.5993 |
| 小公主原始音频 ↔ 三皇子原始音频 | different_speaker_reference_pair | 0.5007 | 0.3035 |

## 校准解读与边界

WavLM 的同说话人分段均值为 **0.9793**，跨角色均值为 **0.6497**；ECAPA 对应为 **0.8110** 和 **0.3746**。

本批每个角色仅有一条参考音频；同说话人正例来自同一录音切分，跨角色负例仅三对。因此不将 SIM 解释为‘同一人概率’，也不设置未经更大校准集确认的通过阈值。

## 可追溯证据

- 24 个克隆对：[`speaker_similarity.jsonl`](task4-2026-07-19-v3-r02/speaker_similarity.jsonl)
- 6 个校准对：[`speaker_calibration.jsonl`](task4-2026-07-19-v3-r02/speaker_calibration.jsonl)
- 完整覆盖与软件版本：[`run_metadata.json`](task4-2026-07-19-v3-r02/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
