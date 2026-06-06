"""Write balanced controls for v_zh_010 funny elder sample synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_DIRECTORY = Path(
    "samples/generated/v_zh_010_搞笑大爷-沧桑醇厚_松弛接地气_幽默热心"
)

VOICE_PROMPT = (
    "中文-普通话男声，口音：中国北方。"
    "请优先还原 readme 中的核心定位：沧桑醇厚、略带沙哑、松弛接地气、幽默热心。"
    "音色目标：年长男性，声音低沉偏哑，喉部有轻微颗粒感，厚实但不要吼，"
    "保留 sample.2.wav 那种更像大爷的年长质感。"
    "语气目标：参考 sample.wav 的自然生活感，像晨练大爷和街坊慢慢聊天，"
    "自信、热心、带一点老顽童式幽默，但不要兴奋、夸张、端着播。"
    "速度和节奏目标：语速约 0.85x，比普通朗读慢；句中允许自然小停顿，"
    "句尾自然下沉，整体松弛、有烟火气，不要追求机械稳定。"
    "吐字自然可懂即可，不要为了清晰把声音变亮、变年轻、变尖，"
    "不要新闻播音腔、广告硬广腔、过度标准普通话腔或过强投射。"
    "保持干净人声，无背景音乐，无明显房间混响。"
)

CONTROLS = {
    "speed": 0.85,
    "pitch_semitones": -1.0,
    "volume_gain_db": 0.0,
    "emotion": "warm",
    "emotion_intensity": 0.5,
    "style": "character_dialogue",
    "style_degree": 0.65,
    "rhythm": "natural",
    "pause_profile": "long_form",
    "stability": 0.7,
    "similarity_boost": 0.88,
    "style_exaggeration": 0.16,
    "use_speaker_boost": False,
    "provider_overrides": {
        "voxcpm2": {
            "cfg_value": 1.45,
            "inference_timesteps": 12,
            "normalize": False,
            "source": str(DEFAULT_DIRECTORY / "voice.json"),
            "prompt_intent": (
                "平衡 sample.2.wav 的年长沧桑音色和 sample.wav 的慢速、松弛、"
                "生活化语气；避免亮嗓、年轻化和标准播报腔。"
            ),
        }
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="生成 v_zh_010 目录的 sample.controls.json 和 sample.voice.txt。"
    )
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    directory = args.directory
    if not directory.is_dir():
        raise SystemExit(f"目录不存在：{directory}")

    controls = dict(CONTROLS)
    controls["provider_overrides"] = json.loads(
        json.dumps(CONTROLS["provider_overrides"], ensure_ascii=False)
    )
    controls["provider_overrides"]["voxcpm2"]["source"] = str(directory / "voice.json")

    prompt_path = directory / "sample.voice.txt"
    controls_path = directory / "sample.controls.json"
    controls_text = json.dumps(controls, ensure_ascii=False, indent=2) + "\n"
    prompt_text = VOICE_PROMPT + "\n"

    if args.dry_run:
        print(f"--- {prompt_path} ---")
        print(prompt_text, end="")
        print(f"--- {controls_path} ---")
        print(controls_text, end="")
        return 0

    prompt_path.write_text(prompt_text, encoding="utf-8")
    controls_path.write_text(controls_text, encoding="utf-8")
    print(f"已写入 {prompt_path}")
    print(f"已写入 {controls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
