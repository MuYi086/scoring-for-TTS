"""Task 3 V2 集中克隆测试的固定角色用例。"""

from __future__ import annotations

from _clone_test_support import CloneCase, REPO_ROOT


OUTPUT_ROOT = REPO_ROOT / "cloneData" / "audio_v2"
REFERENCE_TEMPLATE = (
    "我是{character}，初次见面，请多多指教。正在进行声线校准测试。123，"
    "这段音频将作为我的基准音色，希望能完美演绎接下来的故事，请多关照。"
)


def reference_text(character: str) -> str:
    """返回三段同模板录音对应的校正参考文本。"""

    return REFERENCE_TEMPLATE.format(character=character)


CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白_v2.wav",
        reference_text=reference_text("旁白"),
        text="看着小恶魔那甜甜的微笑，他感觉身体一阵颤栗，他想挣扎，却动弹不得，想大声呼喊，却发不出声音，眨眼间，冷汗浸透了他的衣衫。",
    ),
    CloneCase(
        character="辰南",
        reference_audio=REPO_ROOT / "testData/mimo_辰南_v2.wav",
        reference_text=reference_text("辰南"),
        text="人为刀俎，我为鱼肉。刚刚出来游历，便要遭受这番悲惨遭遇，老天你不会在和我开玩笑吧？",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v2.wav",
        reference_text=reference_text("小公主"),
        text="你们说，当我把烈火仙莲献给我父皇之后，他会是什么表情？嗯，我猜他一定会笑的合不拢嘴，允许我以后自由出入皇城。呵呵，真是太好了，以后我想到哪里玩，就到哪里玩，再也没有人会阻止我了，呵呵……",
    ),
)
