# SenseVoice CER 与 Whisper-large-v3-turbo CER V8 评价报告

本报告只衡量全文台词保真。唯一参考严格为 `longAudioTestV8/text.md` 中实际参与合成、原始顺序固定的文本。V8 的两条成品均须直接使用 text.md 全文合成；CER 只能使用该文件去除空白和标点后的原始顺序文本，不能使用已删除的 `ai_deal.json`、旧 V8 字符数或其他版本台词。两个模型还必须使用由旁白参考语速、句末标点、段落边界和统一停顿策略冻结的同一份分段清单。

- 规范化规则：`zh-v1`；参考字符数：`2537`。
- 共享分段清单：42 段；按旁白参考语速估算，目标片段 `25` 秒、最大 `35` 秒。
- 评测单元：每条完整 `audio_*.wav` 成品。Task 8 使用与最终 WAV 哈希绑定的逐段合成证据；ASR 按语义段独立转写后汇总全文 CER，不使用固定时间窗口。
- 原始证据：[task8_evaluation_results.json](task-V8-evidence-20260729T144419Z/task8_evaluation_results.json)。
- 两个后端独立排名，绝不平均为综合分；ASR 健康门控不通过的后端保留原始值，但不参与对应名次。

## 双后端全文 CER 与独立名次

| 模型 | SenseVoice 严格 CER | SenseVoice 名次 | Whisper-large-v3-turbo 严格 CER | Whisper-large-v3-turbo 名次 | 差值（Whisper - SenseVoice） |
| --- | ---: | ---: | ---: | ---: | ---: |
| IndexTTS2 | 0.037052 | 1 | 0.030351 | 1 | -0.006701 |
| VoxCPM2 | 0.038628 | 2 | 0.037052 | 2 | -0.001577 |

## 完整转写与字符错误位置

### IndexTTS2

#### SenseVoice

