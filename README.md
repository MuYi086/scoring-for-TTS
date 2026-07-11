# TTS 与音色设计评估工作区

本仓库用于比较中文文本转语音（TTS）模型的音色克隆、可懂度、表现力与长文本稳定性。

模型的安装、环境隔离与合成入口统一放在 [`modelScript/`](modelScript/)。评估部分不重复维护这些运行时，而是使用一个冻结的样本清单，收集每个模型同一批合成产物，再分别由评价器给出证据。

- [`评估步骤指南.md`](评估步骤指南.md)：从第一性原理定义的手工评估流程、准入门槛与结果解释。
- [`tts-bench/`](tts-bench/)：基准样本清单、一次实验的运行记录、结果契约与汇总模板。
- [`wavlm/`](wavlm/)：说话人验证用的音色相似度（SIM）评价器边界与记录格式。
- [`asr/`](asr/)：自动语音识别（ASR）用的文本忠实度、字错误率（CER）评价器边界与记录格式。
- [`utmosv2/`](utmosv2/)：合成语音自然度 MOS（平均主观意见分）预测器的安装与结果约定。
- [`listener-review/`](listener-review/)：仅供个人复核停顿、语气和情绪的独立试听材料，不进入自动总分。

对已经登记的合成结果，可用 [`tts-bench/scripts/run_automated_evaluation.py`](tts-bench/scripts/run_automated_evaluation.py) 一次评估全部运行，并生成逐样本 JSONL、模型汇总 CSV 和透明的配置化排名。它不合成音频，也不包含模型权重、音频样本或密钥。
