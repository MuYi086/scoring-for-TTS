# SenseVoice CER 与 Whisper CER V9 评价报告

## 结论摘要

CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。

- SenseVoice 最低 CER 为 **0.0332**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- Whisper 最低 CER 为 **0.0837**，对应**LongCat-AudioDiT-1B**。
- 双后端名次相关为 **0.321**。
- SenseVoice 的顺序是 Qwen3-TTS-12Hz-1.7B-Base、dots.tts-base、OmniVoice、VoxCPM2、IndexTTS2、LongCat-AudioDiT-1B、MOSS-TTS-Local-Transformer-v1.5；Whisper 的顺序是 LongCat-AudioDiT-1B、Qwen3-TTS-12Hz-1.7B-Base、dots.tts-base、IndexTTS2、VoxCPM2、OmniVoice、MOSS-TTS-Local-Transformer-v1.5。两个 ASR 后端排序不完全一致，应核对分歧模型的完整转写。

## 模型全文结果

| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 476.06 | 0.1402 | 2 | 0.1568 | 3 | 0.9495 |
| IndexTTS2 | 501.67 | 0.2405 | 5 | 0.1721 | 4 | 0.9429 |
| LongCat-AudioDiT-1B | 515.21 | 0.2432 | 6 | 0.0837 | 1 | 0.9542 |
| MOSS-TTS-Local-Transformer-v1.5 | 523.48 | 0.4246 | 7 | 0.3847 | 7 | 0.8877 |
| OmniVoice | 478.10 | 0.1880 | 3 | 0.3083 | 6 | 0.9395 |
| Qwen3-TTS-12Hz-1.7B-Base | 392.50 | 0.0332 | 1 | 0.0924 | 2 | 0.9668 |
| VoxCPM2 | 508.09 | 0.2033 | 4 | 0.2764 | 5 | 0.9535 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 旁白 | 0.0000 | 0.0000 |
| 布罗迪 | 0.0000 | 0.0000 |
| 我 | 0.0000 | 0.0000 |
| 布罗迪姐姐 | 0.0000 | 0.0714 |
| 教授 | 0.0000 | 0.0000 |

## 文本边界与证据

成品按 `longAudioTestV9/ai_deal.json` 合成，故以其中 77 段台词、1505 个规范化字符计算 CER。text.md 是小说原文；ai_deal.json 是七条成品实际使用的分角色合成输入。两者规范化后分别为 1527 与 1505 个字符，且部分叙述、引号归属与台词顺序不同；因此全文 CER 只以 ai_deal.json 中 77 段 dialogue 的原始顺序拼接结果为准。若直接使用小说原文作为参考，会把输入差异误计为模型错误。规范化为 `zh-v1`，不做同音字或数字读法等价。

原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。

- 完整转写：[`per_audio.jsonl`](task10-v9-20260726T000000Z/per_audio.jsonl)
- 覆盖与配置：[`run_metadata.json`](task10-v9-20260726T000000Z/run_metadata.json)
- 冻结配置：`tts-bench/config/neutral-evaluation-v9.json`
