from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_minimax_voice_samples.py"
SPEC = importlib.util.spec_from_file_location("export_minimax_voice_samples", SCRIPT_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def test_format_asset_id_matches_requested_example() -> None:
    voice = {
        "voice_name": "活力旁白 - 清亮,抑扬顿挫,戏剧感染力",
        "tag_items": [{"category": 1, "name": "英语"}],
    }

    asset = exporter.build_voice_assets([voice], Path("samples"))[0]

    assert asset.asset_id == "v_en_077_活力旁白-清亮_抑扬顿挫_戏剧感染力"


def test_chinese_voice_uses_zh_prefix_and_starts_from_one() -> None:
    voice = {
        "voice_name": "沉稳高管 - 低沉厚实,磁性,从容不迫",
        "tag_items": [{"category": 1, "name": "中文-普通话"}],
    }

    asset = exporter.build_voice_assets([voice], Path("samples"))[0]

    assert asset.asset_id == "v_zh_001_沉稳高管-低沉厚实_磁性_从容不迫"


def test_hyphenated_english_name_keeps_name_separator() -> None:
    title = exporter.sanitize_voice_title("Gentle-voiced Man - 醇厚深沉,娓娓道来,极具故事感")

    assert title == "Gentle-voiced_Man-醇厚深沉_娓娓道来_极具故事感"


def test_write_voice_asset_outputs_metadata_files(tmp_path) -> None:
    voice = {
        "voice_name": "活力旁白 - 清亮,抑扬顿挫,戏剧感染力",
        "voice_id": "258951953674432",
        "uniq_id": "English_expressive_narrator",
        "tag_list": ["英语", "英语-英音", "男"],
        "tag_items": [{"category": 1, "name": "英语"}],
        "description": "这是一个充满活力的男声。",
        "sample_audio": "https://example.com/sample.mp3",
    }
    asset = exporter.build_voice_assets([voice], tmp_path)[0]
    asset.directory.mkdir(parents=True)
    (asset.directory / "asset.json").write_text("{}\n", encoding="utf-8")
    (asset.directory / "sample.url.txt").write_text("https://old.example.com/sample.mp3\n", encoding="utf-8")

    exporter.write_voice_asset(asset)

    readme = (asset.directory / "README.md").read_text(encoding="utf-8")

    assert (asset.directory / "README.md").is_file()
    assert json.loads((asset.directory / "voice.json").read_text(encoding="utf-8")) == voice
    assert not (asset.directory / "asset.json").exists()
    assert not (asset.directory / "sample.url.txt").exists()
    assert "# 活力旁白 - 清亮,抑扬顿挫,戏剧感染力" in readme
    assert "目录 ID" in readme
    assert "MiniMax 原始音色字段" in readme
