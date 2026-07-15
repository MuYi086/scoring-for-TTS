# IndexTTS2 集中克隆测试

脚本 [`test_clone_indextts2.py`](test_clone_indextts2.py) 在本地直接导入 `IndexTTS2`，测试三位角色：旁白、小公主、见习魔法师。它不调用或依赖任何 HTTP 后端。

通过 [`run_clone_indextts2.sh`](run_clone_indextts2.sh) 在 `unitale-tts-local` conda 环境运行。脚本仅使用任务指定的参考音频、文本与 8 维 `emo_vector`（情绪向量）；默认 `emo_alpha=0.6`、`num_beams=1`，以保持此前 IndexTTS2 服务的行为。

输出固定在 `cloneData/` 根目录，避免和脚本及说明混放：

```text
cloneData/indextts2_旁白.wav
cloneData/indextts2_小公主.wav
cloneData/indextts2_见习魔法师.wav
```

## 手工执行前检查

1. 确认仓库内 `testData/mimo_旁白.wav`、`testData/mimo_小公主.wav`、`testData/mimo_见习魔法师.wav` 存在。脚本会自动定位仓库根目录，不依赖 `/testData` 系统目录。
2. 确认本地模型目录 `<HF_MIRROR_ROOT>/IndexTeam/IndexTTS-2`、官方源码目录 `<TTS_VENDOR_ROOT>/index-tts` 均完整。脚本默认使用 `~/hf-mirror`，并从仓库同级的 `TTS-and-VoiceDesign/api/vendor` 定位官方源码；其他布局可通过同名环境变量覆盖。
3. 从项目根目录执行：

```bash
bash cloneData/indextts2/run_clone_indextts2.sh
```

只校验参考音频、离线模型权重和本地源码路径，并查看输出文件计划时：

```bash
bash cloneData/indextts2/run_clone_indextts2.sh --dry-run
```

默认仅在检测到 CUDA 时运行，避免误触发极慢的 CPU 推理。只有明确接受该代价时，才传入 `--allow-cpu`；此时脚本会自动关闭 FP16（半精度）并使用 CPU。

脚本一次加载模型、顺序完成三位角色的测试；无论成功或失败，都会在 `finally` 中删除模型对象、执行垃圾回收、同步 CUDA，并调用 `torch.cuda.empty_cache()` 与 `torch.cuda.ipc_collect()`。它不会常驻模型或启动任何服务。
