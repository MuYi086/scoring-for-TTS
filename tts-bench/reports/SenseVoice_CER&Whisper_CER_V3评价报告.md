# SenseVoice CER 与 Whisper CER V3 评价报告

## 结论摘要

本次以两个独立自动语音识别后端评价 8 个模型、3 个角色的 24 条 V3 克隆音频，并以 3 条原始参考音频检查后端自身偏差。27 条音频在两个后端均完整返回；CER（字符错误率）越低越好。

- SenseVoice 三角色宏平均最低为 **0.0085**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- Whisper 三角色宏平均最低为 **0.0345**，对应**LongCat-AudioDiT-1B**、**Qwen3-TTS-12Hz-1.7B-Base**。
- 两组稠密名次的相关为 **0.865**。报告保留两套独立名次，不将 CER 简单平均为总分。
- 逐样本后端差异最大的是 **MOSS-TTS-Local-Transformer-v1.5 / 旁白**，绝对差为 **0.1034**。

## 模型宏平均

| 模型 | SenseVoice CER ↓ | 名次 | Whisper CER ↓ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.0200 | 2 | 0.0430 | 2 |
| IndexTTS2 | 0.0200 | 2 | 0.0430 | 2 |
| LongCat-AudioDiT-1B | 0.0315 | 3 | 0.0345 | 1 |
| mimo-v2.5-tts-voiceclone | 0.0463 | 4 | 0.0669 | 4 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.0516 | 5 | 0.0775 | 5 |
| OmniVoice | 0.0315 | 3 | 0.0460 | 3 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.0085 | 1 | 0.0345 | 1 |
| VoxCPM2 | 0.0315 | 3 | 0.0460 | 3 |

## 原始参考音频基线

| 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | ---: | ---: |
| 旁白 | 0.0357 | 0.1250 |
| 小公主 | 0.0000 | 0.0702 |
| 三皇子 | 0.0000 | 0.0702 |
| 三角色宏平均 | **0.0119** | **0.0885** |

## 逐角色结果

| 模型 | 角色 | SenseVoice CER ↓ | Whisper CER ↓ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 0.0345 | 0.1034 |
| dots.tts-base | 小公主 | 0.0000 | 0.0000 |
| dots.tts-base | 三皇子 | 0.0256 | 0.0256 |
| IndexTTS2 | 旁白 | 0.0345 | 0.1034 |
| IndexTTS2 | 小公主 | 0.0000 | 0.0000 |
| IndexTTS2 | 三皇子 | 0.0256 | 0.0256 |
| LongCat-AudioDiT-1B | 旁白 | 0.0690 | 0.1034 |
| LongCat-AudioDiT-1B | 小公主 | 0.0000 | 0.0000 |
| LongCat-AudioDiT-1B | 三皇子 | 0.0256 | 0.0000 |
| mimo-v2.5-tts-voiceclone | 旁白 | 0.0690 | 0.1379 |
| mimo-v2.5-tts-voiceclone | 小公主 | 0.0185 | 0.0370 |
| mimo-v2.5-tts-voiceclone | 三皇子 | 0.0513 | 0.0256 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 0.1034 | 0.2069 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 0.0000 | 0.0000 |
| MOSS-TTS-Local-Transformer-v1.5 | 三皇子 | 0.0513 | 0.0256 |
| OmniVoice | 旁白 | 0.0690 | 0.1379 |
| OmniVoice | 小公主 | 0.0000 | 0.0000 |
| OmniVoice | 三皇子 | 0.0256 | 0.0000 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 0.0000 | 0.1034 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 0.0000 | 0.0000 |
| Qwen3-TTS-12Hz-1.7B-Base | 三皇子 | 0.0256 | 0.0000 |
| VoxCPM2 | 旁白 | 0.0690 | 0.1379 |
| VoxCPM2 | 小公主 | 0.0000 | 0.0000 |
| VoxCPM2 | 三皇子 | 0.0256 | 0.0000 |

## 后端差异与边界

最大差异样本的 SenseVoice 转写为 `小公主恶狠狠的盯着他，其中的意思再明显不过，威胁监恐屑让她配合。`，Whisper 转写为 `小公主恶狠狠地盯着她,其中的意思再明显不过,威胁监控卸让她配合。`。两侧统一使用 `zh-v1`：Unicode NFKC（兼容等价规范化）、小写化、删除空白和标点；不做繁简转换、数字读法归一或同音字容错。

CER 同时受 TTS 可懂度和 ASR 语言模型偏差影响；本批仅三个短句，不能代替更大文本集与人工复核。

## 可追溯证据

- 逐音频原始结果：[`per_audio.jsonl`](task4-2026-07-19-v3-r02/per_audio.jsonl)
- 完整覆盖与软件版本：[`run_metadata.json`](task4-2026-07-19-v3-r02/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
- 评测清单：[`task4-2026-07-19-v3.jsonl`](../manifests/task4-2026-07-19-v3.jsonl)
