# wavlm：音色相似度评价器

`wavlm` 只回答一个问题：合成音频与该 `case`（评测样本）的参考说话人，在说话人表征空间中有多相近。它不证明文本读对、声音自然，也不评价情绪是否合适；这些分别交给 ASR、TTS-PRISM-7B 和人工盲听。

## 固定比较对象

对每个成功合成的样本，只比较：

```text
同一 case 的参考音频  ──> 说话人嵌入 ─┐
                                      ├─ 余弦相似度（SIM）
同一 case 的合成音频  ──> 说话人嵌入 ─┘
```

禁止将不同 `case_id` 的参考音频与合成音频配对，也不要把同一个音频文件复制一份后当作“优秀克隆”样本。前者改变目标说话人，后者会虚高上界。

## 方法边界

- 使用带说话人验证头的 WavLM 检查点，而不是把通用预训练编码器最后一层直接当作身份分数。推荐方案可在 `config/speaker-verification.example.yaml` 中登记。
- 将评价器输入统一派生为单声道、16 kHz 副本；原始 WAV 保持不变。所有重采样、混音、裁剪和静音处理都必须有稳定的 `preprocessing_id`。
- 以余弦相似度记录逐样本 SIM，范围为 `[-1, 1]`。绝对值没有跨检查点、跨语料的通用阈值，不能脱离校准集直接断言“同一音色”。
- 在正式比较前，用两段不同的同说话人自然录音作为正校准、用不同说话人录音作为负校准；只确认方向与异常值，不把它们混入候选模型排名。

## 输入与输出

输入音频均由 `tts-bench/runs/<run_id>/` 的合成记录定位，不复制到本目录。一键评估时，逐样本 WavLM 结果与 ASR、UTMOSv2 等结果一起写入 `tts-bench/reports/automated-*/per_case.jsonl`，并汇总到 `model_summary.csv`。

[`contracts/similarity-record.schema.json`](contracts/similarity-record.schema.json) 保留为人工接入其他 WavLM 实现时的字段约定；本项目的默认入口见 [`../tts-bench/scripts/run_automated_evaluation.py`](../tts-bench/scripts/run_automated_evaluation.py)。
