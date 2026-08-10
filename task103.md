你先阅读`modelScript/tts_local_voxcpm2_安装指南.md`和`modelScript/tts_local_voxcpm2.py`
然后参考上面的方式
1. 创建一个conda 环境，名称是 LongCat-AudioDiT-3.5B-bf16，安装 `~/hf-mirror/drbaph/LongCat-AudioDiT-3.5B-bf16`所要求的软件,需要的其他依赖在`~/tts-depency/LongCat-AudioDiT`,将接入使用的方式写成`tts_local_LongCat_AudioDit_3.5B_bf16.py`和`tts_local_LongCat_AudioDit_3.5B_bf16_安装指南.md`输出到`modelScript`目录


将以上逐个完成
以上执行过程，如果有错误，删除`conda环境安装错误.md`，将最新错误记录在项目根目录`conda环境安装错误.md`
以上执行过程，如果有依赖前提缺失，删除`conda环境依赖缺失.md`，将最新依赖缺失记录在项目根目录`conda环境依赖缺失.md`
如果以上没有错误，没有依赖缺失，删除`conda环境安装错误.md`和`conda环境依赖缺失.md`
注意：直接将需要执行的python命令粘贴到文档中，这样我可以快速复制和执行，命令用国内清华，中科大或者阿里云的镜像