你先阅读`Seed-TTS评测任务.md`和`Seed-TTS运行阻塞.md`

1. `Seed-TTS-test/scripts`，这是执行Seed-TTS测试的各个模型的脚本。每个模型的使用脚本可以参考`~/github/TTS-and-VoiceDesign`中api目录内各个模型的使用
我期望的效果是`Seed-TTS-test/scripts`每个模型的脚本单独维护和执行，不受`~/github/TTS-and-VoiceDesign`影响，只是参考它的实现。每次Seed-TTS测试时，每次只针对一个模型进行测试,每个模型测试时，串行测试生成<utt>音频，这样可以保证不会爆显存，然后执行步骤2

2. 每次模型脚本执行生成的资源放在`Seed-TTS-test/result`目录下对应模型对应的目录内，完成后执行步骤3
3. 每次模型脚本执行生成的报告放在`Seed-TTS-test/report`目录下对应模型对应的目录内，完成后执行下一个模型的步骤1
