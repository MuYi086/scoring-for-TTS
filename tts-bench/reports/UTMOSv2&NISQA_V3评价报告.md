# UTMOSv2 与 NISQA V3 评价报告

## 结论摘要

本次使用 UTMOSv2 和 NISQA-TTS 两个无参考自然度预测器，评价 24 条 V3 克隆音频和 3 条原始参考音频。两个后端均完成 27/27，预测 MOS 越高越好。

- UTMOSv2 三角色宏平均最高为 **3.3008**，对应**OmniVoice**。
- NISQA-TTS 三角色宏平均最高为 **4.1863**，对应**mimo-v2.5-tts-voiceclone**。
- 两组稠密名次的相关为 **-0.048**；两后端保持独立名次，不跨量纲加权。
- 原始参考音频宏平均为 UTMOSv2 **2.8366**、NISQA-TTS **4.2709**。

## 模型宏平均与同角色基线差

| 模型 | UTMOSv2 ↑ | 名次 | 相对原始 | NISQA-TTS ↑ | 名次 | 相对原始 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 2.4121 | 8 | -0.4245 | 3.6900 | 8 | -0.5808 |
| IndexTTS2 | 2.9082 | 5 | +0.0716 | 4.0877 | 3 | -0.1832 |
| LongCat-AudioDiT-1B | 2.7292 | 6 | -0.1074 | 4.0509 | 4 | -0.2199 |
| mimo-v2.5-tts-voiceclone | 3.1608 | 3 | +0.3242 | 4.1863 | 1 | -0.0846 |
| MOSS-TTS-Local-Transformer-v1.5 | 2.7240 | 7 | -0.1126 | 4.1434 | 2 | -0.1274 |
| OmniVoice | 3.3008 | 1 | +0.4642 | 4.0142 | 6 | -0.2566 |
| Qwen3-TTS-12Hz-1.7B-Base | 3.2572 | 2 | +0.4206 | 3.9604 | 7 | -0.3105 |
| VoxCPM2 | 2.9447 | 4 | +0.1081 | 4.0244 | 5 | -0.2464 |

## 原始参考音频基线

| 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |
| --- | ---: | ---: |
| 旁白 | 2.7402 | 4.2813 |
| 小公主 | 2.9453 | 4.3239 |
| 辰南 | 2.8242 | 4.2074 |
| 三角色宏平均 | **2.8366** | **4.2709** |

## 逐角色结果

| 模型 | 角色 | UTMOSv2 ↑ | NISQA-TTS ↑ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 2.3574 | 3.5918 |
| dots.tts-base | 小公主 | 2.0977 | 3.5604 |
| dots.tts-base | 辰南 | 2.7812 | 3.9179 |
| IndexTTS2 | 旁白 | 3.1113 | 4.1371 |
| IndexTTS2 | 小公主 | 2.3789 | 3.8451 |
| IndexTTS2 | 辰南 | 3.2344 | 4.2808 |
| LongCat-AudioDiT-1B | 旁白 | 2.8867 | 4.3135 |
| LongCat-AudioDiT-1B | 小公主 | 2.3516 | 3.5777 |
| LongCat-AudioDiT-1B | 辰南 | 2.9492 | 4.2615 |
| mimo-v2.5-tts-voiceclone | 旁白 | 3.3105 | 4.5531 |
| mimo-v2.5-tts-voiceclone | 小公主 | 3.0703 | 4.0178 |
| mimo-v2.5-tts-voiceclone | 辰南 | 3.1016 | 3.9880 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 3.1602 | 4.1240 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 1.8281 | 4.2248 |
| MOSS-TTS-Local-Transformer-v1.5 | 辰南 | 3.1836 | 4.0815 |
| OmniVoice | 旁白 | 3.2500 | 4.3006 |
| OmniVoice | 小公主 | 3.2129 | 3.5217 |
| OmniVoice | 辰南 | 3.4395 | 4.2204 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 3.4102 | 4.4503 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 2.7969 | 3.3453 |
| Qwen3-TTS-12Hz-1.7B-Base | 辰南 | 3.5645 | 4.0857 |
| VoxCPM2 | 旁白 | 3.2617 | 4.3423 |
| VoxCPM2 | 小公主 | 2.4141 | 3.6810 |
| VoxCPM2 | 辰南 | 3.1582 | 4.0500 |

## 可复现策略与边界

UTMOSv2 固定随机种子 `20260719`，每条音频执行 5 次裁剪并取模型内置平均，静音移除为 `true`。NISQA 使用面向合成语音的 `nisqa_tts.tar`（NISQA-TTS v1.0）离线整批推理。

MOS 预测器没有在本 V3 数据集上用真人评分重新校准，绝对值不等于人工 MOS。自然度也不表示文本念对、音色相似或角色表演合适；应与双 CER、双 SIM 及人工盲听结合。

## 可追溯证据

- 逐音频原始结果：[`per_audio.jsonl`](task4-2026-07-19-v3/per_audio.jsonl)
- 完整覆盖、裁剪参数与软件版本：[`run_metadata.json`](task4-2026-07-19-v3/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v3.json`](../config/neutral-evaluation-v3.json)
