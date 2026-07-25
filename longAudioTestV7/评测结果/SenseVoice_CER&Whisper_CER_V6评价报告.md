# SenseVoice CER 与 Whisper CER V7 评价报告

## 结论摘要

CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。

- SenseVoice 最低 CER 为 **0.0227**，对应**OmniVoice**。
- Whisper 最低 CER 为 **0.1060**，对应**LongCat-AudioDiT-1B**。
- 双后端名次相关为 **-0.071**。
- SenseVoice 的顺序是 OmniVoice、Qwen3-TTS-12Hz-1.7B-Base、dots.tts-base、VoxCPM2、MOSS-TTS-Local-Transformer-v1.5、LongCat-AudioDiT-1B、IndexTTS2；Whisper 的顺序是 LongCat-AudioDiT-1B、Qwen3-TTS-12Hz-1.7B-Base、MOSS-TTS-Local-Transformer-v1.5、OmniVoice、IndexTTS2、dots.tts-base、VoxCPM2。两个 ASR 后端排序呈负相关，不能用单一后端结论替代双后端核验。

## 模型全文结果

| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 614.49 | 0.0561 | 3 | 0.4182 | 6 | 0.9734 |
| IndexTTS2 | 658.60 | 0.1796 | 7 | 0.2488 | 5 | 0.9661 |
| LongCat-AudioDiT-1B | 676.84 | 0.1709 | 6 | 0.1060 | 1 | 0.9734 |
| MOSS-TTS-Local-Transformer-v1.5 | 639.32 | 0.1510 | 5 | 0.1960 | 3 | 0.9763 |
| OmniVoice | 574.03 | 0.0227 | 1 | 0.1985 | 4 | 0.9748 |
| Qwen3-TTS-12Hz-1.7B-Base | 514.59 | 0.0232 | 2 | 0.1713 | 2 | 0.9758 |
| VoxCPM2 | 652.76 | 0.1079 | 4 | 0.4860 | 7 | 0.9497 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 旁白 | 0.0000 | 0.0000 |
| 我 | 0.0385 | 0.0000 |
| 警察 | 0.0000 | 0.0357 |

## 文本边界与证据

成品按 `longAudioTestV7/ai_deal.json` 合成，故以其中 77 段台词、2066 个规范化字符计算 CER。`text.md` 有 2076 个规范化字符，多出的 10 个说话人提示字符不进入合成；若直接作为参考会把输入差异误计为模型错误。规范化为 `zh-v1`，不做同音字或数字读法等价。

原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。

- 完整转写：[`per_audio.jsonl`](task8-20260725-v7-r02/per_audio.jsonl)
- 覆盖与配置：[`run_metadata.json`](task8-20260725-v7-r02/run_metadata.json)
- 冻结配置：`tts-bench/config/neutral-evaluation-v7.json`
