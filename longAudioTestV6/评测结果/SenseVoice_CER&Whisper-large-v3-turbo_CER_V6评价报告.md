# SenseVoice CER 与 Whisper-large-v3-turbo CER V6 评价报告

本报告只衡量全文台词保真。唯一参考严格为 `longAudioTestV6/text.md` 中实际参与合成、原始顺序固定的文本。V6 的两条成品均须直接使用 text.md 全文合成；CER 只能使用该文件去除空白和标点后的原始顺序文本，不能使用不存在的 `ai_deal.json`、旧 V6 字符数或其他版本台词。两个模型还必须使用由旁白参考语速、句末标点、段落边界和统一停顿策略冻结的同一份分段清单。

- 规范化规则：`zh-v1`；参考字符数：`1826`。
- 共享分段清单：30 段；按旁白参考语速估算，目标片段 `25` 秒、最大 `35` 秒。
- 评测单元：每条完整 `audio_*.wav` 成品。Task 6 使用与最终 WAV 哈希绑定的逐段合成证据；ASR 按语义段独立转写后汇总全文 CER，不使用固定时间窗口。
- 原始证据：[task6_evaluation_results.json](task-V6-20260729T163132Z/task6_evaluation_results.json)。
- 两个后端独立排名，绝不平均为综合分；ASR 健康门控不通过的后端保留原始值，但不参与对应名次。

## 双后端全文 CER 与独立名次

| 模型 | SenseVoice 严格 CER | SenseVoice 名次 | Whisper-large-v3-turbo 严格 CER | Whisper-large-v3-turbo 名次 | 差值（Whisper - SenseVoice） |
| --- | ---: | ---: | ---: | ---: | ---: |
| IndexTTS2 | 0.042716 | 1 | 0.046550 | 1 | 0.003834 |
| VoxCPM2 | 0.049836 | 2 | 0.048740 | 2 | -0.001095 |

## 完整转写与字符错误位置

### IndexTTS2

#### SenseVoice

