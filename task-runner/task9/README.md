# Task 9 专用合成脚本

本目录仅维护 Task 9 的运行逻辑，不修改 `modelScript/` 中用于跨设备迁移的模型安装与配置备份。

`run_task9_clone.py` 会严格串行调用 `indextts2.py` 与 `voxcpm2.py`，使用：

- `longAudioTestV9/text.md` 作为两条成品唯一的合成文本；
- `longAudioTestV9/mimo_旁白_v9.wav` 及其任务文案作为克隆参考；
- `longAudioTestV9/audio_indextts2.wav`、`longAudioTestV9/audio_voxcpm2.wav` 作为固定输出。

模型根目录和 IndexTTS2 源码目录必须通过参数或环境变量提供，不在仓库中记录机器专属路径。先进行无模型预检：

```bash
HF_MIRROR_ROOT=/path/to/hf-mirror \
INDEXTTS_CODE_PATH=/path/to/index-tts \
python task-runner/task9/run_task9_clone.py --dry-run
```

确认预检后，移除 `--dry-run` 才会开始合成。脚本默认禁止覆盖已有 WAV；只有明确传入 `--overwrite` 才会覆盖。