- 严格汉字 CER：`0.037052`；字符编辑数：`94`。
- 带声调拼音 CER：`0.012219`；拼音 token 编辑数：`31`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 42 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
基督啊，我自言自语道，第一片雪花开始飘落，他们糊成毛茸茸的一团附在挡风玻璃上，又被雨刷抹去。我已经在姐姐家的车道上等了15不20分钟了。要是刚才选择进屋陪他等，这会儿估计已经被他那两只灰色的猫送去见上帝了。可爱的小恶魔，但对我的鼻窦来说，就是致命毒药，眼睛浮肿，喉咙堵塞，正是我最不需要的。每年圣诞节，我们家都会长途跋涉，去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋。我本想赶在预报的那场大雪之前到达。但姐姐的驾照因为酒驾被吊销了，于是我成了时间的俘虏，手指焦躁的敲着方向盘。当初妈妈让我来接姐姐时，我心里就100个不情愿，不是我们彼此憎恨，只是没那么亲近了。几十年无休止的争吵和激烈的分歧之后，我们渐渐疏远，关系也随之冷却。没错，我们是手足，但说我们是手足残留下的余烬，恐怕更贴切。终于向瓦尔哈拉的大门敞开一般，他的前门开了，他走了出来，头发是森林绿的。上次我见他时还是白色，再上次是紫罗兰色，都戴齐了吗？他笨手笨脚的爬进副驾驶座时，我问道。嗯，他应了一声，扶了扶眼镜，把几个袋子扔到后座。就这样我们出发了。霍普镇大约30分钟车程，车里的尴尬沉没没多久就膨胀开来。收音机坏了，辅助插口也断掉了，放起音乐活像在癫痫发作，这显然没有任何帮助。等我们拐上霍浦公路的岔道时，路面已经铺成厚厚一层白毯。好在平安夜的晚上，通往霍普小镇那长长一段路空旷又安静，小木屋藏在主路5英里外的一片密林堡垒中。我转弯时，姐姐摇下车窗，掏出一根大麻烟卷，用打火机点燃，来一口。他问，车轮碾过雪地，嘎吱作响，开车的时候不行，直路一条，我们差不多到了。他吸了一口，朝窗外吐出一团烟雾，我只想专心开车，行吗？他哼了一声，推了推眼镜。你要真那么紧张，不如开慢点来了那一次一块引我上钩的饵，但我这次不咬钩，他想让我们更快到达，由他想去吧。车程快结束了，马上我就能坐在温暖的客厅里翘起脚，手里端着一杯加了烈酒的淡奶酒，耳边响起包庇赫尔姆斯的铃铛摇滚。我甚至已经能想象杰德叔叔又甩出他那恶俗笑话。圣诞老人为什么有那么大的哥们儿姐姐尖叫起来，手指戳在我腰上，把我的思绪猛的拽回挡风玻璃前。车子刚刚绕过那条茂密的小径，一头驯鹿庞大的身躯挡在我们正前方，眼睛圆睁，空洞无神。即便高光树灯照上去也纹丝不动。惊慌之下，我猛打方向盘，拼命向避开。车子滑溜溜的侧偏过去，溅起一片碎雪泥，那头驯鹿，也就是北美驯鹿，依然一动不动。保险杠从他鼻子前几英寸的地方呼啸而过。我们在主路外的一侧嘎吱一声刹住。天哪，我松了口气，庆幸不已，撞到了吗？没有姐姐说着探出车窗，看了一眼，又吐出一口烟。我把方向盘打正，踩下油门，车轮在原地尖笑，甩起一团团冰渣，却纹丝不动，完美。我呻吟着从座椅上把自己拆下来，下车查看两个前轮裹满了黑乎乎的泥血，几乎被积雪吞没。我踢了几脚，想把轮纹和轮拱下的冰渣弄掉，体累了，只好用手指去刮。滚远点普兰色，我听见姐姐朝那头驯鹿的黑影喊道，她的鹿角像扭曲的手指伸向树梢。接着，他发出一声短促的惊呼，然后是一句，什么鬼，我从积雪中抬起头来。那头驯鹿现在正用两条后腿直立着，看起来怪怪的，像童书里那种滑稽的拟人化形象。但在寂静的树林里，这画面令人毛骨悚然。他那模糊的身形仅凭两条腿站立，竟保持着近乎人类的平衡。不知为何，我这才注意到他没有尾巴。他肌肉发达的脖子扭向一侧，发出一声悠长的尖叫，金属碾膜，金属的惨烈哀嚎。我的双腿像冰雕一样，把我定在原地，那尖叫渐渐化作一连串湿漉漉的咕噜声。驯鹿落回原来的姿态，重重的跺着地面，一团团白气和几缕鼻涕从他的鼻孔里喷出来。我不是猎人，但被激怒的动物要冲过来了。这点常识我还是有的。我扑向驾驶座，拉开车门，砰的关上。与此同时，蹄子沉闷的撞击声已经追到我身边，鹿脚刮过车门，他庞大的身躯几乎擦着我刚才站过的那片地飞掠而过，快太快了。姐姐尖叫起来，那头硕大的鸣人转身又冲了回来，这次撞碎了前大灯，把我们吞没在黑暗中。快走啊，姐姐在我耳边吼道，我在世，该死的，我嘶声说，车轮继续无助的空转。我们被困住了，那东西再次冲撞，这次正中车窗，姐姐脑袋旁边绽开一片蛛网般的裂纹，我拼命搜寻任何任何能当武器的东西。我从来不是什么枪械爱好者，但在那一刻，如果手里能有一把格洛克，我愿意剃光头发，加入世俗僧侣团。那驯鹿又撞击了车身一次，终于像是失去了兴趣，消失在树丛之间。暂时有了喘息和思考的时间，我们给爸爸打了电话，告诉他情况，他会开着他的皮卡过来，帮我们把车弄出来，摆脱这团乱码。我转头看向姐姐，他正把手指捂在脸上，缓慢而平稳的呼吸着，你还好吗？我问你说呢，他嘟囔道，我让你开慢点，又是一次，这次我不打算人了。你想帮上忙，我吼道，那就下去推车。不想，那就他妈闭嘴，我不需要这个，他不再说话，我也不再开口重新陷入那种沉默。我们的关系早已沦落至此，但愿爸爸的车灯早点在远处亮起，忽然他摇下了车窗，你干什么？我问嘘他抿起嘴唇，仔细听，我姑且配合他等了等。果然，我也听到了那个声音，外面传来一个小女孩的轻柔的嗓音，有人吗？他呜咽着，我迷路了，请帮帮我，我迷路了。姐姐解开车锁，伸手要开门，我一把抓住她的手腕，你干什么？她厉声道，外面有人，等一下，这不对劲，不是吗？那声音继续哀泣着，在啜气和哀求之间哽咽，求任何人帮帮她。我不喜欢那声音的质感，同样的脱腔，同样的哭诉，就像有人在反复播放一段录音。不对劲，我的直觉在各个方向竖起红旗，然后姐姐看向我，他的表情骤然扭曲成惊骇。他猛的往后一缩，双肩紧贴车内饰，一些像瓷具的东西从他喉咙里冒出来，却没能成形。我转过身看见了正盯着我的东西，他长着一张男人的脸，嵌在斑驳的驯鹿皮毛之间。皮肤是木乃伊般的褐色，像老旧皱缩的皮革一般，紧紧裹在他修长的头骨上，雪花落在他那双大而空洞的眼睛上，融化进瞳孔暗色的魔种。他绕着车子踱步，晃动鹿角，往车窗上呵气，向内窥视。我的心撞击着喉咙的臂，我和姐姐四目相对，在彻底的不可置信中，一个字也说不出来。我本该抓起手机，拍张照，录段视频。什么都好，但我的思绪乱作一团。紧接着，他再次发出那声可怕的尖叫，但我没看见他紧闭扭曲的嘴唇张开，声音是从他脖子里传来的。小小的肉质的孔洞像嘴巴一样拖动着，把那高亢的尖笑转变成模仿的小女孩哭喊，帮帮我，我迷路了，帮帮我，车灯照亮了整个区域，爸爸的皮卡出现了，沿着小路驶来。那头驯鹿管他他妈的是什么，跑了，再次消失在白雪覆盖的密林里，没有人相信我们怎么会呢？如果有人跟我讲这个故事，我也会以为他们磕了某种迷幻药。但我亲眼所见的现实是冰冷的，至今我仍无法完全咽下。那一夜，我和姐姐没有睡觉，而是查了一些资料，最终找到了关于琵行者的传说。某种存在能模仿声音，伪装成动物，将人诱入林中。读完其他目集记录后，我毫不怀疑我们那晚目睹了什么。那天夜里，我不时望向窗外扫视院子，想着会不会看见那张皮革式的脸，从竖线边注视着我。我和姐姐再也没有去过那趟旅行，这让家人们很是恼火，但乌云背后总有一线光明。我们俩从未像现在这样亲近过。
```

原始转写（仅移除 SenseVoice 控制标记后才计算 CER；此处保留以供复核）：

```text
<|zh|><|HAPPY|><|Speech|><|withitn|>基督啊，我自言自语道，第一片雪花开始飘落，他们糊成毛茸茸的一团附在挡风玻璃上，又被雨刷抹去。我已经在姐姐家的车道上等了15不20分钟了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>要是刚才选择进屋陪他等，这会儿估计已经被他那两只灰色的猫送去见上帝了。可爱的小恶魔，但对我的鼻窦来说，就是致命毒药，眼睛浮肿，喉咙堵塞，正是我最不需要的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>每年圣诞节，我们家都会长途跋涉，去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋。我本想赶在预报的那场大雪之前到达。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但姐姐的驾照因为酒驾被吊销了，于是我成了时间的俘虏，手指焦躁的敲着方向盘。当初妈妈让我来接姐姐时，我心里就100个不情愿，不是我们彼此憎恨，只是没那么亲近了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>几十年无休止的争吵和激烈的分歧之后，我们渐渐疏远，关系也随之冷却。没错，我们是手足，但说我们是手足残留下的余烬，恐怕更贴切。<|zh|><|NEUTRAL|><|Speech|><|withitn|>终于向瓦尔哈拉的大门敞开一般，他的前门开了，他走了出来，头发是森林绿的。上次我见他时还是白色，再上次是紫罗兰色，都戴齐了吗？他笨手笨脚的爬进副驾驶座时，我问道。<|zh|><|NEUTRAL|><|Speech|><|withitn|>嗯，他应了一声，扶了扶眼镜，把几个袋子扔到后座。就这样我们出发了。霍普镇大约30分钟车程，车里的尴尬沉没没多久就膨胀开来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>收音机坏了，辅助插口也断掉了，放起音乐活像在癫痫发作，这显然没有任何帮助。等我们拐上霍浦公路的岔道时，路面已经铺成厚厚一层白毯。<|zh|><|NEUTRAL|><|Speech|><|withitn|>好在平安夜的晚上，通往霍普小镇那长长一段路空旷又安静，小木屋藏在主路5英里外的一片密林堡垒中。我转弯时，姐姐摇下车窗，掏出一根大麻烟卷，用打火机点燃，来一口。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他问，车轮碾过雪地，嘎吱作响，开车的时候不行，直路一条，我们差不多到了。他吸了一口，朝窗外吐出一团烟雾，我只想专心开车，行吗？他哼了一声，推了推眼镜。<|zh|><|NEUTRAL|><|Speech|><|withitn|>你要真那么紧张，不如开慢点来了那一次一块引我上钩的饵，但我这次不咬钩，他想让我们更快到达，由他想去吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车程快结束了，马上我就能坐在温暖的客厅里翘起脚，手里端着一杯加了烈酒的淡奶酒，耳边响起包庇赫尔姆斯的铃铛摇滚。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我甚至已经能想象杰德叔叔又甩出他那恶俗笑话。圣诞老人为什么有那么大的哥们儿姐姐尖叫起来，手指戳在我腰上，把我的思绪猛的拽回挡风玻璃前。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车子刚刚绕过那条茂密的小径，一头驯鹿庞大的身躯挡在我们正前方，眼睛圆睁，空洞无神。即便高光树灯照上去也纹丝不动。惊慌之下，我猛打方向盘，拼命向避开。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车子滑溜溜的侧偏过去，溅起一片碎雪泥，那头驯鹿，也就是北美驯鹿，依然一动不动。保险杠从他鼻子前几英寸的地方呼啸而过。我们在主路外的一侧嘎吱一声刹住。<|zh|><|NEUTRAL|><|Speech|><|withitn|>天哪，我松了口气，庆幸不已，撞到了吗？没有姐姐说着探出车窗，看了一眼，又吐出一口烟。我把方向盘打正，踩下油门，车轮在原地尖笑，甩起一团团冰渣，却纹丝不动，完美。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我呻吟着从座椅上把自己拆下来，下车查看两个前轮裹满了黑乎乎的泥血，几乎被积雪吞没。我踢了几脚，想把轮纹和轮拱下的冰渣弄掉，体累了，只好用手指去刮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>滚远点普兰色，我听见姐姐朝那头驯鹿的黑影喊道，她的鹿角像扭曲的手指伸向树梢。接着，他发出一声短促的惊呼，然后是一句，什么鬼，我从积雪中抬起头来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>那头驯鹿现在正用两条后腿直立着，看起来怪怪的，像童书里那种滑稽的拟人化形象。但在寂静的树林里，这画面令人毛骨悚然。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他那模糊的身形仅凭两条腿站立，竟保持着近乎人类的平衡。不知为何，我这才注意到他没有尾巴。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他肌肉发达的脖子扭向一侧，发出一声悠长的尖叫，金属碾膜，金属的惨烈哀嚎。我的双腿像冰雕一样，把我定在原地，那尖叫渐渐化作一连串湿漉漉的咕噜声。<|zh|><|NEUTRAL|><|Speech|><|withitn|>驯鹿落回原来的姿态，重重的跺着地面，一团团白气和几缕鼻涕从他的鼻孔里喷出来。我不是猎人，但被激怒的动物要冲过来了。这点常识我还是有的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我扑向驾驶座，拉开车门，砰的关上。与此同时，蹄子沉闷的撞击声已经追到我身边，鹿脚刮过车门，他庞大的身躯几乎擦着我刚才站过的那片地飞掠而过，快太快了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>姐姐尖叫起来，那头硕大的鸣人转身又冲了回来，这次撞碎了前大灯，把我们吞没在黑暗中。快走啊，姐姐在我耳边吼道，我在世，该死的，我嘶声说，车轮继续无助的空转。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我们被困住了，那东西再次冲撞，这次正中车窗，姐姐脑袋旁边绽开一片蛛网般的裂纹，我拼命搜寻任何任何能当武器的东西。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我从来不是什么枪械爱好者，但在那一刻，如果手里能有一把格洛克，我愿意剃光头发，加入世俗僧侣团。那驯鹿又撞击了车身一次，终于像是失去了兴趣，消失在树丛之间。<|zh|><|NEUTRAL|><|Speech|><|withitn|>暂时有了喘息和思考的时间，我们给爸爸打了电话，告诉他情况，他会开着他的皮卡过来，帮我们把车弄出来，摆脱这团乱码。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我转头看向姐姐，他正把手指捂在脸上，缓慢而平稳的呼吸着，你还好吗？我问你说呢，他嘟囔道，我让你开慢点，又是一次，这次我不打算人了。你想帮上忙，我吼道，那就下去推车。<|zh|><|NEUTRAL|><|Speech|><|withitn|>不想，那就他妈闭嘴，我不需要这个，他不再说话，我也不再开口重新陷入那种沉默。我们的关系早已沦落至此，但愿爸爸的车灯早点在远处亮起，忽然他摇下了车窗，你干什么？<|zh|><|NEUTRAL|><|Speech|><|withitn|>我问嘘他抿起嘴唇，仔细听，我姑且配合他等了等。果然，我也听到了那个声音，外面传来一个小女孩的轻柔的嗓音，有人吗？他呜咽着，我迷路了，请帮帮我，我迷路了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>姐姐解开车锁，伸手要开门，我一把抓住她的手腕，你干什么？她厉声道，外面有人，等一下，这不对劲，不是吗？那声音继续哀泣着，在啜气和哀求之间哽咽，求任何人帮帮她。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我不喜欢那声音的质感，同样的脱腔，同样的哭诉，就像有人在反复播放一段录音。不对劲，我的直觉在各个方向竖起红旗，然后姐姐看向我，他的表情骤然扭曲成惊骇。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他猛的往后一缩，双肩紧贴车内饰，一些像瓷具的东西从他喉咙里冒出来，却没能成形。我转过身看见了正盯着我的东西，他长着一张男人的脸，嵌在斑驳的驯鹿皮毛之间。<|zh|><|NEUTRAL|><|Speech|><|withitn|>皮肤是木乃伊般的褐色，像老旧皱缩的皮革一般，紧紧裹在他修长的头骨上，雪花落在他那双大而空洞的眼睛上，融化进瞳孔暗色的魔种。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他绕着车子踱步，晃动鹿角，往车窗上呵气，向内窥视。我的心撞击着喉咙的臂，我和姐姐四目相对，在彻底的不可置信中，一个字也说不出来。我本该抓起手机，拍张照，录段视频。<|zh|><|NEUTRAL|><|Speech|><|withitn|>什么都好，但我的思绪乱作一团。紧接着，他再次发出那声可怕的尖叫，但我没看见他紧闭扭曲的嘴唇张开，声音是从他脖子里传来的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小小的肉质的孔洞像嘴巴一样拖动着，把那高亢的尖笑转变成模仿的小女孩哭喊，帮帮我，我迷路了，帮帮我，车灯照亮了整个区域，爸爸的皮卡出现了，沿着小路驶来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>那头驯鹿管他他妈的是什么，跑了，再次消失在白雪覆盖的密林里，没有人相信我们怎么会呢？如果有人跟我讲这个故事，我也会以为他们磕了某种迷幻药。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但我亲眼所见的现实是冰冷的，至今我仍无法完全咽下。<|zh|><|NEUTRAL|><|Speech|><|withitn|>那一夜，我和姐姐没有睡觉，而是查了一些资料，最终找到了关于琵行者的传说。某种存在能模仿声音，伪装成动物，将人诱入林中。<|zh|><|NEUTRAL|><|Speech|><|withitn|>读完其他目集记录后，我毫不怀疑我们那晚目睹了什么。那天夜里，我不时望向窗外扫视院子，想着会不会看见那张皮革式的脸，从竖线边注视着我。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我和姐姐再也没有去过那趟旅行，这让家人们很是恼火，但乌云背后总有一线光明。我们俩从未像现在这样亲近过。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 18 | 它 | 18 | 他 |
| 001 | same_pronunciation_substitution | substitution | 28 | 覆 | 28 | 附 |
| 001 | different_pronunciation_substitution | substitution | 54 | 十 | 54 | 1 |
| 001 | different_pronunciation_substitution | substitution | 55 | 五 | 55 | 5 |
| 001 | different_pronunciation_substitution | substitution | 57 | 二 | 57 | 2 |
| 001 | different_pronunciation_substitution | substitution | 58 | 十 | 58 | 0 |
| 002 | same_pronunciation_substitution | substitution | 71 | 她 | 71 | 他 |
| 002 | same_pronunciation_substitution | substitution | 81 | 她 | 81 | 他 |
| 004 | different_pronunciation_substitution | substitution | 212 | 地 | 212 | 的 |
| 004 | insertion | insertion | 233 | ∅ | 233 | 1 |
| 004 | different_pronunciation_substitution | substitution | 233 | 一 | 234 | 0 |
| 004 | different_pronunciation_substitution | substitution | 234 | 百 | 235 | 0 |
| 006 | same_pronunciation_substitution | substitution | 312 | 像 | 313 | 向 |
| 006 | same_pronunciation_substitution | substitution | 324 | 她 | 325 | 他 |
| 006 | same_pronunciation_substitution | substitution | 330 | 她 | 331 | 他 |
| 006 | same_pronunciation_substitution | substitution | 346 | 她 | 347 | 他 |
| 006 | same_pronunciation_substitution | substitution | 361 | 带 | 362 | 戴 |
| 006 | same_pronunciation_substitution | substitution | 365 | 她 | 366 | 他 |
| 006 | different_pronunciation_substitution | substitution | 370 | 地 | 371 | 的 |
| 007 | same_pronunciation_substitution | substitution | 382 | 她 | 383 | 他 |
| 007 | different_pronunciation_substitution | substitution | 414 | 三 | 415 | 3 |
| 007 | different_pronunciation_substitution | substitution | 415 | 十 | 416 | 0 |
| 007 | different_pronunciation_substitution | substitution | 426 | 默 | 427 | 没 |
| 008 | same_pronunciation_substitution | substitution | 474 | 普 | 475 | 浦 |
| 009 | different_pronunciation_substitution | substitution | 525 | 五 | 526 | 5 |
| 010 | same_pronunciation_substitution | substitution | 564 | 她 | 565 | 他 |
| 010 | same_pronunciation_substitution | substitution | 594 | 她 | 595 | 他 |
| 010 | same_pronunciation_substitution | substitution | 617 | 她 | 618 | 他 |
| 011 | same_pronunciation_substitution | substitution | 643 | 刺 | 644 | 次 |
| 011 | same_pronunciation_substitution | substitution | 659 | 她 | 660 | 他 |
| 011 | same_pronunciation_substitution | substitution | 669 | 她 | 670 | 他 |
| 012 | same_pronunciation_substitution | substitution | 706 | 蛋 | 707 | 淡 |
| 012 | different_pronunciation_substitution | substitution | 713 | 鲍 | 714 | 包 |
| 012 | different_pronunciation_substitution | substitution | 714 | 比 | 715 | 庇 |
| 013 | different_pronunciation_substitution | substitution | 779 | 地 | 780 | 的 |
| 014 | same_pronunciation_substitution | substitution | 828 | 束 | 829 | 树 |
| 014 | different_pronunciation_substitution | substitution | 850 | 想 | 851 | 向 |
| 015 | different_pronunciation_substitution | substitution | 858 | 地 | 859 | 的 |
| 015 | same_pronunciation_substitution | substitution | 891 | 它 | 892 | 他 |
| 016 | same_pronunciation_substitution | substitution | 972 | 啸 | 973 | 笑 |
| 017 | different_pronunciation_substitution | substitution | 1017 | 雪 | 1018 | 血 |
| 017 | different_pronunciation_substitution | substitution | 1043 | 踢 | 1044 | 体 |
| 018 | same_pronunciation_substitution | substitution | 1058 | 瑟 | 1059 | 色 |
| 018 | same_pronunciation_substitution | substitution | 1074 | 它 | 1075 | 她 |
| 018 | same_pronunciation_substitution | substitution | 1090 | 她 | 1091 | 他 |
| 020 | same_pronunciation_substitution | substitution | 1169 | 它 | 1170 | 他 |
| 020 | same_pronunciation_substitution | substitution | 1204 | 它 | 1205 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1209 | 它 | 1210 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1233 | 磨 | 1234 | 膜 |
| 021 | different_pronunciation_substitution | substitution | 1252 | 钉 | 1253 | 定 |
| 022 | different_pronunciation_substitution | substitution | 1284 | 地 | 1285 | 的 |
| 022 | same_pronunciation_substitution | substitution | 1300 | 它 | 1301 | 他 |
| 023 | different_pronunciation_substitution | substitution | 1345 | 地 | 1346 | 的 |
| 023 | same_pronunciation_substitution | substitution | 1368 | 角 | 1369 | 脚 |
| 023 | same_pronunciation_substitution | substitution | 1373 | 它 | 1374 | 他 |
| 024 | same_pronunciation_substitution | substitution | 1411 | 名 | 1412 | 鸣 |
| 024 | same_pronunciation_substitution | substitution | 1450 | 试 | 1451 | 世 |
| 024 | different_pronunciation_substitution | substitution | 1464 | 地 | 1465 | 的 |
| 027 | different_pronunciation_substitution | substitution | 1636 | 麻 | 1637 | 码 |
| 028 | same_pronunciation_substitution | substitution | 1644 | 她 | 1645 | 他 |
| 028 | different_pronunciation_substitution | substitution | 1658 | 地 | 1659 | 的 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 她 | 1672 | 他 |
| 028 | same_pronunciation_substitution | substitution | 1684 | 刺 | 1685 | 次 |
| 028 | different_pronunciation_substitution | substitution | 1691 | 忍 | 1692 | 人 |
| 029 | same_pronunciation_substitution | substitution | 1721 | 她 | 1722 | 他 |
| 029 | same_pronunciation_substitution | substitution | 1767 | 她 | 1768 | 他 |
| 030 | same_pronunciation_substitution | substitution | 1780 | 她 | 1781 | 他 |
| 030 | same_pronunciation_substitution | substitution | 1793 | 她 | 1794 | 他 |
| 030 | same_pronunciation_substitution | substitution | 1826 | 它 | 1827 | 他 |
| 031 | same_pronunciation_substitution | substitution | 1894 | 泣 | 1895 | 气 |
| 032 | same_pronunciation_substitution | substitution | 1922 | 拖 | 1923 | 脱 |
| 032 | same_pronunciation_substitution | substitution | 1965 | 她 | 1966 | 他 |
| 033 | same_pronunciation_substitution | substitution | 1976 | 她 | 1977 | 他 |
| 033 | different_pronunciation_substitution | substitution | 1978 | 地 | 1979 | 的 |
| 033 | same_pronunciation_substitution | substitution | 1993 | 词 | 1994 | 瓷 |
| 033 | same_pronunciation_substitution | substitution | 1994 | 句 | 1995 | 具 |
| 033 | same_pronunciation_substitution | substitution | 1999 | 她 | 2000 | 他 |
| 033 | same_pronunciation_substitution | substitution | 2025 | 它 | 2026 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2069 | 它 | 2070 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2080 | 它 | 2081 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2099 | 膜 | 2100 | 魔 |
| 034 | different_pronunciation_substitution | substitution | 2100 | 中 | 2101 | 种 |
| 035 | same_pronunciation_substitution | substitution | 2101 | 它 | 2102 | 他 |
| 035 | same_pronunciation_substitution | substitution | 2131 | 壁 | 2132 | 臂 |
| 036 | same_pronunciation_substitution | substitution | 2187 | 它 | 2188 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2204 | 它 | 2205 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2218 | 它 | 2219 | 他 |
| 037 | different_pronunciation_substitution | substitution | 2238 | 翕 | 2239 | 拖 |
| 037 | same_pronunciation_substitution | substitution | 2247 | 啸 | 2248 | 笑 |
| 038 | same_pronunciation_substitution | substitution | 2297 | 它 | 2298 | 他 |
| 040 | same_pronunciation_substitution | substitution | 2404 | 皮 | 2405 | 琵 |
| 041 | different_pronunciation_substitution | substitution | 2435 | 击 | 2436 | 集 |
| 041 | same_pronunciation_substitution | substitution | 2479 | 似 | 2480 | 式 |
| 041 | same_pronunciation_substitution | substitution | 2483 | 树 | 2484 | 竖 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.030351`；字符编辑数：`77`。
- 带声调拼音 CER：`0.006307`；拼音 token 编辑数：`16`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 42 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
基督啊我自言自语道第一片雪花开始飘落它们糊成毛茸茸的一团附在挡风玻璃上又被雨刷抹去我已经在姐姐家的车道上等了十五不二十分钟了要是刚才选择进屋陪她等,这会儿估计已经被她那两只灰色的猫送去见上帝了。可爱的小恶魔,但对我的鼻痘来说就是致命毒药,眼睛浮肿,喉咙堵塞,正是我最不需要的。每年圣诞节,我们家都会长途跋涉,去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋,我本想赶在预报的那场大雪之前到达。但姐姐的驾照因为酒驾被吊销了,于是我成了时间的俘虏,手指焦躁地敲着方向盘。当初妈妈让我来接姐姐时,我心里就一百个不情愿,不是我们彼此憎恨,只是没那么亲近了。几十年无休止的争吵和激烈的分歧之后,我们渐渐疏远,关系也随之冷却。没错,我们是手足,但说我们是手足残留下的余劲,恐怕更贴切。终于像瓦尔哈拉的大门敞开一般,他的前门开了,他走了出来,头发是森林绿的,上次我见他时还是白色,再上次是紫罗蓝色,都带齐了吗?他笨手笨脚地爬进副驾驶座时,我问道,嗯,他应了一声,扶了扶眼镜,把几个带子扔到后座。就这样,我们出发了。霍普镇大约三十分钟车程,车里的尴尬沉默没多久就膨胀开来。收音机坏了辅助插口也断掉了放弃音乐活像在滇弦发作这显然没有任何帮助等我们拐上霍普公路的岔道时路面已经铺成厚厚一层白毯好在平安夜的晚上,通往霍普小镇那长长一段,路空旷又安静,小木屋藏在主路五英里外的一片密林堡垒中。我转弯时,姐姐摇下车窗,掏出一根大麻烟卷,用打火机点燃,来一口。他问,车轮碾过雪地,嘎吱作响,开车的时候不行,直路一条,我们差不多到了,他吸了一口,朝窗外吐出一团烟雾,我只想专心开车,行吗?他哼了一声,推了推眼镜。你要真那么紧张,不如开慢点,来了那一次一块引我上钩的耳,但我这次不咬钩,它想让我们更快到达,由它想去吧。车程快结束了,马上我就能坐在温暖的客厅里,翘起脚,手里端着一杯加了烈酒的淡奶酒,耳边响起包庇赫尔姆斯的铃铛摇滚。我甚至已经能想象杰德叔叔又甩出他那恶俗笑话,圣诞老人为什么有那么大的,哥们儿,姐姐尖叫起来,手指戳在我腰上,把我的思绪猛地拽回挡风玻璃前。车子刚刚绕过那条茂密的小径,一头驯鹿庞大的身躯挡在我们正前方,眼睛圆睁,空洞无神,即便高光束灯照上去,也纹丝不动,惊慌之下,我猛打方向盘,拼命想避开。车子滑溜溜地侧偏过去,溅起一片碎血泥,那头驯鹿也就是北美驯鹿,依然一动不动,保险杠从它鼻子前几英寸的地方呼啸而过,我们在主路外的一侧嘎吱一声杀猪。天呐,我松了口气,庆幸不已,撞到了吗?没有。姐姐说着探出车窗看了一眼,又吐出一口烟。我把方向盘打正,踩下油门,车轮在原地尖笑,甩起一团团冰渣,却纹丝不动,完美。我呻吟着,从座椅上把自己拆下来,下车查看,两个前轮裹满了黑乎乎的泥血,几乎被积雪吞没,我踢了几脚,想把轮纹和轮拱下的冰渣弄掉,提累了,只好用手指去刮。滚远点,普兰瑟,我听见姐姐朝那头驯鹿的黑影喊道,她的鹿角像扭曲的手指伸向树梢,接着她发出一声短促的惊呼,然后是一句,什么鬼,我从积雪中抬起头来。那头驯鹿现在正用两条后腿直立着,看起来怪怪的,像童书里那种滑稽的拟人画形象,但在寂静的树林里,这画面令人毛骨悚然。他那模糊的身形仅凭两条腿站立竟保持着近乎人类的平衡不知为何我这才注意到他没有尾巴他肌肉发达的脖子扭向一侧发出一声悠长的尖叫金属碾磨金属的惨烈哀号我的双腿像冰雕一样把我钉在原地那尖叫渐渐化作一连串湿漉漉的咕噜声驯鹿落回原来的姿态,重重地跺着地面,一团团白气和几缕鼻涕从它的鼻孔里喷出来,我不是猎人,但被激怒的动物要冲过来了,这点常识我还是有的。我扑向驾驶座,拉开车门,砰地关上,与此同时蹄子沉闷的撞击声已经追到我身边,路角刮过车门,它庞大的身躯几乎擦着我刚才站过的那片地飞掠而过,快,太快了。姐姐尖叫起来,那头硕大的名人转身又冲了回来,这次撞碎了前大灯,把我们吞没在黑暗中。快走啊,姐姐在我耳边吼道,我在世,该死的。我嘶声说,车轮继续无助地空转。我们被困住了,那东西再次冲撞,这次正中车窗,姐姐脑袋旁边展开一片珠网般的裂纹,我拼命搜寻任何,任何能当武器的东西。我从来不是什么枪械爱好者,但在那一刻,如果手里能有一把格洛克,我愿意剃光头发,加入世俗僧侣团,那驯鹿又撞击了车身一次,终于像是失去了兴趣,消失在树丛之间。暂时有了喘息和思考的时间,我们给爸爸打了电话告诉他情况,他会开着他的皮卡过来,帮我们把车弄出来,摆脱这团乱马。我转头看向姐姐,她正把手指捂在脸上,缓慢而平稳地呼吸着。你还好吗?我问。你说呢?她嘟囔道。我让你开慢点,又是一次,这次我不打算忍了,你想帮上忙。我吼道,那就下去推车。不想,那就他妈闭嘴,我不需要这个,他不再说话,我也不再开口重新陷入那种沉默。我们的关系早已沦落至此,但愿爸爸的车灯早点在远处亮起,忽然他摇下了车窗,你干什么?我问,嘘,她眯起嘴唇,仔细听我姑且配合她,等了等,果然我也听到了那个声音,外面传来一个小女孩的轻柔的嗓音。有人吗?她呜咽着,我迷路了,请帮帮我,我迷路了。姐姐解开车所,伸手要开门,我一把抓住她的手腕,你干什么?她立声道,外面有人,等一下,这不对劲不是吗?那声音继续哀气着,在啜泣和哀求之间哽咽,求任何人帮帮她。我不喜欢那声音的质感,同样的拖枪,同样的哭诉,就像有人在反复播放一段录音,不对劲,我的直觉在各个方向竖起红旗,然后姐姐看向我,她的表情骤然扭曲成惊骇。他猛地往后一缩,双肩紧贴车内饰,一些像磁具的东西从他喉咙里冒出来,却没能成形。我转过身,看见了正盯着我的东西,他长着一张男人的脸,嵌在斑驳的驯鹿皮毛之间。皮肤是木乃伊般的褐色,像老旧皱缩的皮革一般紧紧裹在她修长的头骨上,雪花落在她那双大而空洞的眼睛上,融化进瞳孔暗色的魔种。她绕着车子踱步,晃动路脚,往车窗上喝气,向内窥视。我的心撞击着喉咙的壁,我和姐姐四目相对,在彻底的不可置信中一个字也说不出来。我本该抓起手机,拍张照,录断视频。什么都好,但我的思绪乱作一团,紧接着他再次发出那声可怕的尖叫,但我没看见他紧闭扭曲的嘴唇张开,声音是从他脖子里传来的。小小的,肉质的孔洞,像嘴巴一样托动着,把那高亢的尖笑转变成模仿的小女孩哭喊。帮帮我,我迷路了,帮帮我,车灯照亮了整个区域,爸爸的皮卡出现了,沿着小路驶来。那头驯鹿,管他他妈的是什么,跑了再次消失在白雪覆盖的密林里,没有人相信我们,怎么会呢,如果有人跟我讲这个故事,我也会以为他们嗑了某种迷幻药。但我亲眼所见的现实是冰冷的,至今我仍无法完全咽下。那一夜,我和姐姐没有睡觉,而是查了一些资料,最终找到了关于脾行者的传说,某种存在,能模仿声音,伪装成动物,将人诱入林中。读完其他母级记录后,我毫不怀疑我们那晚目睹了什么。那天夜里,我不时望向窗外扫拾院子,想着会不会看见那张皮革式的脸从竖线边注视着我。我和姐姐再也没有去过那趟旅行,这让家人们很是恼火,但乌云背后总有一线光明,我们俩从未像现在这样亲近过。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 28 | 覆 | 28 | 附 |
| 002 | same_pronunciation_substitution | substitution | 106 | 窦 | 106 | 痘 |
| 005 | same_pronunciation_substitution | substitution | 304 | 烬 | 304 | 劲 |
| 006 | same_pronunciation_substitution | substitution | 324 | 她 | 324 | 他 |
| 006 | same_pronunciation_substitution | substitution | 330 | 她 | 330 | 他 |
| 006 | same_pronunciation_substitution | substitution | 346 | 她 | 346 | 他 |
| 006 | same_pronunciation_substitution | substitution | 358 | 兰 | 358 | 蓝 |
| 006 | same_pronunciation_substitution | substitution | 365 | 她 | 365 | 他 |
| 007 | same_pronunciation_substitution | substitution | 382 | 她 | 382 | 他 |
| 007 | same_pronunciation_substitution | substitution | 395 | 袋 | 395 | 带 |
| 008 | different_pronunciation_substitution | substitution | 449 | 起 | 449 | 弃 |
| 008 | same_pronunciation_substitution | substitution | 455 | 癫 | 455 | 滇 |
| 008 | same_pronunciation_substitution | substitution | 456 | 痫 | 456 | 弦 |
| 010 | same_pronunciation_substitution | substitution | 564 | 她 | 564 | 他 |
| 010 | same_pronunciation_substitution | substitution | 594 | 她 | 594 | 他 |
| 010 | same_pronunciation_substitution | substitution | 617 | 她 | 617 | 他 |
| 011 | same_pronunciation_substitution | substitution | 643 | 刺 | 643 | 次 |
| 011 | same_pronunciation_substitution | substitution | 651 | 饵 | 651 | 耳 |
| 011 | same_pronunciation_substitution | substitution | 659 | 她 | 659 | 它 |
| 011 | same_pronunciation_substitution | substitution | 669 | 她 | 669 | 它 |
| 012 | same_pronunciation_substitution | substitution | 706 | 蛋 | 706 | 淡 |
| 012 | different_pronunciation_substitution | substitution | 713 | 鲍 | 713 | 包 |
| 012 | different_pronunciation_substitution | substitution | 714 | 比 | 714 | 庇 |
| 015 | different_pronunciation_substitution | substitution | 868 | 雪 | 868 | 血 |
| 015 | same_pronunciation_substitution | substitution | 918 | 刹 | 918 | 杀 |
| 015 | different_pronunciation_substitution | substitution | 919 | 住 | 919 | 猪 |
| 016 | different_pronunciation_substitution | substitution | 921 | 哪 | 921 | 呐 |
| 016 | same_pronunciation_substitution | substitution | 972 | 啸 | 972 | 笑 |
| 017 | different_pronunciation_substitution | substitution | 1017 | 雪 | 1017 | 血 |
| 017 | different_pronunciation_substitution | substitution | 1043 | 踢 | 1043 | 提 |
| 018 | same_pronunciation_substitution | substitution | 1074 | 它 | 1074 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1149 | 化 | 1149 | 画 |
| 020 | same_pronunciation_substitution | substitution | 1169 | 它 | 1169 | 他 |
| 020 | same_pronunciation_substitution | substitution | 1204 | 它 | 1204 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1209 | 它 | 1209 | 他 |
| 021 | different_pronunciation_substitution | substitution | 1240 | 嚎 | 1240 | 号 |
| 023 | same_pronunciation_substitution | substitution | 1367 | 鹿 | 1367 | 路 |
| 024 | same_pronunciation_substitution | substitution | 1450 | 试 | 1450 | 世 |
| 025 | different_pronunciation_substitution | substitution | 1492 | 绽 | 1492 | 展 |
| 025 | same_pronunciation_substitution | substitution | 1496 | 蛛 | 1496 | 珠 |
| 027 | different_pronunciation_substitution | substitution | 1636 | 麻 | 1636 | 马 |
| 028 | same_pronunciation_substitution | substitution | 1684 | 刺 | 1684 | 次 |
| 029 | same_pronunciation_substitution | substitution | 1721 | 她 | 1721 | 他 |
| 029 | same_pronunciation_substitution | substitution | 1767 | 她 | 1767 | 他 |
| 030 | different_pronunciation_substitution | substitution | 1781 | 抿 | 1781 | 眯 |
| 030 | same_pronunciation_substitution | substitution | 1826 | 它 | 1826 | 她 |
| 031 | same_pronunciation_substitution | substitution | 1847 | 锁 | 1847 | 所 |
| 031 | same_pronunciation_substitution | substitution | 1867 | 厉 | 1867 | 立 |
| 031 | same_pronunciation_substitution | substitution | 1890 | 泣 | 1890 | 气 |
| 032 | same_pronunciation_substitution | substitution | 1923 | 腔 | 1923 | 枪 |
| 033 | same_pronunciation_substitution | substitution | 1976 | 她 | 1976 | 他 |
| 033 | same_pronunciation_substitution | substitution | 1993 | 词 | 1993 | 磁 |
| 033 | same_pronunciation_substitution | substitution | 1994 | 句 | 1994 | 具 |
| 033 | same_pronunciation_substitution | substitution | 1999 | 她 | 1999 | 他 |
| 033 | same_pronunciation_substitution | substitution | 2025 | 它 | 2025 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2069 | 它 | 2069 | 她 |
| 034 | same_pronunciation_substitution | substitution | 2080 | 它 | 2080 | 她 |
| 034 | same_pronunciation_substitution | substitution | 2099 | 膜 | 2099 | 魔 |
| 034 | different_pronunciation_substitution | substitution | 2100 | 中 | 2100 | 种 |
| 035 | same_pronunciation_substitution | substitution | 2101 | 它 | 2101 | 她 |
| 035 | same_pronunciation_substitution | substitution | 2110 | 鹿 | 2110 | 路 |
| 035 | same_pronunciation_substitution | substitution | 2111 | 角 | 2111 | 脚 |
| 035 | same_pronunciation_substitution | substitution | 2116 | 呵 | 2116 | 喝 |
| 035 | same_pronunciation_substitution | substitution | 2168 | 段 | 2168 | 断 |
| 036 | same_pronunciation_substitution | substitution | 2187 | 它 | 2187 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2204 | 它 | 2204 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2218 | 它 | 2218 | 他 |
| 037 | different_pronunciation_substitution | substitution | 2238 | 翕 | 2238 | 托 |
| 037 | same_pronunciation_substitution | substitution | 2247 | 啸 | 2247 | 笑 |
| 038 | same_pronunciation_substitution | substitution | 2297 | 它 | 2297 | 他 |
| 038 | same_pronunciation_substitution | substitution | 2348 | 磕 | 2348 | 嗑 |
| 040 | same_pronunciation_substitution | substitution | 2404 | 皮 | 2404 | 脾 |
| 041 | different_pronunciation_substitution | substitution | 2434 | 目 | 2434 | 母 |
| 041 | different_pronunciation_substitution | substitution | 2435 | 击 | 2435 | 级 |
| 041 | different_pronunciation_substitution | substitution | 2465 | 视 | 2465 | 拾 |
| 041 | same_pronunciation_substitution | substitution | 2479 | 似 | 2479 | 式 |
| 041 | same_pronunciation_substitution | substitution | 2483 | 树 | 2483 | 竖 |

### VoxCPM2

#### SenseVoice

- 严格汉字 CER：`0.038628`；字符编辑数：`98`。
- 带声调拼音 CER：`0.014584`；拼音 token 编辑数：`37`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 42 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
基督啊，我自言自语道，第一片雪花开始飘落，他们糊成毛茸茸的一团，附在挡风玻璃上，又被雨刷抹去。我已经在姐姐家的车道上等了15，不20分钟了。要是刚才选择进屋陪他等，这会儿估计已经被他那两只灰色的猫送去见上帝了。可爱的小恶魔，但对我的鼻窦来说，就是致命毒药，眼睛浮肿、喉咙堵塞，正是我最不需要的。每年圣诞节，我们家都会长途跋涉去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋。我本想赶在预报的那场大雪之前到达。但姐姐的驾照因为酒驾被吊销了，于是我成了时间的俘虏，手指焦躁的敲着方向盘。当初妈妈让我来接姐姐时，我心里就100个不情愿，不是我们彼此憎恨，只是没那么亲近了。几十年无休止的争吵和激烈的分歧之后，我们渐渐疏远，关系也随之冷却。没错，我们是手足，但说我们是手足残留下的余烬，恐怕更贴切。终于像瓦尔哈拉的大门敞开一般，他的前门开了，他走了出来，头发是森林绿的。上次我见他时还是白色，再上次是紫罗兰色，都戴齐了吗？他笨手笨脚的爬进副驾驶座时，我问道。嗯，他应了一声，扶了副眼镜，把几个袋子扔到后座。就这样，我们出发了，霍普镇大约30分钟车程，车里的尴尬沉没没多久就膨胀开来。收音机坏了，辅助插口也断掉了，放弃音乐，火翔在癫痫发作，这显然没有任何帮助。等我们拐上霍铺公路的岔道时，路面已经铺成厚厚一层白毯。好在平安夜的晚上，通往霍普小镇，那长长一段路空旷又安静，小木屋藏在主路5英里外的一片密林堡垒中，我转弯时，姐姐摇下车窗，掏出一根大麻烟卷，用打火机点燃。来一口。他问，车轮碾过雪地，嘎吱作响，开车的时候不行，只路一条，我们差不多到了，他吸了一口，朝窗外吐出一团烟雾，我只想专心开车，行吗？他哼了一声，推了推眼镜。你要真那么紧张，不如开慢点来了那一次一块引我上钩的饵，但我这次不咬钩，他想让我们更快到达，有他想去吧。车程快结束了，马上我就能坐在温暖的客厅里翘起脚，手里端着一杯加了烈酒的淡奶酒，耳边响起鲍比赫尔姆斯的铃铛摇滚。我甚至已经能想象，杰德叔叔又甩出他那恶俗笑话。圣诞老人为什么有那么大的哥们儿，姐姐尖叫起来，手指戳在我腰上，把我的思绪猛地拽回挡风玻璃前。车子刚刚绕过那条茂密的小径，一头驯鹿庞大的身躯挡在我们正前方，眼睛圆睁，空洞无神，即便高光曙灯照上去，也纹丝不动，惊慌之下，我猛打方向盘，拼命想避开。车子滑溜溜的侧偏过去，溅起一片碎雪泥，那头驯鹿，也就是北美驯鹿，依然一动不动。保险杠从他鼻子前几英寸的地方呼啸而过。我们在主路外的一侧嘎吱一声插住。天哪，我松了口气，庆醒不已，撞到了吗？没有，姐姐说着探出车窗看了一眼，又吐出一口烟。我把方向盘打正，踩下油门，车轮在原地尖笑，甩起一团团冰渣，却纹丝不动，完美。我呻吟着从座椅上把自己拆下来，下车查看，两个前轮裹满了黑乎乎的泥雪，几乎被积雪吞没。我踢了几脚，想把轮纹和轮拱下的冰渣弄掉。踢累了，只好用手指去刮。滚远点儿普兰瑟，我听见姐姐朝那头驯鹿的黑影喊道，她的鹿角像扭曲的手指伸向树梢。接着，他发出一声短促的惊呼，然后是一句什么鬼，我从积雪中抬起头来。那头驯鹿现在正用两条后腿直立着，看起来怪怪的，像童书里那种滑稽的拟人化形象。但在寂静的树林里，这画面令人毛骨悚然。他那模糊的身形仅凭两条腿站立，竟保持着近乎人类的平衡。不知为何，我这才注意到他没有尾巴。他肌肉发达的脖子扭向一侧，发出一声悠长的尖叫，金属碾膜，金属的惨烈哀嚎，我的双腿像冰雕一样，把我钉在原地，那尖叫渐渐化作一连串湿漉漉的咕噜声。驯鹿落回原来的姿态，重重的躲着地面，一团团白气和几缕鼻涕从他的鼻孔里喷出来。我不是猎人，但被激怒的动物要冲过来了。这点常识我还是有的。我扑向驾驶座，拉开车门砰的关上。与此同时，蹄子沉闷的撞击声已经追到我身边。鹿角刮过车门，他庞大的身躯，几乎擦着我刚才站过的那片地飞掠而过，快太快了。姐姐尖叫起来，那头硕大的鸣人转身又冲了回来，这次撞碎了前大灯，把我们吞没在黑暗中。快走啊，姐姐在我耳边吼道，我在是，该死的，我嘶声说，车轮继续无助的空转。我们被困住了，那东西再次冲撞，这次正中车床，姐姐脑袋旁边绽开一片蛛网般的裂纹，我拼命搜寻任何任何能当武器的东西。我从来不是什么强械爱好者，但在那一刻，如果手里能有一把格洛克，我愿意剃光头发加入世俗僧旅团。那驯鹿又撞击了车身一次，终于像是失去了兴趣，消失在树丛之间。但是有了喘息和思考的时间，我们给爸爸打了电话，告诉他情况，他会开着他的皮卡过来，帮我们把车弄出来，摆脱这团乱麻。我转头看向姐姐，她正把手指捂在脸上，缓慢而平稳的呼吸着，你还好吗？我问你说呢他嘟囔道，我让你开慢点，又是一次，这次我不打算忍了，你想帮上忙，我吼道，那就下去推车。不想，那就他妈闭嘴，我不需要这个，他不再说话，我也不再开口，重新陷入那种沉默，我们的关系早已沦落至此，但愿爸爸的车灯早点在远处亮起，忽然他摇下了车窗，你干什么？我问许他抿起嘴唇，仔细听，我姑且配合她等了等。果然我也听到了那个声音，外面传来一个小女孩的轻柔的嗓音。有人吗？他呜咽着，我迷路了，请帮帮我，我迷路了。姐姐解开车锁，伸手要开门，我一把抓住他的手腕，你干什么？他厉声道，外面有人，等一下，这不对劲，不是吗？那声音继续哀泣着，在啜泣和哀求之间哽咽，求任何人帮帮他。我不喜欢那声音的质感，同样的脱腔，同样的哭诉，就像有人在反复播放一段录音。不对劲，我的直觉在各个方向竖起红旗，然后姐姐看向我，她的表情骤然扭曲成惊骇。他猛地往后一缩，双剑紧贴车内室，一些像瓷具的东西从他喉咙里冒出来，却没能成形。我转过身，看见了正盯着我的东西，他长着一张男人的脸，嵌在斑驳的驯鹿皮毛之间。皮肤是木乃伊般的褐色，像老旧皱缩的皮革一般，紧紧裹在他修长的头骨上，雪花落在他那双大而空洞的眼睛上，融化进瞳孔暗色的魔肿。他绕着车子踱步，晃动鹿角，往车窗上呵气，向内窥视。我的心撞击着喉咙的臂，我和姐姐四目相对，在彻底的不可置信中，一个字也说不出来。我本该抓起手机，拍张照，路段视频。什么都好，但我的思绪乱作一团。紧接着，他再次发出那声可怕的尖叫，但我没看见他紧闭扭曲的嘴唇张开，声音是从他脖子里传来的。小小的肉质的孔洞，像嘴巴一样吸动着，把那高亢的尖笑转变成模仿的小女孩哭喊，帮帮我，我迷路了，帮帮我，车灯照亮了整个区域，爸爸的皮卡出现了，沿着小路驶来。那头驯鹿管他他妈的是什么，跑了，再次消失在白雪覆盖的密林里，没有人相信我们，怎么会呢？如果有人跟我讲这个故事，我也会以为他们磕了某种迷幻药。但我亲眼所见的现实是冰冷的，至今我仍无法完全咽下。那一夜，我和姐姐没有睡觉，而是查了一些资料，最终找到了关于琵行者的传说。某种存在能模仿声音，伪装成动物，将人诱入林中。读完其他目击记录后，我毫不怀疑我们那晚目睹了什么。那天夜里，我不时望向窗外扫湿院子，想着会不会看见那张皮革式的脸，从树线边注视着我。我和姐姐再也没有去过那趟旅行，这让家人们很是恼火，但乌云背后总有一线光明，我们俩从未像现在这样亲近过。
```

