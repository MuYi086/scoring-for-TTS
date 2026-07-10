# asr：文本忠实度评价器

`asr` 回答的是“合成音频实际读出了什么”。将自动语音识别（ASR）的转写与 `case.target.text` 的冻结文本比较，中文以字错误率（CER）为主；词错误率（WER）仅在明确的分词规则下作为补充。

## 为什么需要独立目录

音色相似不等于读对文本，听起来自然也可能漏字、错读或把停顿变成错误断句。反过来，低 CER 也不代表语音自然。因此 ASR 只提供忠实度证据，不能与 WavLM 或 TTS-PRISM-7B 的原始分数直接相加。

## 固定规则

1. `reference_text` 必须来自评测清单中的 `target.text`，不能来自参考音频转写。
2. 先保存 ASR 的原始转写，再按同一版本的规范化规则同时处理参考文本和假设文本，最后计算 CER。
3. 中文默认比较去除空白后的字符序列。数字、英文、专名和标点的转换政策必须写在 `normalization/zh-v1.md`；没有明确规则时保留原样，不能事后为某模型改写。
4. 每次更换 ASR 模型、解码参数或规范化版本，必须视为不同评价器版本，不能和旧结果混合求平均。

逐样本结果写在 `asr/outputs/<run_id>/transcription.jsonl`，字段见 [`contracts/transcription-record.schema.json`](contracts/transcription-record.schema.json)。本目录不提供下载或执行脚本。
