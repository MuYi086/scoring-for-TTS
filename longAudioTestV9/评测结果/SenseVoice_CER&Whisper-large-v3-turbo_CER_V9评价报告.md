# SenseVoice CER 与 Whisper-large-v3-turbo CER V9 评价报告

本报告衡量双 ASR 转写与实际合成台词的差异。全文参考严格为 `longAudioTestV9/text.md` 中实际参与合成、原始顺序固定的文本；未使用不存在的 `ai_deal.json`，也未复用旧 V9 字符统计。

- 规范化规则：`zh-v1`；参考字符数：`1527`。
- 共享分段清单：23 段；按旁白参考语速估算，目标片段 `25` 秒、最大 `35` 秒。
- ASR 直接读取与最终 WAV 哈希绑定的逐段合成证据；严格汉字 CER 记录字面差异，拼音 CER 仅用于识别同音字造成的假阳性，二者均不等同于人工确认的朗读错误。
- 原始证据：[task9_evaluation_results.json](task9-v2-20260729T093808Z/task9_evaluation_results.json)。
- 两个后端独立排名，绝不平均为综合分；Whisper 名称完整标注为 Whisper-large-v3-turbo。

## 双后端逐段文本指标与独立名次

| 模型 | SenseVoice 严格汉字 CER | SenseVoice 拼音 CER | SenseVoice 健康 / 名次 | Whisper 严格汉字 CER | Whisper 拼音 CER | Whisper 健康 / 名次 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| IndexTTS2 | 0.033399 | 0.009823 | healthy / 2 | 0.033399 | 0.007204 | healthy / 1 |
| VoxCPM2 | 0.029470 | 0.007859 | healthy / 1 | 0.040602 | 0.009823 | healthy / 2 |

## 完整转写与字符错误位置

### IndexTTS2

#### SenseVoice

