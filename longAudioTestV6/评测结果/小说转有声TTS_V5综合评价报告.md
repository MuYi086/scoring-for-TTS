# 小说转有声 TTS V6 综合评价报告

## 最终结论

按照小说转有声生产工作流的默认权重——台词正确性 **50%**、角色音色 **30%**、自然听感 **20%**——本批排序如下：

1. **OmniVoice：69.17 分**
2. **LongCat-AudioDiT-1B：57.50 分**
3. **MOSS-TTS-Local-Transformer-v1.5：52.50 分**
4. **Qwen3-TTS-12Hz-1.7B-Base：52.50 分**
5. **dots.tts-base：45.83 分**
6. **IndexTTS2：39.17 分**
7. **VoxCPM2：33.33 分**

默认主生产候选为 **OmniVoice**。该结论是本批 7 个模型内的相对生产优先级，不是跨项目绝对质量分。正式定版前仍需核对双后端分歧、逐角色短板和连续长段盲听。

**OmniVoice**：Whisper CER、ECAPA SIM、UTMOSv2列第 1；没有单后端末位。 **LongCat-AudioDiT-1B**：NISQA-TTS列第 1；SenseVoice CER列第 7。 **MOSS-TTS-Local-Transformer-v1.5**：没有单后端第 1；没有单后端末位。 **Qwen3-TTS-12Hz-1.7B-Base**：SenseVoice CER、WavLM SIM列第 1；ECAPA SIM、UTMOSv2、NISQA-TTS列第 7。 **dots.tts-base**：没有单后端第 1；WavLM SIM列第 7。 **IndexTTS2**：没有单后端第 1；没有单后端末位。 **VoxCPM2**：没有单后端第 1；Whisper CER列第 7。

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
| 1 | **OmniVoice** | 58.33 | 29.17 | 83.33 | 25.00 | 75.00 | 15.00 | **69.17** |
| 2 | **LongCat-AudioDiT-1B** | 41.67 | 20.83 | 66.67 | 20.00 | 83.33 | 16.67 | **57.50** |
| 3 | **MOSS-TTS-Local-Transformer-v1.5** | 58.33 | 29.17 | 50.00 | 15.00 | 41.67 | 8.33 | **52.50** |
| 4 | **Qwen3-TTS-12Hz-1.7B-Base** | 75.00 | 37.50 | 50.00 | 15.00 | 0.00 | 0.00 | **52.50** |
| 5 | **dots.tts-base** | 66.67 | 33.33 | 8.33 | 2.50 | 50.00 | 10.00 | **45.83** |
| 6 | **IndexTTS2** | 25.00 | 12.50 | 33.33 | 10.00 | 83.33 | 16.67 | **39.17** |
| 7 | **VoxCPM2** | 25.00 | 12.50 | 58.33 | 17.50 | 16.67 | 3.33 | **33.33** |

## 六后端名次依据

| 模型 | SenseVoice CER | Whisper CER | WavLM SIM | ECAPA SIM | UTMOSv2 | NISQA-TTS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 3 | 3 | 7 | 6 | 5 | 3 |
| IndexTTS2 | 5 | 6 | 6 | 4 | 2 | 2 |
| LongCat-AudioDiT-1B | 7 | 2 | 4 | 2 | 3 | 1 |
| MOSS-TTS-Local-Transformer-v1.5 | 2 | 5 | 5 | 3 | 4 | 5 |
| OmniVoice | 6 | 1 | 3 | 1 | 1 | 4 |
| Qwen3-TTS-12Hz-1.7B-Base | 1 | 4 | 1 | 7 | 7 | 7 |
| VoxCPM2 | 4 | 7 | 2 | 5 | 6 | 6 |

## 权重敏感性

| 场景 | 台词 / 音色 / 听感 | 第 1 名 | 第 2 名 | 第 3 名 | 第 4 名 | 第 5 名 | 第 6 名 | 第 7 名 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 生产默认 | 50% / 30% / 20% | OmniVoice 69.17 | LongCat-AudioDiT-1B 57.50 | MOSS-TTS-Local-Transformer-v1.5 52.50 | Qwen3-TTS-12Hz-1.7B-Base 52.50 | dots.tts-base 45.83 | IndexTTS2 39.17 | VoxCPM2 33.33 |
| 内容优先 | 60% / 25% / 15% | OmniVoice 67.08 | Qwen3-TTS-12Hz-1.7B-Base 57.50 | LongCat-AudioDiT-1B 54.17 | MOSS-TTS-Local-Transformer-v1.5 53.75 | dots.tts-base 49.58 | IndexTTS2 35.83 | VoxCPM2 32.08 |
| 三维较均衡 | 40% / 30% / 30% | OmniVoice 70.83 | LongCat-AudioDiT-1B 61.67 | MOSS-TTS-Local-Transformer-v1.5 50.83 | IndexTTS2 45.00 | Qwen3-TTS-12Hz-1.7B-Base 45.00 | dots.tts-base 44.17 | VoxCPM2 32.50 |
| 角色音色优先 | 35% / 45% / 20% | OmniVoice 72.92 | LongCat-AudioDiT-1B 61.25 | MOSS-TTS-Local-Transformer-v1.5 51.25 | Qwen3-TTS-12Hz-1.7B-Base 48.75 | IndexTTS2 40.42 | VoxCPM2 38.33 | dots.tts-base 37.08 |
| 自然听感优先 | 35% / 20% / 45% | OmniVoice 70.83 | LongCat-AudioDiT-1B 65.42 | IndexTTS2 52.92 | MOSS-TTS-Local-Transformer-v1.5 49.17 | dots.tts-base 47.50 | Qwen3-TTS-12Hz-1.7B-Base 36.25 | VoxCPM2 27.92 |

## 生产建议与边界

1. 先用 **OmniVoice** 做一章试生产，逐句核对漏句、角色切换、停顿和异常重音。
2. 对 4 个有参考音频的角色做人工盲听，核对角色区分度与一致性。
3. 至少连续听取 10–15 分钟，检查机械感、伪影、背景层干扰和听觉疲劳。
4. 不因单一后端第一直接定版；背景音乐和音效会共同影响 ASR、说话人嵌入和质量预测器。

## 数据来源

- [SenseVoice CER 与 Whisper CER V6 评价报告](SenseVoice_CER&Whisper_CER_V6评价报告.md)
- [WavLM SIM 与 SpeechBrain ECAPA SIM V6 评价报告](WavLM_SIM&SpeechBrain_ECAPA_SIM_V6评价报告.md)
- [UTMOSv2 与 NISQA V6 评价报告](UTMOSv2&NISQA_V6评价报告.md)
- [V6 完整覆盖与配置快照](task7-20260725-v6-r01/run_metadata.json)
