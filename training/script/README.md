# 训练数据处理脚本

这些脚本将指定 Windows 下载目录中的 PDF 批量提交给 MinerU，提取结果 ZIP 中的 `full.md`，
并以原 PDF 文件名（仅将扩展名改为 `.md`）保存至对应训练目录。WSL 下会自动使用 `/mnt/c/Downloads`
映射路径。

| 任务 | 脚本 | Windows 输入目录 | Markdown 输出目录 |
| --- | --- | --- | --- |
| Task 11 | `dealPdf/deal_nsnsjb.py` | `C:\Downloads\男生女生金版2002-2015` | `training/原始资源/男生女生金版/` |
| Task 12 | `dealPdf/deal_bk.py` | `C:\Downloads\怖客2010-2018` | `training/原始资源/怖客/` |
| Task 13 | `dealPdf/deal_mgzzgs.py` | `C:\Downloads\猛鬼杂志故事-56本` | `training/原始资源/猛鬼杂志故事/` |
| Task 14 | `dealPdf/deal_mjgsdxg.py` | `C:\Downloads\民间故事胆小鬼` | `training/原始资源/民间故事胆小鬼/` |
| Task 15 | `dealPdf/deal_sz.py` | `C:\Downloads\悚族-75本` | `training/原始资源/悚族/` |
| Task 16 | `dealPdf/deal_sytl.py` | `C:\Downloads\岁月推理` | `training/原始资源/岁月推理/` |
| Task 17 | `dealPdf/deal_zmn.py` | `C:\Downloads\啄木鸟` | `training/原始资源/啄木鸟/` |

所有入口只从环境变量读取 MinerU API Token，绝不把 Token 写入仓库：

```bash
export MINEU_API_KEY='你的 MinerU API Token'
python -c "import os; print('MINEU_API_KEY 已设置' if os.getenv('MINEU_API_KEY') else 'MINEU_API_KEY 未设置')"
python training/script/dealPdf/deal_nsnsjb.py --dry-run
python training/script/dealPdf/deal_nsnsjb.py
```

其他数据集将命令中的脚本名替换为上表对应入口。例如：

```bash
python training/script/dealPdf/deal_bk.py --dry-run
python training/script/dealPdf/deal_bk.py
```

脚本读取的是启动它的 Python 进程继承的环境变量，不会自行解析 `~/.bashrc`。因此 `.bashrc` 中必须使用
`export MINEU_API_KEY='...'`，而不是仅赋值 `MINEU_API_KEY='...'`。上面的检查命令只显示变量是否存在，
不会输出 Token。

Token 只填 API 管理页创建的原始值；不要把示例中的 `Bearer `、`Authorization:` 或引号一并复制进去。
脚本仅读取 `MINEU_API_KEY`，并忽略其他 MinerU 变量名。

本地 PDF 按 MinerU 官方批量接口处理：每次申请最多 50 个上传地址，通过系统 `curl -T` 并发
上传 4 个文件，无须安装 Python `requests` 包。每批上传完便开始轮询，按请求中的 `data_id` 匹配结果；
每轮发现新完成的文件都会立即下载并写入 Markdown，只有本批全部成功或失败后才开始下一批。
Ubuntu/WSL 通常已自带 `curl`；临时断线会自动重试 3 次，HTTP 4xx 等确定性错误不会重试。

上传阶段每 30 秒输出一次心跳。若某次上传连续 60 秒低于 1 KB/s，会终止该次连接并自动重试，
避免最后一个上传长时间没有任何日志。

每批最多处理 50 个 PDF。网络较慢或连接不稳定时可降低上传并发数；确认带宽充足时可提高：

```bash
python training/script/dealPdf/deal_nsnsjb.py --upload-workers 2
python training/script/dealPdf/deal_nsnsjb.py --upload-workers 8 --download-workers 8
```

`--batch-size` 的取值范围为 1–50，默认 50；`--poll-timeout` 是每批结果的最长等待时间。

转换会向 MinerU 上传原始 PDF 并消耗相应服务额度。已有同名且非空的 Markdown 会自动跳过；
单文件上传、解析或下载失败会记录为相邻的 `.md.error`，不会阻断同批其他文件。因此在中断或失败后，
重新执行同一命令即可继续。需要强制重新转换时才传入 `--overwrite`。

MinerU 精准解析 API 限制单个文件不超过 200 MB、200 页。脚本会在上传前拦截超过 200 MB 的
PDF；页数由 MinerU 在服务端校验。

生成的 Markdown 和错误标记已加入 `.gitignore`，仅保留在本机训练数据目录中。

## 教师数据与 QLoRA 流水线

PDF 转换完成后，只按
[`training/最适合你的模型流水线.md`](../最适合你的模型流水线.md) 的 Step 0–8 执行。当前正式
数据集由 `step_0_plan_sources.py` 冻结为四个刊物各 20 份来源，共 80 份；Step 1 不再扫描整个
`training/`，也不接受旧的数量切分参数。

先验证冻结清单和 Step 1 本地入口：

```bash
python training/script/step_0_plan_sources.py --dry-run
python training/script/step_1_prepare_stories.py --auto-boundaries --dry-run
```

正常结束应分别显示 542→80 的规划统计和 `Step 1a 检查通过（退出码 0）`。两条命令都不会调用
模型或写入工作目录。正式运行数据默认写入已忽略的 `work/training-pipeline-fear-v1/`。

确认云端处理和训练授权后，再按主文档底部的
[Step 0–8 快速操作表](../最适合你的模型流水线.md#step-08-快速操作表)运行。Step 2–5 可用
`--limit 20 --continue-on-error` 分批执行；Step 1 Terra 复核默认每批 10 份。重复同一命令会跳过
来源哈希未变化的有效结果并继续。自动调用只允许 Luna/Terra medium，必要修复最多 Terra high
一次；脚本禁用 profile/Fast 且不会自动调用 Sol，未解决项会生成手工升级包。
当 Step 1 显示“自动待处理 0；等待人工 Sol N”时，不要继续空跑相同命令；应按主文档 Step 1d
逐项保存人工 JSON，再按 Step 1e 运行正式命令导入。Step 1 的两份进度都完成后才能进入 Step 2。
遇到 429、账户并发限制或网络不稳定时，将对应 worker 参数降为 1。按一次 Ctrl+C 会终止当前
模型子进程并取消尚未提交的任务，之后可重复同一命令续跑。
