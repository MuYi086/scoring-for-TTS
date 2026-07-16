# WavLM SIM 与 SpeechBrain ECAPA SIM V2 评价报告

## 结论摘要

本次将 24 条克隆音频逐一与同角色原始参考音频比较，并使用两个独立说话人表征后端计算余弦相似度。另加入 3 个同说话人前后半段对照和 3 个跨角色原始音频对照。两个后端各 30/30 完成，相似度越高越好。

- WavLM 宏平均最高的是**dots.tts-base**：**0.9530**。
- SpeechBrain ECAPA 宏平均最高的是**VoxCPM2**：**0.7959**。
- 两套独立名次的 Spearman 秩相关为 **-0.167**；领先模型不同，不能把某一个后端当作唯一事实。
- WavLM 的跨角色最高对照是“旁白原始音频 ↔ 见习魔法师原始音频”：**0.9429**，已经接近部分克隆对得分，说明本批数据不能使用未经校准的统一 WavLM 阈值。

## 模型宏平均

两个余弦分数的量纲和分布不同，只在各自后端内部排名，不跨后端平均。

| 模型 | WavLM SIM ↑ | 名次 | SpeechBrain ECAPA SIM ↑ | 名次 |
| --- | ---: | ---: | ---: | ---: |
| dots.tts-base | 0.9530 | 1 | 0.6859 | 8 |
| IndexTTS2 | 0.9169 | 8 | 0.7635 | 5 |
| LongCat-AudioDiT-1B | 0.9414 | 5 | 0.7948 | 2 |
| mimo-v2.5-tts-voiceclone | 0.9429 | 4 | 0.7900 | 3 |
| MOSS-TTS-Local-Transformer-v1.5 | 0.9327 | 6 | 0.7121 | 7 |
| OmniVoice | 0.9205 | 7 | 0.7816 | 4 |
| Qwen3-TTS-12Hz-1.7B-Base | 0.9496 | 2 | 0.7410 | 6 |
| VoxCPM2 | 0.9461 | 3 | 0.7959 | 1 |

## 校准对照

同说话人对照把同一条原始音频按时间切成前后两半，属于乐观上界；跨角色对照仅有三个角色，属于本批局部负例，不足以训练或冻结正式阈值。

| 对照 | 类型 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |
| --- | --- | ---: | ---: |
| 旁白原始音频前半段 ↔ 后半段 | 同说话人分段 | 0.9853 | 0.8369 |
| 小公主原始音频前半段 ↔ 后半段 | 同说话人分段 | 0.9763 | 0.8423 |
| 见习魔法师原始音频前半段 ↔ 后半段 | 同说话人分段 | 0.9847 | 0.8949 |
| 旁白原始音频 ↔ 小公主原始音频 | 跨角色原始音频 | 0.6133 | 0.3039 |
| 旁白原始音频 ↔ 见习魔法师原始音频 | 跨角色原始音频 | 0.9429 | 0.6354 |
| 小公主原始音频 ↔ 见习魔法师原始音频 | 跨角色原始音频 | 0.7306 | 0.3216 |
| 同说话人分段均值 | 汇总 | **0.9821** | **0.8580** |
| 跨角色原始音频均值 | 汇总 | **0.7623** | **0.4203** |

## 逐角色结果

| 模型 | 角色 | WavLM SIM ↑ | SpeechBrain ECAPA SIM ↑ |
| --- | --- | ---: | ---: |
| dots.tts-base | 旁白 | 0.9812 | 0.7298 |
| dots.tts-base | 小公主 | 0.9437 | 0.6281 |
| dots.tts-base | 见习魔法师 | 0.9342 | 0.6998 |
| IndexTTS2 | 旁白 | 0.9504 | 0.8756 |
| IndexTTS2 | 小公主 | 0.8416 | 0.7110 |
| IndexTTS2 | 见习魔法师 | 0.9586 | 0.7040 |
| LongCat-AudioDiT-1B | 旁白 | 0.9637 | 0.8701 |
| LongCat-AudioDiT-1B | 小公主 | 0.8948 | 0.6752 |
| LongCat-AudioDiT-1B | 见习魔法师 | 0.9656 | 0.8392 |
| mimo-v2.5-tts-voiceclone | 旁白 | 0.9374 | 0.8277 |
| mimo-v2.5-tts-voiceclone | 小公主 | 0.9378 | 0.7478 |
| mimo-v2.5-tts-voiceclone | 见习魔法师 | 0.9536 | 0.7946 |
| MOSS-TTS-Local-Transformer-v1.5 | 旁白 | 0.9266 | 0.7147 |
| MOSS-TTS-Local-Transformer-v1.5 | 小公主 | 0.9033 | 0.7151 |
| MOSS-TTS-Local-Transformer-v1.5 | 见习魔法师 | 0.9683 | 0.7065 |
| OmniVoice | 旁白 | 0.9622 | 0.8282 |
| OmniVoice | 小公主 | 0.8242 | 0.7104 |
| OmniVoice | 见习魔法师 | 0.9752 | 0.8062 |
| Qwen3-TTS-12Hz-1.7B-Base | 旁白 | 0.9317 | 0.7680 |
| Qwen3-TTS-12Hz-1.7B-Base | 小公主 | 0.9594 | 0.6957 |
| Qwen3-TTS-12Hz-1.7B-Base | 见习魔法师 | 0.9576 | 0.7593 |
| VoxCPM2 | 旁白 | 0.9779 | 0.8954 |
| VoxCPM2 | 小公主 | 0.8929 | 0.6366 |
| VoxCPM2 | 见习魔法师 | 0.9676 | 0.8557 |

## 结果解读

WavLM 更偏好 dots.tts-base 与 Qwen3-TTS；ECAPA 更偏好 VoxCPM2、LongCat 和 MiMo。IndexTTS2 在 WavLM 宏平均中最低，但在 ECAPA 中居中；dots.tts-base 则从 WavLM 第一降到 ECAPA 最后。这不是计算错误，而是两个检查点的训练数据、嵌入空间和对音高、韵律、录音条件的敏感性不同。

尤其是旁白与见习魔法师都是男性声线，WavLM 对这两个原始角色给出 0.9429 的高跨角色分。因此报告只陈述同一后端内的相对次序，不把 SIM 解释为‘同一人概率’，也不设置通过线。

## 适用边界

每个角色只有一条参考与一条目标句；同说话人正例来自同一录音切分，跨角色负例也只有三对。正式验证应加入更多同说话人跨文本录音、更多异说话人负例、性别与音高匹配的困难负例，并用人工盲听校准。

## 可追溯证据

- 24 个克隆对：[`speaker_similarity.jsonl`](task3-2026-07-16-v2/speaker_similarity.jsonl)
- 6 个校准对：[`speaker_calibration.jsonl`](task3-2026-07-16-v2/speaker_calibration.jsonl)
- 完整覆盖与软件版本：[`run_metadata.json`](task3-2026-07-16-v2/run_metadata.json)
- 冻结配置：[`neutral-evaluation-v2.json`](../config/neutral-evaluation-v2.json)
