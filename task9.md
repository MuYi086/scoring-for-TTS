你先阅读`longAudioTestV9`目录
其中text.md是合成音频所需的小说原始文本.
ai_deal.json是大模型识别人物和情绪处理后的完整json，用来将每句话匹配到具体人物和音色

以下是人物和音色介绍
1. * 人物: 旁白
   * 音色: "女声，20-30岁，中音区略偏低，音色沉静而敏锐，略带暖意，不沙哑或气声过度。咬字清晰但不刻板，语速中等偏慢，有自然的停顿；默认气质冷静而克制，像深夜播讲都市传说中的悬念播客主，不动声色地铺垫紧张氛围。"
   * 参考音频: "longAudioTestV9/mimo_旁白_v9.wav"
   * 参考文案: "深夜空旷的旧走廊里那盏旧灯忽明忽暗，从远处隐约传来一阵低语声。"

2. * 人物: 布罗迪
   * 音色: "男性，青年，中低音域，音色温暖醇厚略带沙哑，共鸣自然，发声力度适中。咬字清晰圆润，语速中等偏慢，节奏平稳，默认气质温和稳重，略带深沉感。"
   * 参考音频: "longAudioTestV9/mimo_布罗迪_v9.wav"
   * 参考文案: "这个旧箱子里装的东西，让我想起了那些非常久以前的一些模糊往事。"

3. * 人物: 我
   * 音色: "女性，青年，音域适中，声线清亮微哑，带有轻微的气声质感。咬字清晰，语速中速偏慢，节奏平稳，默认气质是灵巧而中性，带有叙述感。"
   * 参考音频: "longAudioTestV9/mimo_我_v9.wav"
   * 参考文案: "我听见了脚步声很轻，像是有人在悄悄靠近，慢点，先停下，别动。"

4. * 人物: 布罗迪姐姐
   * 音色: "成年女性，中音区温暖略带沙哑，声线偏厚实但不过分低沉。咬字清晰利落，语速中等偏慢，停顿自然留有思索余地，发声力度均匀克制，默认情绪带着谨慎的关切与一丝犹豫。"
   * 参考音频: "longAudioTestV9/mimo_布罗迪姐姐_v9.wav"
   * 参考文案: "嗯我觉得他真的总不太对劲，但就是说不上来到底哪里不太对了吧。"

5. * 人物: 教授
   * 音色: "女性，中年，中音域，声线醇厚偏暗，带轻微气声，温润而有分量。咬字清晰利落，语速中等偏慢，停顿沉稳，带有学者式的从容与笃定气质，默认情绪基调为温和、审慎的关切。"
   * 参考音频: "longAudioTestV9/mimo_教授_v9.wav"
   * 参考文案: "每个问题背后，其实都隐藏着更深层的真相，需要我们用耐心去追寻"


audio_*.wav是各个模型分析音色并对角色说的文本使用对应音色克隆后合成的最终的音频文件

现在期望你每次只分析一个模型对应的 wav。

## Seed-TTS-Eval 手动执行前置条件

本任务不在本次操作中执行任何评测。后续手动运行 Seed-TTS-Eval（Seed TTS 官方客观基准）前，先完成以下预检；预检失败时停止，不得用 V9 长音频或替代模型权重继续评分：

