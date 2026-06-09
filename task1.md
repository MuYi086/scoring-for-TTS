1. 先修复 CosyVoice3（最容易，效果最明显）
pip uninstall cosyvoice
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
参考音频在`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`

目前系统里下载了多个tts引擎:
1. CosyVoice3: /persistent/home/muyi086/hf-mirror/Fun-CosyVoice3-0.5B-2512
参考文档: https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
<!-- 2. MOSS-TTS: /persistent/home/muyi086/hf-mirror/MOSS/MOSS-TTS
参考文档: https://huggingface.co/OpenMOSS-Team/MOSS-TTS-v1.5 -->
3. Qwen3-TTS-12Hz-1.7B-Base: /persistent/home/muyi086/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-Base
参考文档: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base
你分别使用1和3对应的tts，结合`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式`目录的sample.wav，将`第一章.md`合成对应的音频wav,放在同级目录，命名为对应的tts名称_第一章.wav。我需要试听最终效果来比较这几个tts，如果tts需要锁定音色，你就先解析目录离的sample.wav特征作为锁定的音色