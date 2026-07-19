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
对应增加该模型的测试脚本(名称中标记v2)，然后分别测试克隆以下三个音频，应该会用到"参考音频,text"，其他的参数我也给了，具体看模型是否需要。然后该脚本执行后的输出目录为cloneData/audio_v2目录,音频命名分别按照对应模型+人物命名。脚本要求模型执行完成后需要从显存中移除，避免占用显存。
集中克隆测试:
1. * 人物: 旁白
   * 音色: 男声，中年，声线低沉浑厚，略带沙哑。
   * 参考音频: "/testData/mimo_旁白_v2.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 0, 0, 0, 0, 0.5]
   * text: "看着小恶魔那甜甜的微笑，他感觉身体一阵颤栗，他想挣扎，却动弹不得，想大声呼喊，却发不出声音，眨眼间，冷汗浸透了他的衣衫。"

2. * 人物: 辰南
   * 音色: 年轻男性，声线清朗，略带少年感。
   * 参考音频: "/testData/mimo_辰南_v2.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0, 0, 0, 1, 0, 0, 0, 0]
   * text: "人为刀俎，我为鱼肉。刚刚出来游历，便要遭受这番悲惨遭遇，老天你不会在和我开玩笑吧？"

3. * 人物: 小公主
   * 音色: 少女声线清脆，略尖细，带稚气。
   * 参考音频: "/testData/mimo_小公主_v2.wav"
   * 模型: indextts2
   * 接口: http://127.0.0.1:8300/v2/synthesize
   * emo_vector: [0.75, 0, 0, 0, 0, 0, 0, 0]
   * text: "你们说，当我把烈火仙莲献给我父皇之后，他会是什么表情？嗯，我猜他一定会笑的合不拢嘴，允许我以后自由出入皇城。呵呵，真是太好了，以后我想到哪里玩，就到哪里玩，再也没有人会阻止我了，呵呵……"

上面我给的示例是indextts2,实际你要将上面所有提到的模型都处理克隆操作
全部模型克隆完成后
在cloneData/audio_v2目录下有各自模型克隆音频产生了三份"辰南、小公主、旁白"的音频

所需要的模型都在hf-mirror目录
现在我需要你使用更加中立的评测机制，
  - SenseVoice CER + Whisper CER
  - WavLM SIM + SpeechBrain ECAPA SIM
  - UTMOSv2 + NISQA
对每个模型克隆的音频和原始音频做对比，输出
`SenseVoice_CER&Whisper_CER_V2评价报告`
`WavLM_SIM&SpeechBrain_ECAPA_SIM_V2评价报告`
`UTMOSv2&NISQA_V2评价报告`
