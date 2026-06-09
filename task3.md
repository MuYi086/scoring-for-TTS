1. 先修复 CosyVoice3（最容易，效果最明显）
pip uninstall cosyvoice
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
2. 调试 Qwen3-TTS（需要提供 24kHz 参考音频）
先完成1和2，参考音频在`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`,然后读取`task1.md`并完成里面的任务