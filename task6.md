# Task 6：V6 旁白固定输入与成品

本文件只定义 Task 6 的固定输入、目标成品和本地证据位置。合成与公共评测的唯一执行顺序、命令、环境预检和报告规则均以[公共评测任务.md](公共评测任务.md)为准；执行时选择其中的 Task 6 绑定。

## 固定输入与最终成品

| 项目 | 固定值 |
| --- | --- |
| `<任务目录>` / `<评测目录>` | `longAudioTestV6` |
| `<版本标识>` | `V6` |
| 合成全文 / `<实际台词串>` | `longAudioTestV6/text.md` 全文，原始顺序不变 |
| 人物 | 旁白 |
| 旁白参考音频 | `longAudioTestV6/mimo_旁白_v6.wav` |
| 参考文案 | 夜色中，两路人马各怀心思，表面客套，暗藏机锋，彼此试探周旋。 |
| 音色说明 | 男性，中年，音域中低，声线厚实略带磁性，明亮而不刺耳，音色沉稳平和中蕴含细微的叙述张力。咬字清晰干脆，语速中等偏慢，节奏均匀从容，语气平稳理性，自带一种冷眼旁观、洞察世事的气质。 |
| IndexTTS2 成品 | `longAudioTestV6/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV6/audio_voxcpm2.wav` |
| 共享分段清单 | `longAudioTestV6/.task6_segment_manifest.json`（本地生成，不提交） |
| 逐段合成证据 | `longAudioTestV6/.task6_synthesis_evidence/<模型>/<成品 SHA-256>/`（本地生成，不提交） |
| 原始结果与报告目录 | `longAudioTestV6/评测结果` |
| 冻结评测契约 | `task-runner/task6/evaluation-contract.json` |

`audio_indextts2.wav` 和 `audio_voxcpm2.wav` 是第一阶段合成的输出，并非启动 Task 6 前必须由外部提供的前置条件。不得以 `ai_deal.json`、历史 V6/V7/V8/V9 音频、旧字符数或其他版本文本替代本表输入；CER（字符错误率）的唯一参考是本表 `text.md` 的实际全文。
