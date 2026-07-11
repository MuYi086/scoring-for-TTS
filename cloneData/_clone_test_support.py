"""集中克隆测试共用的固定角色用例。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "cloneData"


@dataclass(frozen=True)
class CloneCase:
    """一个用于不同 TTS 模型横向比较的固定克隆用例。"""

    character: str
    reference_audio: Path
    reference_text: str
    text: str


CASES = (
    CloneCase(
        character="旁白",
        reference_audio=REPO_ROOT / "testData/mimo_旁白.wav",
        reference_text="我是旁白，初次见面，请多多指教。正在进行声线校准测试。123，这段音频将作为我的基准音色，希望能完美演绎接下来的故事，请多关照。",
        text="小公主手下的侍卫紧张无比，其中一个见习魔法师道：",
    ),
    CloneCase(
        character="小公主",
        reference_audio=REPO_ROOT / "testData/mimo_小公主.wav",
        reference_text="我是小公主，初次见面，请多多指教。正在进行声线校准测试。123，这段音频将作为我的基准音色，希望能完美演绎接下来的故事，请多关照。",
        text="当然有，你们是不是害怕了？",
    ),
    CloneCase(
        character="见习魔法师",
        reference_audio=REPO_ROOT / "testData/mimo_见习魔法师.wav",
        reference_text="我是见习魔法师，初次见面，请多多指教。正在进行声线校准测试。123，这段音频将作为我的基准音色，希望能完美演绎接下来的故事，请多关照。",
        text="公主殿下，火山口真的有烈火仙莲吗？",
    ),
)


def selected_cases(characters: list[str] | None) -> tuple[CloneCase, ...]:
    """按声明顺序返回用户选择的角色；未选择时返回全部。"""

    if not characters:
        return CASES
    requested = set(characters)
    return tuple(case for case in CASES if case.character in requested)
