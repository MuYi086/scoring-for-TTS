# Task 7：V7 旁白固定输入与成品

本文件只定义 Task 7 的固定输入、目标成品和本地证据位置。合成与公共评测的唯一执行顺序、命令、环境预检和报告规则均以[公共评测任务.md](公共评测任务.md)为准；执行时选择其中的 Task 7 绑定。

## 固定输入与最终成品

| 项目 | 固定值 |
| --- | --- |
| `<任务目录>` / `<评测目录>` | `longAudioTestV7` |
| `<版本标识>` | `V7` |
| 合成全文 / `<实际台词串>` | `longAudioTestV7/text.md` 全文，原始顺序不变 |
| 人物 | 旁白 |
| 旁白参考音频 | `longAudioTestV7/mimo_旁白_v7.wav` |
| 参考文案 | 夜夜如此，我听见头顶传来三声闷响，不像老鼠，更像精准的敲击。 |
| 音色说明 | 成年女性，中频偏暗，音色略带沙哑与气声，声线薄透但不过分尖锐，共鸣自然，发声力度适中偏轻柔。咬字清晰利落，语速中等偏慢，节奏均匀，停顿自然沉稳，默认情绪基调为冷静克制的叙述，隐含一丝不安但波动极小，整体气质内敛而耐听。 |
| IndexTTS2 成品 | `longAudioTestV7/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV7/audio_voxcpm2.wav` |
| 共享分段清单 | `longAudioTestV7/.task7_segment_manifest.json`（本地生成，不提交） |
| 逐段合成证据 | `longAudioTestV7/.task7_synthesis_evidence/<模型>/<成品 SHA-256>/`（本地生成，不提交） |
| 原始结果与报告目录 | `longAudioTestV7/评测结果` |
| 冻结评测契约 | `task-runner/task7/evaluation-contract.json` |

`audio_indextts2.wav` 和 `audio_voxcpm2.wav` 是第一阶段合成的输出，并非启动 Task 7 前必须由外部提供的前置条件。不得以 `ai_deal.json`、历史 V6/V7/V8/V9 音频、旧字符数或其他版本文本替代本表输入；CER（字符错误率）的唯一参考是本表 `text.md` 的实际全文。