原始转写（仅移除 SenseVoice 控制标记后才计算 CER；此处保留以供复核）：

```text
<|zh|><|NEUTRAL|><|Speech|><|withitn|>基督啊，我自言自语道，第一片雪花开始飘落，他们糊成毛茸茸的一团，附在挡风玻璃上，又被雨刷抹去。我已经在姐姐家的车道上等了15，不20分钟了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>要是刚才选择进屋陪他等，这会儿估计已经被他那两只灰色的猫送去见上帝了。可爱的小恶魔，但对我的鼻窦来说，就是致命毒药，眼睛浮肿、喉咙堵塞，正是我最不需要的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>每年圣诞节，我们家都会长途跋涉去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋。我本想赶在预报的那场大雪之前到达。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但姐姐的驾照因为酒驾被吊销了，于是我成了时间的俘虏，手指焦躁的敲着方向盘。当初妈妈让我来接姐姐时，我心里就100个不情愿，不是我们彼此憎恨，只是没那么亲近了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>几十年无休止的争吵和激烈的分歧之后，我们渐渐疏远，关系也随之冷却。没错，我们是手足，但说我们是手足残留下的余烬，恐怕更贴切。<|zh|><|NEUTRAL|><|Speech|><|withitn|>终于像瓦尔哈拉的大门敞开一般，他的前门开了，他走了出来，头发是森林绿的。上次我见他时还是白色，再上次是紫罗兰色，都戴齐了吗？他笨手笨脚的爬进副驾驶座时，我问道。<|zh|><|NEUTRAL|><|Speech|><|withitn|>嗯，他应了一声，扶了副眼镜，把几个袋子扔到后座。就这样，我们出发了，霍普镇大约30分钟车程，车里的尴尬沉没没多久就膨胀开来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>收音机坏了，辅助插口也断掉了，放弃音乐，火翔在癫痫发作，这显然没有任何帮助。等我们拐上霍铺公路的岔道时，路面已经铺成厚厚一层白毯。<|zh|><|NEUTRAL|><|Speech|><|withitn|>好在平安夜的晚上，通往霍普小镇，那长长一段路空旷又安静，小木屋藏在主路5英里外的一片密林堡垒中，我转弯时，姐姐摇下车窗，掏出一根大麻烟卷，用打火机点燃。来一口。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他问，车轮碾过雪地，嘎吱作响，开车的时候不行，只路一条，我们差不多到了，他吸了一口，朝窗外吐出一团烟雾，我只想专心开车，行吗？他哼了一声，推了推眼镜。<|zh|><|NEUTRAL|><|Speech|><|withitn|>你要真那么紧张，不如开慢点来了那一次一块引我上钩的饵，但我这次不咬钩，他想让我们更快到达，有他想去吧。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车程快结束了，马上我就能坐在温暖的客厅里翘起脚，手里端着一杯加了烈酒的淡奶酒，耳边响起鲍比赫尔姆斯的铃铛摇滚。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我甚至已经能想象，杰德叔叔又甩出他那恶俗笑话。圣诞老人为什么有那么大的哥们儿，姐姐尖叫起来，手指戳在我腰上，把我的思绪猛地拽回挡风玻璃前。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车子刚刚绕过那条茂密的小径，一头驯鹿庞大的身躯挡在我们正前方，眼睛圆睁，空洞无神，即便高光曙灯照上去，也纹丝不动，惊慌之下，我猛打方向盘，拼命想避开。<|zh|><|NEUTRAL|><|Speech|><|withitn|>车子滑溜溜的侧偏过去，溅起一片碎雪泥，那头驯鹿，也就是北美驯鹿，依然一动不动。保险杠从他鼻子前几英寸的地方呼啸而过。我们在主路外的一侧嘎吱一声插住。<|zh|><|SAD|><|Speech|><|withitn|>天哪，我松了口气，庆醒不已，撞到了吗？没有，姐姐说着探出车窗看了一眼，又吐出一口烟。我把方向盘打正，踩下油门，车轮在原地尖笑，甩起一团团冰渣，却纹丝不动，完美。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我呻吟着从座椅上把自己拆下来，下车查看，两个前轮裹满了黑乎乎的泥雪，几乎被积雪吞没。我踢了几脚，想把轮纹和轮拱下的冰渣弄掉。踢累了，只好用手指去刮。<|zh|><|NEUTRAL|><|Speech|><|withitn|>滚远点儿普兰瑟，我听见姐姐朝那头驯鹿的黑影喊道，她的鹿角像扭曲的手指伸向树梢。接着，他发出一声短促的惊呼，然后是一句什么鬼，我从积雪中抬起头来。<|zh|><|NEUTRAL|><|Speech|><|withitn|>那头驯鹿现在正用两条后腿直立着，看起来怪怪的，像童书里那种滑稽的拟人化形象。但在寂静的树林里，这画面令人毛骨悚然。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他那模糊的身形仅凭两条腿站立，竟保持着近乎人类的平衡。不知为何，我这才注意到他没有尾巴。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他肌肉发达的脖子扭向一侧，发出一声悠长的尖叫，金属碾膜，金属的惨烈哀嚎，我的双腿像冰雕一样，把我钉在原地，那尖叫渐渐化作一连串湿漉漉的咕噜声。<|zh|><|NEUTRAL|><|Speech|><|withitn|>驯鹿落回原来的姿态，重重的躲着地面，一团团白气和几缕鼻涕从他的鼻孔里喷出来。我不是猎人，但被激怒的动物要冲过来了。这点常识我还是有的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我扑向驾驶座，拉开车门砰的关上。与此同时，蹄子沉闷的撞击声已经追到我身边。鹿角刮过车门，他庞大的身躯，几乎擦着我刚才站过的那片地飞掠而过，快太快了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>姐姐尖叫起来，那头硕大的鸣人转身又冲了回来，这次撞碎了前大灯，把我们吞没在黑暗中。快走啊，姐姐在我耳边吼道，我在是，该死的，我嘶声说，车轮继续无助的空转。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我们被困住了，那东西再次冲撞，这次正中车床，姐姐脑袋旁边绽开一片蛛网般的裂纹，我拼命搜寻任何任何能当武器的东西。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我从来不是什么强械爱好者，但在那一刻，如果手里能有一把格洛克，我愿意剃光头发加入世俗僧旅团。那驯鹿又撞击了车身一次，终于像是失去了兴趣，消失在树丛之间。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但是有了喘息和思考的时间，我们给爸爸打了电话，告诉他情况，他会开着他的皮卡过来，帮我们把车弄出来，摆脱这团乱麻。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我转头看向姐姐，她正把手指捂在脸上，缓慢而平稳的呼吸着，你还好吗？我问你说呢他嘟囔道，我让你开慢点，又是一次，这次我不打算忍了，你想帮上忙，我吼道，那就下去推车。<|zh|><|SAD|><|Speech|><|withitn|>不想，那就他妈闭嘴，我不需要这个，他不再说话，我也不再开口，重新陷入那种沉默，我们的关系早已沦落至此，但愿爸爸的车灯早点在远处亮起，忽然他摇下了车窗，你干什么？<|zh|><|SAD|><|Speech|><|withitn|>我问许他抿起嘴唇，仔细听，我姑且配合她等了等。果然我也听到了那个声音，外面传来一个小女孩的轻柔的嗓音。有人吗？他呜咽着，我迷路了，请帮帮我，我迷路了。<|zh|><|NEUTRAL|><|Speech|><|withitn|>姐姐解开车锁，伸手要开门，我一把抓住他的手腕，你干什么？他厉声道，外面有人，等一下，这不对劲，不是吗？那声音继续哀泣着，在啜泣和哀求之间哽咽，求任何人帮帮他。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我不喜欢那声音的质感，同样的脱腔，同样的哭诉，就像有人在反复播放一段录音。不对劲，我的直觉在各个方向竖起红旗，然后姐姐看向我，她的表情骤然扭曲成惊骇。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他猛地往后一缩，双剑紧贴车内室，一些像瓷具的东西从他喉咙里冒出来，却没能成形。我转过身，看见了正盯着我的东西，他长着一张男人的脸，嵌在斑驳的驯鹿皮毛之间。<|zh|><|NEUTRAL|><|Speech|><|withitn|>皮肤是木乃伊般的褐色，像老旧皱缩的皮革一般，紧紧裹在他修长的头骨上，雪花落在他那双大而空洞的眼睛上，融化进瞳孔暗色的魔肿。<|zh|><|NEUTRAL|><|Speech|><|withitn|>他绕着车子踱步，晃动鹿角，往车窗上呵气，向内窥视。我的心撞击着喉咙的臂，我和姐姐四目相对，在彻底的不可置信中，一个字也说不出来。我本该抓起手机，拍张照，路段视频。<|zh|><|SAD|><|Speech|><|withitn|>什么都好，但我的思绪乱作一团。紧接着，他再次发出那声可怕的尖叫，但我没看见他紧闭扭曲的嘴唇张开，声音是从他脖子里传来的。<|zh|><|NEUTRAL|><|Speech|><|withitn|>小小的肉质的孔洞，像嘴巴一样吸动着，把那高亢的尖笑转变成模仿的小女孩哭喊，帮帮我，我迷路了，帮帮我，车灯照亮了整个区域，爸爸的皮卡出现了，沿着小路驶来。<|zh|><|SAD|><|Speech|><|withitn|>那头驯鹿管他他妈的是什么，跑了，再次消失在白雪覆盖的密林里，没有人相信我们，怎么会呢？如果有人跟我讲这个故事，我也会以为他们磕了某种迷幻药。<|zh|><|NEUTRAL|><|Speech|><|withitn|>但我亲眼所见的现实是冰冷的，至今我仍无法完全咽下。<|zh|><|NEUTRAL|><|Speech|><|withitn|>那一夜，我和姐姐没有睡觉，而是查了一些资料，最终找到了关于琵行者的传说。某种存在能模仿声音，伪装成动物，将人诱入林中。<|zh|><|NEUTRAL|><|Speech|><|withitn|>读完其他目击记录后，我毫不怀疑我们那晚目睹了什么。那天夜里，我不时望向窗外扫湿院子，想着会不会看见那张皮革式的脸，从树线边注视着我。<|zh|><|NEUTRAL|><|Speech|><|withitn|>我和姐姐再也没有去过那趟旅行，这让家人们很是恼火，但乌云背后总有一线光明，我们俩从未像现在这样亲近过。
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 18 | 它 | 18 | 他 |
| 001 | same_pronunciation_substitution | substitution | 28 | 覆 | 28 | 附 |
| 001 | different_pronunciation_substitution | substitution | 54 | 十 | 54 | 1 |
| 001 | different_pronunciation_substitution | substitution | 55 | 五 | 55 | 5 |
| 001 | different_pronunciation_substitution | substitution | 57 | 二 | 57 | 2 |
| 001 | different_pronunciation_substitution | substitution | 58 | 十 | 58 | 0 |
| 002 | same_pronunciation_substitution | substitution | 71 | 她 | 71 | 他 |
| 002 | same_pronunciation_substitution | substitution | 81 | 她 | 81 | 他 |
| 004 | different_pronunciation_substitution | substitution | 212 | 地 | 212 | 的 |
| 004 | insertion | insertion | 233 | ∅ | 233 | 1 |
| 004 | different_pronunciation_substitution | substitution | 233 | 一 | 234 | 0 |
| 004 | different_pronunciation_substitution | substitution | 234 | 百 | 235 | 0 |
| 006 | same_pronunciation_substitution | substitution | 324 | 她 | 325 | 他 |
| 006 | same_pronunciation_substitution | substitution | 330 | 她 | 331 | 他 |
| 006 | same_pronunciation_substitution | substitution | 346 | 她 | 347 | 他 |
| 006 | same_pronunciation_substitution | substitution | 361 | 带 | 362 | 戴 |
| 006 | same_pronunciation_substitution | substitution | 365 | 她 | 366 | 他 |
| 006 | different_pronunciation_substitution | substitution | 370 | 地 | 371 | 的 |
| 007 | same_pronunciation_substitution | substitution | 382 | 她 | 383 | 他 |
| 007 | different_pronunciation_substitution | substitution | 389 | 扶 | 390 | 副 |
| 007 | different_pronunciation_substitution | substitution | 414 | 三 | 415 | 3 |
| 007 | different_pronunciation_substitution | substitution | 415 | 十 | 416 | 0 |
| 007 | different_pronunciation_substitution | substitution | 426 | 默 | 427 | 没 |
| 008 | different_pronunciation_substitution | substitution | 449 | 起 | 450 | 弃 |
| 008 | different_pronunciation_substitution | substitution | 452 | 活 | 453 | 火 |
| 008 | different_pronunciation_substitution | substitution | 453 | 像 | 454 | 翔 |
| 008 | different_pronunciation_substitution | substitution | 474 | 普 | 475 | 铺 |
| 009 | different_pronunciation_substitution | substitution | 525 | 五 | 526 | 5 |
| 010 | same_pronunciation_substitution | substitution | 564 | 她 | 565 | 他 |
| 010 | different_pronunciation_substitution | substitution | 583 | 直 | 584 | 只 |
| 010 | same_pronunciation_substitution | substitution | 594 | 她 | 595 | 他 |
| 010 | same_pronunciation_substitution | substitution | 617 | 她 | 618 | 他 |
| 011 | same_pronunciation_substitution | substitution | 643 | 刺 | 644 | 次 |
| 011 | same_pronunciation_substitution | substitution | 659 | 她 | 660 | 他 |
| 011 | different_pronunciation_substitution | substitution | 668 | 由 | 669 | 有 |
| 011 | same_pronunciation_substitution | substitution | 669 | 她 | 670 | 他 |
| 012 | same_pronunciation_substitution | substitution | 706 | 蛋 | 707 | 淡 |
| 014 | different_pronunciation_substitution | substitution | 828 | 束 | 829 | 曙 |
| 015 | different_pronunciation_substitution | substitution | 858 | 地 | 859 | 的 |
| 015 | same_pronunciation_substitution | substitution | 891 | 它 | 892 | 他 |
| 015 | different_pronunciation_substitution | substitution | 918 | 刹 | 919 | 插 |
| 016 | different_pronunciation_substitution | substitution | 928 | 幸 | 929 | 醒 |
| 016 | same_pronunciation_substitution | substitution | 972 | 啸 | 973 | 笑 |
| 018 | insertion | insertion | 1056 | ∅ | 1057 | 儿 |
| 018 | same_pronunciation_substitution | substitution | 1074 | 它 | 1076 | 她 |
| 018 | same_pronunciation_substitution | substitution | 1090 | 她 | 1092 | 他 |
| 020 | same_pronunciation_substitution | substitution | 1169 | 它 | 1171 | 他 |
| 020 | same_pronunciation_substitution | substitution | 1204 | 它 | 1206 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1209 | 它 | 1211 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1233 | 磨 | 1235 | 膜 |
| 022 | different_pronunciation_substitution | substitution | 1284 | 地 | 1286 | 的 |
| 022 | different_pronunciation_substitution | substitution | 1285 | 跺 | 1287 | 躲 |
| 022 | same_pronunciation_substitution | substitution | 1300 | 它 | 1302 | 他 |
| 023 | different_pronunciation_substitution | substitution | 1345 | 地 | 1347 | 的 |
| 023 | same_pronunciation_substitution | substitution | 1373 | 它 | 1375 | 他 |
| 024 | same_pronunciation_substitution | substitution | 1411 | 名 | 1413 | 鸣 |
| 024 | same_pronunciation_substitution | substitution | 1450 | 试 | 1452 | 是 |
| 024 | different_pronunciation_substitution | substitution | 1464 | 地 | 1466 | 的 |
| 025 | different_pronunciation_substitution | substitution | 1485 | 窗 | 1487 | 床 |
| 026 | different_pronunciation_substitution | substitution | 1525 | 枪 | 1527 | 强 |
| 026 | same_pronunciation_substitution | substitution | 1558 | 侣 | 1560 | 旅 |
| 027 | different_pronunciation_substitution | substitution | 1587 | 暂 | 1589 | 但 |
| 027 | different_pronunciation_substitution | substitution | 1588 | 时 | 1590 | 是 |
| 028 | different_pronunciation_substitution | substitution | 1658 | 地 | 1660 | 的 |
| 028 | same_pronunciation_substitution | substitution | 1671 | 她 | 1673 | 他 |
| 028 | same_pronunciation_substitution | substitution | 1684 | 刺 | 1686 | 次 |
| 029 | same_pronunciation_substitution | substitution | 1721 | 她 | 1723 | 他 |
| 029 | same_pronunciation_substitution | substitution | 1767 | 她 | 1769 | 他 |
| 030 | different_pronunciation_substitution | substitution | 1779 | 嘘 | 1781 | 许 |
| 030 | same_pronunciation_substitution | substitution | 1780 | 她 | 1782 | 他 |
| 030 | same_pronunciation_substitution | substitution | 1826 | 它 | 1828 | 他 |
| 031 | same_pronunciation_substitution | substitution | 1858 | 她 | 1860 | 他 |
| 031 | same_pronunciation_substitution | substitution | 1866 | 她 | 1868 | 他 |
| 031 | same_pronunciation_substitution | substitution | 1908 | 她 | 1910 | 他 |
| 032 | same_pronunciation_substitution | substitution | 1922 | 拖 | 1924 | 脱 |
| 033 | same_pronunciation_substitution | substitution | 1976 | 她 | 1978 | 他 |
| 033 | different_pronunciation_substitution | substitution | 1984 | 肩 | 1986 | 剑 |
| 033 | same_pronunciation_substitution | substitution | 1989 | 饰 | 1991 | 室 |
| 033 | same_pronunciation_substitution | substitution | 1993 | 词 | 1995 | 瓷 |
| 033 | same_pronunciation_substitution | substitution | 1994 | 句 | 1996 | 具 |
| 033 | same_pronunciation_substitution | substitution | 1999 | 她 | 2001 | 他 |
| 033 | same_pronunciation_substitution | substitution | 2025 | 它 | 2027 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2069 | 它 | 2071 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2080 | 它 | 2082 | 他 |
| 034 | same_pronunciation_substitution | substitution | 2099 | 膜 | 2101 | 魔 |
| 034 | different_pronunciation_substitution | substitution | 2100 | 中 | 2102 | 肿 |
| 035 | same_pronunciation_substitution | substitution | 2101 | 它 | 2103 | 他 |
| 035 | same_pronunciation_substitution | substitution | 2131 | 壁 | 2133 | 臂 |
| 035 | same_pronunciation_substitution | substitution | 2167 | 录 | 2169 | 路 |
| 036 | same_pronunciation_substitution | substitution | 2187 | 它 | 2189 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2204 | 它 | 2206 | 他 |
| 036 | same_pronunciation_substitution | substitution | 2218 | 它 | 2220 | 他 |
| 037 | same_pronunciation_substitution | substitution | 2238 | 翕 | 2240 | 吸 |
| 037 | same_pronunciation_substitution | substitution | 2247 | 啸 | 2249 | 笑 |
| 038 | same_pronunciation_substitution | substitution | 2297 | 它 | 2299 | 他 |
| 040 | same_pronunciation_substitution | substitution | 2404 | 皮 | 2406 | 琵 |
| 041 | different_pronunciation_substitution | substitution | 2465 | 视 | 2467 | 湿 |
| 041 | same_pronunciation_substitution | substitution | 2479 | 似 | 2481 | 式 |

#### Whisper-large-v3-turbo

- 严格汉字 CER：`0.037052`；字符编辑数：`94`。
- 带声调拼音 CER：`0.013402`；拼音 token 编辑数：`34`。该指标只提示同音字假阳性可能性，不能取代严格 CER。
- ASR 健康：`healthy`；不可靠片段：无；该后端参与名次。
- 分段：按冻结合成证据的 42 个语义段逐段解码；解码参数已保存在原始证据。

完整转写：

```text
基督啊,我自言自语道,第一片雪花开始飘落,它们糊成毛茸茸的一团附在挡风玻璃上,又被雨刷抹去,我已经在姐姐家的车道上等了十五,不,二十分钟了。要是刚才选择进屋陪她等这会儿估计已经被她那两只灰色的猫送去见上帝了可爱的小恶魔但对我的鼻痘来说就是致命毒药眼睛浮肿喉咙堵塞正是我最不需要的每年圣诞节我们家都会长途跋涉去爷爷奶奶那座藏在阿拉斯加霍普镇森林里的小木屋我本想赶在预报的那场大雪之前到达但姐姐的驾照因为酒驾被吊销了,于是我成了时间的俘虏,手指焦躁地敲着方向盘。当初妈妈让我来接姐姐时,我心里就一百个不情愿,不是我们彼此憎恨,只是没那么亲近了。几十年无休止的争吵和激烈的分歧之后我们渐渐疏远关系也随之冷却没错我们是手足但说我们是手足残留下的余劲恐怕更贴切终于像瓦尔哈拉的大门敞开一般他的前门开了他走了出来头发是森林绿的上次我见他时还是白色再上次是紫罗蓝色都带齐了吗他笨手笨脚地爬进副驾驶做事我问道嗯,他应了一声,扶了扶眼镜,把几个带子扔到后座就这样,我们出发了,霍普镇大约三十分钟车程,车里的尴尬沉默没多久就膨胀开来收音机坏了,辅助插口也断掉了,放弃音乐,活响在滇闲发作这显然没有任何帮助等我们拐上霍普公路的插道时,路面已经铺成厚厚一层白毯好在平安夜的晚上通往霍普小镇那长长一段路空旷又安静小木屋藏在主路五英里外的一片密林堡垒中我转弯时姐姐摇下车窗掏出一根大麻烟卷用打火机点燃来一口他问车轮碾过雪地嘎吱作响开车的时候不行直路一跳我们差不多到了他吸了一口朝窗外吐出一团烟雾我只想专心开车行吗他哼了一声推了推眼镜你要真那么紧张不如开慢点来了那一次一块引我上钩的二但我这次不要钩他想让我们更快到达由他想去吧车程快结束了马上我就能坐在温暖的客厅里翘起脚手里端着一杯加了烈酒的淡奶酒耳边响起鲍比赫尔姆斯的铃铛摇滚我甚至已经能想象杰德叔叔又甩出他那恶俗笑话圣诞老人为什么有那么大的哥们儿姐姐尖叫起来手指戳在我腰上把我的思绪猛地拽回挡风玻璃前车子刚刚绕过那条茂密的小径一头迅路庞大的身躯挡在我们正前方眼睛圆睁空洞无神即便高光鼠灯照上去也纹丝不动惊慌之下我猛打方向盘拼命想避开车子滑溜溜地侧偏过去溅起一片碎血泥那头驯鹿也就是北美驯鹿依然一动不动保险杠从它鼻子前几英寸的地方呼啸而过我们在主路外的一侧嘎吱一声插住天哪我怂了口气清醒不已撞到了吗没有姐姐说着探出车窗看了一眼又吐出一口烟我把方向盘打正踩下油门车轮在原地尖笑甩起一团团冰渣却纹丝不动完美我伸吟着从座椅上把自己拆下来下车查看两个前轮裹满了黑乎乎的泥血几乎被积雪吞没我踢了几脚想把轮纹和轮拱下的冰渣弄掉踢累了只好用手指去刮滚远点,普兰瑟,我听见姐姐朝那头驯鹿的黑影喊道,她的鹿角像扭曲的手指伸向树梢,接着她发出一声短促的惊呼,然后是一句,什么鬼?我从积雪中抬起头来。那头驯鹿现在正用两条后腿直立着看起来怪怪的像童书里那种滑稽的拟人画形象但在寂静的树林里这画面令人毛骨悚然他那模糊的神性仅凭两条腿站立竟保持着近乎人类的平衡不知为何我这才注意到他没有尾巴他肌肉发达的脖子扭向一侧发出一声悠长的尖叫金属念墨金属的惨烈哀号我的双腿像冰雕一样把我钉在原地那尖叫渐渐化作一连串湿漉漉的咕噜声驯鹿落回原来的姿态重重地躲着地面一团团白气和几缕鼻涕从它的鼻孔里喷出来我不是猎人但被激怒的动物要冲过来了这点常识我还是有的我扑向驾驶座,拉开车门,碰到关上与此同时,蹄子沉闷的撞击声已经追到我身边路角刮过车门,它庞大的身躯几乎擦着我刚才站过的那片地飞掠而过快,太快了姐姐尖叫起来那头硕大的名人转身又冲了回来这次撞碎了前大灯把我们吞没在黑暗中快走啊姐姐在我耳边吼道我在事该死的我嘶声说车轮继续无助地空转我们被困住了那东西再次冲撞这次正中车床姐姐脑袋旁边粘开一片珠网般的裂纹我拼命搜寻任何任何能当武器的东西我从来不是什么枪械爱好者但在那一刻如果手里能有一把格洛克我愿意剃光头发加入世俗僧侣团那驯鹿又撞击了车身一次终于像是失去了兴趣消失在树丛之间但是有了喘息和思考的时间我们给爸爸打了电话告诉他情况他会开着他的皮卡过来帮我们把车弄出来拜托这团乱马我转头看向姐姐她正把手指捂在脸上缓慢而平稳地呼吸着你还好吗我问你说呢她嘟囔道我让你开慢点又是一次这次我不打算忍了你想帮上忙我吼道那就下去推车不想那就他妈闭嘴我不需要这个他不再说话我也不再开口重新陷入那种沉默我们的关系早已沦落至此但愿爸爸的车灯早点在远处亮起忽然他摇下了车窗你干什么我问嘘她眯起嘴唇仔细听我姑且配合她等了等果然我也听到了那个声音外面传来一个小女孩的轻柔的嗓音有人吗她呜咽着我迷路了请帮帮我我迷路了姐姐解开车锁伸手要开门我一把抓住她的手腕你干什么她力声道外面有人等一下这不对劲不是吗那声音继续哀气着在啰气和哀求之间哽咽求任何人帮帮她我不喜欢那声音的质感同样的拖枪同样的哭诉就像有人在反复播放一段录音不对劲我的直觉在各个方向竖起红旗然后姐姐看向我她的表情骤然扭曲成惊骇她猛地往后一缩双肩紧贴车内饰一些像磁具的东西从她喉咙里冒出来却没能成形我转过身看见了正盯着我的东西她长着一张男人的脸嵌在斑驳的迅鹿皮毛之间皮肤是木乃伊般的褐色,像老旧皱缩的皮革一般,紧紧裹在她修长的头骨上,雪花落在她那双大而空洞的眼睛上,融化进瞳孔暗色的模种。她绕着车子踱步晃动路脚往车窗上喝气向内窥视我的心撞击着喉咙的壁我和姐姐四目相对在彻底的不可置信中一个字也说不出来我本该抓起手机拍张照录端视频什么都好但我的思绪乱作一团紧接着她再次发出那声可怕的尖叫但我没看见她紧闭扭曲的嘴唇张开声音是从她脖子里传来的小小的,肉质的孔洞,像嘴巴一样戏动着,把那高亢的尖笑转变成模仿的小女孩哭喊帮帮我,我迷路了,帮帮我车灯照亮了整个区域,爸爸的皮卡出现了,沿着小路驶来那头驯鹿,管他他妈的是什么,跑了再次消失在白雪覆盖的蜜林里。没有人相信我们,怎么会呢?如果有人跟我讲这个故事,我也会以为他们嗑了某种迷幻药。但我亲眼所见的现实是冰冷的至今我仍无法完全咽下那一夜,我和姐姐没有睡觉,而是查了一些资料,最终找到了关于脾行者的传说,某种存在,能模仿声音,伪装成动物,将人诱入林中。读完其他目击记录后,我毫不怀疑我们那晚目睹了什么,那天夜里,我不时望向窗外扫尸院子,想着会不会看见那张皮革似的脸从树线边注视着我。我和姐姐再也没有去过那趟旅行这让家人们很是恼火但乌云背后总有一线光明我们俩从未像现在这样亲近过
```

严格汉字差异位置（参考与转写索引均从 0 开始；不是人工确认的错读结论）：

| 片段 | 分类 | 操作 | 参考索引 | 参考字符 | 转写索引 | 转写字符 |
| --- | --- | --- | ---: | --- | ---: | --- |
| 001 | same_pronunciation_substitution | substitution | 28 | 覆 | 28 | 附 |
| 002 | same_pronunciation_substitution | substitution | 106 | 窦 | 106 | 痘 |
| 005 | same_pronunciation_substitution | substitution | 304 | 烬 | 304 | 劲 |
| 006 | same_pronunciation_substitution | substitution | 324 | 她 | 324 | 他 |
| 006 | same_pronunciation_substitution | substitution | 330 | 她 | 330 | 他 |
| 006 | same_pronunciation_substitution | substitution | 346 | 她 | 346 | 他 |
| 006 | same_pronunciation_substitution | substitution | 358 | 兰 | 358 | 蓝 |
| 006 | same_pronunciation_substitution | substitution | 365 | 她 | 365 | 他 |
| 006 | same_pronunciation_substitution | substitution | 376 | 座 | 376 | 做 |
| 006 | different_pronunciation_substitution | substitution | 377 | 时 | 377 | 事 |
| 007 | same_pronunciation_substitution | substitution | 382 | 她 | 382 | 他 |
| 007 | same_pronunciation_substitution | substitution | 395 | 袋 | 395 | 带 |
| 008 | different_pronunciation_substitution | substitution | 449 | 起 | 449 | 弃 |
| 008 | different_pronunciation_substitution | substitution | 453 | 像 | 453 | 响 |
| 008 | same_pronunciation_substitution | substitution | 455 | 癫 | 455 | 滇 |
| 008 | same_pronunciation_substitution | substitution | 456 | 痫 | 456 | 闲 |
| 008 | different_pronunciation_substitution | substitution | 478 | 岔 | 478 | 插 |
| 010 | same_pronunciation_substitution | substitution | 564 | 她 | 564 | 他 |
| 010 | different_pronunciation_substitution | substitution | 586 | 条 | 586 | 跳 |
| 010 | same_pronunciation_substitution | substitution | 594 | 她 | 594 | 他 |
| 010 | same_pronunciation_substitution | substitution | 617 | 她 | 617 | 他 |
| 011 | same_pronunciation_substitution | substitution | 643 | 刺 | 643 | 次 |
| 011 | different_pronunciation_substitution | substitution | 651 | 饵 | 651 | 二 |
| 011 | different_pronunciation_substitution | substitution | 657 | 咬 | 657 | 要 |
| 011 | same_pronunciation_substitution | substitution | 659 | 她 | 659 | 他 |
| 011 | same_pronunciation_substitution | substitution | 669 | 她 | 669 | 他 |
| 012 | same_pronunciation_substitution | substitution | 706 | 蛋 | 706 | 淡 |
| 014 | same_pronunciation_substitution | substitution | 802 | 驯 | 802 | 迅 |
| 014 | same_pronunciation_substitution | substitution | 803 | 鹿 | 803 | 路 |
| 014 | different_pronunciation_substitution | substitution | 828 | 束 | 828 | 鼠 |
| 015 | different_pronunciation_substitution | substitution | 868 | 雪 | 868 | 血 |
| 015 | different_pronunciation_substitution | substitution | 918 | 刹 | 918 | 插 |
| 016 | different_pronunciation_substitution | substitution | 923 | 松 | 923 | 怂 |
| 016 | different_pronunciation_substitution | substitution | 927 | 庆 | 927 | 清 |
| 016 | different_pronunciation_substitution | substitution | 928 | 幸 | 928 | 醒 |
| 016 | same_pronunciation_substitution | substitution | 972 | 啸 | 972 | 笑 |
| 017 | same_pronunciation_substitution | substitution | 988 | 呻 | 988 | 伸 |
| 017 | different_pronunciation_substitution | substitution | 1017 | 雪 | 1017 | 血 |
| 018 | same_pronunciation_substitution | substitution | 1074 | 它 | 1074 | 她 |
| 019 | same_pronunciation_substitution | substitution | 1149 | 化 | 1149 | 画 |
| 020 | same_pronunciation_substitution | substitution | 1169 | 它 | 1169 | 他 |
| 020 | different_pronunciation_substitution | substitution | 1174 | 身 | 1174 | 神 |
| 020 | different_pronunciation_substitution | substitution | 1175 | 形 | 1175 | 性 |
| 020 | same_pronunciation_substitution | substitution | 1204 | 它 | 1204 | 他 |
| 021 | same_pronunciation_substitution | substitution | 1209 | 它 | 1209 | 他 |
| 021 | different_pronunciation_substitution | substitution | 1232 | 碾 | 1232 | 念 |
| 021 | different_pronunciation_substitution | substitution | 1233 | 磨 | 1233 | 墨 |
| 021 | different_pronunciation_substitution | substitution | 1240 | 嚎 | 1240 | 号 |
| 022 | different_pronunciation_substitution | substitution | 1285 | 跺 | 1285 | 躲 |
| 023 | different_pronunciation_substitution | substitution | 1344 | 砰 | 1344 | 碰 |
| 023 | different_pronunciation_substitution | substitution | 1345 | 地 | 1345 | 到 |
| 023 | same_pronunciation_substitution | substitution | 1367 | 鹿 | 1367 | 路 |
| 024 | same_pronunciation_substitution | substitution | 1450 | 试 | 1450 | 事 |
| 025 | different_pronunciation_substitution | substitution | 1485 | 窗 | 1485 | 床 |
| 025 | different_pronunciation_substitution | substitution | 1492 | 绽 | 1492 | 粘 |
| 025 | same_pronunciation_substitution | substitution | 1496 | 蛛 | 1496 | 珠 |
| 027 | different_pronunciation_substitution | substitution | 1587 | 暂 | 1587 | 但 |
| 027 | different_pronunciation_substitution | substitution | 1588 | 时 | 1588 | 是 |
| 027 | different_pronunciation_substitution | substitution | 1631 | 摆 | 1631 | 拜 |
| 027 | same_pronunciation_substitution | substitution | 1632 | 脱 | 1632 | 托 |
| 027 | different_pronunciation_substitution | substitution | 1636 | 麻 | 1636 | 马 |
| 028 | same_pronunciation_substitution | substitution | 1684 | 刺 | 1684 | 次 |
| 029 | same_pronunciation_substitution | substitution | 1721 | 她 | 1721 | 他 |
| 029 | same_pronunciation_substitution | substitution | 1767 | 她 | 1767 | 他 |
| 030 | different_pronunciation_substitution | substitution | 1781 | 抿 | 1781 | 眯 |
| 030 | same_pronunciation_substitution | substitution | 1826 | 它 | 1826 | 她 |
| 031 | same_pronunciation_substitution | substitution | 1867 | 厉 | 1867 | 力 |
| 031 | same_pronunciation_substitution | substitution | 1890 | 泣 | 1890 | 气 |
| 031 | different_pronunciation_substitution | substitution | 1893 | 啜 | 1893 | 啰 |
| 031 | same_pronunciation_substitution | substitution | 1894 | 泣 | 1894 | 气 |
| 032 | same_pronunciation_substitution | substitution | 1923 | 腔 | 1923 | 枪 |
| 033 | same_pronunciation_substitution | substitution | 1993 | 词 | 1993 | 磁 |
| 033 | same_pronunciation_substitution | substitution | 1994 | 句 | 1994 | 具 |
| 033 | same_pronunciation_substitution | substitution | 2025 | 它 | 2025 | 她 |
| 033 | same_pronunciation_substitution | substitution | 2039 | 驯 | 2039 | 迅 |
| 034 | same_pronunciation_substitution | substitution | 2069 | 它 | 2069 | 她 |
| 034 | same_pronunciation_substitution | substitution | 2080 | 它 | 2080 | 她 |
| 034 | same_pronunciation_substitution | substitution | 2099 | 膜 | 2099 | 模 |
| 034 | different_pronunciation_substitution | substitution | 2100 | 中 | 2100 | 种 |
| 035 | same_pronunciation_substitution | substitution | 2101 | 它 | 2101 | 她 |
| 035 | same_pronunciation_substitution | substitution | 2110 | 鹿 | 2110 | 路 |
| 035 | same_pronunciation_substitution | substitution | 2111 | 角 | 2111 | 脚 |
| 035 | same_pronunciation_substitution | substitution | 2116 | 呵 | 2116 | 喝 |
| 035 | different_pronunciation_substitution | substitution | 2168 | 段 | 2168 | 端 |
| 036 | same_pronunciation_substitution | substitution | 2187 | 它 | 2187 | 她 |
| 036 | same_pronunciation_substitution | substitution | 2204 | 它 | 2204 | 她 |
| 036 | same_pronunciation_substitution | substitution | 2218 | 它 | 2218 | 她 |
| 037 | different_pronunciation_substitution | substitution | 2238 | 翕 | 2238 | 戏 |
| 037 | same_pronunciation_substitution | substitution | 2247 | 啸 | 2247 | 笑 |
| 038 | same_pronunciation_substitution | substitution | 2297 | 它 | 2297 | 他 |
| 038 | same_pronunciation_substitution | substitution | 2316 | 密 | 2316 | 蜜 |
| 038 | same_pronunciation_substitution | substitution | 2348 | 磕 | 2348 | 嗑 |
| 040 | same_pronunciation_substitution | substitution | 2404 | 皮 | 2404 | 脾 |
| 041 | different_pronunciation_substitution | substitution | 2465 | 视 | 2465 | 尸 |

## 双后端分歧与 ASR 健康门控

### IndexTTS2

- 仅 SenseVoice 报告的错误：58 项。
- 仅 Whisper-large-v3-turbo 报告的错误：41 项。
- 两后端共同报告的错误：36 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。

### VoxCPM2

- 仅 SenseVoice 报告的错误：67 项。
- 仅 Whisper-large-v3-turbo 报告的错误：63 项。
- 两后端共同报告的错误：31 项。
- 同段转写共识健康：`healthy`；分歧过大的片段：无。