- 使用两个隔离的 Conda（Python 环境管理器）环境：`seed_tts_eval` 只运行中文 Seed WER（词错误率）及 V9 的 SenseVoice / Whisper-large-v3-turbo CER（字符错误率）；`seed_tts_sim` 只运行官方 WavLM-large-SV SIM（说话人余弦相似度）。两者的 PyTorch、Torchaudio、Hydra 依赖不兼容，禁止混装，也不得误用 V9 的 `audio_eval` 环境。
- 在 `seed_tts_eval` 中执行 `python -m pip check`，并确认 Python、PyTorch、Torchaudio、FunASR、Transformers、Librosa、SoundFile、SciPy、JiWER、`zhconv`、`zhon` 与 `tqdm` 均可导入，且 `torch.cuda.is_available()` 为真；在 `seed_tts_sim` 中单独确认 Python、PyTorch、Torchaudio、NumPy、SoundFile、Librosa、`h5py`、Fire、Fairseq、OmegaConf 与 S3PRL 的运行时导入，以及 `torch.cuda.is_available()`。`h5py` 是 Fairseq 顶层导入的必要依赖；S3PRL 仅安装 SIM 实际调用的接口，因此其训练/数据集可选依赖产生的 `pip check` 告警只记录，不作为失败条件；必须保留该输出、目标导入结果和精确版本。所有命令优先使用 `conda run --no-capture-output -n <环境名> <命令>`，避免安装或运行到错误环境。
- 本项目只评测中文，冻结 Seed-TTS-Eval 源码提交、官方测试集 SHA-256、官方 `wavlm_large_finetune.pth` SHA-256、本地 `funasr/paraformer-zh` 的 `model.pt` 与配置文件 SHA-256、本地 `FunAudioLLM/SenseVoiceSmall` 的 `model.pt` 与配置文件 SHA-256、本地 `openai/whisper-large-v3-turbo` 的 `model.safetensors` 与配置文件 SHA-256、两个环境的 `pip freeze`、GPU/驱动/CUDA、推理参数、文本规范化配置和随机种子；`seed_tts_sim` 还必须冻结当前 UniSpeech vendored Fairseq 的源码提交及以 `READTHEDOCS=1` 跳过可选原生扩展的安装方式。这些机器记录写入本次结果目录，绝不写入仓库配置。中文流程不下载、不加载、也不记录 `openai/whisper-large-v3`。
- 在本机 shell 中设置不入库的 `SEED_TTS_EVAL_ROOT`、`SEED_TTS_DATA_ROOT`、`SEED_TTS_WAVLM_CKPT`、`SEED_TTS_PARAFORMER_DIR`、`SEED_TTS_SENSEVOICE_DIR`、`SEED_TTS_TURBO_DIR` 与 `ARNOLD_WORKER_GPU`。三个本地 ASR 目录必须分别指向 `hf-mirror/funasr/paraformer-zh`、`hf-mirror/FunAudioLLM/SenseVoiceSmall` 和 `hf-mirror/openai/whisper-large-v3-turbo`；`ARNOLD_WORKER_GPU` 必须等于实际可用 GPU 数。
- 在运行前制作并冻结 Seed-TTS-Eval 源码兼容补丁及其 SHA-256。补丁必须：① 中文 WER 时跳过 `cal_wer.sh` 中无实际评分作用、却会下载 Whisper-large-v3 的 `prepare_ckpt.py`；② 令 `run_wer.py` 使用 `AutoModel(model=os.environ["SEED_TTS_PARAFORMER_DIR"], hub="hf")` 加载本地 Paraformer；③ 将 `cal_wer.sh` 与 `cal_sim.sh` 中的 `sudo split` 改为普通用户的 `split`；④ 保留 SIM 目录中避免 `select.py` 遮蔽 Python 标准库的已记录改名补丁；⑤ 使用 UniSpeech `setup.py` 已有的 `READTHEDOCS=1` 安装开关跳过未被说话人验证路径调用的可选 Fairseq 原生扩展。补丁与安装方式均不得改变输入、分片规则、ASR 解码、WavLM 嵌入/相似度计算或汇总公式。
- 先用一个官方中文样本完成“本地 Paraformer 加载、V9 Whisper-large-v3-turbo 加载、独立 `utt.wav` 生成、WER 和 SIM 结果文件可写”的烟雾检查；该检查只验证环境，不能作为模型比较结果，也不能覆盖或续跑正式输出目录。

你需要使用以下可直接参考的自动评测机制。所有数值阈值、交付格式和目标渠道的响度规范必须在实际评测前冻结到机器可读配置；若某项没有冻结阈值，只报告原始测量值和异常位置，不得自行判定通过、失败或优劣。

### 一、音频交付硬门槛

- 文件可解码且非空；哈希、采样率、声道数、位深和时长符合冻结的交付契约。
- 削波、最大真峰值、直流偏置、前后静音、非预期长静音、掉音和突然截断均按冻结阈值检查。
- 集成响度、短时响度、响度范围和最大真峰值符合目标发布渠道的冻结规范。

### 二、台词与结构完整性

- 对每个模型的完整合成音频，以 `ai_deal.json` 中实际合成的 77 段台词串为唯一 CER（字符错误率）参考，分别运行 SenseVoice CER 与本地 Whisper-large-v3-turbo CER。前者必须从 `SEED_TTS_SENSEVOICE_DIR` 加载，后者必须从 `SEED_TTS_TURBO_DIR` 加载，均冻结权重、依赖版本、解码参数和文本规范化配置。
- 核对台词覆盖、缺失、插入、重复和顺序错误，并保留完整转写、错误位置和对应原始台词；双后端分别报告和排名，不得平均为综合分。CER 仅衡量文本保真，不表示音频质量、自然度或角色表现；Whisper-large-v3-turbo CER 不得标作原版 Whisper-large-v3 CER。

