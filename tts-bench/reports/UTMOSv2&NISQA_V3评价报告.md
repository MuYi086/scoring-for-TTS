# UTMOSv2 与 NISQA V3 评价报告

## 结论摘要

本次使用 UTMOSv2 和 NISQA-TTS 两个无参考自然度预测器，评价 24 条 V3 克隆音频和 3 条原始参考音频。两个后端均完成 27/27，预测 MOS 越高越好。

- UTMOSv2 三角色宏平均最高为 **3.5651**，对应**Qwen3-TTS-12Hz-1.7B-Base**。
- NISQA-TTS 三角色宏平均最高为 **4.5588**，对应**mimo-v2.5-tts-voiceclone**。
- 两组稠密名次的相关为 **0.381**；两后端保持独立名次，不跨量纲加权。
- 原始参考音频宏平均为 UTMOSv2 **2.7982**、NISQA-TTS **4.3215**。

## 模型宏平均与同角色基线差

| 模型 | UTMOSv2 ↑ | 名次 | 相对原始 | NISQA-TTS ↑ | 名次 | 相对原始 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 3.0501 | 8 | +0.2520 | 4.2401 | 6 | -0.0814 |
| IndexTTS2 | 3.2012 | 3 | +0.4030 | 4.1173 | 8 | -0.2043 |
| LongCat-AudioDiT-1B | 3.1582 | 4 | +0.3600 | 4.3112 | 3 | -0.0104 |
| mimo-v2.5-tts-voiceclone | 3.1549 | 5 | +0.3568 | 4.5588 | 1 | +0.2373 |
| MOSS-TTS-Local-Transformer-v1.5 | 3.2598 | 2 | +0.4616 | 4.2957 | 4 | -0.0259 |
| OmniVoice | 3.1289 | 6 | +0.3307 | 4.2814 | 5 | -0.0401 |
| Qwen3-TTS-12Hz-1.7B-Base | 3.5651 | 1 | +0.7669 | 4.4984 | 2 | +0.1769 |
| VoxCPM2 | 3.1100 | 7 | +0.3118 | 4.1587 | 7 | -0.1628 |

## 原始参考音频基线

| 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |
| --- | ---: | ---: |
| 旁白 | 2.7402 | 4.2813 |
| 小公主 | 2.9453 | 4.3239 |
| 三皇子 | 2.7090 | 4.3594 |
| 三角色宏平均 | **2.7982** | **4.3215** |

## 逐角色结果

| 模型 | 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 2.5449 | 4.0970 |
| dots.tts-base | 小公主 | 3.4219 | 4.3124 |
| dots.tts-base | 三皇子 | 3.1836 | 4.3110 |
| IndexTTS2 | 旁白 | 3.0645 | 4.1658 |
| IndexTTS2 | 小公主 | 3.3496 | 4.2504 |
| IndexTTS2 | 三皇子 | 3.1895 | 3.9355 |
| LongCat-AudioDiT-1B | 旁白 | 3.0938 | 4.4040 |
| LongCat-AudioDiT-1B | 小公主 | 3.4258 | 4.2593 |
| LongCat-AudioDiT-1B | 三皇子 | 2.9551 | 4.2703 |
| mimo-v2.5-tts-voiceclone | 旁白 | 2.6641 | 4.4387 |
| mimo-v2.5-tts-voiceclone | 小公主 | 3.2578 | 4.8039 |
| mimo-v2.5-tts-voiceclone | 三皇子 | 3.5430 | 4.4338 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 3.1953 | 4.1682 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 3.2422 | 4.4047 |
| MOSS-TTS-Local-Transformer-v1.5 | 三皇子 | 3.3418 | 4.3141 |
| OmniVoice | 旁白 | 3.0430 | 4.1698 |
| OmniVoice | 小公主 | 2.9766 | 4.4038 |
| OmniVoice | 三皇子 | 3.3672 | 4.2707 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 3.6426 | 4.4095 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 3.6953 | 4.4389 |
| Qwen3-TTS-12Hz-1.7B-Base | 三皇子 | 3.3574 | 4.6469 |
| VoxCPM2 | 旁白 | 2.9043 | 3.9367 |
| VoxCPM2 | 小公主 | 3.1055 | 4.2341 |
| VoxCPM2 | 三皇子 | 3.3203 | 4.3054 |

## 可复现策略与边界

UTMOSv2 固定随机种子 `20260719`，每条音频执行 5 次裁剪并取模型内置平均，静音移除为 `true`。NISQA 使用面向合成语音的 `nisqa_tts.tar`（NISQA-TTS v1.0）离线整批推理。

MOS 预测器没有在本 V3 数据集上用真人评分重新校准，绝对值不等于人工 MOS。自然度也不表示文本念对、音色相似或角色表演合适；应与双 CER、双 SIM 及人工盲听结合。

## 可追溯证据

- 逐音频原始结果：[`per_audio.jsonl`](task4-2026-07-19-v3-r02/per_audio.jsonl)
- 完整覆盖、裁剪参数与软件版本：[`run_metadata.json`](task4-2026-07-19-v3-r02/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
