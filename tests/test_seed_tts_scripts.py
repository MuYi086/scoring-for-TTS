from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "Seed-TTS-test" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_seed_tts_report as report  # noqa: E402
import seed_tts_runner as runner  # noqa: E402


def write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 160)


def test_parse_meta_list_preserves_official_fields(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "zh" / "prompt-wavs"
    prompt_dir.mkdir(parents=True)
    write_wav(prompt_dir / "p.wav")
    (tmp_path / "zh" / "meta.lst").write_text("utt-1|参考文本|prompt-wavs/p.wav|目标文本\n", encoding="utf-8")

    items = runner.parse_meta_list(tmp_path, "meta", "zh/meta.lst")

    assert items == [runner.SeedItem("meta", "utt-1", "参考文本", prompt_dir / "p.wav", "目标文本")]


def test_parse_meta_list_rejects_unsafe_utt(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "zh" / "prompt-wavs"
    prompt_dir.mkdir(parents=True)
    write_wav(prompt_dir / "p.wav")
    (tmp_path / "zh" / "meta.lst").write_text("../bad|参考|prompt-wavs/p.wav|目标\n", encoding="utf-8")

    with pytest.raises(runner.SeedTtsError, match="utt 非法"):
        runner.parse_meta_list(tmp_path, "meta", "zh/meta.lst")


def test_item_seed_is_stable_and_utt_specific() -> None:
    assert runner.stable_item_seed(42, "same") == runner.stable_item_seed(42, "same")
    assert runner.stable_item_seed(42, "one") != runner.stable_item_seed(42, "two")


def test_model_config_has_exactly_seven_independent_launchers() -> None:
    config = runner.load_json(runner.CONFIG_PATH)
    assert set(config["models"]) == set(runner.BACKENDS)
    for model_id in config["models"]:
        launcher = SCRIPTS_DIR / f"run_{model_id}.sh"
        assert launcher.is_file()
        assert "TTS-and-VoiceDesign" not in launcher.read_text(encoding="utf-8")
    assert config["models"]["indextts2"]["runtime_distribution"] == "indextts"
    assert config["models"]["longcat_audiodit"]["output_dir"] == "longCat"
    assert config["models"]["omnivoice"]["output_dir"] == "omniVoice"
    assert config["models"]["qwen3_tts"]["required_executable_env"] == "SEED_TTS_QWEN3_SOX_BIN"
    assert (SCRIPTS_DIR / "prepare_indextts2_environment.sh").is_file()


def test_report_parsers_require_exact_raw_coverage(tmp_path: Path) -> None:
    wer_path = tmp_path / "meta.wer.tsv"
    wer_path.write_text(
        "utt\twav_res\tres_wer\ttext_ref\ttext_res\tres_wer_ins\tres_wer_del\tres_wer_sub\n"
        "a.wav\t0.1\t甲\t甲\t0\t0\t0\n"
        "b.wav\t0.2\t乙\t乙\t0\t0\t0\n"
        "WER: 15.0%\n",
        encoding="utf-8",
    )
    sim_path = tmp_path / "meta.sim.tsv"
    sim_path.write_text("a|r\t0.8\nb|r\t0.9\nASV: 0.85\nASV-var: 0.003\n", encoding="utf-8")

    assert report.parse_wer(wer_path, 2) == (15.0, 2)
    assert report.parse_sim(sim_path, 2) == (0.85, 0.003, 2)
    with pytest.raises(runner.SeedTtsError):
        report.parse_sim(sim_path, 3)


def test_frozen_patch_declares_only_required_compatibility_changes() -> None:
    content = (SCRIPTS_DIR / "patches" / "0001-seed-tts-local-offline.patch").read_text(encoding="utf-8")
    assert "SEED_TTS_PARAFORMER_DIR" in content
    assert "sudo split" in content
    assert "select_speakers.py" in content
    assert "prepare_ckpt.py" in content
