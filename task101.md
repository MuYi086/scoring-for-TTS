你先阅读`modelScript/tts_local_voxcpm2_安装指南.md`和`modelScript/tts_local_voxcpm2.py`
然后参考上面的方式
1. 创建一个conda 环境，名称是 qwen3-voiceDesign，安装 `~/hf-mirror/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`所要求的软件，将接入使用的方式写成`tts_local_qwen3_voiceDesign.py`和`tts_local_qwen3_voiceDesign_安装指南.md`输出到`modelScript`目录

2. 创建一个conda 环境，名称是 moss-voiceGenerator，安装 `~/hf-mirror/OpenMOSS-Team/MOSS-VoiceGenerator`所要求的软件，将接入使用的方式写成`tts_local_moss-voiceGenerator.py`和`tts_local_moss-voiceGenerator_安装指南.md`输出到`modelScript`目录


4. 创建一个conda 环境，名称是 Step-Audio-EditX，安装 `:~/hf-mirror/stepfun-ai/Step-Audio-EditX`所要求的软件，将接入使用的方式写成`tts_local_Step_Audio_EditX.py`和`tts_local_Step_Audio_EditX_安装指南.md`输出到`modelScript`目录

5. 创建一个conda 环境，名称是 Ming-omni-tts-0.5B，安装 `:~/hf-mirror/inclusionAI/Ming-omni-tts-0.5B`所要求的软件，将接入使用的方式写成`tts_local_Ming_omni_tts.py`和`tts_local_Ming_omni_tts_安装指南.md`输出到`modelScript`目录

将以上逐个完成
以上执行过程，如果有错误，将错误记录在项目根目录`conda环境安装错误.md`
以上执行过程，如果有依赖前提缺失，将依赖缺失记录在项目根目录`conda环境依赖缺失.md`
