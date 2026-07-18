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
        text="三皇子大吃一惊，对辰南的身份开始胡乱猜疑起来，他咳嗽了一声，",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主_v3.wav",
        reference_text=reference_text("小公主"),
        text="认识，当然认识。",
    ),
    CloneCase(
        character="辰南",
        reference_audio=REPO_ROOT / "testData/mimo_辰南_v3.wav",
        reference_text=reference_text("辰南"),
        text="请公主殿下责罚。",
    ),
)
