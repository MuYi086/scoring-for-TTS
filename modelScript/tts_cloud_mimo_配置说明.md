# MiMo 云端 TTS 配置说明

本文记录 `modelScript/tts_cloud_mimo.py` 的运行配置。脚本用于调用 MiMo-V2.5-TTS
系列云端 API，复用本仓库现有公版书样例文本和参考音频，默认执行 voiceclone（声音克隆）合成。

## 运行前配置

脚本只依赖 Python 标准库，不需要额外安装 `openai` SDK。

需要配置 MiMo API Key：

```bash
export MIMO_API_KEY="你的 MiMo API Key"
```

也可以在命令行中临时传入：

```bash
python modelScript/tts_cloud_mimo.py --api-key "你的 MiMo API Key"
```

不要把 API Key 写入脚本或提交到仓库。

## 默认运行

```bash
cd /path/to/timbre-design
python modelScript/tts_cloud_mimo.py
```

默认行为：

- 模型：`mimo-v2.5-tts-voiceclone`
- 合成文本：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/第一章.md`
- 参考音频：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/sample.wav`
- 风格指令：`低沉、沉稳、沉浸式，像电台主持一样自然叙述。`
- 输出目录：`samples/v_zh_046_电台主持-低沉_沉稳_沉浸式/`
- 输出文件名：`mimo-v2.5-tts-voiceclone_${t}_${k}khz.wav`

## 常用模式

使用内置音色：

```bash
python modelScript/tts_cloud_mimo.py \
  --model mimo-v2.5-tts \
  --voice 冰糖
```

使用声音设计：

```bash
python modelScript/tts_cloud_mimo.py \
  --model mimo-v2.5-tts-voicedesign \
  --instruction "一位中年男性，说标准普通话，嗓音低沉有磁性，像纪录片旁白。"
```

检查请求摘要但不调用云端 API：

```bash
python modelScript/tts_cloud_mimo.py --dry-run
```

## 注意事项

- 官方文档要求合成目标文本放在 `assistant` 角色消息中；`user` 角色消息用于风格控制或声音设计描述。
- `mimo-v2.5-tts-voiceclone` 的参考音频会被编码为 `data:{MIME_TYPE};base64,...`；当前支持 `wav` 和 `mp3`。
- 官方限制 voiceclone 参考音频 Base64 编码后不能超过 10 MB。
- 脚本默认使用非流式 `wav` 输出；多分块合成时会用标准 WAV 拼接并插入 `--pause-ms` 指定的静音。
