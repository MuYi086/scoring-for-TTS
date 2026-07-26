# 小说转有声 TTS V9 综合评价报告

## 最终结论

按照小说转有声生产工作流的默认权重——台词正确性 **50%**、角色音色 **30%**、自然听感 **20%**——本批排序如下：

1. **Qwen3-TTS-12Hz-1.7B-Base：59.17 分**
2. **OmniVoice：57.50 分**
3. **dots.tts-base：55.00 分**
4. **IndexTTS2：55.00 分**
5. **VoxCPM2：51.67 分**
6. **LongCat-AudioDiT-1B：44.17 分**
7. **MOSS-TTS-Local-Transformer-v1.5：27.50 分**

默认主生产候选为 **Qwen3-TTS-12Hz-1.7B-Base**。该结论是本批 7 个模型内的相对生产优先级，不是跨项目绝对质量分。正式定版前仍需核对双后端分歧、逐角色短板和连续长段盲听。

**Qwen3-TTS-12Hz-1.7B-Base**：SenseVoice CER、UTMOSv2列第 1；WavLM SIM、ECAPA SIM列第 7。 **OmniVoice**：ECAPA SIM、NISQA-TTS列第 1；没有单后端末位。 **dots.tts-base**：没有单后端第 1；UTMOSv2列第 7。 **IndexTTS2**：没有单后端第 1；没有单后端末位。 **VoxCPM2**：没有单后端第 1；没有单后端末位。 **LongCat-AudioDiT-1B**：Whisper CER列第 1；NISQA-TTS列第 7。 **MOSS-TTS-Local-Transformer-v1.5**：WavLM SIM列第 1；SenseVoice CER、Whisper CER列第 7。

## 权重与统一尺度

| 生产维度 | 后端 | 权重 | 工作流依据 |
| --- | --- | ---: | --- |
| 台词正确性 | SenseVoice CER + Whisper CER | **50%** | 错字、漏句和重复会改变剧情并产生最高返工成本。 |
| 角色音色 | WavLM SIM + ECAPA SIM | **30%** | 多角色小说依赖稳定、可区分的角色配音映射。 |
| 自然听感 | UTMOSv2 + NISQA-TTS | **20%** | 影响长听疲劳和交付品质，但部分混音问题可后期修复。 |

六个后端原始值跨量纲，不能直接平均。本报告先在每个后端内独立排名，再统一转换为名次分：

```text
单后端名次分 = (模型数 - 该后端名次) / (模型数 - 1) × 100
维度分       = 该维度两个后端名次分的平均值
综合分       = 台词正确性分 × 50% + 角色音色分 × 30% + 自然听感分 × 20%
```

## 加权排序明细

| 综合名次 | 模型 | 台词正确性分 | 50% 贡献 | 角色音色分 | 30% 贡献 | 自然听感分 | 20% 贡献 | 综合分 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | **Qwen3-TTS-12Hz-1.7B-Base** | 91.67 | 45.83 | 0.00 | 0.00 | 66.67 | 13.33 | **59.17** |
| 2 | **OmniVoice** | 41.67 | 20.83 | 83.33 | 25.00 | 58.33 | 11.67 | **57.50** |
| 3 | **dots.tts-base** | 75.00 | 37.50 | 41.67 | 12.50 | 25.00 | 5.00 | **55.00** |
| 4 | **IndexTTS2** | 41.67 | 20.83 | 58.33 | 17.50 | 83.33 | 16.67 | **55.00** |
| 5 | **VoxCPM2** | 41.67 | 20.83 | 75.00 | 22.50 | 41.67 | 8.33 | **51.67** |
| 6 | **LongCat-AudioDiT-1B** | 58.33 | 29.17 | 33.33 | 10.00 | 25.00 | 5.00 | **44.17** |
| 7 | **MOSS-TTS-Local-Transformer-v1.5** | 0.00 | 0.00 | 58.33 | 17.50 | 50.00 | 10.00 | **27.50** |

