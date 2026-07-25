# 小说转有声 TTS V7 综合评价报告

## 最终结论

按照小说转有声生产工作流的默认权重——台词正确性 **50%**、角色音色 **30%**、自然听感 **20%**——本批排序如下：

1. **OmniVoice：83.33 分**
2. **MOSS-TTS-Local-Transformer-v1.5：70.83 分**
3. **Qwen3-TTS-12Hz-1.7B-Base：55.83 分**
4. **LongCat-AudioDiT-1B：47.50 分**
5. **dots.tts-base：33.33 分**
6. **VoxCPM2：31.67 分**
7. **IndexTTS2：27.50 分**

默认主生产候选为 **OmniVoice**。该结论是本批 7 个模型内的相对生产优先级，不是跨项目绝对质量分。正式定版前仍需核对双后端分歧、逐角色短板和连续长段盲听。

**OmniVoice**：SenseVoice CER、ECAPA SIM、NISQA-TTS列第 1；没有单后端末位。 **MOSS-TTS-Local-Transformer-v1.5**：WavLM SIM、UTMOSv2列第 1；没有单后端末位。 **Qwen3-TTS-12Hz-1.7B-Base**：没有单后端第 1；ECAPA SIM列第 7。 **LongCat-AudioDiT-1B**：Whisper CER列第 1；WavLM SIM列第 7。 **dots.tts-base**：没有单后端第 1；UTMOSv2、NISQA-TTS列第 7。 **VoxCPM2**：没有单后端第 1；Whisper CER列第 7。 **IndexTTS2**：没有单后端第 1；SenseVoice CER列第 7。

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
| 1 | **OmniVoice** | 75.00 | 37.50 | 91.67 | 27.50 | 91.67 | 18.33 | **83.33** |
| 2 | **MOSS-TTS-Local-Transformer-v1.5** | 50.00 | 25.00 | 91.67 | 27.50 | 91.67 | 18.33 | **70.83** |
| 3 | **Qwen3-TTS-12Hz-1.7B-Base** | 83.33 | 41.67 | 25.00 | 7.50 | 33.33 | 6.67 | **55.83** |
| 4 | **LongCat-AudioDiT-1B** | 58.33 | 29.17 | 33.33 | 10.00 | 41.67 | 8.33 | **47.50** |
| 5 | **dots.tts-base** | 41.67 | 20.83 | 41.67 | 12.50 | 0.00 | 0.00 | **33.33** |
| 6 | **VoxCPM2** | 25.00 | 12.50 | 25.00 | 7.50 | 58.33 | 11.67 | **31.67** |
| 7 | **IndexTTS2** | 16.67 | 8.33 | 41.67 | 12.50 | 33.33 | 6.67 | **27.50** |

## 六后端名次依据

| 模型 | SenseVoice CER | Whisper CER | WavLM SIM | ECAPA SIM | UTMOSv2 | NISQA-TTS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dots.tts-base | 3 | 6 | 5 | 4 | 7 | 7 |
| IndexTTS2 | 7 | 5 | 3 | 6 | 4 | 6 |
| LongCat-AudioDiT-1B | 6 | 1 | 7 | 3 | 6 | 3 |
| MOSS-TTS-Local-Transformer-v1.5 | 5 | 3 | 1 | 2 | 1 | 2 |
| OmniVoice | 1 | 4 | 2 | 1 | 2 | 1 |
| Qwen3-TTS-12Hz-1.7B-Base | 2 | 2 | 4 | 7 | 5 | 5 |
| VoxCPM2 | 4 | 7 | 6 | 5 | 3 | 4 |

## 权重敏感性

| 场景 | 台词 / 音色 / 听感 | 第 1 名 | 第 2 名 | 第 3 名 | 第 4 名 | 第 5 名 | 第 6 名 | 第 7 名 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 生产默认 | 50% / 30% / 20% | OmniVoice 83.33 | MOSS-TTS-Local-Transformer-v1.5 70.83 | Qwen3-TTS-12Hz-1.7B-Base 55.83 | LongCat-AudioDiT-1B 47.50 | dots.tts-base 33.33 | VoxCPM2 31.67 | IndexTTS2 27.50 |
| 内容优先 | 60% / 25% / 15% | OmniVoice 81.67 | MOSS-TTS-Local-Transformer-v1.5 66.67 | Qwen3-TTS-12Hz-1.7B-Base 61.25 | LongCat-AudioDiT-1B 49.58 | dots.tts-base 35.42 | VoxCPM2 30.00 | IndexTTS2 25.42 |
| 三维较均衡 | 40% / 30% / 30% | OmniVoice 85.00 | MOSS-TTS-Local-Transformer-v1.5 75.00 | Qwen3-TTS-12Hz-1.7B-Base 50.83 | LongCat-AudioDiT-1B 45.83 | VoxCPM2 35.00 | dots.tts-base 29.17 | IndexTTS2 29.17 |
| 角色音色优先 | 35% / 45% / 20% | OmniVoice 85.83 | MOSS-TTS-Local-Transformer-v1.5 77.08 | Qwen3-TTS-12Hz-1.7B-Base 47.08 | LongCat-AudioDiT-1B 43.75 | dots.tts-base 33.33 | VoxCPM2 31.67 | IndexTTS2 31.25 |
| 自然听感优先 | 35% / 20% / 45% | OmniVoice 85.83 | MOSS-TTS-Local-Transformer-v1.5 77.08 | Qwen3-TTS-12Hz-1.7B-Base 49.17 | LongCat-AudioDiT-1B 45.83 | VoxCPM2 40.00 | IndexTTS2 29.17 | dots.tts-base 22.92 |

## 生产建议与边界

1. 先用 **OmniVoice** 做一章试生产，逐句核对漏句、角色切换、停顿和异常重音。
2. 对 3 个有参考音频的角色做人工盲听，核对角色区分度与一致性。
3. 至少连续听取 10–15 分钟，检查机械感、伪影、背景层干扰和听觉疲劳。
4. 不因单一后端第一直接定版；背景音乐和音效会共同影响 ASR、说话人嵌入和质量预测器。

## 数据来源

- [SenseVoice CER 与 Whisper CER V7 评价报告](SenseVoice_CER&Whisper_CER_V6评价报告.md)
- [WavLM SIM 与 SpeechBrain ECAPA SIM V7 评价报告](WavLM_SIM&SpeechBrain_ECAPA_SIM_V6评价报告.md)
- [UTMOSv2 与 NISQA V7 评价报告](UTMOSv2&NISQA_V6评价报告.md)
- [V7 完整覆盖与配置快照](task8-20260725-v7-r02/run_metadata.json)
