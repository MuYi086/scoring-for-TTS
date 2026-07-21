你先阅读`longAudioTest`目录
其中text.md是合成音频所需的小说原始文本.
ai_deal.json是大模型识别人物和情绪处理后的完整json，用来将每句话匹配到具体人物和音色

以下是人物和音色介绍
1. * 人物: 辰南
   * 音色: 男性，声线中等，年龄二十左右，音色清澈。
   * 参考音频: "longAudioTest/mimo_辰南_v4.wav"

2. * 人物: 见习魔法师
   * 音色: 男，年轻，声线清澈。
   * 参考音频: "longAudioTest/mimo_见习魔法师_v4.wav"

3. * 人物: 女侍卫
   * 音色: 女侍卫音色清冷微哑，年轻有力。
   * 参考音频: "longAudioTest/mimo_女侍卫_v4.wav"

4. * 人物: 旁白
   * 音色: 男性，声线浑厚沉稳，略带沙哑。
   * 参考音频: "longAudioTest/mimo_旁白_v4.wav"

5. * 人物: 侍卫
   * 音色: 女侍卫音色清亮，年轻细腻。
   * 参考音频: "longAudioTest/mimo_侍卫_v4.wav"

6. * 人物: 小公主
   * 音色: 女，清脆明亮的少女音。
   * 参考音频: "longAudioTest/mimo_小公主_v4.wav"

audio_*.wav是各个模型分析音色并对角色说的文本使用对应音色克隆后合成的最终的音频文件

我使用goal执行这个任务，终端已崩溃了三次了, 原因是`wsl_1006错误.md`，现在已修复，你要保证执行过程中不会再次出现oom的情况导致失败
现在期望你每次只分析一个模型对应的wav，
你需要使用更加中立的评测机制，
  - SenseVoice CER + Whisper CER
  - WavLM SIM + SpeechBrain ECAPA SIM
  - UTMOSv2 + NISQA
对每个模型克隆的音频和原始音频做对比，输出该模型对应的评价报告到`longAudioTest/评测结果`目录`。
等所有模型都分析完成后，再回过来总结所有的分析报告，输出最终的
`SenseVoice_CER&Whisper_CER_V4评价报告`
`WavLM_SIM&SpeechBrain_ECAPA_SIM_V4评价报告`
`UTMOSv2&NISQA_V4评价报告`
到`longAudioTest/评测结果`目录