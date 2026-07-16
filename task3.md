集中克隆已经完成，在cloneData目录下有各自模型克隆音频产生了三份"见习魔法师、小公主、旁白"的音频
1. * 人物: 旁白
   * 音色: 男声，青年，清亮微磁。
   * 参考音频: "/testData/mimo_旁白.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0, 0, 0, 0.5]
   * text: "小公主手下的侍卫紧张无比，其中一个见习魔法师道："

2. * 人物: 小公主
   * 音色: 女，少女音，声线清脆略带鼻音。
   * 参考音频: "/testData/mimo_小公主.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0.35, 0, 0, 0, 0, 0, 0]
   * text: "当然有，你们是不是害怕了？"

3. * 人物: 见习魔法师
   * 音色: 年轻男性，声线偏细，略带沙哑。
   * 参考音频: "/testData/mimo_见习魔法师.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0.5, 0, 0, 0, 0]
   * text: 公主殿下，火山口真的有烈火仙莲吗？

所需要的模型都在hf-mirror目录
现在我需要你使用更加中立的评测机制，
  - SenseVoice CER + Whisper CER
  - WavLM SIM + SpeechBrain ECAPA SIM
  - UTMOSv2 + NISQA
对每个模型克隆的音频和原始音频做对比，输出
`SenseVoice_CER&Whisper_CER_V2评价报告`
`WavLM_SIM&SpeechBrain_ECAPA_SIM_V2评价报告`
`UTMOSv2&NISQA_V2评价报告`