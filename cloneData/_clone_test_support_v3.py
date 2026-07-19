"""Task 4 V3 集中克隆测试的固定角色用例。"""

from __future__ import annotations

from _clone_test_support import CloneCase, REPO_ROOT


OUTPUT_ROOT = REPO_ROOT / "cloneData" / "audio_v3"
REFERENCE_TEMPLATE = (
    "我是{character}，初次见面，请多多指教。正在进行声线校准测试。123，"
    "这段音频将作为我的基准音色，希望能完美演绎接下来的故事，请多关照。"
)


def reference_text(character: str) -> str:
    """返回已经 SenseVoice 转写并按同模板录音校正的参考文本。"""

    return REFERENCE_TEMPLATE.format(character=character)


CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白_v3.wav",
        reference_text=reference_text("旁白"),
        text="小公主恶狠狠的盯着他，其中的意思再明显不过，威胁兼恐吓让他配合。",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v3.wav",
        reference_text=reference_text("小公主"),
        text="他是从我宫内带出来的小太监，本来是出来伺候我的，没想到遇上远古巨人时，他第一个就跑了。小李子你没想到会这么快见到我吧？",
    ),
    CloneCase(
        character="三皇子",
        reference_audio=REPO_ROOT / "testData/mimo_三皇子_v3.wav",
        reference_text=reference_text("三皇子"),
        text="这个人在路上一直鬼鬼祟祟地跟在我们后面，后来被我的手下抓住了，公主殿下认识这个人吗？",
    ),
)
