你需要先阅读`modelScript`中各模型的使用
然后cloneData目录下的
cloneData/dots_tts_base
cloneData/indextts2
cloneData/longcat_audiodit_1b
cloneData/mimo
cloneData/moss_tts_local_transformer
cloneData/omnivoice
cloneData/qwen3_tts_12hz_1_7b_base
cloneData/voxcpm2
对应增加该模型的测试脚本(名称中标记v3)，然后分别测试克隆以下三个音频，应该会用到"参考音频,text"，其他的参数我也给了，具体看模型是否需要。然后该脚本执行后的输出目录为cloneData/audio_v3目录,音频命名分别按照对应模型+人物命名。脚本要求模型执行完成后需要从显存中移除，避免占用显存。
集中克隆测试:
1. * 人物: 旁白
   * 音色: 男性旁白，声线低沉，略带沙哑，中年感。
   * 参考音频: "/testData/mimo_旁白_v3.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0, 0, 0, 0.5]
   * text: "三皇子大吃一惊，对辰南的身份开始胡乱猜疑起来，他咳嗽了一声，"

2. * 人物: 小公主
   * 音色: 女声尖细，咬字紧实，略带咬牙切齿感。
   * 参考音频: "testData/mimo_小公主_v3.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0.5, 0, 0, 0, 0, 0, 0]
   * text: "认识，当然认识。"

3. * 人物: 辰南
   * 音色: 男，青年音色，清朗略带磁性。
   * 参考音频: "testData/mimo_辰南_v3.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0, 0.35, 0, 0]
   * text: "请公主殿下责罚。"

上面我给的示例是indextts2,实际你要将上面所有提到的模型都处理克隆操作
全部模型克隆完成后
在cloneData/audio_v3目录下有各自模型克隆音频产生了三份"辰南、小公主、旁白"的音频

所需要的模型都在hf-mirror目录
现在我需要你使用更加中立的评测机制，
  - SenseVoice CER + Whisper CER
  - WavLM SIM + SpeechBrain ECAPA SIM
  - UTMOSv2 + NISQA
对每个模型克隆的音频和原始音频做对比，输出
`SenseVoice_CER&Whisper_CER_V3评价报告`
`WavLM_SIM&SpeechBrain_ECAPA_SIM_V3评价报告`
`UTMOSv2&NISQA_V3评价报告`