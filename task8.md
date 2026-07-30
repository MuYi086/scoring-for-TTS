# Task 8：V8 旁白固定输入与成品

本文件只定义 Task 8 的固定输入、目标成品和本地证据位置。合成与公共评测的唯一执行顺序、命令、环境预检和报告规则均以[公共评测任务.md](公共评测任务.md)为准；执行时选择其中的 Task 8 绑定。

## 固定输入与最终成品

| 项目 | 固定值 |
| --- | --- |
| `<任务目录>` / `<评测目录>` | `longAudioTestV8` |
| `<版本标识>` | `V8` |
| 合成全文 / `<实际台词串>` | `longAudioTestV8/text.md` 的实际全文与原始顺序 |
| 人物 | 旁白 |
| 旁白参考音频 | `longAudioTestV8/mimo_旁白_v8.wav` |
| 参考文案 | 车轮碾过积雪，细碎声响中驯鹿的身影在漆黑的夜里纹丝不动。 |
| 音色说明 | 男性，三十至四十五岁，中低音域，音色厚实沉稳，略带沙哑质感，明亮度偏暗，共鸣饱满。咬字清晰有力，语速中等偏慢，节奏平稳，停顿自然，默认情绪基调冷静克制，带有成人叙述故事的神秘感和沉稳气质。 |
| IndexTTS2 成品 | `longAudioTestV8/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV8/audio_voxcpm2.wav` |
| 共享分段清单 | `longAudioTestV8/.task8_segment_manifest.json`（本地生成，不提交） |
| 逐段合成证据 | `longAudioTestV8/.task8_synthesis_evidence/<模型>/<成品 SHA-256>/`（本地生成，不提交） |
| 原始结果与报告目录 | `longAudioTestV8/评测结果` |
| 冻结评测契约 | `task-runner/task8/evaluation-contract.json` |

`audio_indextts2.wav` 和 `audio_voxcpm2.wav` 是第一阶段合成的输出，并非启动 Task 8 前必须由外部提供的前置条件。不得以 `ai_deal.json`、历史 V6/V7/V8/V9 音频、旧字符数、旧报告或其他版本文本替代本表输入；CER（字符错误率）的唯一参考是本表 `text.md` 的实际全文。
