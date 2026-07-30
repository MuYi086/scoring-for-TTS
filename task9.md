# Task 9：V9 旁白固定输入与成品

本文件只定义 Task 9 的固定输入、目标成品和本地证据位置。合成与公共评测的唯一执行顺序、命令、环境预检和报告规则均以[公共评测任务.md](公共评测任务.md)为准；执行时选择其中的 Task 9 绑定。

## 固定输入与最终成品

| 项目 | 固定值 |
| --- | --- |
| `<任务目录>` / `<评测目录>` | `longAudioTestV9` |
| `<版本标识>` | `V9` |
| 合成全文 / `<实际台词串>` | `longAudioTestV9/text.md` 的实际全文与原始顺序 |
| 人物 | 旁白 |
| 旁白参考音频 | `longAudioTestV9/mimo_旁白_v9.wav` |
| 参考文案 | 深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。 |
| 音色说明 | 女声，20–30 岁，中音区略偏低；音色沉静而敏锐，略带暖意，不沙哑或气声过度。咬字清晰但不刻板，语速中等偏慢，自然停顿；默认气质冷静而克制，像深夜播讲都市传说中的悬念播客主，不动声色地铺垫紧张氛围。 |
| IndexTTS2 成品 | `longAudioTestV9/audio_indextts2.wav` |
| VoxCPM2 成品 | `longAudioTestV9/audio_voxcpm2.wav` |
| 共享分段清单 | `longAudioTestV9/.task9_segment_manifest.json`（本地生成，不提交） |
| 逐段合成证据 | `longAudioTestV9/.task9_synthesis_evidence/<模型>/<成品 SHA-256>/`（本地生成，不提交） |
| 原始结果与报告目录 | `longAudioTestV9/评测结果` |
| 冻结评测契约 | `task-runner/task9/evaluation-contract.json` |

`audio_indextts2.wav` 和 `audio_voxcpm2.wav` 是第一阶段合成的输出，并非启动 Task 9 前必须由外部提供的前置条件。不得以 `ai_deal.json`、旧 V9 分角色台词、旧字符统计或其他版本文本/音频替代本表输入；CER（字符错误率）的唯一参考是本表 `text.md` 的实际全文。
