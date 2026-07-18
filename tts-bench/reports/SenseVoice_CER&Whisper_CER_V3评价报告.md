# SenseVoice CER 与 Whisper CER V3 评价报告

## 结论摘要

本次以两个独立自动语音识别后端评价 8 个模型、3 个角色的 24 条 V3 克隆音频，并以 3 条原始参考音频检查后端自身偏差。27 条音频在两个后端均完整返回；CER（字符错误率）越低越好。

- SenseVoice 三角色宏平均最低为 **0.0123**，对应**IndexTTS2**、**mimo-v2.5-tts-voiceclone**、**OmniVoice**。
- Whisper 三角色宏平均最低为 **0.0123**，对应**dots.tts-base**、**LongCat-AudioDiT-1B**、**MOSS-TTS-Local-Transformer-v1.5**、**OmniVoice**、**Qwen3-TTS-12Hz-1.7B-Base**、**VoxCPM2**。
- 两组稠密名次的相关为 **-0.576**。报告保留两套独立名次，不将 CER 简单平均为总分。
- 逐样本后端差异最大的是 **mimo-v2.5-tts-voiceclone / 旁白**，绝对差为 **0.1481**。

## 模型宏平均

| 模型 | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.0247 | 2 | 0.0123 | 1 |
| IndexTTS2 | 0.0123 | 1 | 0.0247 | 2 |
| LongCat-AudioDiT-1B | 0.0247 | 2 | 0.0123 | 1 |
| mimo-v2.5-tts-voiceclone | 0.0123 | 1 | 0.0617 | 3 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.0600 | 3 | 0.0123 | 1 |
| OmniVoice | 0.0123 | 1 | 0.0123 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.0723 | 4 | 0.0123 | 1 |
| VoxCPM2 | 0.0600 | 3 | 0.0123 | 1 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 旁白 | 0.0357 | 0.1250 |
| 小公主 | 0.0000 | 0.0702 |
| 辰南 | 0.0536 | 0.0893 |
| 三角色宏平均 | **0.0298** | **0.0948** |

## 逐角色结果

| 模型 | 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 0.0741 | 0.0370 |
| dots.tts-base | 小公主 | 0.0000 | 0.0000 |
| dots.tts-base | 辰南 | 0.0000 | 0.0000 |
| IndexTTS2 | 旁白 | 0.0370 | 0.0741 |
| IndexTTS2 | 小公主 | 0.0000 | 0.0000 |
| IndexTTS2 | 辰南 | 0.0000 | 0.0000 |
| LongCat-AudioDiT-1B | 旁白 | 0.0741 | 0.0370 |
| LongCat-AudioDiT-1B | 小公主 | 0.0000 | 0.0000 |
| LongCat-AudioDiT-1B | 辰南 | 0.0000 | 0.0000 |
| mimo-v2.5-tts-voiceclone | 旁白 | 0.0370 | 0.1852 |
| mimo-v2.5-tts-voiceclone | 小公主 | 0.0000 | 0.0000 |
| mimo-v2.5-tts-voiceclone | 辰南 | 0.0000 | 0.0000 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 0.0370 | 0.0370 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 0.0000 | 0.0000 |
| MOSS-TTS-Local-Transformer-v1.5 | 辰南 | 0.1429 | 0.0000 |
| OmniVoice | 旁白 | 0.0370 | 0.0370 |
| OmniVoice | 小公主 | 0.0000 | 0.0000 |
| OmniVoice | 辰南 | 0.0000 | 0.0000 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 0.0741 | 0.0370 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 0.0000 | 0.0000 |
| Qwen3-TTS-12Hz-1.7B-Base | 辰南 | 0.1429 | 0.0000 |
| VoxCPM2 | 旁白 | 0.0370 | 0.0370 |
| VoxCPM2 | 小公主 | 0.0000 | 0.0000 |
| VoxCPM2 | 辰南 | 0.1429 | 0.0000 |

## 后端差异与边界

最大差异样本的 SenseVoice 转写为 `三皇子大吃一惊，对陈南的身份开始胡乱猜疑起来，他咳嗽了一声。`，Whisper 转写为 `三皇子大吃一惊对陈南的身份开始胡乱猜意起来他咳嗽了一声咳咳咳`。两侧统一使用 `zh-v1`：Unicode NFKC（兼容等价规范化）、小写化、删除空白和标点；不做繁简转换、数字读法归一或同音字容错。

CER 同时受 TTS 可懂度和 ASR 语言模型偏差影响；本批仅三个短句，不能代替更大文本集与人工复核。

## 可追溯证据

- 逐音频原始结果：[`per_audio.jsonl`](task4-2026-07-19-v3/per_audio.jsonl)
- 完整覆盖与软件版本：[`run_metadata.json`](task4-2026-07-19-v3/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
- 评测清单：[`task4-2026-07-19-v3.jsonl`](../manifests/task4-2026-07-19-v3.jsonl)
