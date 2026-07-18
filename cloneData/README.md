# 集中声音克隆测试

每个目录都通过对应 conda 环境直接调用 `modelScript/` 中的本地 TTS（文本转语音）脚本，不启动或依赖 HTTP 后端。每位角色会在独立模型子进程中完成一次克隆；子进程退出后，模型对象和 CUDA（英伟达通用计算平台）显存由系统回收，避免模型之间叠加占用显存。

测试使用仓库内的三段参考音频、固定台词和离线 SenseVoiceSmall 自动转写的参考文本。支持参考文本的模型会直接使用它；这避免了 OmniVoice 在离线模式下自动下载 Whisper（语音识别模型），也通常能提高克隆相似度。见习魔法师的角色名按任务定义校正了 ASR 的同音误识。

| 模型 | 目录与运行命令 | conda 环境 |
| --- | --- | --- |
| IndexTTS2 | `bash cloneData/indextts2/run_clone_indextts2.sh` | `unitale-tts-local` |
| dots.tts-base | `bash cloneData/dots_tts_base/run_clone_dots_tts_base.sh` | `dots_tts` |
| Qwen3-TTS-12Hz-1.7B-Base | `bash cloneData/qwen3_tts_12hz_1_7b_base/run_clone_qwen3_tts_12hz_1_7b_base.sh` | `qwen3-tts` |
| VoxCPM2 | `bash cloneData/voxcpm2/run_clone_voxcpm2.sh` | `voxcpm2` |
| MOSS-TTS-Local-Transformer-v1.5 | `bash cloneData/moss_tts_local_transformer/run_clone_moss_tts_local_transformer.sh` | `moss-tts-py310` |
| LongCat-AudioDiT-1B | `bash cloneData/longcat_audiodit_1b/run_clone_longcat_audiodit_1b.sh` | `longcat_audiodit` |
| OmniVoice | `bash cloneData/omnivoice/run_clone_omnivoice.sh` | `omnivoice` |
| MiMo-V2.5-TTS voiceclone | `python cloneData/mimo/test_clone_mimo.py` | 原生云端接口 |

所有本地模型输出统一到 `cloneData/` 根目录，文件名为 `<模型名>_<人物>.wav`。在真实运行前可附加 `--dry-run` 做纯本地预检；如果需要重测并覆盖同名文件，附加 `--overwrite`。

本地 Hugging Face 模型统一从 `HF_MIRROR_ROOT` 读取，默认目录为 `~/hf-mirror`。LongCat 与 IndexTTS2 需要的官方源码默认从仓库同级的 `TTS-and-VoiceDesign/api/vendor` 定位；目录布局不同时设置 `TTS_VENDOR_ROOT`。脚本和文档不保存机器专属绝对路径。

MiMo 是云端模型，没有可用的本地 conda 推理运行时；它的测试脚本直接调用官方云端接口，不经过本地后端，运行前需要在环境中设置 `MIMO_API_KEY`。不得将该密钥写入仓库或脚本。

## Task 4 V3 用例

V3 脚本名称统一带 `_v3`，使用 `testData/mimo_<人物>_v3.wav` 三段参考音频，角色为旁白、小公主和辰南。所有输出写入 `cloneData/audio_v3/`，命名为 `<模型名>_<人物>.wav`，不会覆盖上一轮音频。

本地模型使用对应的 `run_clone_*_v3.sh`；MiMo 使用：

```bash
python cloneData/mimo/test_clone_mimo_v3.py
```

每个通用本地模型的角色都在独立子进程中生成，完成后子进程退出；IndexTTS2 在一次加载中串行完成三个角色，并在 `finally` 中删除模型对象和清理 CUDA 缓存。两种路径都不会让模型常驻显存。运行前可加 `--dry-run`预检，重跑通用脚本或 MiMo 时需加 `--overwrite`。