- 严格汉字 CER：`0.042716`；字符编辑数：`78`。
- 带声调拼音 CER：`0.004929`；拼音 token 编辑数：`9`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 30 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
陈南将这一切看得清清楚楚，暗叹两人不愧出生在勾心斗角的帝王之家，短短片刻功夫就已完成了一次新战术。小公主领着一干身受重伤的侍卫，遇到拜月国的三皇子后，心中颇为不安，他不相信这是巧遇，最大的可能就是对方早已守候在这里。为了自保，他先是咄咄逼人的主动出击，令三皇子摸不清他的虚实，而后又无意间抬出诸葛成风，令三皇子心中颇为忌惮。然而，三皇子也绝非泛泛之辈，他心中虽然惊疑不定，但并没有就此退缩，而是想一路跟下去，进一步探听虚实。这两人可以说是满嘴鬼话，胡说八道。三皇子和小公主两拨人马一起向大山外走去。陈楠走在队伍的后面，暗暗庆幸，幸亏三皇子缠住了小公主，使小公主没有注意到她躲在队伍的后面。但好景不长，小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏。一个侍卫跑上前去对小恶魔耳语了几句。在那一刻，陈楠觉得黑暗笼罩了大地，天空失去了色彩。小公主满脸兴奋之色，笑嘻嘻的向陈南走来，毫无疑问，这是她遇到三皇子以来最真实的表情。但是陈楠宁愿看她那虚假的笑容，也不愿见到她此时发自内心的微笑。他在心中高呼，地狱的恶魔快把你们的子孙领走。开始时，三皇子怎么也不明白这个楚国的小公主为何突然兴奋起来，他不禁暗暗猜想是不是诸葛成风已到了不远处。后来，他随着小公主的目光望去，终于发现了令小公主兴奋的根源，竟然是前日抓到的那个俘虏。三皇子大吃一惊，对陈楠的身份开始胡乱猜疑起来。他咳嗽了一声道，这个人在路上一直鬼鬼祟祟的跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？认识当然认识。小公主咬牙切齿道，她是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子，你没想到会这么快见到我吧。陈楠简直要晕了，居然被人称作太监。小公主恶狠狠的盯着他，其中的意思再明显，不过，威胁兼恐吓让她配合人在屋檐下不得不低头。陈楠犹豫了一下，最后无奈的道，请公主殿下责罚。三皇子笑道，既然是玉公主的奴才，就请殿下自行发落吧。说罢，转身离去。嘿嘿嘿小公主看着陈楠脸上充满了笑意，陈楠身体一阵发寒，她压低声音道，公主殿下，我们做个交易吧。小公主想起先前城南的那些污言秽语，气得身躯一阵颤抖，尖声道，和我做交易，你凭什么你做梦吧。诸葛成风其实不在三皇子想对付你。陈楠在小恶魔的手掌落下之前，飞快的说出了这句话，小公主将举起的手掌放了下来，仔仔细细将她打量了一遍。道，看来我真的小看你了，没想到你这个臭贼还有几分头脑。不过，我现在心中非常不爽，交易延迟，现在我要发泄啊，林中响起了陈楠悲惨的叫声，期间夹杂着小恶魔公主得意的笑声。远处的三皇子等人面面相觑，对这位传闻中的小魔女有了进一步的认识。一轮明月高挂天边，皎洁的月光如洁白的羽毛般大片大片的洒在林间，夜风习习吹来阵阵花草的幽香，整片山林笼罩在如水的月光之下，远远望去，素淡，朦胧和谐宁静。鼻青脸肿的陈楠正在和小恶魔公主在一间帐篷内低声交换意见，两人已经确定林间巧遇三皇子等人绝非偶然，这一切都是有预谋的。这些人早已守侯在这条出山的路上。小公主道，我一开始就有一种直觉，他们要对我不利，但我不明白他们为什么有这样的动机。臣难道拜越国和楚国关系如何？小公主到两国近年来关系还算可以，没发生过什么不愉快的事情，这就怪了，既然如此，他们为什么要对公主不利呢？陈楠沉思了一会儿后，笑了起来道，我明白了，他们是想在此劫色去死。小公主对着陈楠的头狠狠的捶了一拳，陈楠吃痛，小声叫道，我不是正在帮殿下分析吗？公主殿下怎么能够这样激动呢？再说又不是没有这种可能。这方面你就不用考虑了，谁都知道这位三皇子不是一个生活糜烂之人。臣难道，也许也许他想将公主殿下作为一件礼物送给别人。听陈楠将他比作礼物，小恶魔公主气得怒目圆睁，冷声道，你这个败类说话真是太难听了，你不知道在和谁说话吗？但随后他又迅速冷静了下来，沉吟了一下道，可能性几乎为0。这就怪了，除了公主殿下之外，什么还能够令三皇子铤而走险呢？等等。后羿宫后羿公陈南和小公主一起叫导，他们同时醒悟过来。当日，公主殿下用后羿宫射杀巨蛇之时，金光剑划破长空之际，必是被三皇子看到了。怪不得这个家伙总是瞟向我背后的盒子，居然在打我们传国之宝后羿宫的主意，真是该死。小公主攥紧了小拳头，道，你这个败类到现在还没有想出一条应对之策吗？这也不能怪我啊，巧妇难为无米之炊，公主殿下的侍卫都已身受重伤，现在无可用之兵，我能怎么办？我看还是将后羿宫直接送给三皇子算了。所谓时时务者为。嘿嘿，看到小恶魔公主嘴角露出一丝冷笑，陈楠赶忙打住话语，干笑起来。你这个败类白天还大言不惭，说要和我做交易，到头来却什么也帮不上。嘿嘿，这样也好，我可以毫无顾虑的收拾你了。你不知道这两天我找你有多么辛苦，恨不得立刻扒了你的皮。看着小公主那邪恶的笑容，陈楠不禁打了个冷战。公主殿下，当初我不是有意偷看你出狱。听到这句话后，小公主的双眼几乎喷出火来了啊，你这个该死的败类，还敢提我杀了你。
```

原始转写（仅移除 SenseVoice 控制标记后才计算 CER；此处保留以供复核）：

```text
<|zh|><|NEUTRAL|><|Speech|><|withitn|>陈南将这一切看得清清楚楚，暗叹两人不愧出生在勾心斗角的帝王之家，短短片刻功夫就已完成了一次新战术。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主领着一干身受重伤的侍卫，遇到拜月国的三皇子后，心中颇为不安，他不相信这是巧遇，最大的可能就是对方早已守候在这里。<|zh|><|NEUTRAL|><|Speech|><|withitn|>为了自保，他先是咄咄逼人的主动出击，令三皇子摸不清他的虚实，而后又无意间抬出诸葛成风，令三皇子心中颇为忌惮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>然而，三皇子也绝非泛泛之辈，他心中虽然惊疑不定，但并没有就此退缩，而是想一路跟下去，进一步探听虚实。这两人可以说是满嘴鬼话，胡说八道。<|zh|><|HAPPY|><|Speech|><|withitn|>三皇子和小公主两拨人马一起向大山外走去。陈楠走在队伍的后面，暗暗庆幸，幸亏三皇子缠住了小公主，使小公主没有注意到她躲在队伍的后面。<|zh|><|HAPPY|><|Speech|><|withitn|>但好景不长，小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏。一个侍卫跑上前去对小恶魔耳语了几句。在那一刻，陈楠觉得黑暗笼罩了大地，天空失去了色彩。<|zh|><|HAPPY|><|Speech|><|withitn|>小公主满脸兴奋之色，笑嘻嘻的向陈南走来，毫无疑问，这是她遇到三皇子以来最真实的表情。但是陈楠宁愿看她那虚假的笑容，也不愿见到她此时发自内心的微笑。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他在心中高呼，地狱的恶魔快把你们的子孙领走。<|zh|><|HAPPY|><|Speech|><|withitn|>开始时，三皇子怎么也不明白这个楚国的小公主为何突然兴奋起来，他不禁暗暗猜想是不是诸葛成风已到了不远处。后来，他随着小公主的目光望去，终于发现了令小公主兴奋的根源，竟然是前日抓到的那个俘虏。<|zh|><|HAPPY|><|Speech|><|withitn|>三皇子大吃一惊，对陈楠的身份开始胡乱猜疑起来。他咳嗽了一声道，这个人在路上一直鬼鬼祟祟的跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？认识当然认识。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主咬牙切齿道，她是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子，你没想到会这么快见到我吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>陈楠简直要晕了，居然被人称作太监。小公主恶狠狠的盯着他，其中的意思再明显，不过，威胁兼恐吓让她配合人在屋檐下不得不低头。陈楠犹豫了一下，最后无奈的道，请公主殿下责罚。<|zh|><|HAPPY|><|Speech|><|withitn|>三皇子笑道，既然是玉公主的奴才，就请殿下自行发落吧。说罢，转身离去。嘿嘿嘿小公主看着陈楠脸上充满了笑意，陈楠身体一阵发寒，她压低声音道，公主殿下，我们做个交易吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主想起先前城南的那些污言秽语，气得身躯一阵颤抖，尖声道，和我做交易，你凭什么你做梦吧。诸葛成风其实不在三皇子想对付你。<|zh|><|HAPPY|><|Speech|><|withitn|>陈楠在小恶魔的手掌落下之前，飞快的说出了这句话，小公主将举起的手掌放了下来，仔仔细细将她打量了一遍。道，看来我真的小看你了，没想到你这个臭贼还有几分头脑。<|zh|><|HAPPY|><|Speech|><|withitn|>不过，我现在心中非常不爽，交易延迟，现在我要发泄啊，林中响起了陈楠悲惨的叫声，期间夹杂着小恶魔公主得意的笑声。<|zh|><|NEUTRAL|><|Speech|><|withitn|>远处的三皇子等人面面相觑，对这位传闻中的小魔女有了进一步的认识。<|zh|><|NEUTRAL|><|Speech|><|withitn|>一轮明月高挂天边，皎洁的月光如洁白的羽毛般大片大片的洒在林间，夜风习习吹来阵阵花草的幽香，整片山林笼罩在如水的月光之下，远远望去，素淡，朦胧和谐宁静。<|zh|><|NEUTRAL|><|Speech|><|withitn|>鼻青脸肿的陈楠正在和小恶魔公主在一间帐篷内低声交换意见，两人已经确定林间巧遇三皇子等人绝非偶然，这一切都是有预谋的。这些人早已守侯在这条出山的路上。<|zh|><|HAPPY|><|Speech|><|withitn|>小公主道，我一开始就有一种直觉，他们要对我不利，但我不明白他们为什么有这样的动机。臣难道拜越国和楚国关系如何？<|zh|><|HAPPY|><|Speech|><|withitn|>小公主到两国近年来关系还算可以，没发生过什么不愉快的事情，这就怪了，既然如此，他们为什么要对公主不利呢？陈楠沉思了一会儿后，笑了起来道，我明白了，他们是想在此劫色去死。<|zh|><|HAPPY|><|Speech|><|withitn|>小公主对着陈楠的头狠狠的捶了一拳，陈楠吃痛，小声叫道，我不是正在帮殿下分析吗？公主殿下怎么能够这样激动呢？再说又不是没有这种可能。<|zh|><|HAPPY|><|Speech|><|withitn|>这方面你就不用考虑了，谁都知道这位三皇子不是一个生活糜烂之人。臣难道，也许也许他想将公主殿下作为一件礼物送给别人。<|zh|><|NEUTRAL|><|Speech|><|withitn|>听陈楠将他比作礼物，小恶魔公主气得怒目圆睁，冷声道，你这个败类说话真是太难听了，你不知道在和谁说话吗？但随后他又迅速冷静了下来，沉吟了一下道，可能性几乎为0。<|zh|><|NEUTRAL|><|Speech|><|withitn|>这就怪了，除了公主殿下之外，什么还能够令三皇子铤而走险呢？等等。后羿宫后羿公陈南和小公主一起叫导，他们同时醒悟过来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>当日，公主殿下用后羿宫射杀巨蛇之时，金光剑划破长空之际，必是被三皇子看到了。怪不得这个家伙总是瞟向我背后的盒子，居然在打我们传国之宝后羿宫的主意，真是该死。<|zh|><|HAPPY|><|Speech|><|withitn|>小公主攥紧了小拳头，道，你这个败类到现在还没有想出一条应对之策吗？这也不能怪我啊，巧妇难为无米之炊，公主殿下的侍卫都已身受重伤，现在无可用之兵，我能怎么办？<|zh|><|HAPPY|><|Speech|><|withitn|>我看还是将后羿宫直接送给三皇子算了。所谓时时务者为。嘿嘿，看到小恶魔公主嘴角露出一丝冷笑，陈楠赶忙打住话语，干笑起来。<|zh|><|HAPPY|><|Speech|><|withitn|>你这个败类白天还大言不惭，说要和我做交易，到头来却什么也帮不上。嘿嘿，这样也好，我可以毫无顾虑的收拾你了。你不知道这两天我找你有多么辛苦，恨不得立刻扒了你的皮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>看着小公主那邪恶的笑容，陈楠不禁打了个冷战。公主殿下，当初我不是有意偷看你出狱。听到这句话后，小公主的双眼几乎喷出火来了啊，你这个该死的败类，还敢提我杀了你。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 0 | 辰 | 0 | 陈 |
| 001 | different_pronunciation_substitution | substitution | 7 | 的 | 7 | 得 |
| 001 | same_pronunciation_substitution | substitution | 34 | 工 | 34 | 功 |
| 001 | same_pronunciation_substitution | substitution | 43 | 心 | 43 | 新 |
| 001 | insertion | insertion | 45 | ∅ | 45 | 术 |
| 002 | same_pronunciation_substitution | substitution | 75 | 她 | 76 | 他 |
| 002 | different_pronunciation_substitution | substitution | 95 | 侯 | 96 | 候 |
| 003 | same_pronunciation_substitution | substitution | 103 | 她 | 104 | 他 |
| 003 | same_pronunciation_substitution | substitution | 122 | 她 | 123 | 他 |
| 003 | same_pronunciation_substitution | substitution | 136 | 乘 | 137 | 成 |
| 005 | same_pronunciation_substitution | substitution | 226 | 辰 | 227 | 陈 |
| 005 | same_pronunciation_substitution | substitution | 227 | 南 | 228 | 楠 |
| 005 | same_pronunciation_substitution | substitution | 259 | 他 | 260 | 她 |
| 006 | same_pronunciation_substitution | substitution | 315 | 辰 | 316 | 陈 |
| 006 | same_pronunciation_substitution | substitution | 316 | 南 | 317 | 楠 |
| 007 | different_pronunciation_substitution | substitution | 345 | 地 | 346 | 的 |
| 007 | same_pronunciation_substitution | substitution | 347 | 辰 | 348 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 373 | 辰 | 374 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 374 | 南 | 375 | 楠 |
| 009 | same_pronunciation_substitution | substitution | 460 | 乘 | 461 | 成 |
| 010 | same_pronunciation_substitution | substitution | 515 | 辰 | 516 | 陈 |
| 010 | same_pronunciation_substitution | substitution | 516 | 南 | 517 | 楠 |
| 010 | different_pronunciation_substitution | substitution | 547 | 地 | 548 | 的 |
| 011 | same_pronunciation_substitution | substitution | 588 | 他 | 589 | 她 |
| 012 | same_pronunciation_substitution | substitution | 642 | 辰 | 643 | 陈 |
| 012 | same_pronunciation_substitution | substitution | 643 | 南 | 644 | 楠 |
| 012 | same_pronunciation_substitution | substitution | 683 | 他 | 684 | 她 |
| 012 | same_pronunciation_substitution | substitution | 696 | 辰 | 697 | 陈 |
| 012 | same_pronunciation_substitution | substitution | 697 | 南 | 698 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 724 | 钰 | 725 | 玉 |
| 013 | same_pronunciation_substitution | substitution | 753 | 辰 | 754 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 754 | 南 | 755 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 762 | 辰 | 763 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 763 | 南 | 764 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 770 | 他 | 771 | 她 |
| 014 | different_pronunciation_substitution | substitution | 794 | 辰 | 795 | 城 |
| 014 | different_pronunciation_substitution | substitution | 804 | 的 | 805 | 得 |
| 014 | same_pronunciation_substitution | substitution | 829 | 乘 | 830 | 成 |
| 015 | same_pronunciation_substitution | substitution | 842 | 辰 | 843 | 陈 |
| 015 | same_pronunciation_substitution | substitution | 843 | 南 | 844 | 楠 |
| 015 | same_pronunciation_substitution | substitution | 882 | 他 | 883 | 她 |
| 016 | same_pronunciation_substitution | substitution | 939 | 辰 | 940 | 陈 |
| 016 | same_pronunciation_substitution | substitution | 940 | 南 | 941 | 楠 |
| 019 | same_pronunciation_substitution | substitution | 1064 | 辰 | 1065 | 陈 |
| 019 | same_pronunciation_substitution | substitution | 1065 | 南 | 1066 | 楠 |
| 020 | same_pronunciation_substitution | substitution | 1166 | 辰 | 1167 | 臣 |
| 020 | same_pronunciation_substitution | substitution | 1167 | 南 | 1168 | 难 |
| 020 | same_pronunciation_substitution | substitution | 1170 | 月 | 1171 | 越 |
| 021 | same_pronunciation_substitution | substitution | 1182 | 道 | 1183 | 到 |
| 021 | same_pronunciation_substitution | substitution | 1226 | 辰 | 1227 | 陈 |
| 021 | same_pronunciation_substitution | substitution | 1227 | 南 | 1228 | 楠 |
| 022 | same_pronunciation_substitution | substitution | 1259 | 辰 | 1260 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1260 | 南 | 1261 | 楠 |
| 022 | same_pronunciation_substitution | substitution | 1270 | 辰 | 1271 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1271 | 南 | 1272 | 楠 |
| 023 | same_pronunciation_substitution | substitution | 1342 | 辰 | 1343 | 臣 |
| 023 | same_pronunciation_substitution | substitution | 1343 | 南 | 1344 | 难 |
| 024 | same_pronunciation_substitution | substitution | 1367 | 辰 | 1368 | 陈 |
| 024 | same_pronunciation_substitution | substitution | 1368 | 南 | 1369 | 楠 |
| 024 | same_pronunciation_substitution | substitution | 1370 | 她 | 1371 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1381 | 的 | 1382 | 得 |
| 024 | same_pronunciation_substitution | substitution | 1415 | 她 | 1416 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1436 | 零 | 1437 | 0 |
| 025 | same_pronunciation_substitution | substitution | 1467 | 弓 | 1468 | 宫 |
| 025 | same_pronunciation_substitution | substitution | 1470 | 弓 | 1471 | 公 |
| 025 | same_pronunciation_substitution | substitution | 1471 | 辰 | 1472 | 陈 |
| 025 | different_pronunciation_substitution | substitution | 1480 | 道 | 1481 | 导 |
| 026 | same_pronunciation_substitution | substitution | 1498 | 弓 | 1499 | 宫 |
| 026 | same_pronunciation_substitution | substitution | 1507 | 箭 | 1508 | 剑 |
| 026 | same_pronunciation_substitution | substitution | 1552 | 弓 | 1553 | 宫 |
| 028 | same_pronunciation_substitution | substitution | 1637 | 弓 | 1638 | 宫 |
| 028 | same_pronunciation_substitution | substitution | 1649 | 识 | 1650 | 时 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 辰 | 1672 | 陈 |
| 028 | same_pronunciation_substitution | substitution | 1672 | 南 | 1673 | 楠 |
| 030 | same_pronunciation_substitution | substitution | 1766 | 辰 | 1767 | 陈 |
| 030 | same_pronunciation_substitution | substitution | 1767 | 南 | 1768 | 楠 |
| 030 | different_pronunciation_substitution | substitution | 1774 | 颤 | 1775 | 战 |
| 030 | same_pronunciation_substitution | substitution | 1790 | 浴 | 1791 | 狱 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.046550`；字符编辑数：`85`。
- 带声调拼音 CER：`0.008762`；拼音 token 编辑数：`16`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 30 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
陈南将这一切看得清清楚楚,暗叹两人不愧出生在勾心斗角的帝王之家,短短片刻功夫就已完成了一次新战损。小公主领着一干身受重伤的侍卫遇到拜越国的三皇子后心中颇为不安她不相信这是巧遇最大的可能就是对方早已守候在这里为了自保,他先是咄咄逼人的主动出击,令三皇子摸不清他的虚实,而后又无意间抬出诸葛成风,令三皇子心中颇为忌惮。然而三皇子也绝非泛泛之辈他心中虽然惊疑不定但并没有就此退缩而是想一路跟下去进一步探听虚实这两人可以说是满嘴鬼话胡说八道三皇子和小公主两拨人马一起向大山外走去陈南走在队伍的后面暗暗庆幸幸亏三皇子缠住了小公主使小公主没有注意到她躲在队伍的后面但好景不长,小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏,一个侍卫跑上前去对小恶魔耳语了几句,在那一刻陈南觉得黑暗笼罩了大地,天空失去了色彩。小公主满脸兴奋之色,笑嘻嘻地向陈楠走来,毫无疑问,这是她遇到三皇子以来最真实的表情,但是陈楠宁愿看她那虚假的笑容,也不愿见到她此时发自内心的微笑。他在心中高呼地狱的恶魔快把你们的子孙领走开始时三皇子怎么也不明白这个楚国的小公主为何突然兴奋起来他不禁暗暗猜想是不是诸葛乘风已到了不远处后来他随着小公主的目光望去终于发现了令小公主兴奋的根源竟然是前日抓到的那个俘虏三皇子大吃一惊,对陈南的身份开始胡乱猜疑起来,他咳嗽了一声道,这个人在路上一直鬼鬼祟祟地跟在我们后面,后来被我的手下抓住了,公主殿下认识这个人吗?认识当然认识。小公主咬牙切齿道,她是从我宫内带出来的小太监,本来是出来伺候我的,没想到遇上远古巨人时,她第一个就跑了。小李子,你没想到会这么快见到我吧?陈南简直要晕了,居然被人称作太监,小公主恶狠狠地盯着他,其中的意思再明显不过,威胁兼恐吓让他配合,人在屋檐下不得不低头。陈南犹豫了一下,最后无奈地道,请公主殿下责罚。三皇子笑道,既然是玉公主的奴才,就请殿下自行发落吧,说吧,转身离去,嘿嘿嘿,小公主看着陈南脸上充满了笑意,陈南身体一阵发寒,她压低声音道,公主殿下,我们做个交易吧。小公主想起先前陈南的那些乌言晦语,气得身躯一阵颤抖,奸声道,和我做交易,你凭什么,你做梦吧?诸葛成风其实不在,三皇子想对付你。陈南在小恶魔的手掌落下之前飞快地说出了这句话小公主将举起的手掌放了下来仔仔细细将她打亮了一遍道看来我真的小看你了没想到你这个臭贼还有几分头脑不过,我现在心中非常不爽,交易延迟,现在我要发泄。阿林中响起了陈南悲惨的叫声,期间夹杂着小恶魔公主得意的笑声。远处的三皇子等人面面相觑,对这位传闻中的小魔女有了进一步的认识。一轮明月高挂天边,皎洁的月光如洁白的羽毛般大片大片地洒在林间,夜风袭袭,吹来阵阵花草的幽香,整片山林笼罩在如水的月光之下,远远望去肃淡、朦胧、和谐、宁静。鼻青脸肿的陈男正在和小恶魔公主在一间帐篷内低声交换意见,两人已经确定临间巧遇三皇子等人绝非偶然,这一切都是有预谋的。这些人早已守候在这条出山的路上。小公主道,我一开始就有一种直觉,他们要对我不利,但我不明白他们为什么有这样的动机。陈南道,拜越国和楚国关系如何?小公主道,两国近年来关系还算可以,没发生过什么不愉快的事情,这就怪了,既然如此,他们为什么要对公主不利呢?陈南沉思了一会儿后,笑了起来道,我明白了,他们是想在此劫色,去死。小公主对着陈南的头狠狠地捶了一拳陈南吃痛小声叫道我不是正在帮殿下分析吗公主殿下怎么能够这样激动呢再说又不是没有这种可能这方面你就不用考虑了谁都知道这位三皇子不是一个生活糜烂之人真难道也许也许他想将公主殿下作为一件礼物送给别人听陈南将他比作礼物小恶魔公主气得怒目缘争冷声道你这个败类说话真是太难听了你不知道在和谁说话吗但随后他又迅速冷静了下来沉吟了一下道可能性几乎为零这就怪了,除了公主殿下之外,什么还能够令三皇子铤而走险呢?等等,后翼公。后翼公,陈南和小公主一起叫道,他们同时醒悟过来。当日公主殿下用后裔弓射杀巨蛇之时,金光剑划破长空之际,必是被三皇子看到了。怪不得这个家伙总是瞟向我背后的盒子,居然在打我们传国之宝后裔弓的主意,真是该死。小公主攥紧了小拳头,道,你这个败类到现在还没有想出一条应对之策吗?这也不能怪我啊,巧妇难为五米之吹,公主殿下的侍卫都已身受重伤,现在无可用之兵,我能怎么办?我看还是将后义公直接送给三皇子算了所谓实实物者为嘿嘿看到小恶魔公主嘴角露出一丝冷笑陈男赶忙打住话语干笑起来你这个败类,白天还大言不惭,说要和我做交易,到头来却什么也帮不上,嘿嘿,这样也好,我可以毫无顾虑地收拾你了,你不知道这两天我找你有多么辛苦,恨不得立刻扒了你的皮。看着小公主那邪恶的笑容,陈南不禁打了个冷战,公主殿下,当初我不是有意偷看你,出狱。听到这句话后,小公主的双眼几乎喷出火来了,你这个该死的败类还敢提我杀了你。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 0 | 辰 | 0 | 陈 |
| 001 | different_pronunciation_substitution | substitution | 7 | 的 | 7 | 得 |
| 001 | same_pronunciation_substitution | substitution | 34 | 工 | 34 | 功 |
| 001 | same_pronunciation_substitution | substitution | 43 | 心 | 43 | 新 |
| 001 | insertion | insertion | 45 | ∅ | 45 | 损 |
| 002 | same_pronunciation_substitution | substitution | 62 | 月 | 63 | 越 |
| 002 | different_pronunciation_substitution | substitution | 95 | 侯 | 96 | 候 |
| 003 | same_pronunciation_substitution | substitution | 103 | 她 | 104 | 他 |
| 003 | same_pronunciation_substitution | substitution | 122 | 她 | 123 | 他 |
| 003 | same_pronunciation_substitution | substitution | 136 | 乘 | 137 | 成 |
| 005 | same_pronunciation_substitution | substitution | 226 | 辰 | 227 | 陈 |
| 005 | same_pronunciation_substitution | substitution | 259 | 他 | 260 | 她 |
| 006 | same_pronunciation_substitution | substitution | 315 | 辰 | 316 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 347 | 辰 | 348 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 348 | 南 | 349 | 楠 |
| 007 | same_pronunciation_substitution | substitution | 373 | 辰 | 374 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 374 | 南 | 375 | 楠 |
| 010 | same_pronunciation_substitution | substitution | 515 | 辰 | 516 | 陈 |
| 011 | same_pronunciation_substitution | substitution | 588 | 他 | 589 | 她 |
| 011 | same_pronunciation_substitution | substitution | 620 | 他 | 621 | 她 |
| 012 | same_pronunciation_substitution | substitution | 642 | 辰 | 643 | 陈 |
| 012 | different_pronunciation_substitution | substitution | 663 | 的 | 664 | 地 |
| 012 | same_pronunciation_substitution | substitution | 696 | 辰 | 697 | 陈 |
| 012 | different_pronunciation_substitution | substitution | 707 | 的 | 708 | 地 |
| 013 | same_pronunciation_substitution | substitution | 724 | 钰 | 725 | 玉 |
| 013 | different_pronunciation_substitution | substitution | 740 | 罢 | 741 | 吧 |
| 013 | same_pronunciation_substitution | substitution | 753 | 辰 | 754 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 762 | 辰 | 763 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 770 | 他 | 771 | 她 |
| 014 | same_pronunciation_substitution | substitution | 794 | 辰 | 795 | 陈 |
| 014 | same_pronunciation_substitution | substitution | 799 | 污 | 800 | 乌 |
| 014 | same_pronunciation_substitution | substitution | 801 | 秽 | 802 | 晦 |
| 014 | different_pronunciation_substitution | substitution | 804 | 的 | 805 | 得 |
| 014 | same_pronunciation_substitution | substitution | 811 | 尖 | 812 | 奸 |
| 014 | same_pronunciation_substitution | substitution | 829 | 乘 | 830 | 成 |
| 015 | same_pronunciation_substitution | substitution | 842 | 辰 | 843 | 陈 |
| 015 | different_pronunciation_substitution | substitution | 857 | 的 | 858 | 地 |
| 015 | same_pronunciation_substitution | substitution | 882 | 他 | 883 | 她 |
| 015 | same_pronunciation_substitution | substitution | 884 | 量 | 885 | 亮 |
| 016 | different_pronunciation_substitution | substitution | 933 | 啊 | 934 | 阿 |
| 016 | same_pronunciation_substitution | substitution | 939 | 辰 | 940 | 陈 |
| 018 | different_pronunciation_substitution | substitution | 1015 | 的 | 1016 | 地 |
| 018 | same_pronunciation_substitution | substitution | 1022 | 习 | 1023 | 袭 |
| 018 | same_pronunciation_substitution | substitution | 1023 | 习 | 1024 | 袭 |
| 018 | same_pronunciation_substitution | substitution | 1051 | 素 | 1052 | 肃 |
| 019 | same_pronunciation_substitution | substitution | 1064 | 辰 | 1065 | 陈 |
| 019 | same_pronunciation_substitution | substitution | 1065 | 南 | 1066 | 男 |
| 019 | same_pronunciation_substitution | substitution | 1092 | 林 | 1093 | 临 |
| 019 | different_pronunciation_substitution | substitution | 1120 | 侯 | 1121 | 候 |
| 020 | same_pronunciation_substitution | substitution | 1166 | 辰 | 1167 | 陈 |
| 020 | same_pronunciation_substitution | substitution | 1170 | 月 | 1171 | 越 |
| 021 | same_pronunciation_substitution | substitution | 1226 | 辰 | 1227 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1259 | 辰 | 1260 | 陈 |
| 022 | different_pronunciation_substitution | substitution | 1265 | 的 | 1266 | 地 |
| 022 | same_pronunciation_substitution | substitution | 1270 | 辰 | 1271 | 陈 |
| 023 | different_pronunciation_substitution | substitution | 1342 | 辰 | 1343 | 真 |
| 023 | same_pronunciation_substitution | substitution | 1343 | 南 | 1344 | 难 |
| 024 | same_pronunciation_substitution | substitution | 1367 | 辰 | 1368 | 陈 |
| 024 | same_pronunciation_substitution | substitution | 1370 | 她 | 1371 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1381 | 的 | 1382 | 得 |
| 024 | same_pronunciation_substitution | substitution | 1384 | 圆 | 1385 | 缘 |
| 024 | same_pronunciation_substitution | substitution | 1385 | 睁 | 1386 | 争 |
| 024 | same_pronunciation_substitution | substitution | 1415 | 她 | 1416 | 他 |
| 025 | same_pronunciation_substitution | substitution | 1466 | 羿 | 1467 | 翼 |
| 025 | same_pronunciation_substitution | substitution | 1467 | 弓 | 1468 | 公 |
| 025 | same_pronunciation_substitution | substitution | 1469 | 羿 | 1470 | 翼 |
| 025 | same_pronunciation_substitution | substitution | 1470 | 弓 | 1471 | 公 |
| 025 | same_pronunciation_substitution | substitution | 1471 | 辰 | 1472 | 陈 |
| 026 | same_pronunciation_substitution | substitution | 1497 | 羿 | 1498 | 裔 |
| 026 | same_pronunciation_substitution | substitution | 1507 | 箭 | 1508 | 剑 |
| 026 | same_pronunciation_substitution | substitution | 1551 | 羿 | 1552 | 裔 |
| 027 | different_pronunciation_substitution | substitution | 1601 | 无 | 1602 | 五 |
| 027 | same_pronunciation_substitution | substitution | 1604 | 炊 | 1605 | 吹 |
| 028 | same_pronunciation_substitution | substitution | 1636 | 羿 | 1637 | 义 |
| 028 | same_pronunciation_substitution | substitution | 1637 | 弓 | 1638 | 公 |
| 028 | same_pronunciation_substitution | substitution | 1649 | 识 | 1650 | 实 |
| 028 | same_pronunciation_substitution | substitution | 1650 | 时 | 1651 | 实 |
| 028 | same_pronunciation_substitution | substitution | 1651 | 务 | 1652 | 物 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 辰 | 1672 | 陈 |
| 028 | same_pronunciation_substitution | substitution | 1672 | 南 | 1673 | 男 |
| 029 | different_pronunciation_substitution | substitution | 1725 | 的 | 1726 | 地 |
| 030 | same_pronunciation_substitution | substitution | 1766 | 辰 | 1767 | 陈 |
| 030 | different_pronunciation_substitution | substitution | 1774 | 颤 | 1775 | 战 |
| 030 | same_pronunciation_substitution | substitution | 1790 | 浴 | 1791 | 狱 |
| 030 | deletion | deletion | 1810 | 啊 | 1811 | ∅ |

### VoxCPM2

#### SenseVoice

- 严格汉字 CER：`0.049836`；字符编辑数：`91`。
- 带声调拼音 CER：`0.012596`；拼音 token 编辑数：`23`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 30 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
陈南将这一切看得清清楚楚，暗叹两人不愧出生在勾心斗角的帝王之家，短短片刻工夫就已完成了一次星战。小公主领着一杆身受重伤的侍卫，遇到拜月国的三皇子后，心中颇为不安，他不相信这是巧遇，最大的可能就是对方早已守候在这里。为了自保，他先是咄咄逼人的主动出击，岭三皇子摸不清他的虚实，而后又无意间抬出诸葛成风。岭三皇子心中颇为忌惮。然而，三皇子也绝非泛泛之辈，他心中虽然惊疑不定，但并没有就此退缩，而是想一路跟下去，进一步探听虚实。这两人可以说是满嘴鬼话，胡说八道。三皇子和小公主两拨人马一起向大山外走去，陈楠走在队伍的后面，暗暗清醒，幸亏三皇子缠住了小公主，使小公主没有注意到他躲在队伍的后面。但好景不长，小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏，一个侍卫跑上前去对小恶魔耳语了几句。在那一刻，陈楠觉得黑暗笼罩了大地，天空失去了色彩。小公主满脸兴奋之色，笑嘻嘻的向陈楠走来，毫无疑问，这是他遇到三皇子以来最真实的表情。但是陈楠宁愿看她那虚假的笑容，也不愿见到她此时发自内心的微笑。他在心中高呼，地狱的恶魔快把你们的子孙领走。开始时，三皇子怎么也不明白这个楚国的小公主为何突然兴奋起来，她不禁暗暗猜想，是不是诸葛成风已到了不远处。后来，她随着小公主的目光望去，终于发现了令小公主兴奋的根源，竟然是前日抓到的那个俘虏。三皇子大吃一惊，对陈南的身份开始胡乱猜疑起来，他咳嗽了一声，道，这个人在路上一直鬼鬼祟祟的跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？认识当然认识。小公主咬牙切齿道，她是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子，你没想到会这么快见到我吧。陈楠简直要晕了，居然被人称作太监，小公主恶狠狠的盯着他，其中的意思再明显不过，威胁兼恐吓，让她配合。人在屋檐下不得不低头，陈楠犹豫了一下，最后无奈的道，请公主殿下责罚。三皇子笑道，既然是玉公主的奴才，就请殿下自行发落吧。说罢，转身离去。嘿嘿嘿，小公主看着陈楠，脸上充满了笑意，陈楠身体一阵发寒，她压低声音道，公主殿下，我们做个交易吧。小公主想起先前城南的那些污言秽语，气得身躯一阵颤抖，尖声道，和我做交易，你凭什么你做梦吧，诸葛成风其实不在，三皇子想对付你。陈楠在小恶魔的手掌落下之前，飞快的说出了这句话，小公主将举起的手掌放了下来，仔仔细细将她打量了一遍。道，看来我真的小看你了，没想到你这个臭贼还有几分头脑。不过我现在心中非常不爽，交易延迟，现在我要发泄啊，林中响起了陈楠悲惨的叫声，其间夹杂着小恶魔公主得意的笑声。远处的三皇子等人面面相觑，对这位传闻中的小魔女有了进一步的认识。一轮明月高挂天边，皎洁的月光如洁白的羽毛般大片大片的洒在林间，夜风习习，吹来阵阵花草的幽香，整片山林笼罩在如水的月光之下，远远望去，素淡朦胧，和谐宁静。鼻青脸肿的陈南正在和小恶魔公主在一间帐篷内低声交换意见，两人已经确定林间巧遇三皇子等人绝非偶然，这一切都是有预谋的。这些人早已守候在这条出山的路上。小公主道，我一开始就有一种直觉，他们要对我不利，但我不明白他们为什么有这样的动机。臣楠道，白月过和楚国关系如何？小公主道，两国近年来关系还算可以，没发生过什么不愉快的事情，这就怪了，既然如此，他们为什么要对公主不利呢？陈楠陈思了一会儿后笑了起来，道，我明白了，他们是想在此劫色，去死。小公主对着陈楠的头狠狠的捶了一拳，陈楠吃痛，小声叫道，我不是正在帮殿下分析吗？公主殿下怎么能够这样激动呢？再说又不是没有这种可能。这方面你就不用考虑了，谁都知道这位三皇子不是一个生活糜烂之人。臣难道，也许也许她想将公主殿下作为一件礼物送给别人。听陈南将他比作礼物，小恶魔公主气得怒目圆睁，愣声道，你这个败类说话真是太难听了，你不知道在和谁说话吗？但随后他又迅速冷静了下来，沉吟了一下，道，可能性几乎为0。这就怪了，除了公主殿下之外，什么还能够令三皇子铤而走险呢？等等。后一宫后一公陈南和小公主一起教导，他们同时醒悟过来。当日，公主殿下用后裔宫射杀巨蛇之时，金光剑划破长空之际，必是被三皇子看到了，怪不得这个家伙总是漂向我背后的盒子，居然在打我们传国之宝后裔宫的主意，真是该死。小公主攥紧了小拳头，道，你这个败类到现在还没有想出一条应对之策吗？这也不能怪我啊，巧妇难为无米之炊，公主殿下的侍卫都已身受重伤，现在无可用之兵，我能怎么办？我看还是将后一宫直接送给三皇子算了。所谓时时务者为，嘿嘿，看到小恶魔公主嘴角露出一丝冷笑，陈南赶忙打住话语，干笑起来。你这个败类白天还大言不惭，说要和我做交易，到头来却什么也帮不上。嘿嘿，这样也好，我可以毫无顾虑的收拾你了。你不知道这两天我找你有多么辛苦，恨不得立刻扒了你的皮。看着小公主那邪恶的笑容，陈南不禁打了个冷颤。公主殿下，当初我不是有意偷看你楚狱听到这句话后，小公主的双眼几乎喷出火来了啊，你这个该死的败类，还敢提我杀了你。
```