## 六后端名次依据

| 模型 | SenseVoice CER | Whisper CER | WavLM SIM | ECAPA SIM | UTMOSv2 | NISQA-TTS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 2 | 3 | 4 | 5 | 7 | 4 |
| IndexTTS2 | 5 | 4 | 5 | 2 | 2 | 2 |
| LongCat-AudioDiT-1B | 6 | 1 | 6 | 4 | 4 | 7 |
| MOSS-TTS-Local-Transformer-v1.5 | 7 | 7 | 1 | 6 | 5 | 3 |
| OmniVoice | 3 | 6 | 3 | 1 | 6 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 1 | 2 | 7 | 7 | 1 | 5 |
| VoxCPM2 | 4 | 5 | 2 | 3 | 3 | 6 |

## 权重敏感性

| 场景 | 台词 / 音色 / 听感 | 第 1 名 | 第 2 名 | 第 3 名 | 第 4 名 | 第 5 名 | 第 6 名 | 第 7 名 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 生产默认 | 50% / 30% / 20% | Qwen3-TTS-12Hz-1.7B-Base 59.17 | OmniVoice 57.50 | dots.tts-base 55.00 | IndexTTS2 55.00 | VoxCPM2 51.67 | LongCat-AudioDiT-1B 44.17 | MOSS-TTS-Local-Transformer-v1.5 27.50 |
| 内容优先 | 60% / 25% / 15% | Qwen3-TTS-12Hz-1.7B-Base 65.00 | dots.tts-base 59.17 | OmniVoice 54.58 | IndexTTS2 52.08 | VoxCPM2 50.00 | LongCat-AudioDiT-1B 47.08 | MOSS-TTS-Local-Transformer-v1.5 22.08 |
| 三维较均衡 | 40% / 30% / 30% | IndexTTS2 59.17 | OmniVoice 59.17 | Qwen3-TTS-12Hz-1.7B-Base 56.67 | VoxCPM2 51.67 | dots.tts-base 50.00 | LongCat-AudioDiT-1B 40.83 | MOSS-TTS-Local-Transformer-v1.5 32.50 |
| 角色音色优先 | 35% / 45% / 20% | OmniVoice 63.75 | IndexTTS2 57.50 | VoxCPM2 56.67 | dots.tts-base 50.00 | Qwen3-TTS-12Hz-1.7B-Base 45.42 | LongCat-AudioDiT-1B 40.42 | MOSS-TTS-Local-Transformer-v1.5 36.25 |
| 自然听感优先 | 35% / 20% / 45% | IndexTTS2 63.75 | Qwen3-TTS-12Hz-1.7B-Base 62.08 | OmniVoice 57.50 | VoxCPM2 48.33 | dots.tts-base 45.83 | LongCat-AudioDiT-1B 38.33 | MOSS-TTS-Local-Transformer-v1.5 34.17 |

## 生产建议与边界

1. 先用 **Qwen3-TTS-12Hz-1.7B-Base** 做一章试生产，逐句核对漏句、角色切换、停顿和异常重音。
2. 对 5 个有参考音频的角色做人工盲听，核对角色区分度与一致性。
3. 至少连续听取 10–15 分钟，检查机械感、伪影、背景层干扰和听觉疲劳。
4. 不因单一后端第一直接定版；背景音乐和音效会共同影响 ASR、说话人嵌入和质量预测器。

## 数据来源

- [SenseVoice CER 与 Whisper CER V9 评价报告](SenseVoice_CER&Whisper_CER_V9评价报告.md)
- [WavLM SIM 与 SpeechBrain ECAPA SIM V9 评价报告](WavLM_SIM&SpeechBrain_ECAPA_SIM_V9评价报告.md)
- [UTMOSv2 与 NISQA V9 评价报告](UTMOSv2&NISQA_V9评价报告.md)
- [V9 完整覆盖与配置快照](task10-v9-20260726T000000Z/run_metadata.json)
