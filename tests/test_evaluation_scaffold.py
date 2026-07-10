"""验证评估目录的静态模板与数据契约可被基础工具读取。"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_evaluation_documents_exist() -> None:
    required_paths = [
        "评估步骤指南.md",
        "tts-bench/README.md",
        "tts-bench/datasets/README.md",
        "wavlm/README.md",
        "asr/README.md",
        "tts-prism-7b/README.md",
        "listener-review/README.md",
    ]

    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_json_contracts_and_example_manifest_are_parseable() -> None:
    contract_paths = [
        "tts-bench/contracts/benchmark-case.schema.json",
        "tts-bench/contracts/synthesis-record.schema.json",
        "tts-bench/contracts/metric-record.schema.json",
        "wavlm/contracts/similarity-record.schema.json",
        "asr/contracts/transcription-record.schema.json",
        "tts-prism-7b/contracts/diagnosis-record.schema.json",
        "listener-review/contracts/listener-review.schema.json",
    ]

    for relative_path in contract_paths:
        contract = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        assert contract["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert contract["type"] == "object"
        assert contract["required"]

    manifest_path = ROOT / "tts-bench/manifests/case.example.jsonl"
    cases = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    assert {case["split"] for case in cases} == {"calibration", "development", "holdout"}
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all(case["reference"]["transcript"] for case in cases)
    assert all(case["target"]["text"] for case in cases)


def test_prism_scales_and_listener_form_match_the_documented_contract() -> None:
    prism_contract = json.loads(
        (ROOT / "tts-prism-7b/contracts/diagnosis-record.schema.json").read_text(encoding="utf-8")
    )
    basic = prism_contract["properties"]["basic_capability"]["properties"]
    advanced = prism_contract["properties"]["advanced_expressiveness"]["properties"]

    assert {field["minimum"] for field in basic.values()} == {1}
    assert {field["maximum"] for field in basic.values()} == {5}
    assert {field["minimum"] for field in advanced.values()} == {0}
    assert {field["maximum"] for field in advanced.values()} == {2}

    with (ROOT / "listener-review/forms/review-form.example.csv").open(
        encoding="utf-8", newline=""
    ) as form_file:
        form = csv.DictReader(form_file)
        assert form.fieldnames is not None
        assert set(form.fieldnames) >= {
            "blind_id",
            "case_id",
            "rater_id",
            "naturalness",
            "timbre_similarity",
            "intelligibility",
            "style_appropriateness",
            "artifact_absence",
            "valid",
        }