原始转写（仅移除 SenseVoice 控制标记后才计算 CER；此处保留以供复核）：

```text
<|zh|><|NEUTRAL|><|Speech|><|withitn|>陈南将这一切看得清清楚楚，暗叹两人不愧出生在勾心斗角的帝王之家，短短片刻工夫就已完成了一次星战。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主领着一杆身受重伤的侍卫，遇到拜月国的三皇子后，心中颇为不安，他不相信这是巧遇，最大的可能就是对方早已守候在这里。<|zh|><|NEUTRAL|><|Speech|><|withitn|>为了自保，他先是咄咄逼人的主动出击，岭三皇子摸不清他的虚实，而后又无意间抬出诸葛成风。岭三皇子心中颇为忌惮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>然而，三皇子也绝非泛泛之辈，他心中虽然惊疑不定，但并没有就此退缩，而是想一路跟下去，进一步探听虚实。这两人可以说是满嘴鬼话，胡说八道。<|zh|><|NEUTRAL|><|Speech|><|withitn|>三皇子和小公主两拨人马一起向大山外走去，陈楠走在队伍的后面，暗暗清醒，幸亏三皇子缠住了小公主，使小公主没有注意到他躲在队伍的后面。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但好景不长，小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏，一个侍卫跑上前去对小恶魔耳语了几句。在那一刻，陈楠觉得黑暗笼罩了大地，天空失去了色彩。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主满脸兴奋之色，笑嘻嘻的向陈楠走来，毫无疑问，这是他遇到三皇子以来最真实的表情。但是陈楠宁愿看她那虚假的笑容，也不愿见到她此时发自内心的微笑。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他在心中高呼，地狱的恶魔快把你们的子孙领走。<|zh|><|NEUTRAL|><|Speech|><|withitn|>开始时，三皇子怎么也不明白这个楚国的小公主为何突然兴奋起来，她不禁暗暗猜想，是不是诸葛成风已到了不远处。后来，她随着小公主的目光望去，终于发现了令小公主兴奋的根源，竟然是前日抓到的那个俘虏。<|zh|><|NEUTRAL|><|Speech|><|withitn|>三皇子大吃一惊，对陈南的身份开始胡乱猜疑起来，他咳嗽了一声，道，这个人在路上一直鬼鬼祟祟的跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？认识当然认识。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主咬牙切齿道，她是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子，你没想到会这么快见到我吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>陈楠简直要晕了，居然被人称作太监，小公主恶狠狠的盯着他，其中的意思再明显不过，威胁兼恐吓，让她配合。人在屋檐下不得不低头，陈楠犹豫了一下，最后无奈的道，请公主殿下责罚。<|zh|><|NEUTRAL|><|Speech|><|withitn|>三皇子笑道，既然是玉公主的奴才，就请殿下自行发落吧。说罢，转身离去。嘿嘿嘿，小公主看着陈楠，脸上充满了笑意，陈楠身体一阵发寒，她压低声音道，公主殿下，我们做个交易吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主想起先前城南的那些污言秽语，气得身躯一阵颤抖，尖声道，和我做交易，你凭什么你做梦吧，诸葛成风其实不在，三皇子想对付你。<|zh|><|NEUTRAL|><|Speech|><|withitn|>陈楠在小恶魔的手掌落下之前，飞快的说出了这句话，小公主将举起的手掌放了下来，仔仔细细将她打量了一遍。道，看来我真的小看你了，没想到你这个臭贼还有几分头脑。<|zh|><|NEUTRAL|><|Speech|><|withitn|>不过我现在心中非常不爽，交易延迟，现在我要发泄啊，林中响起了陈楠悲惨的叫声，其间夹杂着小恶魔公主得意的笑声。<|zh|><|NEUTRAL|><|Speech|><|withitn|>远处的三皇子等人面面相觑，对这位传闻中的小魔女有了进一步的认识。<|zh|><|NEUTRAL|><|Speech|><|withitn|>一轮明月高挂天边，皎洁的月光如洁白的羽毛般大片大片的洒在林间，夜风习习，吹来阵阵花草的幽香，整片山林笼罩在如水的月光之下，远远望去，素淡朦胧，和谐宁静。<|zh|><|NEUTRAL|><|Speech|><|withitn|>鼻青脸肿的陈南正在和小恶魔公主在一间帐篷内低声交换意见，两人已经确定林间巧遇三皇子等人绝非偶然，这一切都是有预谋的。这些人早已守候在这条出山的路上。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主道，我一开始就有一种直觉，他们要对我不利，但我不明白他们为什么有这样的动机。臣楠道，白月过和楚国关系如何？<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主道，两国近年来关系还算可以，没发生过什么不愉快的事情，这就怪了，既然如此，他们为什么要对公主不利呢？陈楠陈思了一会儿后笑了起来，道，我明白了，他们是想在此劫色，去死。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主对着陈楠的头狠狠的捶了一拳，陈楠吃痛，小声叫道，我不是正在帮殿下分析吗？公主殿下怎么能够这样激动呢？再说又不是没有这种可能。<|zh|><|NEUTRAL|><|Speech|><|withitn|>这方面你就不用考虑了，谁都知道这位三皇子不是一个生活糜烂之人。臣难道，也许也许她想将公主殿下作为一件礼物送给别人。<|zh|><|NEUTRAL|><|Speech|><|withitn|>听陈南将他比作礼物，小恶魔公主气得怒目圆睁，愣声道，你这个败类说话真是太难听了，你不知道在和谁说话吗？但随后他又迅速冷静了下来，沉吟了一下，道，可能性几乎为0。<|zh|><|NEUTRAL|><|Speech|><|withitn|>这就怪了，除了公主殿下之外，什么还能够令三皇子铤而走险呢？等等。后一宫后一公陈南和小公主一起教导，他们同时醒悟过来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>当日，公主殿下用后裔宫射杀巨蛇之时，金光剑划破长空之际，必是被三皇子看到了，怪不得这个家伙总是漂向我背后的盒子，居然在打我们传国之宝后裔宫的主意，真是该死。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小公主攥紧了小拳头，道，你这个败类到现在还没有想出一条应对之策吗？这也不能怪我啊，巧妇难为无米之炊，公主殿下的侍卫都已身受重伤，现在无可用之兵，我能怎么办？<|zh|><|NEUTRAL|><|Speech|><|withitn|>我看还是将后一宫直接送给三皇子算了。所谓时时务者为，嘿嘿，看到小恶魔公主嘴角露出一丝冷笑，陈南赶忙打住话语，干笑起来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>你这个败类白天还大言不惭，说要和我做交易，到头来却什么也帮不上。嘿嘿，这样也好，我可以毫无顾虑的收拾你了。你不知道这两天我找你有多么辛苦，恨不得立刻扒了你的皮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>看着小公主那邪恶的笑容，陈南不禁打了个冷颤。公主殿下，当初我不是有意偷看你楚狱听到这句话后，小公主的双眼几乎喷出火来了啊，你这个该死的败类，还敢提我杀了你。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 0 | 辰 | 0 | 陈 |
| 001 | different_pronunciation_substitution | substitution | 7 | 的 | 7 | 得 |
| 001 | different_pronunciation_substitution | substitution | 43 | 心 | 43 | 星 |
| 002 | different_pronunciation_substitution | substitution | 51 | 干 | 51 | 杆 |
| 002 | same_pronunciation_substitution | substitution | 75 | 她 | 75 | 他 |
| 002 | different_pronunciation_substitution | substitution | 95 | 侯 | 95 | 候 |
| 003 | same_pronunciation_substitution | substitution | 103 | 她 | 103 | 他 |
| 003 | different_pronunciation_substitution | substitution | 115 | 令 | 115 | 岭 |
| 003 | same_pronunciation_substitution | substitution | 122 | 她 | 122 | 他 |
| 003 | same_pronunciation_substitution | substitution | 136 | 乘 | 136 | 成 |
| 003 | different_pronunciation_substitution | substitution | 138 | 令 | 138 | 岭 |
| 005 | same_pronunciation_substitution | substitution | 226 | 辰 | 226 | 陈 |
| 005 | same_pronunciation_substitution | substitution | 227 | 南 | 227 | 楠 |
| 005 | different_pronunciation_substitution | substitution | 237 | 庆 | 237 | 清 |
| 005 | different_pronunciation_substitution | substitution | 238 | 幸 | 238 | 醒 |
| 006 | same_pronunciation_substitution | substitution | 315 | 辰 | 315 | 陈 |
| 006 | same_pronunciation_substitution | substitution | 316 | 南 | 316 | 楠 |
| 007 | different_pronunciation_substitution | substitution | 345 | 地 | 345 | 的 |
| 007 | same_pronunciation_substitution | substitution | 347 | 辰 | 347 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 348 | 南 | 348 | 楠 |
| 007 | same_pronunciation_substitution | substitution | 357 | 她 | 357 | 他 |
| 007 | same_pronunciation_substitution | substitution | 373 | 辰 | 373 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 374 | 南 | 374 | 楠 |
| 009 | same_pronunciation_substitution | substitution | 448 | 他 | 448 | 她 |
| 009 | same_pronunciation_substitution | substitution | 460 | 乘 | 460 | 成 |
| 009 | same_pronunciation_substitution | substitution | 470 | 他 | 470 | 她 |
| 010 | same_pronunciation_substitution | substitution | 515 | 辰 | 515 | 陈 |
| 010 | different_pronunciation_substitution | substitution | 547 | 地 | 547 | 的 |
| 011 | same_pronunciation_substitution | substitution | 588 | 他 | 588 | 她 |
| 012 | same_pronunciation_substitution | substitution | 642 | 辰 | 642 | 陈 |
| 012 | same_pronunciation_substitution | substitution | 643 | 南 | 643 | 楠 |
| 012 | same_pronunciation_substitution | substitution | 683 | 他 | 683 | 她 |
| 012 | same_pronunciation_substitution | substitution | 696 | 辰 | 696 | 陈 |
| 012 | same_pronunciation_substitution | substitution | 697 | 南 | 697 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 724 | 钰 | 724 | 玉 |
| 013 | same_pronunciation_substitution | substitution | 753 | 辰 | 753 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 754 | 南 | 754 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 762 | 辰 | 762 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 763 | 南 | 763 | 楠 |
| 013 | same_pronunciation_substitution | substitution | 770 | 他 | 770 | 她 |
| 014 | different_pronunciation_substitution | substitution | 794 | 辰 | 794 | 城 |
| 014 | different_pronunciation_substitution | substitution | 804 | 的 | 804 | 得 |
| 014 | same_pronunciation_substitution | substitution | 829 | 乘 | 829 | 成 |
| 015 | same_pronunciation_substitution | substitution | 842 | 辰 | 842 | 陈 |
| 015 | same_pronunciation_substitution | substitution | 843 | 南 | 843 | 楠 |
| 015 | same_pronunciation_substitution | substitution | 882 | 他 | 882 | 她 |
| 016 | same_pronunciation_substitution | substitution | 939 | 辰 | 939 | 陈 |
| 016 | same_pronunciation_substitution | substitution | 940 | 南 | 940 | 楠 |
| 016 | different_pronunciation_substitution | substitution | 946 | 期 | 946 | 其 |
| 019 | same_pronunciation_substitution | substitution | 1064 | 辰 | 1064 | 陈 |
| 019 | different_pronunciation_substitution | substitution | 1120 | 侯 | 1120 | 候 |
| 020 | same_pronunciation_substitution | substitution | 1166 | 辰 | 1166 | 臣 |
| 020 | same_pronunciation_substitution | substitution | 1167 | 南 | 1167 | 楠 |
| 020 | different_pronunciation_substitution | substitution | 1169 | 拜 | 1169 | 白 |
| 020 | different_pronunciation_substitution | substitution | 1171 | 国 | 1171 | 过 |
| 021 | same_pronunciation_substitution | substitution | 1226 | 辰 | 1226 | 陈 |
| 021 | same_pronunciation_substitution | substitution | 1227 | 南 | 1227 | 楠 |
| 021 | same_pronunciation_substitution | substitution | 1228 | 沉 | 1228 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1259 | 辰 | 1259 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1260 | 南 | 1260 | 楠 |
| 022 | same_pronunciation_substitution | substitution | 1270 | 辰 | 1270 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1271 | 南 | 1271 | 楠 |
| 023 | same_pronunciation_substitution | substitution | 1342 | 辰 | 1342 | 臣 |
| 023 | same_pronunciation_substitution | substitution | 1343 | 南 | 1343 | 难 |
| 023 | same_pronunciation_substitution | substitution | 1349 | 他 | 1349 | 她 |
| 024 | same_pronunciation_substitution | substitution | 1367 | 辰 | 1367 | 陈 |
| 024 | same_pronunciation_substitution | substitution | 1370 | 她 | 1370 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1381 | 的 | 1381 | 得 |
| 024 | different_pronunciation_substitution | substitution | 1386 | 冷 | 1386 | 愣 |
| 024 | same_pronunciation_substitution | substitution | 1415 | 她 | 1415 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1436 | 零 | 1436 | 0 |
| 025 | different_pronunciation_substitution | substitution | 1466 | 羿 | 1466 | 一 |
| 025 | same_pronunciation_substitution | substitution | 1467 | 弓 | 1467 | 宫 |
| 025 | different_pronunciation_substitution | substitution | 1469 | 羿 | 1469 | 一 |
| 025 | same_pronunciation_substitution | substitution | 1470 | 弓 | 1470 | 公 |
| 025 | same_pronunciation_substitution | substitution | 1471 | 辰 | 1471 | 陈 |
| 025 | same_pronunciation_substitution | substitution | 1479 | 叫 | 1479 | 教 |
| 025 | different_pronunciation_substitution | substitution | 1480 | 道 | 1480 | 导 |
| 026 | same_pronunciation_substitution | substitution | 1497 | 羿 | 1497 | 裔 |
| 026 | same_pronunciation_substitution | substitution | 1498 | 弓 | 1498 | 宫 |
| 026 | same_pronunciation_substitution | substitution | 1507 | 箭 | 1507 | 剑 |
| 026 | different_pronunciation_substitution | substitution | 1532 | 瞟 | 1532 | 漂 |
| 026 | same_pronunciation_substitution | substitution | 1551 | 羿 | 1551 | 裔 |
| 026 | same_pronunciation_substitution | substitution | 1552 | 弓 | 1552 | 宫 |
| 028 | different_pronunciation_substitution | substitution | 1636 | 羿 | 1636 | 一 |
| 028 | same_pronunciation_substitution | substitution | 1637 | 弓 | 1637 | 宫 |
| 028 | same_pronunciation_substitution | substitution | 1649 | 识 | 1649 | 时 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 辰 | 1671 | 陈 |
| 030 | same_pronunciation_substitution | substitution | 1766 | 辰 | 1766 | 陈 |
| 030 | different_pronunciation_substitution | substitution | 1789 | 出 | 1789 | 楚 |
| 030 | same_pronunciation_substitution | substitution | 1790 | 浴 | 1790 | 狱 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.048740`；字符编辑数：`89`。
- 带声调拼音 CER：`0.016977`；拼音 token 编辑数：`31`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 30 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
陈南将这一切看得清清楚楚暗叹两人不愧出生在勾心斗角的帝王之家短短片刻功夫就已完成了一次星战小公主领着一干身受重伤的侍卫,遇到拜越国的三皇子后,心中颇为不安,她不相信这是巧遇,最大的可能就是对方早已守候在这里。为了自保他先是咄咄逼人地主动出击令三皇子摸不清他的虚实而后又无意间抬出诸葛乘风令三皇子心中颇为忌惮然而三皇子也绝非泛泛之辈他心中虽然惊疑不定但并没有就此退缩而是想一路跟下去静一步探听虚实这两人可以说是满嘴鬼话胡说八道三皇子和小公主两拨人马一起向大山外走去,陈楠走在队伍的后面,暗暗请兴,幸亏三皇子缠住了小公主,使小公主没有注意到她躲在队伍的后面。但好景不长小恶魔手下的侍卫很快发现了他这个被捆绑的俘虏一个侍卫跑上前去对小恶魔耳语了几句在那一刻陈南觉得黑暗笼罩了大地天空失去了色彩小公主满脸兴奋之色,笑嘻嘻地向陈楠走来,毫无疑问,这是她遇到三皇子以来最真实的表情,但是陈楠宁愿看她那虚假的笑容,也不愿见到她此时发自内心的微笑。他在心中高呼地狱的恶魔快把你们的子孙领走开始时散皇子怎么也不明白这个楚国的小公主为何突然兴奋起来他不禁暗暗猜想是不是诸葛乘风已到了不远处后来他随着小公主的目光望去终于发现了令小公主兴奋的根源竟然是前日抓到的那个俘虏三皇子大吃一惊对陈南的身份开始胡乱猜疑起来他咳嗽了一声道这个人在路上一直鬼鬼祟祟地跟在我们后面后来被我的手下抓住了公主殿下认识这个人吗认识当然认识小公主咬牙切齿道,她是从我宫内带出来的小太监,本来是出来伺候我的,没想到遇上远古巨人时,她第一个就跑了,小李子你没想到会这么快见到我吧?陈南简直要晕了居然被人称作太监小公主恶狠狠地盯着他其中的意思再明显不过威胁兼恐吓让他配合人在屋檐下不得不低头陈南犹豫了一下最后无奈地道请公主殿下责罚三皇子笑道,既然是玉公主的奴才,就请殿下自行发落吧,说吧,转身离去,嘿嘿嘿,小公主看着陈南,脸上充满了笑意,陈南身体一阵发寒,他压低声音道,公主殿下,我们做个交易吧。小公主想起先前陈南的那些乌言晦语气得身躯一阵颤抖奸声道和我做交易你凭什么你做梦吧诸葛乘风其实不在三皇子想对付你陈南在小恶魔的手掌落下之前废快地说出了这句话小公主将举起的手掌放了下来滋滋细细将她打量了一遍道看来我真的小看你了没想到你这个臭贼还有几分头脑不过,我现在心中非常不爽,交易延迟,现在我要发泄。啊,临终响起了陈南悲惨的叫声,期间夹杂着小恶魔公主得意的笑声。远处的三皇子等人面面相去对这位传闻中的小魔女有了进一步的认识一轮明月高挂天边皎洁的月光如洁白的羽毛般大片大片地洒在林间夜风袭袭吹来阵阵花草的幽香整片山林笼罩在如水的月光之下远远望去肃淡 朦胧 和谐 宁静比青脸肿的陈楠正在和小恶魔公主在一间帐篷内低声交换意见两人已经确定林间巧遇三皇子等人绝非偶然这一切都是有预谋的这些人早已守候在这条出山的路上小公主道,我一开始就有一种直觉,他们要对我不利,但我不明白他们为什么有这样的动机。陈南道,百岳国和楚国关系如何。小公主道,两国近年来,关系还算可以,没发生过什么不愉快的事情,这就怪了,既然如此,他们为什么要对公主不利呢?陈南沉思了一会儿后,笑了起来,道,我明白了,他们是想在此劫色,去死。小公主对着陈南的头狠狠地捶了一圈陈南吃痛小声叫道我不是正在帮殿下分析吗公主殿下怎么能够这样激动呢再说又不是没有这种可能这方面你就不用考虑了谁都知道这位三皇子不是一个生活糜烂之人陈南道也许也许他想将公主殿下作为一件礼物送给别人听陈南将他比作礼物小恶魔公主气得怒目圆争冷声道你这个败类说话真是太难听了你不知道在和谁说话吗但随后他又迅速冷静了下来沉吟了一下道可能性几乎为零这就怪了,除了公主殿下之外,什么还能够令三皇子铤而走险呢?等等。后一宫,后一宫,陈南和小公主一起教导,他们同时醒悟过来。当日公主殿下用后裔弓射杀巨蛇之时,金光剑划破长空之际,必是被三皇子看到了,怪不得这个家伙总是瞟向我背后的盒子,居然在打我们传国之宝后裔弓的主意,真是该死。小公主攥紧了小拳头道你这个败类到现在还没有想出一条应对之策吗这也不能怪我啊巧妇难为无米之炊公主殿下的侍卫都已身受重伤现在无可用之兵我能怎么办我看还是将后裔宫直接送给三皇子算了所谓诗诗误者为嘿嘿看到小恶魔公主嘴角露出一丝冷笑陈南赶忙打住话语干笑起来你这个白类,白天还大言不惭说要和我做交易,到头来却什么也帮不上,嘿嘿,这样也好,我可以毫无顾虑地收拾你了,你不知道这两天我找你有多么辛苦,恨不得立刻扒了你的皮。看着小公主那邪恶的笑容,陈南不禁打了个冷颤,公主殿下,当初我不是有意偷看你,出狱,听到这句话后,小公主的双眼几乎喷出火来了,啊,你这个该死的败类,还敢提我杀了你。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 0 | 辰 | 0 | 陈 |
| 001 | different_pronunciation_substitution | substitution | 7 | 的 | 7 | 得 |
| 001 | same_pronunciation_substitution | substitution | 34 | 工 | 34 | 功 |
| 001 | different_pronunciation_substitution | substitution | 43 | 心 | 43 | 星 |
| 002 | same_pronunciation_substitution | substitution | 62 | 月 | 62 | 越 |
| 002 | different_pronunciation_substitution | substitution | 95 | 侯 | 95 | 候 |
| 003 | same_pronunciation_substitution | substitution | 103 | 她 | 103 | 他 |
| 003 | different_pronunciation_substitution | substitution | 110 | 的 | 110 | 地 |
| 003 | same_pronunciation_substitution | substitution | 122 | 她 | 122 | 他 |
| 004 | different_pronunciation_substitution | substitution | 185 | 进 | 185 | 静 |
| 005 | same_pronunciation_substitution | substitution | 226 | 辰 | 226 | 陈 |
| 005 | same_pronunciation_substitution | substitution | 227 | 南 | 227 | 楠 |
| 005 | different_pronunciation_substitution | substitution | 237 | 庆 | 237 | 请 |
| 005 | different_pronunciation_substitution | substitution | 238 | 幸 | 238 | 兴 |
| 005 | same_pronunciation_substitution | substitution | 259 | 他 | 259 | 她 |
| 006 | same_pronunciation_substitution | substitution | 315 | 辰 | 315 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 347 | 辰 | 347 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 348 | 南 | 348 | 楠 |
| 007 | same_pronunciation_substitution | substitution | 373 | 辰 | 373 | 陈 |
| 007 | same_pronunciation_substitution | substitution | 374 | 南 | 374 | 楠 |
| 009 | different_pronunciation_substitution | substitution | 423 | 三 | 423 | 散 |
| 010 | same_pronunciation_substitution | substitution | 515 | 辰 | 515 | 陈 |
| 011 | same_pronunciation_substitution | substitution | 588 | 他 | 588 | 她 |
| 011 | same_pronunciation_substitution | substitution | 620 | 他 | 620 | 她 |
| 012 | same_pronunciation_substitution | substitution | 642 | 辰 | 642 | 陈 |
| 012 | different_pronunciation_substitution | substitution | 663 | 的 | 663 | 地 |
| 012 | same_pronunciation_substitution | substitution | 696 | 辰 | 696 | 陈 |
| 012 | different_pronunciation_substitution | substitution | 707 | 的 | 707 | 地 |
| 013 | same_pronunciation_substitution | substitution | 724 | 钰 | 724 | 玉 |
| 013 | different_pronunciation_substitution | substitution | 740 | 罢 | 740 | 吧 |
| 013 | same_pronunciation_substitution | substitution | 753 | 辰 | 753 | 陈 |
| 013 | same_pronunciation_substitution | substitution | 762 | 辰 | 762 | 陈 |
| 014 | same_pronunciation_substitution | substitution | 794 | 辰 | 794 | 陈 |
| 014 | same_pronunciation_substitution | substitution | 799 | 污 | 799 | 乌 |
| 014 | same_pronunciation_substitution | substitution | 801 | 秽 | 801 | 晦 |
| 014 | different_pronunciation_substitution | substitution | 804 | 的 | 804 | 得 |
| 014 | same_pronunciation_substitution | substitution | 811 | 尖 | 811 | 奸 |
| 015 | same_pronunciation_substitution | substitution | 842 | 辰 | 842 | 陈 |
| 015 | different_pronunciation_substitution | substitution | 855 | 飞 | 855 | 废 |
| 015 | different_pronunciation_substitution | substitution | 857 | 的 | 857 | 地 |
| 015 | different_pronunciation_substitution | substitution | 877 | 仔 | 877 | 滋 |
| 015 | different_pronunciation_substitution | substitution | 878 | 仔 | 878 | 滋 |
| 015 | same_pronunciation_substitution | substitution | 882 | 他 | 882 | 她 |
| 016 | same_pronunciation_substitution | substitution | 934 | 林 | 934 | 临 |
| 016 | same_pronunciation_substitution | substitution | 935 | 中 | 935 | 终 |
| 016 | same_pronunciation_substitution | substitution | 939 | 辰 | 939 | 陈 |
| 017 | same_pronunciation_substitution | substitution | 972 | 觑 | 972 | 去 |
| 018 | different_pronunciation_substitution | substitution | 1015 | 的 | 1015 | 地 |
| 018 | same_pronunciation_substitution | substitution | 1022 | 习 | 1022 | 袭 |
| 018 | same_pronunciation_substitution | substitution | 1023 | 习 | 1023 | 袭 |
| 018 | same_pronunciation_substitution | substitution | 1051 | 素 | 1051 | 肃 |
| 019 | different_pronunciation_substitution | substitution | 1059 | 鼻 | 1059 | 比 |
| 019 | same_pronunciation_substitution | substitution | 1064 | 辰 | 1064 | 陈 |
| 019 | same_pronunciation_substitution | substitution | 1065 | 南 | 1065 | 楠 |
| 019 | different_pronunciation_substitution | substitution | 1120 | 侯 | 1120 | 候 |
| 020 | same_pronunciation_substitution | substitution | 1166 | 辰 | 1166 | 陈 |
| 020 | different_pronunciation_substitution | substitution | 1169 | 拜 | 1169 | 百 |
| 020 | same_pronunciation_substitution | substitution | 1170 | 月 | 1170 | 岳 |
| 021 | same_pronunciation_substitution | substitution | 1226 | 辰 | 1226 | 陈 |
| 022 | same_pronunciation_substitution | substitution | 1259 | 辰 | 1259 | 陈 |
| 022 | different_pronunciation_substitution | substitution | 1265 | 的 | 1265 | 地 |
| 022 | different_pronunciation_substitution | substitution | 1269 | 拳 | 1269 | 圈 |
| 022 | same_pronunciation_substitution | substitution | 1270 | 辰 | 1270 | 陈 |
| 023 | same_pronunciation_substitution | substitution | 1342 | 辰 | 1342 | 陈 |
| 024 | same_pronunciation_substitution | substitution | 1367 | 辰 | 1367 | 陈 |
| 024 | same_pronunciation_substitution | substitution | 1370 | 她 | 1370 | 他 |
| 024 | different_pronunciation_substitution | substitution | 1381 | 的 | 1381 | 得 |
| 024 | same_pronunciation_substitution | substitution | 1385 | 睁 | 1385 | 争 |
| 024 | same_pronunciation_substitution | substitution | 1415 | 她 | 1415 | 他 |
| 025 | different_pronunciation_substitution | substitution | 1466 | 羿 | 1466 | 一 |
| 025 | same_pronunciation_substitution | substitution | 1467 | 弓 | 1467 | 宫 |
| 025 | different_pronunciation_substitution | substitution | 1469 | 羿 | 1469 | 一 |
| 025 | same_pronunciation_substitution | substitution | 1470 | 弓 | 1470 | 宫 |
| 025 | same_pronunciation_substitution | substitution | 1471 | 辰 | 1471 | 陈 |
| 025 | same_pronunciation_substitution | substitution | 1479 | 叫 | 1479 | 教 |
| 025 | different_pronunciation_substitution | substitution | 1480 | 道 | 1480 | 导 |
| 026 | same_pronunciation_substitution | substitution | 1497 | 羿 | 1497 | 裔 |
| 026 | same_pronunciation_substitution | substitution | 1507 | 箭 | 1507 | 剑 |
| 026 | same_pronunciation_substitution | substitution | 1551 | 羿 | 1551 | 裔 |
| 028 | same_pronunciation_substitution | substitution | 1636 | 羿 | 1636 | 裔 |
| 028 | same_pronunciation_substitution | substitution | 1637 | 弓 | 1637 | 宫 |
| 028 | different_pronunciation_substitution | substitution | 1649 | 识 | 1649 | 诗 |
| 028 | different_pronunciation_substitution | substitution | 1650 | 时 | 1650 | 诗 |
| 028 | same_pronunciation_substitution | substitution | 1651 | 务 | 1651 | 误 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 辰 | 1671 | 陈 |
| 029 | different_pronunciation_substitution | substitution | 1686 | 败 | 1686 | 白 |
| 029 | different_pronunciation_substitution | substitution | 1725 | 的 | 1725 | 地 |
| 030 | same_pronunciation_substitution | substitution | 1766 | 辰 | 1766 | 陈 |
| 030 | same_pronunciation_substitution | substitution | 1790 | 浴 | 1790 | 狱 |

## 双后端分歧与 ASR 健康门控

### IndexTTS2

- 仅 SenseVoice 报告的错误：34 项。
- 仅 Whisper-large-v3-turbo 报告的错误：41 项。
- 两后端共同报告的错误：44 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。

### VoxCPM2

- 仅 SenseVoice 报告的错误：45 项。
- 仅 Whisper-large-v3-turbo 报告的错误：43 项。
- 两后端共同报告的错误：46 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。
