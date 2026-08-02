"""兼容 task101.md 指定文件名的 MOSS-VoiceGenerator 入口。"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("tts_local_moss_voiceGenerator.py")), run_name="__main__")
