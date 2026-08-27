# 训练数据处理脚本

## `deal_nsnsjb.py`

将 `C:\Downloads\男生女生金版2002-2015` 中的 PDF 逐个提交给 MinerU，提取结果中的
`full.md`，并以原 PDF 文件名（仅扩展名改为 `.md`）保存至 `training/男生女生金版/`。

脚本在 WSL 环境中自动使用对应的
`/mnt/c/Downloads/男生女生金版2002-2015` 目录。它只从环境变量读取 MinerU API Token，绝不把
Token 写入仓库：

```bash
export MINEU_API_KEY='你的 MinerU API Token'
python -c "import os; print('MINEU_API_KEY 已设置' if os.getenv('MINEU_API_KEY') else 'MINEU_API_KEY 未设置')"
python training/script/deal_nsnsjb.py --dry-run
python training/script/deal_nsnsjb.py
```

脚本读取的是启动它的 Python 进程继承的环境变量，不会自行解析 `~/.bashrc`。因此 `.bashrc` 中必须使用
`export MINEU_API_KEY='...'`，而不是仅赋值 `MINEU_API_KEY='...'`。上面的检查命令只显示变量是否存在，
不会输出 Token。

Token 只填 API 管理页创建的原始值；不要把示例中的 `Bearer `、`Authorization:` 或引号一并复制进去。
脚本仅读取 `MINEU_API_KEY`，并忽略其他 MinerU 变量名。

本地 PDF 按 MinerU 官方批量接口处理：每次申请最多 50 个上传地址，通过系统 `curl -T` 并发
上传 4 个文件，无须安装 Python `requests` 包。脚本先提交全部批次，让 MinerU 在后台并行解析，
再按请求中的 `data_id` 匹配结果并发下载。Ubuntu/WSL 通常已自带 `curl`；临时断线会自动重试
3 次，HTTP 4xx 等确定性错误不会重试。

默认参数适合当前 166 个 PDF，会拆成 4 批（50、50、50、16）。网络较慢或连接不稳定时可降低
上传并发数；确认带宽充足时可提高：

```bash
python training/script/deal_nsnsjb.py --upload-workers 2
python training/script/deal_nsnsjb.py --upload-workers 8 --download-workers 8
```

`--batch-size` 的取值范围为 1–50，默认 50；`--poll-timeout` 是每批结果的最长等待时间。

转换会向 MinerU 上传原始 PDF 并消耗相应服务额度。已有同名且非空的 Markdown 会自动跳过；
单文件上传、解析或下载失败会记录为相邻的 `.md.error`，不会阻断同批其他文件。因此在中断或失败后，
重新执行同一命令即可继续。需要强制重新转换时才传入 `--overwrite`。

MinerU 精准解析 API 限制单个文件不超过 200 MB、200 页。脚本会在上传前拦截超过 200 MB 的
PDF；页数由 MinerU 在服务端校验。当前 166 个源文件均满足大小限制。

生成的 Markdown 和错误标记已加入 `.gitignore`，仅保留在本机训练数据目录中。
