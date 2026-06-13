帮我在`scripts`目录完成一个脚本，命名为`tts_local_${模型名缩写}.py`。
脚本使用指定的模型完成克隆，当前指定的模型地址为: `/home/muyi086/hf-mirror/FunAudioLLM/Fun-CosyVoice3-0.5B-2512`,
参考音频使用`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`,
要合成的文本是`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`,
输出合成后的音频wav到该目录,统计合成所需的时间t，和音频频率k
命名为`${模型名}_${t}_${k}khz.wav`
最后把以上安装对应tts运行环境所需的软件和过程总结后输出到scripts目录中，命名为`tts_${模型名}_安装指南.md`
