# SenseVoice CER 与 Whisper CER V8 评价报告

## 结论摘要

CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。

- SenseVoice 最低 CER 为 **0.0390**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- Whisper 最低 CER 为 **0.1437**，对应**VoxCPM2**。
- 双后端名次相关为 **0.000**。
- SenseVoice 的顺序是 Qwen3-TTS-12Hz-1.7B-Base、OmniVoice、dots.tts-base、IndexTTS2、VoxCPM2、MOSS-TTS-Local-Transformer-v1.5、LongCat-AudioDiT-1B；Whisper 的顺序是 VoxCPM2、Qwen3-TTS-12Hz-1.7B-Base、MOSS-TTS-Local-Transformer-v1.5、dots.tts-base、LongCat-AudioDiT-1B、OmniVoice、IndexTTS2。两个 ASR 后端排序不完全一致，应核对分歧模型的完整转写。

## 模型全文结果

| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 753.31 | 0.1114 | 3 | 0.1691 | 4 | 0.9550 |
| IndexTTS2 | 801.71 | 0.1787 | 4 | 0.2336 | 7 | 0.9395 |
| LongCat-AudioDiT-1B | 850.84 | 0.3247 | 7 | 0.1755 | 5 | 0.9578 |
| MOSS-TTS-Local-Transformer-v1.5 | 779.10 | 0.2563 | 6 | 0.1632 | 3 | 0.9574 |
| OmniVoice | 746.06 | 0.0836 | 2 | 0.2264 | 6 | 0.9594 |
| Qwen3-TTS-12Hz-1.7B-Base | 609.97 | 0.0390 | 1 | 0.1584 | 2 | 0.9554 |
| VoxCPM2 | 814.36 | 0.2181 | 5 | 0.1437 | 1 | 0.9487 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 我 | 0.0000 | 0.0000 |
| 旁白 | 0.0000 | 0.1154 |
| 姐姐 | 0.0000 | 0.0000 |
| 神秘声音 | 0.0385 | 0.1538 |

## 文本边界与证据

成品按 `longAudioTestV8/ai_deal.json` 合成，故以其中 97 段台词、2513 个规范化字符计算 CER。`text.md` 有 2537 个规范化字符，多出的 24 个说话人提示字符不进入合成；若直接作为参考会把输入差异误计为模型错误。规范化为 `zh-v1`，不做同音字或数字读法等价。

原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。

- 完整转写：[`per_audio.jsonl`](task9-20260726-v8-r01/per_audio.jsonl)
- 覆盖与配置：[`run_metadata.json`](task9-20260726-v8-r01/run_metadata.json)
- 冻结配置：`tts-bench/config/neutral-evaluation-v8.json`