### 三、文本时间与读法合规

- 使用冻结发音词典的强制对齐，检查字符或词级可对齐覆盖率、未对齐比例、台词/角色覆盖和文本顺序。
- 根据冻结阈值检查标点停顿时长、语速和异常静音；中文专有名词、数字、日期和英文读法以冻结词典为准。

### 四、角色路由告警（非音色评分）

- 仅在已配置并校准的闭集角色分类器、参考音频集和阈值均齐备时，检查每段的目标角色 Top-1 与对其他候选角色的置信差距，输出“疑似串角/错路由”告警。
- 该检查不是 WavLM SIM 或 SpeechBrain ECAPA SIM 的原始分数替代品，不用于音色贴合打分、自动排名或综合分；未配置校准分类器时，应在报告标明未执行，而不得用原始 SIM 分数补位。

### 五、Seed-TTS-Eval（Seed TTS 官方客观基准）中文零样本音色克隆评测

- 此项是独立于 V9 小说长音频的标准化外部基准，不得把 `audio_*.wav` 整条成品直接作为 Seed-TTS-Eval 输入，也不得把其分数与 V9 长音频的任何结果混合。
- 仅运行官方中文常规集 `zh/meta.lst` 与中文难例集 `zh/hardcase.lst`；本项目当前为中文评测，不运行英文集，以避免与项目范围无关的生成和计算。
- 对每个模型，严格按每条 meta 的参考音频、参考文本和待合成文本生成独立的 `utt.wav`。冻结 Seed-TTS-Eval 仓库提交、数据与模型权重哈希、模型 revision、推理参数、文本规范化配置和随机种子；缺少任一冻结项时，报告不得宣称可复现或可横向比较。
- 使用经上述非语义兼容补丁处理的官方 `cal_wer.sh`，以本地 Hugging Face（模型托管平台）`funasr/paraformer-zh` 计算两个中文集的官方 WER。中文 `run_wer.py` 不会调用 Whisper；不得为此下载、加载或用 Whisper-large-v3-turbo 替换 Paraformer。其中文实现先将每个汉字拆为计分 token（记号），因此应标注为“Seed-TTS 中文 WER（逐字 token）”，而不得与 V9 的 CER 直接合并；保留逐条转写、逐条错误和分集汇总。
- 使用官方 `cal_sim.sh` 与其指定的 WavLM-large 说话人验证权重，分别计算两个中文集的 WavLM-large-SV SIM（说话人验证余弦相似度）；保留逐条“生成音频—meta 参考音频”配对分数和分集均值。
- Seed-TTS-Eval 的 WER 与 SIM 只可在相同官方分集、相同 evaluator（评测器）版本和相同冻结推理配置下直接比较；分别报告，不得加权成一个分数或与 V9 长音频名次合并。它们用于零样本音色克隆的标准化基准比较，不表示小说长音频的自然度、情绪、角色区分度或最终生产排名。正式运行一律使用新建且为空的输出目录；只有同一次中断的同一目录才可续跑。

输出逐模型的自动核验结果到 `longAudioTestV9/评测结果` 目录。每项必须列明原始值、冻结阈值、通过/失败状态、异常位置和可复核证据。

等所有模型都分析完成后，分别输出以下最终报告到 `longAudioTestV9/评测结果` 目录：

- `SenseVoice_CER&Whisper-large-v3-turbo_CER_V9评价报告`：双 ASR 的全文 CER、完整转写、台词错误位置、双后端名次和分歧项；
- `音频交付与文本一致性_V9自动检查报告`：交付硬门槛、台词与结构完整性、强制对齐/读法合规和角色路由告警的逐模型结果。
- `Seed-TTS_ZH_WER&WavLM-large-SV_SIM_V9标准基准报告.md`：中文常规集与难例集分别列出官方 WER、官方 WavLM-large-SV SIM、逐条证据、冻结版本和推理配置。

除上述 Seed-TTS-Eval 官方 WavLM-large-SV SIM 外，不运行直接针对 V9 长音频的 WavLM SIM、SpeechBrain ECAPA SIM、UTMOSv2 或 NISQA-TTS，也不生成自动综合分或自动总排名。音色贴合、角色区分度、自然度、情绪、作为表演效果的停顿、伪影主观感受和长时间听觉疲劳属于人工盲听范围，不在本任务的自动评测机制中。具体边界见 [`自动评测与人工盲听边界说明.md`](自动评测与人工盲听边界说明.md)。
