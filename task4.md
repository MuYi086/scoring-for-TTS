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
   * text: "小公主恶狠狠的盯着他，其中的意思再明显不过，威胁兼恐吓让他配合。"

2. * 人物: 小公主
   * 音色: 女声尖细，咬字紧实，略带咬牙切齿感。
   * 参考音频: "testData/mimo_小公主_v3.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0.75, 0, 0, 0]
   * text: "他是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子你没想到会这么快见到我吧？"

3. * 人物: 三皇子
   * 音色: 男性，声线清朗，略带年轻感。
   * 参考音频: "testData/mimo_三皇子_v3.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0, 0, 0, 0.35]
   * text: "这个人在路上一直鬼鬼祟祟地跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？"

上面我给的示例是indextts2,实际你要将上面所有提到的模型都处理克隆操作
全部模型克隆完成后
在cloneData/audio_v3目录下有各自模型克隆音频产生了三份"三皇子、小公主、旁白"的音频

所需要的模型都在hf-mirror目录
现在我需要你使用更加中立的评测机制，
  - SenseVoice CER + Whisper CER
  - WavLM SIM + SpeechBrain ECAPA SIM
  - UTMOSv2 + NISQA
对每个模型克隆的音频和原始音频做对比，输出
`SenseVoice_CER&Whisper_CER_V3评价报告`
`WavLM_SIM&SpeechBrain_ECAPA_SIM_V3评价报告`
`UTMOSv2&NISQA_V3评价报告`
