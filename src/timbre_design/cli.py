"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from timbre_design.assets import (
    DEFAULT_ASSET_ROOT,
    DEFAULT_SAMPLE_TEXT,
    VoiceAssetBundle,
    convert_wav_to_mp3,
    synthesize_voice_asset,
    voice_asset_paths,
    write_voice_asset_bundle,
)
from timbre_design.casting import build_voice_casting
from timbre_design.controls import render_voxcpm2_prompt
from timbre_design.library import VoiceLibrary, load_voice_library
from timbre_design.matcher import CharacterProfile, load_character_profiles, match_voice
from timbre_design.models import Voice
from timbre_design.voxcpm import synthesize_with_voxcpm2


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="timbre-design")
    parser.add_argument("--library", type=Path, help="音色库 JSON；默认使用内置 voices_v2_96.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="校验音色库")
    validate.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    validate.set_defaults(func=cmd_validate)

    list_cmd = subparsers.add_parser("list", help="列出音色")
    list_cmd.add_argument("--group", help="按 group 过滤")
    list_cmd.add_argument("--species", help="按 species 过滤")
    list_cmd.add_argument("--gender", help="按 gender 过滤")
    list_cmd.add_argument("--limit", type=int, default=30)
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    match = subparsers.add_parser("match", help="为角色匹配音色")
    match.add_argument("--character-json", type=Path, help="角色 JSON 文件")
    match.add_argument("--name", help="角色名")
    match.add_argument("--gender", default="unknown")
    match.add_argument("--age", default="unknown")
    match.add_argument("--species", default="human")
    match.add_argument("--hint", default="", help="音色/性格提示")
    match.add_argument("--top", type=int, default=5)
    match.add_argument("--json", action="store_true")
    match.set_defaults(func=cmd_match)

    prompt = subparsers.add_parser("prompt", help="输出指定 voice_id 的 VoxCPM2 控制提示")
    prompt.add_argument("voice_id")
    prompt.add_argument("--context", default="", help="角色上下文")
    prompt.add_argument("--output", type=Path)
    prompt.set_defaults(func=cmd_prompt)

    cast = subparsers.add_parser("cast", help="从 characters.json 生成 voice-casting.json")
    cast.add_argument("--characters", type=Path, required=True)
    cast.add_argument("--output", type=Path, required=True)
    cast.add_argument("--provider", default="voxcpm2-local")
    cast.add_argument("--dedicated-limit", type=int, default=12)
    cast.set_defaults(func=cmd_cast)

    synth = subparsers.add_parser("synthesize", help="调用本地 VoxCPM2 生成样例音频")
    synth.add_argument("--voice-id", required=True)
    synth.add_argument("--text-file", type=Path, required=True)
    synth.add_argument("--output-wav", type=Path, required=True)
    synth.add_argument("--command", help="覆盖 TIMBRE_VOXCPM2_COMMAND")
    synth.set_defaults(func=cmd_synthesize)

    assets = subparsers.add_parser("assets", help="生成一音色一目录的试听资产")
    assets.add_argument("--output-dir", type=Path, default=DEFAULT_ASSET_ROOT)
    assets.add_argument("--voice-id", action="append", dest="voice_ids", help="指定音色；可重复")
    assets.add_argument("--group", help="按 group 过滤")
    assets.add_argument("--species", help="按 species 过滤")
    assets.add_argument("--gender", help="按 gender 过滤")
    assets.add_argument("--limit", type=int, help="限制生成数量")
    assets.add_argument("--text-file", type=Path, help="试听文本；默认使用内置短句")
    assets.add_argument("--synthesize", action="store_true", help="调用 VoxCPM2 生成 sample.wav")
    assets.add_argument("--mp3", action="store_true", help="生成或转换 sample.mp3")
    assets.add_argument("--command", help="覆盖 TIMBRE_VOXCPM2_COMMAND")
    assets.add_argument("--mp3-command", help="覆盖 TIMBRE_AUDIO_CONVERT_COMMAND")
    assets.add_argument("--no-overwrite", action="store_true", help="保留已有元数据文件")
    assets.add_argument("--json", action="store_true")
    assets.set_defaults(func=cmd_assets)
    return parser


def cmd_validate(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    errors = library.validate()
    payload = {"ok": not errors, "summary": library.summary(), "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print("音色库校验失败：")
        for error in errors:
            print(f"- {error}")
    else:
        summary = library.summary()
        print(f"音色库校验通过：version={summary['version']} total={summary['total_voices']}")
    if errors:
        raise SystemExit(1)


def cmd_list(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    voices = library.filter(
        group=args.group,
        species=args.species,
        gender=args.gender,
    )[: args.limit]
    if args.json:
        print(json.dumps([voice.to_dict() for voice in voices], ensure_ascii=False, indent=2))
        return
    for voice in voices:
        print(
            f"{voice.voice_id}\t{voice.group}\t{voice.profile.gender}/"
            f"{voice.profile.age_band}/{voice.profile.species}\t{','.join(voice.fit_roles)}"
        )


def cmd_match(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    character = _load_single_character(args)
    matches = match_voice(character, library, top_k=args.top)
    if args.json:
        print(json.dumps([match.to_dict() for match in matches], ensure_ascii=False, indent=2))
        return
    for match in matches:
        print(f"{match.voice.voice_id}\tscore={match.score:.3f}\t{','.join(match.reasons)}")


def cmd_prompt(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    voice = library.get(args.voice_id)
    prompt = render_voxcpm2_prompt(voice, extra_context=args.context)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt + "\n", encoding="utf-8")
    else:
        print(prompt)


def cmd_cast(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    payload = _read_json(args.characters)
    characters = load_character_profiles(payload)
    casting = build_voice_casting(
        characters,
        library,
        provider=args.provider,
        dedicated_limit=args.dedicated_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(casting, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已写入 {args.output}")


def cmd_synthesize(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    voice = library.get(args.voice_id)
    text = args.text_file.read_text(encoding="utf-8")
    synthesize_with_voxcpm2(
        command=args.command,
        text=text,
        voice=voice,
        output_wav=args.output_wav,
    )
    print(f"已生成 {args.output_wav}")


def cmd_assets(args: argparse.Namespace) -> None:
    library = load_voice_library(args.library)
    voices = _select_asset_voices(args, library)
    if not voices:
        raise ValueError("没有匹配到需要生成资产的音色")
    sample_text = (
        args.text_file.read_text(encoding="utf-8") if args.text_file else DEFAULT_SAMPLE_TEXT
    )
    overwrite = not args.no_overwrite
    results: list[VoiceAssetBundle] = []
    for voice in voices:
        if args.synthesize:
            bundle = synthesize_voice_asset(
                voice,
                args.output_dir,
                sample_text=sample_text,
                command=args.command,
                make_mp3=args.mp3,
                mp3_command=args.mp3_command,
                overwrite=overwrite,
            )
        else:
            bundle = write_voice_asset_bundle(
                voice,
                args.output_dir,
                sample_text=sample_text,
                overwrite=overwrite,
            )
            if args.mp3:
                paths = voice_asset_paths(args.output_dir, voice.voice_id)
                convert_wav_to_mp3(
                    paths.wav,
                    paths.mp3,
                    command=args.mp3_command,
                    voice_id=voice.voice_id,
                )
                bundle = VoiceAssetBundle(
                    voice_id=bundle.voice_id,
                    paths=bundle.paths,
                    files=(*bundle.files, paths.mp3),
                )
        results.append(bundle)
    if args.json:
        print(json.dumps([bundle.to_dict() for bundle in results], ensure_ascii=False, indent=2))
        return
    for bundle in results:
        print(f"已生成 {bundle.voice_id}\t{bundle.directory}")


def _load_single_character(args: argparse.Namespace) -> CharacterProfile:
    if args.character_json:
        payload = _read_json(args.character_json)
        characters = load_character_profiles(payload)
        if not characters:
            raise ValueError("角色 JSON 中没有可用角色")
        return characters[0]
    if not args.name:
        raise ValueError("match 需要 --character-json 或 --name")
    return CharacterProfile(
        character_id=args.name,
        display_name=args.name,
        gender_group=args.gender,
        age_group=args.age,
        species=args.species,
        voice_style_hint=args.hint,
    )


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _select_asset_voices(args: argparse.Namespace, library: VoiceLibrary) -> list[Voice]:
    if args.voice_ids:
        voices = [library.get(voice_id) for voice_id in args.voice_ids]
    else:
        voices = library.filter(group=args.group, species=args.species, gender=args.gender)
    if args.limit is not None:
        voices = voices[: args.limit]
    return voices
