# OmniVoice 集中克隆说明

OmniVoice 在未提供参考音频转写时，会自动加载 `openai/whisper-large-v3-turbo`。该模型未缓存在本机，且本测试默认离线运行，因此会产生“找不到 cached snapshot”的错误。

测试入口已使用本地 SenseVoiceSmall 自动转写的三条参考文本，并通过 `--ref-text` 传给 OmniVoice；因此不会触发 Whisper 下载。三条转写定义在 [`../_clone_test_support.py`](../_clone_test_support.py) 中，其中“见习魔法师”按任务角色名修正了 ASR 的同音误识。

从任意工作目录执行：

```bash
bash cloneData/omnivoice/run_clone_omnivoice.sh
```

如需覆盖既有的输出，传入 `--overwrite`。运行期间的缓存和临时文本都会保留在本目录下的忽略目录中，不会进入版本控制。
