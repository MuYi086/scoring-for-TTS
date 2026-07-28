# Seed-TTS 运行状态与恢复边界

状态：**准备完成；尚未执行任何 Seed-TTS 合成、WER（词错误率）或 SIM（说话人相似度）评分。**

本文件与 [Seed-TTS评测任务.md](Seed-TTS评测任务.md) 配套，说明为什么当前没有可比较的 Seed-TTS 结论，以及操作者何时可以开始手动执行。它不属于 `task6.md` 至 `task9.md` 的长音频任务。

## 当前已完成的准备

- 官方中文输入已核验：`zh/meta.lst` 2,020 条、`zh/hardcase.lst` 400 条，及其全部参考 WAV（Waveform Audio File Format，波形音频文件）均存在。
- 七个模型都有独立启动脚本、离线权重路径、结果目录与报告目录；每次只启动一个模型，并按 `utt` 串行生成。
- IndexTTS2 与 LongCat-AudioDiT-1B 使用独立的官方源码工作副本，不在运行时导入 `~/github/TTS-and-VoiceDesign`。
- 七个模型的 Conda（Python 环境管理器）环境、所需运行时发行包、Qwen3-TTS 的 SoX（音频处理工具）与两个评分环境已通过 `check_seed_tts_setup.py` 无模型加载预检。
- Seed-TTS-Eval 已有专用补丁工作副本；补丁冻结记录固定了本地 Paraformer、普通用户 `split` 与 UniSpeech 文件重命名。
- `Seed-TTS-test/result/` 与 `Seed-TTS-test/report/` 只有 Git 保留目录；没有 `utt.wav`、原始 WER/SIM 输出或报告。

## 仍未发生的操作

尚未加载任何模型权重、占用 GPU（图形处理器）、生成音频或调用评分器。因此，当前没有模型优劣、WER、SIM 或排名结论可供解释。

正式执行会为七个模型生成 7 × (2,020 + 400) = 16,940 个独立 WAV，并随后运行两套评分环境；这一步必须由操作者按 [Seed-TTS评测任务.md](Seed-TTS评测任务.md) 手动授权和启动。

## 跨机器重建提示

- 首次创建 IndexTTS2 环境时使用 `prepare_indextts2_environment.sh` 同步官方 `uv.lock`。当前机器已经通过预检；不要为单次正式运行重复同步。
- 若离线同步报告锁定包不在缓存，属于新机器的依赖下载前置条件；获得授权后以 `--allow-network` 同步，再运行预检。不得改写锁文件、伪造缓存或借用参考项目源码。
- 首次创建评分器补丁工作副本时运行 `prepare_seed_tts_evaluator.sh`。已存在的冻结副本不得覆盖，应直接预检或新建路径。

## 开始正式执行前

1. 在新的 shell 加载本机 `.env`，运行 `python Seed-TTS-test/scripts/check_seed_tts_setup.py`，必须全通过。
2. 为单个模型创建从未使用的正式 `run-id`，执行对应的 `run_<model>.sh`；不要并行运行模型，也不要使用 `--limit`。
3. 仅在两个分集都完成 2,420 条 WAV 后，运行 `score_model.sh`。报告保持 WER 与 SIM 独立呈现，禁止生成跨量纲总分。

长音频目录及其历史占位报告不能替代本基准输入、输出或结论。
