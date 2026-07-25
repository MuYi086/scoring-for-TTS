# SenseVoice CER 与 Whisper CER V6 评价报告

## 结论摘要

CER（字符错误率）衡量错字、漏字和多字，越低越好。小说生产中台词正确性应作为第一道硬门槛；它不评价音色、表演或自然度。两个 ASR（自动语音识别）后端独立排名，不直接平均原始 CER。

- SenseVoice 最低 CER 为 **0.0836**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- Whisper 最低 CER 为 **0.0970**，对应**OmniVoice**。
- 双后端名次相关为 **-0.393**。
- SenseVoice 的顺序是 Qwen3-TTS-12Hz-1.7B-Base、MOSS-TTS-Local-Transformer-v1.5、dots.tts-base、VoxCPM2、IndexTTS2、OmniVoice、LongCat-AudioDiT-1B；Whisper 的顺序是 OmniVoice、LongCat-AudioDiT-1B、dots.tts-base、Qwen3-TTS-12Hz-1.7B-Base、MOSS-TTS-Local-Transformer-v1.5、IndexTTS2、VoxCPM2。两个 ASR 后端排序呈负相关，不能用单一后端结论替代双后端核验。

## 模型全文结果

| 模型 | 时长（秒） | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 | 精确对齐率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 499.34 | 0.1430 | 3 | 0.1077 | 3 | 0.9417 |
| IndexTTS2 | 504.76 | 0.2647 | 5 | 0.1402 | 6 | 0.9310 |
| LongCat-AudioDiT-1B | 539.45 | 0.4004 | 7 | 0.1010 | 2 | 0.9389 |
| MOSS-TTS-Local-Transformer-v1.5 | 493.61 | 0.0875 | 2 | 0.1363 | 5 | 0.9344 |
| OmniVoice | 533.96 | 0.2956 | 6 | 0.0970 | 1 | 0.9316 |
| Qwen3-TTS-12Hz-1.7B-Base | 425.53 | 0.0836 | 1 | 0.1296 | 4 | 0.9467 |
| VoxCPM2 | 491.06 | 0.1884 | 4 | 0.3965 | 7 | 0.9361 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 旁白 | 0.0800 | 0.0800 |
| 三皇子 | 0.0370 | 0.0370 |
| 小公主 | 0.0385 | 0.0385 |
| 辰南 | 0.0000 | 0.0000 |

## 文本边界与证据

成品按 `longAudioTestV6/ai_deal.json` 合成，故以其中 58 段台词、1783 个规范化字符计算 CER。`text.md` 有 1826 个规范化字符，多出的 43 个说话人提示字符不进入合成；若直接作为参考会把输入差异误计为模型错误。规范化为 `zh-v1`，不做同音字或数字读法等价。

原始参考音频的 CER 可用于观察 ASR 对不同音色和录音条件的偏差，但不与成品直接排名。成品 CER 同时受 TTS、背景层和 ASR 影响；模型选择应检查完整转写，不把一个后端的名次当作绝对事实。

- 完整转写：[`per_audio.jsonl`](task7-20260725-v6-r01/per_audio.jsonl)
- 覆盖与配置：[`run_metadata.json`](task7-20260725-v6-r01/run_metadata.json)
- 冻结配置：`tts-bench/config/neutral-evaluation-v6.json`