- 严格汉字 CER：`0.033399`；字符编辑数：`51`。
- 拼音 CER：`0.009823`；拼音 token 编辑数：`15`。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 23 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
视频通话接通了，我的男朋友微笑着，首先我爱你，我想你，我等不及你回家了，我也爱你，我也等不及了。我盯着电脑屏幕，你在哪儿？我在阁楼里，布罗迪回答，我把弓箭器材放上去的时候，发现了个挺酷的东西。他刚在休斯敦一个安静的社区买了一栋老房子，我希望那里有一天能成为我们的社区。我们交往三年了，我猜他可能会在今年春天，我大学毕业之后求婚。看看这个，他把一个落满灰尘的箱子拖到吊灯下面，好让我看清上面的课文，看起来像是阿拉伯文。他打开箱子，取出一个三角形护身符，银制的上面有同样的标记，接着是一个极小的推拉盒，里面装着碎纸片、木屑，还有一些辨认不出的块状物，闻起来像茉莉花，他凑近嗅了嗅。下一个物件是个束口袋，他打开袋子，把里面的东西倒在掌心里。嗯，叫指甲搞什么鬼？箱子里最后两样东西是一本破旧的古蓝鲸和一盒玻璃球装饰品，不是没有挂钩或绳子的地方。有三个透明的，还有这个，他举起来给我看是烟熏黄的颜色。我发誓那球在他掌心里动了一下，他摔到地上碎了，有什么东西闪过，像火焰一样。布罗迪骂了一句，那是什么？我喊道。我我不知道他盯着我视线之外的地方，他歪着头好像在听什么。布罗迪，他说，然后唐纳特什么？唐纳特是他母亲的名字，布罗迪茫然的看着屏幕说，我得挂了。没再多说一个字，他结束了skype通话，我试图打回去，他没接。那晚他也没接。终于第二天早上他接了，我现在有点忙，他说声音很沉，你还好吗？嗯，他说然后挂断了。接下来一整天，我都没有他的消息，于是我打电话给他姐姐，让他去看看他。一小时后，他回了电话，他的声音很谨慎。嗯，阿丽呀，我看见他了，她看起来有点糟，听着你们吵架了吗？什么？没有我告诉他，你在担心他，他就那么看着我，他昨天还好好的，我们还在计划圣诞假期的安排，又是一阵犹豫。他表现的几乎像磕了药。我从不知道布罗迪会，他不会从来不。好吧，只是给他一两天时间，也许他真的在忙什么事，有消息我会告诉你的，但他没有，我也没有他不接我电话，也不回短信，这太不像布罗迪了。我为力翻江倒海，真不知道我怎么熬过期末考试的。我想到了他找到的那些奇怪的东西，一定和那有关。我的祖母是孟加拉裔穆斯林。我父亲不信仰任何宗教，但我上学期修了一门伊斯兰传统的课程，我很喜欢那位教授，在飞回家前的那个早上，我顺道去了他的办公室。阿利亚真是个惊喜。当我告诉他布罗迪的发现和那通诡异的视频通话时，他的笑容消失了。他走到书架前拿起一本书，翻了几页，他停下来递给我。那些课文和护身符是不是长这样？是的，这是什么？我们课上没有多讲，但古兰鲸认为安拉有三种有致石的造物，天使、人类和精灵。你描述的那些物件是魔法师用来控制和意识精灵的。有时他们会把这些生物困在玻璃球里。精灵。我笑了，你是说神灯精灵，你描述的那些是邪恶的魔法，你说他重复了他母亲的名字，传说中魔法师需要三样东西才能跟恶魔谈论你一个名字，你母亲的名字和一份痕迹。头发指甲屑，您不会真的相信有精灵吧。他看了我很久，然后说我会发一封邮件给你。里面有一些经文可以抵御精灵附身。等你见到布罗迪，不妨试试。还有阿利亚，小心点。我对他的警告一笑置止，但那天下午敲响布罗迪家门时，我的心沉甸甸的，他敲到第三下才开门，他的样子让我震惊，他看起来很疲惫，胡子拉碴，他看着我仿佛我是个陌生人。布罗迪。怎么回事？他身后的走廊里有什么东西一闪而过，像是相机闪光灯的余晖。我发誓，我瞬间看见了一个火焰凝成的女人，他回头看了一眼，又转向我，你该走了，他当着我的面关上了门。我一直等到夜幕降临，拿了藏着的钥匙，自己开了门，房子里很安静，我蹑手蹑脚的穿过各个房间寻找他。当我偷偷望向他的卧室时，我倒吸一口凉气，布罗底趴浮在床上，盯着天花板。那个火焰女人坐在他身上，他听到我的动静，猛的转过头来，嘶嘶作响，露出两英寸长的尖牙。我跑了，穿过房子时，门像枪声一样砰砰的关合，前门打不开了，我尖叫着猛拉门把手。他在逼近阁楼的梯子放下来了，我冲了上去，我掏出手机，疯狂的想打开教授发给我的邮件。透过阁楼口，布罗迪和那个火焰女人仰头盯着我门砰的关上了。我被困在这里好几个小时了，我一直念诵着导师发给我的经吻，直到我的声音和手机电池都耗尽。现在我闻到了烟味。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 003 | same_pronunciation_substitution | substitution | 175 | 刻 | 175 | 课 |
| 003 | same_pronunciation_substitution | substitution | 176 | 纹 | 176 | 文 |
| 004 | same_pronunciation_substitution | substitution | 202 | 质 | 202 | 制 |
| 005 | different_pronunciation_substitution | substitution | 283 | 呃 | 283 | 嗯 |
| 005 | different_pronunciation_substitution | substitution | 284 | 脚 | 284 | 叫 |
| 005 | same_pronunciation_substitution | substitution | 285 | 趾 | 285 | 指 |
| 005 | same_pronunciation_substitution | substitution | 307 | 兰 | 307 | 蓝 |
| 005 | same_pronunciation_substitution | substitution | 308 | 经 | 308 | 鲸 |
| 006 | same_pronunciation_substitution | substitution | 368 | 它 | 368 | 他 |
| 007 | same_pronunciation_substitution | substitution | 435 | 娜 | 435 | 纳 |
| 007 | same_pronunciation_substitution | substitution | 440 | 娜 | 440 | 纳 |
| 007 | different_pronunciation_substitution | substitution | 454 | 地 | 454 | 的 |
| 009 | same_pronunciation_substitution | substitution | 556 | 她 | 556 | 他 |
| 009 | same_pronunciation_substitution | substitution | 565 | 她 | 565 | 他 |
| 009 | same_pronunciation_substitution | substitution | 570 | 她 | 570 | 他 |
| 009 | same_pronunciation_substitution | substitution | 579 | 莉 | 579 | 丽 |
| 009 | different_pronunciation_substitution | substitution | 580 | 娅 | 580 | 呀 |
| 009 | same_pronunciation_substitution | substitution | 586 | 他 | 586 | 她 |
| 010 | different_pronunciation_substitution | substitution | 650 | 得 | 650 | 的 |
| 011 | same_pronunciation_substitution | substitution | 703 | 她 | 703 | 他 |
| 012 | same_pronunciation_substitution | substitution | 730 | 胃 | 730 | 为 |
| 012 | different_pronunciation_substitution | substitution | 731 | 里 | 731 | 力 |
| 013 | same_pronunciation_substitution | substitution | 833 | 她 | 833 | 他 |
| 013 | same_pronunciation_substitution | substitution | 839 | 莉 | 839 | 利 |
| 013 | same_pronunciation_substitution | substitution | 840 | 娅 | 840 | 亚 |
| 014 | same_pronunciation_substitution | substitution | 850 | 她 | 850 | 他 |
| 014 | same_pronunciation_substitution | substitution | 868 | 她 | 868 | 他 |
| 014 | same_pronunciation_substitution | substitution | 875 | 她 | 875 | 他 |
| 014 | same_pronunciation_substitution | substitution | 890 | 她 | 890 | 他 |
| 014 | same_pronunciation_substitution | substitution | 899 | 刻 | 899 | 课 |
| 014 | same_pronunciation_substitution | substitution | 900 | 纹 | 900 | 文 |
| 015 | same_pronunciation_substitution | substitution | 928 | 经 | 928 | 鲸 |
| 015 | same_pronunciation_substitution | substitution | 937 | 智 | 937 | 致 |
| 015 | same_pronunciation_substitution | substitution | 938 | 识 | 938 | 石 |
| 015 | same_pronunciation_substitution | substitution | 966 | 役 | 966 | 意 |
| 015 | different_pronunciation_substitution | substitution | 967 | 使 | 967 | 识 |
| 017 | same_pronunciation_substitution | substitution | 1074 | 她 | 1074 | 他 |
| 017 | same_pronunciation_substitution | substitution | 1121 | 莉 | 1121 | 利 |
| 017 | same_pronunciation_substitution | substitution | 1122 | 娅 | 1122 | 亚 |
| 018 | same_pronunciation_substitution | substitution | 1128 | 她 | 1128 | 他 |
| 018 | different_pronunciation_substitution | substitution | 1135 | 之 | 1135 | 止 |
| 020 | different_pronunciation_substitution | substitution | 1304 | 地 | 1304 | 的 |
| 020 | different_pronunciation_substitution | substitution | 1334 | 迪 | 1334 | 底 |
| 020 | same_pronunciation_substitution | substitution | 1336 | 伏 | 1336 | 浮 |
| 021 | same_pronunciation_substitution | substitution | 1356 | 她 | 1356 | 他 |
| 021 | different_pronunciation_substitution | substitution | 1364 | 地 | 1364 | 的 |
| 021 | different_pronunciation_substitution | substitution | 1398 | 地 | 1398 | 的 |
| 022 | same_pronunciation_substitution | substitution | 1416 | 她 | 1416 | 他 |
| 022 | different_pronunciation_substitution | substitution | 1441 | 地 | 1441 | 的 |
| 022 | different_pronunciation_substitution | substitution | 1475 | 地 | 1475 | 的 |
| 023 | different_pronunciation_substitution | substitution | 1504 | 文 | 1504 | 吻 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.033399`；字符编辑数：`51`。
- 拼音 CER：`0.007204`；拼音 token 编辑数：`11`。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 23 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
视频通话接通了,我的男朋友微笑着,首先,我爱你,我想你,我等不及你回家了,我也爱你,我也等不及了,我盯着电脑屏幕,你在哪儿呢?我在阁楼里布罗迪回答我把弓箭器材放上去的时候发现了个挺酷的东西他刚在休斯敦一个安静的社区买了一栋老房子我希望那里有一天能成为我们的社区我们交往三年了我猜他可能会在今年春天我大学毕业之后求婚看看这个他把一个落满灰尘的箱子拖到吊灯下面好让我看清上面的课文看起来像是阿拉伯文他打开箱子,取出一个三角形护身符,银制的上面有同样的标记。接着是一个极小的推拉盒,里面装着碎纸片,木屑,还有一些辨认不出的快撞物,闻起来像茉莉花。他凑近秀了秀。下一个物件是个漱口袋,他打开袋子,把里面的东西倒在掌心里。嗯,叫指甲,搞什么鬼?箱子里最后两样东西是一本破旧的古兰经和一盒玻璃球,装饰品,不是没有挂钩或绳子的地方。有三个透明的还有这个他举起来给我看是烟熏黄的颜色我发誓那球在他掌心里冻了一下他摔到地上碎了有什么东西闪过像火焰一样布罗迪骂了一句那是什么我喊道我,我不知道,他盯着我视线之外的地方,他歪着头,好像在听什么,布罗迪,他说,然后唐纳特什么,唐纳特是他母亲的名字,布罗迪茫然地看着屏幕,说,我得挂了。没再多说一个字,他结束了skype通话,我试图打回去,他没接,那晚他也没接,终于第二天早上他接了,我现在有点忙,他说声音很沉,你还好吗?嗯,他说,然后挂断了。接下来一整天我都没有她的消息于是我打电话给她姐姐让她去看看她一小时后她回了电话她的声音很谨慎嗯 阿丽啊我看见她了她看起来有点糟听着你们吵架了吗什么没有,我告诉他你在担心他,他就那么看着我,他昨天还好好的,我们还在计划圣诞假期的安排,又是一阵犹豫,他表现得几乎像磕了药,我从不知道布罗迪会,他不会从来不。好吧,只是给他一两天时间,也许他真的在忙什么事,有消息我会告诉你的,但他没有,我也没有,他不接我电话,也不回短信,这太不像布罗迪了。我胃里翻江倒海真不知道我怎么熬过期末考试的我想到了他找到的那些奇怪的东西一定和那有关我的祖母是孟加拉义穆斯林我父亲不信仰任何宗教,但我上学期修了一门伊斯兰传统的课程。我很喜欢那位教授,在飞回家前的那个早上,我顺道去了他的办公室,阿里亚真是个惊喜。当我告诉他布罗迪的发现和那通诡异的视频通话时,他的笑容消失了。他走到书架前拿起一本书,翻了几页他停下来递给我。那些课文和护身符是不是长这样?是的,这是什么?我们课上没有多讲但古兰经认为安拉有三种有智识的造物天使人类和精灵你描述的那些物件是魔法师用来控制和意识精灵的有时他们会把这些生物困在玻璃球里精灵我笑了你是说神灯精灵你描述的那些是邪恶的魔法你说他重复了他母亲的名字传说中魔法师需要三样东西才能跟恶魔谈论你一个名字你母亲的名字和一份痕迹头发指甲蟹您不会真的相信有精灵吧他看了我很久然后说我会发一封邮件给你里面有一些经文可以抵御精灵附身等你见到布罗迪不妨试试还有阿利亚小心点我对他的警告一笑置之但那天下午敲响布罗迪家门时我的心沉甸甸的他敲到第三下才开门他的样子让我震惊他看起来很疲惫胡子拉叉他看着我仿佛我是个陌生人布罗迪怎么回事她身后的走廊里有什么东西一闪而过像是相机闪光灯的余晖我发誓我瞬间看见了一个火焰凝成的女人她回头看了一眼又转向我你该走了她当着我的面关上了门我一直等到夜幕降临,拿了藏着的钥匙,自己开了门。房子里很安静,我捏手捏脚地穿过各个房间,寻找他。当我偷偷望向他的卧室时,我倒吸一口凉气,布罗迪趴伏在床上,盯着天花板。那个火焰女人坐在她身上,她听到我的动静,猛地转过头来,嘶嘶作响,露出两英寸长的尖牙。我跑了,穿过房子时,门像枪声一样,砰砰地关门,前门打不开了,我尖叫着猛拉门把手。他在逼近,阁楼的梯子放下来了,我冲了上去,我掏出手机,疯狂地想打开教授发给我的邮件。透过阁楼口,布罗迪和那个火焰女人仰头盯着我,门砰得关上了。我被困在这里好几个小时了我一直念诵着导师发给我的经文直到我的声音和手机电池都耗尽现在我闻到了烟味
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | insertion | insertion | 52 | ∅ | 52 | 呢 |
| 003 | same_pronunciation_substitution | substitution | 175 | 刻 | 176 | 课 |
| 003 | same_pronunciation_substitution | substitution | 176 | 纹 | 177 | 文 |
| 004 | same_pronunciation_substitution | substitution | 202 | 质 | 203 | 制 |
| 004 | same_pronunciation_substitution | substitution | 241 | 块 | 242 | 快 |
| 004 | same_pronunciation_substitution | substitution | 242 | 状 | 243 | 撞 |
| 004 | same_pronunciation_substitution | substitution | 254 | 嗅 | 255 | 秀 |
| 004 | same_pronunciation_substitution | substitution | 256 | 嗅 | 257 | 秀 |
| 005 | same_pronunciation_substitution | substitution | 264 | 束 | 265 | 漱 |
| 005 | different_pronunciation_substitution | substitution | 283 | 呃 | 284 | 嗯 |
| 005 | different_pronunciation_substitution | substitution | 284 | 脚 | 285 | 叫 |
| 005 | same_pronunciation_substitution | substitution | 285 | 趾 | 286 | 指 |
| 006 | same_pronunciation_substitution | substitution | 364 | 动 | 365 | 冻 |
| 006 | same_pronunciation_substitution | substitution | 368 | 它 | 369 | 他 |
| 007 | same_pronunciation_substitution | substitution | 435 | 娜 | 436 | 纳 |
| 007 | same_pronunciation_substitution | substitution | 440 | 娜 | 441 | 纳 |
| 009 | same_pronunciation_substitution | substitution | 541 | 他 | 542 | 她 |
| 009 | same_pronunciation_substitution | substitution | 552 | 他 | 553 | 她 |
| 009 | same_pronunciation_substitution | substitution | 560 | 他 | 561 | 她 |
| 009 | same_pronunciation_substitution | substitution | 579 | 莉 | 580 | 丽 |
| 009 | different_pronunciation_substitution | substitution | 580 | 娅 | 581 | 啊 |
| 009 | same_pronunciation_substitution | substitution | 584 | 他 | 585 | 她 |
| 009 | same_pronunciation_substitution | substitution | 586 | 他 | 587 | 她 |
| 011 | same_pronunciation_substitution | substitution | 703 | 她 | 704 | 他 |
| 012 | same_pronunciation_substitution | substitution | 779 | 裔 | 780 | 义 |
| 013 | same_pronunciation_substitution | substitution | 833 | 她 | 834 | 他 |
| 013 | different_pronunciation_substitution | substitution | 839 | 莉 | 840 | 里 |
| 013 | same_pronunciation_substitution | substitution | 840 | 娅 | 841 | 亚 |
| 014 | same_pronunciation_substitution | substitution | 850 | 她 | 851 | 他 |
| 014 | same_pronunciation_substitution | substitution | 868 | 她 | 869 | 他 |
| 014 | same_pronunciation_substitution | substitution | 875 | 她 | 876 | 他 |
| 014 | same_pronunciation_substitution | substitution | 890 | 她 | 891 | 他 |
| 014 | same_pronunciation_substitution | substitution | 899 | 刻 | 900 | 课 |
| 014 | same_pronunciation_substitution | substitution | 900 | 纹 | 901 | 文 |
| 015 | same_pronunciation_substitution | substitution | 966 | 役 | 967 | 意 |
| 015 | different_pronunciation_substitution | substitution | 967 | 使 | 968 | 识 |
| 017 | same_pronunciation_substitution | substitution | 1062 | 屑 | 1063 | 蟹 |
| 017 | same_pronunciation_substitution | substitution | 1074 | 她 | 1075 | 他 |
| 017 | same_pronunciation_substitution | substitution | 1121 | 莉 | 1122 | 利 |
| 017 | same_pronunciation_substitution | substitution | 1122 | 娅 | 1123 | 亚 |
| 018 | same_pronunciation_substitution | substitution | 1128 | 她 | 1129 | 他 |
| 018 | different_pronunciation_substitution | substitution | 1183 | 碴 | 1184 | 叉 |
| 019 | same_pronunciation_substitution | substitution | 1203 | 他 | 1204 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1247 | 他 | 1248 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1262 | 他 | 1263 | 她 |
| 020 | different_pronunciation_substitution | substitution | 1300 | 蹑 | 1301 | 捏 |
| 020 | different_pronunciation_substitution | substitution | 1302 | 蹑 | 1303 | 捏 |
| 021 | same_pronunciation_substitution | substitution | 1353 | 他 | 1354 | 她 |
| 021 | different_pronunciation_substitution | substitution | 1400 | 合 | 1401 | 门 |
| 022 | same_pronunciation_substitution | substitution | 1416 | 她 | 1417 | 他 |
| 022 | different_pronunciation_substitution | substitution | 1475 | 地 | 1476 | 得 |

### VoxCPM2

#### SenseVoice

- 严格汉字 CER：`0.029470`；字符编辑数：`45`。
- 拼音 CER：`0.007859`；拼音 token 编辑数：`12`。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 23 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
视频通话接通了，我的男朋友微笑着，首先我爱你，我想你，我等不及你回家了，我也爱你，我也等不及了，我盯着电脑屏幕，你在哪儿？我在阁楼里，布洛迪回答，我把弓箭器材放上去的时候，发现了个挺酷的东西。他刚在休斯敦一个安静的社区买了一栋老房子，我希望那里有一天能成为我们的社区。我们交往三年了，我猜他可能会在今年春天，我大学毕业之后求婚。看看这个他把一个落满灰尘的箱子拖到吊灯下面，好让我看清上面的课文，看起来像是阿拉伯文。他打开箱子，取出一个三角形护身符，银制的上面有同样的标记，接着是一个极小的推拉盒，里面装着碎纸片、木屑，还有一些辨认不出的块状物，闻起来像茉莉花，他凑近嗅了嗅。下一个物件是个束口袋，他打开袋子，把里面的东西倒在掌心里。呃，脚趾甲搞什么鬼，箱子里最后两样东西是一本破旧的古蓝鲸和一盒玻璃球装饰品，不是没有挂钩或绳子的地方。有三个透明的，还有这个他举起来给我看，是烟熏黄的颜色。我发誓那球在他掌心里动了一下，他摔到地上碎了。有什么东西闪过，像火焰一样，布罗迪骂了一句，那是什么？我喊道。我我不知道他盯着我视线之外的地方，他歪着头好像在听什么。布罗迪他说，然后唐纳特，什么唐纳特是他母亲的名字，布罗迪茫然的看着屏幕，说，我得挂了。没再多说一个字，他结束了skype通话，我试图打回去，他没接，那晚他也没接。终于第二天早上他接了，我现在有点忙，他说声音很沉，你还好吗？嗯，他说然后挂断了。接下来一整天，我都没有她的消息，于是我打电话给他姐姐，让她去看看她。一小时后，她回了电话，她的声音很谨慎，嗯，阿丽亚，我看见她了，她看起来有点糟，听着你们吵架了吗？什么？没有我告诉他，你在担心他，他就那么看着我，他昨天还好好的，我们还在计划圣诞假期的安排，又是一阵犹豫，他表现的几乎像磕了药，我从不知道布罗迪会，他不会，从来不。好吧，只是给他一两天时间，也许他真的在忙什么事，有消息我会告诉你的，但他没有，我也没有，他不接我电话，也不回短信，这太不像布洛迪了。无谓里翻江倒海，真不知道我怎么熬过期末考试的。我想到了他找到的那些奇怪的东西，一定和那有关。我的祖母是孟加拉裔穆斯林。我父亲不信仰任何宗教，但我上学期修了一门伊斯兰传统的课程，我很喜欢那位教授，在飞回家前的那个早上，我顺道去了他的办公室。阿丽亚真是个惊喜。当我告诉他，布罗迪的发现和那通诡异的视频通话时，他的笑容消失了。他走到书架前，拿起一本书，翻了几页，他停下来递给我。那些课文和护身符是不是长这样？是的，这是什么？我们课上没有多讲，但古兰经认为安拉有三种有志识的造物，天使、人类和精灵，你描述的那些物件是魔法师用来控制和意识精灵的。有时他们会把这些生物困在玻璃球里，精灵。我笑了，你是说神灯精灵，你描述的那些是邪恶的魔法，你说他重复了他母亲的名字，传说中魔法师需要三样东西才能跟恶魔谈论你一个名字，你母亲的名字和一份痕迹。头发指甲屑，您不会真的相信有精灵吧。他看了我很久，然后说我会发一封邮件给你。里面有一些经文，可以抵御精灵附身，等你见到布罗迪，不妨试试，还有阿利亚，小心点。我对他的警告一笑置之，但那天下午敲响布罗迪家门时，我的心沉甸甸的，他敲到第三下才开门，他的样子让我震惊，他看起来很疲惫，胡子拉碴，他看着我仿佛我是个陌生人，布罗迪。怎么回事？他身后的走廊里有什么东西一闪而过，像是相机、闪光灯的余晖。我发誓我瞬间看见了一个火焰凝成的女人，他回头看了一眼，又转向我，你该走了，他当着我的面关上了门。我一直等到夜幕降临，拿了藏着的钥匙，自己开了门，房子里很安静，我蹑手蹑脚的穿过各个房间寻找他。当我偷偷望向他的卧室时，我倒吸一口凉气。布罗迪趴伏在床上盯着天花板。那个火焰女人坐在他身上，他听到我的动静，猛的转过头来，嘶嘶作响，露出2英寸长的尖牙。我跑了，穿过房子时，门像枪声一样砰砰的关合，前门打不开了，我尖叫着猛拉门把手。他在逼近阁楼的梯子放下来了，我冲了上去，我掏出手机，疯狂的想打开教授发给我的邮件，透过阁楼口，布罗迪和那个火焰女人仰头盯着我，门砰的关上了。我被困在这里好几个小时了，我一直念诵着导师发给我的经文，直到我的声音和手机电池都耗尽。现在我闻到了烟味。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 002 | different_pronunciation_substitution | substitution | 58 | 罗 | 58 | 洛 |
| 003 | same_pronunciation_substitution | substitution | 175 | 刻 | 175 | 课 |
| 003 | same_pronunciation_substitution | substitution | 176 | 纹 | 176 | 文 |
| 004 | same_pronunciation_substitution | substitution | 202 | 质 | 202 | 制 |
| 005 | same_pronunciation_substitution | substitution | 307 | 兰 | 307 | 蓝 |
| 005 | same_pronunciation_substitution | substitution | 308 | 经 | 308 | 鲸 |
| 006 | same_pronunciation_substitution | substitution | 368 | 它 | 368 | 他 |
| 007 | same_pronunciation_substitution | substitution | 435 | 娜 | 435 | 纳 |
| 007 | same_pronunciation_substitution | substitution | 440 | 娜 | 440 | 纳 |
| 007 | different_pronunciation_substitution | substitution | 454 | 地 | 454 | 的 |
| 009 | same_pronunciation_substitution | substitution | 541 | 他 | 541 | 她 |
| 009 | same_pronunciation_substitution | substitution | 560 | 他 | 560 | 她 |
| 009 | same_pronunciation_substitution | substitution | 579 | 莉 | 579 | 丽 |
| 009 | same_pronunciation_substitution | substitution | 580 | 娅 | 580 | 亚 |
| 009 | same_pronunciation_substitution | substitution | 584 | 他 | 584 | 她 |
| 009 | same_pronunciation_substitution | substitution | 586 | 他 | 586 | 她 |
| 010 | different_pronunciation_substitution | substitution | 650 | 得 | 650 | 的 |
| 011 | same_pronunciation_substitution | substitution | 703 | 她 | 703 | 他 |
| 011 | different_pronunciation_substitution | substitution | 726 | 罗 | 726 | 洛 |
| 012 | different_pronunciation_substitution | substitution | 729 | 我 | 729 | 无 |
| 012 | same_pronunciation_substitution | substitution | 730 | 胃 | 730 | 谓 |
| 013 | same_pronunciation_substitution | substitution | 833 | 她 | 833 | 他 |
| 013 | same_pronunciation_substitution | substitution | 839 | 莉 | 839 | 丽 |
| 013 | same_pronunciation_substitution | substitution | 840 | 娅 | 840 | 亚 |
| 014 | same_pronunciation_substitution | substitution | 850 | 她 | 850 | 他 |
| 014 | same_pronunciation_substitution | substitution | 868 | 她 | 868 | 他 |
| 014 | same_pronunciation_substitution | substitution | 875 | 她 | 875 | 他 |
| 014 | same_pronunciation_substitution | substitution | 890 | 她 | 890 | 他 |
| 014 | same_pronunciation_substitution | substitution | 899 | 刻 | 899 | 课 |
| 014 | same_pronunciation_substitution | substitution | 900 | 纹 | 900 | 文 |
| 015 | same_pronunciation_substitution | substitution | 937 | 智 | 937 | 志 |
| 015 | same_pronunciation_substitution | substitution | 966 | 役 | 966 | 意 |
| 015 | different_pronunciation_substitution | substitution | 967 | 使 | 967 | 识 |
| 017 | same_pronunciation_substitution | substitution | 1074 | 她 | 1074 | 他 |
| 017 | same_pronunciation_substitution | substitution | 1121 | 莉 | 1121 | 利 |
| 017 | same_pronunciation_substitution | substitution | 1122 | 娅 | 1122 | 亚 |
| 018 | same_pronunciation_substitution | substitution | 1128 | 她 | 1128 | 他 |
| 020 | different_pronunciation_substitution | substitution | 1304 | 地 | 1304 | 的 |
| 021 | same_pronunciation_substitution | substitution | 1356 | 她 | 1356 | 他 |
| 021 | different_pronunciation_substitution | substitution | 1364 | 地 | 1364 | 的 |
| 021 | different_pronunciation_substitution | substitution | 1375 | 两 | 1375 | 2 |
| 021 | different_pronunciation_substitution | substitution | 1398 | 地 | 1398 | 的 |
| 022 | same_pronunciation_substitution | substitution | 1416 | 她 | 1416 | 他 |
| 022 | different_pronunciation_substitution | substitution | 1441 | 地 | 1441 | 的 |
| 022 | different_pronunciation_substitution | substitution | 1475 | 地 | 1475 | 的 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.040602`；字符编辑数：`62`。
- 拼音 CER：`0.009823`；拼音 token 编辑数：`15`。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 23 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
视频通话接通了,我的男朋友微笑着,首先,我爱你,我想你,我等不及你回家了,我也爱你,我也等不及了,我盯着电脑屏幕,你在哪儿?我在阁楼里布洛迪回答我把弓箭器材放上去的时候发现了个挺酷的东西他刚在休斯顿一个安静的社区买了一栋老房子我希望那里有一天能成为我们的社区我们交往三年了我猜他可能会在今年春天我大学毕业之后求婚看看这个他把一个落满灰尘的箱子拖到吊灯下面好让我看清上面的课文看起来像是阿拉伯文她打开箱子取出一个三角形护身符银制的上面有同样的标记接着是一个极小的推拉盒里面装着碎纸片木屑还有一些辨认不出的块状物闻起来像茉莉花她凑近绣了绣下一个物件是个漱口袋他打开袋子把里面的东西倒在掌心里呃脚指甲搞什么鬼箱子里最后两样东西是一本破旧的古兰经和一盒玻璃球装饰品不是没有挂钩或绳子的地方有三个透明的还有这个他举起来给我看是烟熏黄的颜色我发誓那球在他掌心里冻了一下他摔到地上碎了有什么东西闪过像火焰一样布罗迪骂了一句那是什么我喊道我我不知道他盯着我视线之外的地方他歪着头好像在听什么布罗迪他说然后唐纳特什么唐纳特是他母亲的名字布罗迪茫然地看着屏幕说我得挂了没再多说一个字,她结束了Skype通话。我试图打回去,她没接,那晚她也没接。终于,第二天早上,她接了,我现在有点忙。她说,声音很沉,你还好吗?嗯,她说,然后挂断了。接下来一整天我都没有她的消息于是我打电话给她姐姐让她去看看她一小时后她回了电话她的声音很谨慎嗯阿丽雅我看见她了她看起来有点糟听着你们吵架了吗什么没有我告诉他你在担心他他就那么看着我他昨天还好好的我们还在计划圣诞假期的安排又是一阵犹豫他表现得几乎像磕了药我从不知道布罗迪会他不会从来不会好吧只是给他一两天时间也许他真的在忙什么事有消息我会告诉你的但他没有我也没有他不接我电话也不回短信这太不像布罗迪了我为李翻江倒海真不知道我怎么熬过期末考试的我想到了他找到的那些奇怪的东西一定和那有关我的祖母是孟加拉乙穆斯林我父亲不信仰任何宗教但我上学期修了一门伊斯兰传统的课程我很喜欢那位教授在飞回家前的那个早上我顺道去了他的办公室阿里亚真是个惊喜当我告诉他布洛迪的发现和那同诡异的视频通话时他的笑容消失了他走到书架前拿起一本书翻了几页他停下来递给我那些课文和护身符是不是长这样是的这是什么我们课上没有多讲但古兰经认为安拉有三种有智史的造物天使人类和精灵你描述的那些物件是魔法师用来控制和意识精灵的有时他们会把这些生物困在玻璃球里精灵我笑了你是说神灯精灵你描述的那些是邪恶的魔法你说他重复了他母亲的名字传说中魔法师需要三样东西才能跟恶魔谈论你一个名字你母亲的名字和一份痕迹头发指甲屑您不会真的相信有精灵吧他看了我很久然后说我会发一封邮件给你里面有一些经文可以抵御精灵附身等你见到布罗迪不妨试试还有阿利亚小心点我对他的警告一笑置之但那天下午敲响布罗迪家门时我的心沉甸甸的他敲到第三下才开门他的样子让我震惊他看起来很疲惫胡子拉叉他看着我仿佛我是个陌生人布罗迪怎么回事她身后的走廊里有什么东西一闪而过像是相机闪光灯的余晖我发誓我瞬间看见了一个火焰凝成的女人她回头看了一眼又转向我你该走了她当着我的面关上了门我一直等到夜幕降临拿了藏着的钥匙自己开了门房子里很安静我捏手捏脚地穿过各个房间寻找他当我偷偷望向他的卧室时我倒吸一口凉气布罗迪趴扶在床上盯着天花板那个火焰女人坐在她身上她听到我的动静猛地转过头来嘶嘶作响露出两英寸长的尖牙我跑了穿过房子时门像枪声一样砰砰的关河前门打不开了我尖叫着猛拉门把手他在逼近阁楼的梯子放下来了我冲了上去我掏出手机疯狂地想打开教授发给我的邮件透过阁楼口布罗迪和那个火焰女人仰头盯着我门砰地关上了我被困在这里好几个小时了我一直念诵着导师发给我的经文直到我的声音和手机电池都耗尽现在我闻到了烟味
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 002 | different_pronunciation_substitution | substitution | 58 | 罗 | 58 | 洛 |
| 002 | different_pronunciation_substitution | substitution | 88 | 敦 | 88 | 顿 |
| 003 | same_pronunciation_substitution | substitution | 175 | 刻 | 175 | 课 |
| 003 | same_pronunciation_substitution | substitution | 176 | 纹 | 176 | 文 |
| 004 | same_pronunciation_substitution | substitution | 186 | 他 | 186 | 她 |
| 004 | same_pronunciation_substitution | substitution | 202 | 质 | 202 | 制 |
| 004 | same_pronunciation_substitution | substitution | 251 | 他 | 251 | 她 |
| 004 | same_pronunciation_substitution | substitution | 254 | 嗅 | 254 | 绣 |
| 004 | same_pronunciation_substitution | substitution | 256 | 嗅 | 256 | 绣 |
| 005 | same_pronunciation_substitution | substitution | 264 | 束 | 264 | 漱 |
| 005 | same_pronunciation_substitution | substitution | 285 | 趾 | 285 | 指 |
| 006 | same_pronunciation_substitution | substitution | 364 | 动 | 364 | 冻 |
| 006 | same_pronunciation_substitution | substitution | 368 | 它 | 368 | 他 |
| 007 | same_pronunciation_substitution | substitution | 435 | 娜 | 435 | 纳 |
| 007 | same_pronunciation_substitution | substitution | 440 | 娜 | 440 | 纳 |
| 008 | same_pronunciation_substitution | substitution | 471 | 他 | 471 | 她 |
| 008 | same_pronunciation_substitution | substitution | 488 | 他 | 488 | 她 |
| 008 | same_pronunciation_substitution | substitution | 493 | 他 | 493 | 她 |
| 008 | same_pronunciation_substitution | substitution | 504 | 他 | 504 | 她 |
| 008 | same_pronunciation_substitution | substitution | 513 | 他 | 513 | 她 |
| 008 | same_pronunciation_substitution | substitution | 524 | 他 | 524 | 她 |
| 009 | same_pronunciation_substitution | substitution | 541 | 他 | 541 | 她 |
| 009 | same_pronunciation_substitution | substitution | 552 | 他 | 552 | 她 |
| 009 | same_pronunciation_substitution | substitution | 560 | 他 | 560 | 她 |
| 009 | same_pronunciation_substitution | substitution | 579 | 莉 | 579 | 丽 |
| 009 | different_pronunciation_substitution | substitution | 580 | 娅 | 580 | 雅 |
| 009 | same_pronunciation_substitution | substitution | 584 | 他 | 584 | 她 |
| 009 | same_pronunciation_substitution | substitution | 586 | 他 | 586 | 她 |
| 010 | insertion | insertion | 672 | ∅ | 672 | 会 |
| 011 | same_pronunciation_substitution | substitution | 703 | 她 | 704 | 他 |
| 012 | same_pronunciation_substitution | substitution | 730 | 胃 | 731 | 为 |
| 012 | same_pronunciation_substitution | substitution | 731 | 里 | 732 | 李 |
| 012 | different_pronunciation_substitution | substitution | 779 | 裔 | 780 | 乙 |
| 013 | same_pronunciation_substitution | substitution | 833 | 她 | 834 | 他 |
| 013 | different_pronunciation_substitution | substitution | 839 | 莉 | 840 | 里 |
| 013 | same_pronunciation_substitution | substitution | 840 | 娅 | 841 | 亚 |
| 014 | same_pronunciation_substitution | substitution | 850 | 她 | 851 | 他 |
| 014 | different_pronunciation_substitution | substitution | 852 | 罗 | 853 | 洛 |
| 014 | different_pronunciation_substitution | substitution | 859 | 通 | 860 | 同 |
| 014 | same_pronunciation_substitution | substitution | 868 | 她 | 869 | 他 |
| 014 | same_pronunciation_substitution | substitution | 875 | 她 | 876 | 他 |
| 014 | same_pronunciation_substitution | substitution | 890 | 她 | 891 | 他 |
| 014 | same_pronunciation_substitution | substitution | 899 | 刻 | 900 | 课 |
| 014 | same_pronunciation_substitution | substitution | 900 | 纹 | 901 | 文 |
| 015 | different_pronunciation_substitution | substitution | 938 | 识 | 939 | 史 |
| 015 | same_pronunciation_substitution | substitution | 966 | 役 | 967 | 意 |
| 015 | different_pronunciation_substitution | substitution | 967 | 使 | 968 | 识 |
| 017 | same_pronunciation_substitution | substitution | 1074 | 她 | 1075 | 他 |
| 017 | same_pronunciation_substitution | substitution | 1121 | 莉 | 1122 | 利 |
| 017 | same_pronunciation_substitution | substitution | 1122 | 娅 | 1123 | 亚 |
| 018 | same_pronunciation_substitution | substitution | 1128 | 她 | 1129 | 他 |
| 018 | different_pronunciation_substitution | substitution | 1183 | 碴 | 1184 | 叉 |
| 019 | same_pronunciation_substitution | substitution | 1203 | 他 | 1204 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1247 | 他 | 1248 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1262 | 他 | 1263 | 她 |
| 020 | different_pronunciation_substitution | substitution | 1300 | 蹑 | 1301 | 捏 |
| 020 | different_pronunciation_substitution | substitution | 1302 | 蹑 | 1303 | 捏 |
| 020 | same_pronunciation_substitution | substitution | 1336 | 伏 | 1337 | 扶 |
| 021 | same_pronunciation_substitution | substitution | 1353 | 他 | 1354 | 她 |
| 021 | different_pronunciation_substitution | substitution | 1398 | 地 | 1399 | 的 |
| 021 | same_pronunciation_substitution | substitution | 1400 | 合 | 1401 | 河 |
| 022 | same_pronunciation_substitution | substitution | 1416 | 她 | 1417 | 他 |

## 双后端分歧与 ASR 健康门控

### IndexTTS2

- 仅 SenseVoice 报告的错误：24 项。
- 仅 Whisper-large-v3-turbo 报告的错误：24 项。
- 两后端共同报告的错误：27 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。

### VoxCPM2

- 仅 SenseVoice 报告的错误：16 项。
- 仅 Whisper-large-v3-turbo 报告的错误：33 项。
- 两后端共同报告的错误：29 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。
