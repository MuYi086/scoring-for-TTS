我使用task3.md的操作使用不同模型分别合成了
`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/dots.tts-base_232.67s_48khz.wav`
`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/MOSS-TTS-Local-Transformer_178.47s_24khz.wav`
`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/Qwen3-TTS-12Hz-1.7B-Base_40.75s_24khz.wav`
`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/VoxCPM2_72.45s_48khz.wav`
克隆的参考音频是`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
合成的文本是`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`
我现在通过耳朵听无法辨别出这四个wav的好坏，你按照音频领域最佳实践和权威的测试流程，帮我在本地建一个可以标准量化的流程，分析这四个wav，并最终给出得分，输出`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/模型合成音频评测.md`,测试脚本放在`scripts`