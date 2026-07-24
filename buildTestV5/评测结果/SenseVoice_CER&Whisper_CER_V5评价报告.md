# SenseVoice CER 与 Whisper CER V5 评价报告

## 结论摘要

CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。

- SenseVoice 最低 CER 为 **0.0365**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- Whisper 最低 CER 为 **0.0917**，对应**OmniVoice**。
- 双后端名次相关为 **0.429**。
- SenseVoice 的顺序是 Qwen3-TTS-12Hz-1.7B-Base、MOSS-TTS-Local-Transformer-v1.5、OmniVoice、dots.tts-base、VoxCPM2、IndexTTS2、LongCat-AudioDiT-1B；Whisper 的顺序是 OmniVoice、Qwen3-TTS-12Hz-1.7B-Base、IndexTTS2、MOSS-TTS-Local-Transformer-v1.5、LongCat-AudioDiT-1B、VoxCPM2、dots.tts-base。两个 ASR 后端排序不完全一致，应核对分歧模型的完整转写。

## 模型全文结果

| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 1188.44 | 0.1574 | 4 | 0.3425 | 7 | 0.8979 |
| IndexTTS2 | 1392.54 | 0.2130 | 6 | 0.1502 | 3 | 0.9463 |
| LongCat-AudioDiT-1B | 1477.40 | 0.2599 | 7 | 0.2156 | 5 | 0.9427 |
| MOSS-TTS-Local-Transformer-v1.5 | 1395.38 | 0.1256 | 2 | 0.1600 | 4 | 0.9499 |
| OmniVoice | 1317.83 | 0.1483 | 3 | 0.0917 | 1 | 0.9569 |
| Qwen3-TTS-12Hz-1.7B-Base | 1118.19 | 0.0365 | 1 | 0.1307 | 2 | 0.9576 |
| VoxCPM2 | 1384.51 | 0.1744 | 5 | 0.2253 | 6 | 0.9417 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 我 | 0.0213 | 0.0638 |
| 旁白 | 0.0000 | 0.0303 |
| 枯臂男子 | 0.0444 | 0.0222 |
| 老妇人 | 0.0536 | 0.0714 |
| 蒙眼罩的老人 | 0.3855 | 0.1446 |

## 文本边界与证据

成品按 `buildTestV5/ai_deal.json` 合成，故以其中 93 段台词、4713 个规范化字符计算 CER。`text.md` 有 4911 个规范化字符，多出的 198 个说话人提示字符不进入合成；若直接作为参考会把输入差异误计为模型错误。规范化为 `zh-v1`，不做同音字或数字读法等价。

原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。

- 完整转写：[`per_audio.jsonl`](task6-20260724-v5-r01/per_audio.jsonl)
- 覆盖与配置：[`run_metadata.json`](task6-20260724-v5-r01/run_metadata.json)
- 冻结配置：`tts-bench/config/neutral-evaluation-v5.json`
