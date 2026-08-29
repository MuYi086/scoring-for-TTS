"""训练文本教师模型流水线的无模型回归测试。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "training" / "script"
sys.path.insert(0, str(SCRIPT_DIR))
try:
    import step_1_prepare_stories as step_1
    import step_2_analyze_stories as step_2
    import step_3_rewrite_stories as step_3
    import step_4_review_rewrites as step_4
    import step_6_export_datasets as step_6
    import step_7_prepare_blind_test as step_7
    import step_8_prepare_llamafactory as step_8
finally:
    sys.path.remove(str(SCRIPT_DIR))


SOURCE_ID_TRAIN = "story_0123456789abcdef"
SOURCE_ID_BLIND = "story_fedcba9876543210"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class TrainingModelPipelineTests(unittest.TestCase):
    def test_clean_markdown_removes_deterministic_noise_but_preserves_story(self):
        source = """# 雨夜来客

![](images/cover.jpg)
编辑部地址：哈尔滨市某街
张明说：“门外有人。”

张明说：“门外有人。”
王兰问：“你确定吗？”
"""

        cleaned = step_1.clean_markdown(source)

        self.assertIn("雨夜来客", cleaned)
        self.assertIn("张明说", cleaned)
        self.assertIn("王兰问", cleaned)
        self.assertNotIn("images/cover", cleaned)
        self.assertNotIn("编辑部地址", cleaned)
        self.assertEqual(cleaned.count("张明说"), 2)

    def test_inventory_only_collects_collection_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            (input_dir / "说明.md").write_text("说明", encoding="utf-8")
            collection = input_dir / "刊物"
            collection.mkdir()
            (collection / "一期.md").write_text("# 故事\n正文", encoding="utf-8")
            scripts = input_dir / "script"
            scripts.mkdir()
            (scripts / "README.md").write_text("脚本", encoding="utf-8")

            paths = step_1.collect_markdown_files(input_dir)

            self.assertEqual([path.name for path in paths], ["一期.md"])

    def test_prepare_stories_requires_boundaries_and_preserves_rights_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "training"
            collection = input_dir / "刊物"
            collection.mkdir(parents=True)
            source = collection / "一期.md"
            source.write_text(
                "# 完整故事\n![](images/a.jpg)\n张明说门外有人。\n王兰问他是谁。\n结局揭晓。\n",
                encoding="utf-8",
            )
            boundary_manifest = root / "boundaries.jsonl"
            step_1.write_jsonl(
                boundary_manifest,
                [
                    {
                        "source_path": "刊物/一期.md",
                        "title": "完整故事",
                        "start_line": 1,
                        "end_line": 5,
                        "boundary_status": "approved",
                        "rights_status": step_1.APPROVED_RIGHTS_STATUS,
                        "split": "auto",
                    }
                ],
            )
            work_dir = root / "work"

            records = step_1.prepare_stories(
                input_dir,
                work_dir,
                boundary_manifest,
                min_chars=10,
                max_chars=1000,
                blind_count=1,
                validation_count=0,
                simhash_threshold=3,
                dry_run=False,
            )

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["eligible_for_cloud"])
            self.assertEqual(records[0]["split"], "blind")
            story_text = (work_dir / records[0]["story_path"]).read_text(encoding="utf-8")
            self.assertNotIn("images/a.jpg", story_text)
            self.assertIn("结局揭晓", story_text)

    def test_codex_command_is_ephemeral_read_only_and_schema_constrained(self):
        command = step_1.codex_command(
            prompt="处理故事",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            schema_path=Path("schema.json"),
            output_path=Path("output.json"),
        )

        self.assertIn("--ephemeral", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-terra")
        self.assertIn("--output-schema", command)
        self.assertIn('model_reasoning_effort="high"', command)

    def test_cloud_selection_rejects_unknown_rights(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "stories.jsonl"
            approved = story_record(SOURCE_ID_TRAIN, "train")
            unknown = story_record(SOURCE_ID_BLIND, "blind")
            unknown["rights_status"] = "unknown"
            unknown["eligible_for_cloud"] = False
            step_1.write_jsonl(manifest, [approved, unknown])

            selected = step_1.eligible_story_records(manifest)

            self.assertEqual([record["source_id"] for record in selected], [SOURCE_ID_TRAIN])

    def test_approved_boundary_ranges_must_not_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "training"
            collection = input_dir / "刊物"
            collection.mkdir(parents=True)
            (collection / "一期.md").write_text("一\n二\n三\n四\n五\n", encoding="utf-8")
            boundaries = root / "boundaries.jsonl"
            step_1.write_jsonl(
                boundaries,
                [
                    boundary_record(1, 3, "第一篇"),
                    boundary_record(3, 5, "第二篇"),
                ],
            )

            with self.assertRaisesRegex(step_1.PipelineError, "边界重叠"):
                step_1.prepare_stories(
                    input_dir,
                    root / "work",
                    boundaries,
                    min_chars=1,
                    max_chars=100,
                    blind_count=0,
                    validation_count=0,
                    simhash_threshold=3,
                    dry_run=True,
                )

    def test_approved_record_must_bind_reviewed_output_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            approvals = Path(directory) / "approvals.jsonl"
            step_1.write_jsonl(
                approvals,
                [
                    {
                        "source_id": SOURCE_ID_TRAIN,
                        "decision": "approved",
                        "reviewer": "tester",
                    }
                ],
            )

            with self.assertRaisesRegex(step_1.PipelineError, "output_sha256"):
                step_6.load_approvals(approvals)

    def test_stage_validators_and_gate_reject_director_tags_and_weak_pass(self):
        rewrite = {
            "source_id": SOURCE_ID_TRAIN,
            "input_sha256": "a" * 64,
            "output_b": "[SFX: 雷声]张明推开门。",
            "quality_flags": [],
            "needs_human_review": False,
        }
        with self.assertRaisesRegex(step_1.PipelineError, "禁用标签"):
            step_3.validate_rewrite(rewrite, SOURCE_ID_TRAIN, "a" * 64)

        review = valid_review(SOURCE_ID_TRAIN)
        review["factual_consistency"] = 0.90
        self.assertEqual(step_4.deterministic_gate(review)["decision"], "revise")

    def test_export_matches_local_easy_dataset_and_protects_blind_split(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory) / "work"
            records = [
                story_record(SOURCE_ID_TRAIN, "train"),
                story_record(SOURCE_ID_BLIND, "blind"),
            ]
            step_1.write_jsonl(work_dir / "stories.jsonl", records)
            for record in records:
                source_id = record["source_id"]
                story_path = work_dir / record["story_path"]
                story_path.parent.mkdir(parents=True, exist_ok=True)
                story_path.write_text("张明在雨夜推开门，最终发现真相。\n", encoding="utf-8")
                write_json(
                    work_dir / "rewrites" / "teacher" / f"{source_id}.json",
                    valid_rewrite(source_id),
                )
                review = valid_review(source_id)
                review["_deterministic_gate"] = step_4.deterministic_gate(review)
                write_json(
                    work_dir / "reviews" / "teacher" / f"{source_id}.json",
                    review,
                )
            approvals = work_dir / "approvals.jsonl"
            step_1.write_jsonl(
                approvals,
                [
                    {
                        "source_id": SOURCE_ID_TRAIN,
                        "decision": "approved",
                        "reviewer": "tester",
                        "split": "train",
                        "output_sha256": step_1.sha256_text(
                            valid_rewrite(SOURCE_ID_TRAIN)["output_b"]
                        ),
                    },
                    {
                        "source_id": SOURCE_ID_BLIND,
                        "decision": "approved",
                        "reviewer": "tester",
                        "split": "blind",
                        "output_sha256": step_1.sha256_text(
                            valid_rewrite(SOURCE_ID_BLIND)["output_b"]
                        ),
                    },
                ],
            )

            exit_code = step_6.main(
                [
                    "--work-dir",
                    str(work_dir),
                    "--approval-manifest",
                    str(approvals),
                    "--max-estimated-tokens",
                    "1000",
                ]
            )

            self.assertEqual(exit_code, 0)
            exported = json.loads(
                (work_dir / "exports" / "sharegpt_train.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(exported), 1)
            self.assertEqual(
                [message["role"] for message in exported[0]["messages"]],
                ["system", "user", "assistant"],
            )
            dataset_info = json.loads(
                (work_dir / "exports" / "dataset_info.json").read_text(encoding="utf-8")
            )
            tags = dataset_info["audio_polisher_train"]["tags"]
            self.assertEqual(tags["role_tag"], "role")
            report = json.loads(
                (work_dir / "exports" / "export_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["train_count"], 1)
            self.assertEqual(report["protected_story_count"], 1)

    def test_blind_codes_are_deterministic_and_do_not_expose_variant(self):
        first = step_7.anonymous_code("seed", SOURCE_ID_BLIND, "terra_high")
        second = step_7.anonymous_code("seed", SOURCE_ID_BLIND, "terra_high")

        self.assertEqual(first, second)
        self.assertNotIn("TERRA", first)

    def test_llamafactory_config_uses_qwen35_nothink_qlora(self):
        config = step_8.training_yaml(
            model_name_or_path="Qwen/Qwen3.5-9B",
            dataset_dir=Path("/tmp/data"),
            output_dir=Path("/tmp/output"),
            cutoff_len=8192,
            has_validation=True,
        )

        self.assertIn("quantization_bit: 4", config)
        self.assertIn("quantization_method: bnb", config)
        self.assertIn("template: qwen3_5_nothink", config)
        self.assertIn("enable_thinking: false", config)
        self.assertIn("eval_dataset: audio_polisher_validation", config)

    def test_all_codex_schemas_are_valid_json_objects(self):
        schema_dir = SCRIPT_DIR / "schemas"
        for schema_path in sorted(schema_dir.glob("*.schema.json")):
            with self.subTest(schema=schema_path.name):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])


def story_record(source_id: str, split: str) -> dict:
    return {
        "source_id": source_id,
        "title": source_id,
        "source_path": f"刊物/{source_id}.md",
        "story_path": f"stories/{source_id}.md",
        "sha256": "a" * 64,
        "rights_status": step_1.APPROVED_RIGHTS_STATUS,
        "eligible_for_cloud": True,
        "duplicate_of": None,
        "split": split,
    }


def boundary_record(start_line: int, end_line: int, title: str) -> dict:
    return {
        "source_path": "刊物/一期.md",
        "title": title,
        "start_line": start_line,
        "end_line": end_line,
        "boundary_status": "approved",
        "rights_status": step_1.APPROVED_RIGHTS_STATUS,
        "split": "train",
    }


def valid_rewrite(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "input_sha256": "a" * 64,
        "output_b": "雨夜里，张明推开门，最终发现了真相。",
        "quality_flags": [],
        "needs_human_review": False,
    }


def valid_review(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "factual_consistency": 0.98,
        "audio_readability": 0.92,
        "suspense_preservation": 0.90,
        "problems": [],
        "decision": "pass",
    }


if __name__ == "__main__":
    unittest.main()
