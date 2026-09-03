"""训练文本教师模型流水线的无模型回归测试。"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "training" / "script"
sys.path.insert(0, str(SCRIPT_DIR))
try:
    import step_0_plan_sources as step_0
    import step_1_prepare_stories as step_1
    import step_2_analyze_stories as step_2
    import step_2_auto_resolve_boundaries as step_2b
    import step_3_rewrite_stories as step_3
    import step_4_review_rewrites as step_4
    import step_5_adjudicate_stories as step_5
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


def frozen_source_record(source_root: Path, source: Path, split: str = "train"):
    content = source.read_bytes()
    text = content.decode("utf-8")
    collection = source.relative_to(source_root).parts[0]
    return {
        "source_path": source.relative_to(source_root).as_posix(),
        "source_collection": collection,
        "source_group": f"{collection}:test:{source.stem}",
        "year": None,
        "split": split,
        "sha256": step_0.sha256_bytes(content),
        "bytes": len(content),
        "line_count": len(text.splitlines()),
        "heading_count": len(step_1.heading_candidates(text)),
    }


class TrainingModelPipelineTests(unittest.TestCase):
    def test_auto_boundary_repair_requires_exact_safe_suggestion(self):
        repair = {
            "source_id": SOURCE_ID_TRAIN,
            "source_path": "刊物/一期.md",
            "current_start_line": 10,
            "current_end_line": 40,
            "suggested_start_line": 8,
            "suggested_end_line": 38,
        }
        approved = {
            "source_id": SOURCE_ID_TRAIN,
            "decision": "approve",
            "start_line": 8,
            "end_line": 38,
            "confidence": 0.95,
            "rationale": "完整且无相邻内容。",
            "unresolved_risks": [],
        }
        step_2b.validate_decision(approved, repair)
        unsafe = {**approved, "end_line": 39}
        with self.assertRaisesRegex(step_1.PipelineError, "精确连续范围"):
            step_2b.validate_decision(unsafe, repair)
        rejected = {**approved, "decision": "reject", "start_line": None, "end_line": None}
        step_2b.validate_decision(rejected, repair)

    def test_auto_boundary_repair_skips_unchanged_ranges(self):
        self.assertFalse(
            step_2b.repair_has_changed_range(
                {
                    "current_start_line": 10,
                    "current_end_line": 20,
                    "suggested_start_line": 10,
                    "suggested_end_line": None,
                }
            )
        )
    def test_step_1_auto_boundary_dry_run_reports_success_without_writing(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            root = Path(directory)
            input_dir = root / "training"
            collection = input_dir / "刊物"
            collection.mkdir(parents=True)
            (collection / "一期.md").write_text(
                "# 雨夜来客\n门外传来敲门声。\n",
                encoding="utf-8",
            )
            work_dir = root / "work"
            source_manifest = root / "selected_sources.jsonl"
            step_1.write_jsonl(
                source_manifest,
                [frozen_source_record(input_dir, collection / "一期.md")],
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = step_1.main(
                    [
                        "--input-dir",
                        str(input_dir),
                        "--source-manifest",
                        str(source_manifest),
                        "--work-dir",
                        str(work_dir),
                        "--auto-boundaries",
                        "--dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("正式运行命令预览（仅展示，本次未执行）", output.getvalue())
            self.assertIn("Step 1a 检查通过（退出码 0）", output.getvalue())
            self.assertFalse(work_dir.exists())

    def test_step_1_dry_run_reports_manual_package_before_existing_terra_result(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            root = Path(directory)
            input_dir = root / "training"
            source_file = input_dir / "刊物" / "一期.md"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("# 待复核故事\n正文。\n", encoding="utf-8")
            work_dir = root / "work"
            source_manifest = root / "selected_sources.jsonl"
            step_1.write_jsonl(
                source_manifest,
                [frozen_source_record(input_dir, source_file)],
            )
            relative = source_file.relative_to(input_dir).as_posix()
            review_name = step_1.source_detection_name(relative)
            source_text = source_file.read_text(encoding="utf-8")
            detection = {
                "source_path": relative,
                "source_sha256": step_1.sha256_text(source_text),
                "line_count": len(source_text.splitlines()),
                "stories": [],
                "document_notes": "没有可自动批准的边界",
                "_provenance": {
                    "input_sha256": step_1.sha256_text(source_text),
                    "model": "gpt-5.6-luna",
                },
            }
            step_1.write_json(work_dir / "boundary_detection" / review_name, detection)
            reviewed = {
                **detection,
                "_provenance": {
                    "input_sha256": detection["source_sha256"],
                    "model": "gpt-5.6-terra",
                },
            }
            step_1.write_json(
                work_dir / "boundary_detection_review" / review_name,
                reviewed,
            )
            package_path = (
                work_dir
                / "manual_escalation"
                / "step_1"
                / f"{Path(review_name).stem}.md"
            )
            package_path.parent.mkdir(parents=True)
            package_path.write_text("# 人工 Sol 升级\n", encoding="utf-8")
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = step_1.main(
                    [
                        "--input-dir",
                        str(input_dir),
                        "--source-manifest",
                        str(source_manifest),
                        "--work-dir",
                        str(work_dir),
                        "--auto-boundaries",
                        "--resolve-ambiguous",
                        "--dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "Terra 边界复核：已完成 0/1；自动待处理 0；等待人工 Sol 1",
                output.getvalue(),
            )
            self.assertIn("下一步：处理 Step 1d 人工 Sol 升级包", output.getvalue())

    def test_step_0_selects_balanced_reproducible_four_way_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory) / "原始资源"
            collections = ("怖客", "猛鬼杂志故事", "男生女生金版", "悚族")
            for collection in collections:
                collection_dir = source_root / collection
                collection_dir.mkdir(parents=True)
                for index in range(8):
                    (collection_dir / f"{collection}20{index + 10:02d}年01月.md").write_text(
                        f"# {collection}-{index}\n正文\n",
                        encoding="utf-8",
                    )

            inventory = step_0.collect_source_inventory(source_root, collections)
            first = step_0.build_plan(
                inventory,
                dataset_version="test-v1",
                collections=collections,
                per_collection=4,
                quotas={"train": 1, "validation": 1, "blind": 1, "test": 1},
                seed=7,
            )
            second = step_0.build_plan(
                inventory,
                dataset_version="test-v1",
                collections=collections,
                per_collection=4,
                quotas={"train": 1, "validation": 1, "blind": 1, "test": 1},
                seed=7,
            )

            self.assertEqual(first[1], second[1])
            self.assertEqual(first[2]["plan_sha256"], second[2]["plan_sha256"])
            self.assertEqual(first[2]["selected_source_count"], 16)
            self.assertEqual(
                first[2]["split_counts"],
                {"train": 4, "validation": 4, "blind": 4, "test": 4},
            )
            self.assertEqual(len({record["source_group"] for record in first[1]}), 16)

    def test_step_0_parses_two_digit_months_without_collapsing_to_january(self):
        groups = {
            step_0.source_group_id("怖客", f"怖客2011年{month}月.md")[0]
            for month in ("01", "10", "11", "12")
        }

        self.assertEqual(
            groups,
            {
                "怖客:issue:2011-01",
                "怖客:issue:2011-10",
                "怖客:issue:2011-11",
                "怖客:issue:2011-12",
            },
        )

    def test_frozen_source_manifest_rejects_content_drift_and_cross_split_group(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory) / "原始资源"
            collection = source_root / "怖客"
            collection.mkdir(parents=True)
            first = collection / "一期.md"
            second = collection / "二期.md"
            first.write_text("# 一期\n正文\n", encoding="utf-8")
            second.write_text("# 二期\n正文\n", encoding="utf-8")
            records = [
                frozen_source_record(source_root, first, "train"),
                frozen_source_record(source_root, second, "test"),
            ]
            records[1]["source_group"] = records[0]["source_group"]
            manifest = Path(directory) / "selected_sources.jsonl"
            step_1.write_jsonl(manifest, records)

            with self.assertRaisesRegex(step_1.PipelineError, "source_group 跨集合"):
                step_1.load_frozen_sources(source_root, manifest)

            records[1]["source_group"] = "怖客:test:二期"
            step_1.write_jsonl(manifest, records)
            first.write_text("# 一期\n内容已经变化\n", encoding="utf-8")
            with self.assertRaisesRegex(step_1.PipelineError, "内容已变化"):
                step_1.load_frozen_sources(source_root, manifest)

    def test_pilot_selection_uses_one_training_source_per_collection(self):
        sources = []
        for collection in ("甲", "乙", "丙", "丁"):
            for split in ("validation", "train"):
                sources.append(
                    step_1.FrozenSource(
                        path=Path(f"/{collection}/{split}.md"),
                        source_path=f"{collection}/{split}.md",
                        source_collection=collection,
                        source_group=f"{collection}:{split}",
                        source_year=None,
                        split=split,
                        sha256="a" * 64,
                        bytes=1,
                        line_count=1,
                        heading_count=0,
                    )
                )

        selected = step_1.limit_pilot_sources(sources, 1)

        self.assertEqual(len(selected), 4)
        self.assertEqual({source.source_collection for source in selected}, {"甲", "乙", "丙", "丁"})
        self.assertEqual({source.split for source in selected}, {"train"})

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

    def test_automatic_boundary_records_accept_complete_fiction_and_queue_uncertain(self):
        source_text = "# 完整故事\n" + ("这是悬疑故事正文。" * 120) + "\n结局揭晓。\n"
        line_count = len(source_text.splitlines())
        detection = {
            "source_path": "刊物/一期.md",
            "source_sha256": step_1.sha256_text(source_text),
            "line_count": line_count,
            "stories": [
                {
                    "title": "完整故事",
                    "start_line": 1,
                    "end_line": line_count,
                    "confidence": 0.95,
                    "completeness": "complete",
                    "content_kind": "fiction",
                    "target_genre": True,
                    "reason": "标题、开端和结局完整",
                },
                {
                    "title": "待确认故事",
                    "start_line": line_count,
                    "end_line": line_count,
                    "confidence": 0.4,
                    "completeness": "uncertain",
                    "content_kind": "fiction",
                    "target_genre": True,
                    "reason": "只有结尾残片",
                },
            ],
            "document_notes": "",
            "_provenance": {"model": "gpt-5.6-luna"},
        }

        records, queue = step_1.automatic_boundary_records(
            detection,
            source_text,
            minimum_confidence=0.8,
            min_chars=1,
            max_chars=10000,
            rights_status=step_1.APPROVED_RIGHTS_STATUS,
        )

        self.assertEqual(records[0]["boundary_status"], "auto_approved")
        self.assertEqual(records[0]["boundary_source"], "gpt-5.6-luna")
        self.assertEqual(records[1]["boundary_status"], "needs_review")
        self.assertIn("confidence_below_threshold", records[1]["review_reasons"])
        self.assertEqual(len(queue), 1)

    def test_deterministic_exclusions_do_not_trigger_sol_boundary_review(self):
        source_text = "# 连载故事\n未完待续。\n"
        detection = {
            "source_path": "刊物/一期.md",
            "source_sha256": step_1.sha256_text(source_text),
            "line_count": 2,
            "stories": [
                {
                    "title": "连载故事",
                    "start_line": 1,
                    "end_line": 2,
                    "confidence": 0.99,
                    "completeness": "installment",
                    "content_kind": "fiction",
                    "target_genre": True,
                    "reason": "本期没有结局",
                }
            ],
            "document_notes": "",
            "_provenance": {"model": "gpt-5.6-luna"},
        }

        records, queue = step_1.automatic_boundary_records(
            detection,
            source_text,
            minimum_confidence=0.8,
            min_chars=800,
            max_chars=50000,
            rights_status=step_1.APPROVED_RIGHTS_STATUS,
        )

        self.assertEqual(records[0]["boundary_status"], "excluded")
        self.assertIn("completeness_installment", records[0]["review_reasons"])
        self.assertIn("too_short", records[0]["review_reasons"])
        self.assertFalse(queue)

    def test_high_confidence_ocr_title_difference_is_warning_not_sol_review(self):
        source_text = "# 请把 还给我\n" + ("正文内容。" * 200) + "\n结局。\n"
        detection = {
            "source_path": "刊物/一期.md",
            "source_sha256": step_1.sha256_text(source_text),
            "line_count": 3,
            "stories": [
                {
                    "title": "请把心还给我",
                    "start_line": 1,
                    "end_line": 3,
                    "confidence": 0.96,
                    "completeness": "complete",
                    "content_kind": "fiction",
                    "target_genre": True,
                    "reason": "目录标题与正文 OCR 标题对应",
                }
            ],
            "document_notes": "",
            "_provenance": {"model": "gpt-5.6-luna"},
        }

        records, queue = step_1.automatic_boundary_records(
            detection,
            source_text,
            minimum_confidence=0.8,
            min_chars=100,
            max_chars=50000,
            rights_status=step_1.APPROVED_RIGHTS_STATUS,
        )

        self.assertEqual(records[0]["boundary_status"], "auto_approved")
        self.assertIn("title_not_near_start", records[0]["review_reasons"])
        self.assertFalse(queue)

    def test_boundary_evidence_contains_exact_segment_tail_lines(self):
        source_text = "# 第一篇\n开头。\n结尾。\n\n# 第二篇\n正文。\n"

        evidence = step_1.build_boundary_evidence(source_text)

        self.assertIn("L1\tH1", evidence)
        self.assertIn("segment_end=L3", evidence)
        self.assertIn("L3:结尾。", evidence)
        self.assertIn("L5\tH1", evidence)

    def test_auto_approved_boundary_can_be_extracted_without_human_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "training"
            source = input_dir / "刊物" / "一期.md"
            source.parent.mkdir(parents=True)
            source_text = "# 雨夜来客\n" + ("张明在雨夜听见敲门声。\n" * 100) + "真相揭晓。\n"
            source.write_text(source_text, encoding="utf-8")
            line_count = len(source_text.splitlines())
            detection = {
                "source_path": "刊物/一期.md",
                "source_sha256": step_1.sha256_text(source_text),
                "line_count": line_count,
                "stories": [
                    {
                        "title": "雨夜来客",
                        "start_line": 1,
                        "end_line": line_count,
                        "confidence": 0.96,
                        "completeness": "complete",
                        "content_kind": "fiction",
                        "target_genre": True,
                        "reason": "故事起止和结局完整",
                    }
                ],
                "document_notes": "",
                "_provenance": {"model": "gpt-5.6-luna"},
            }
            boundaries, queue = step_1.automatic_boundary_records(
                detection,
                source_text,
                minimum_confidence=0.8,
                min_chars=10,
                max_chars=10000,
                rights_status=step_1.APPROVED_RIGHTS_STATUS,
            )
            for boundary in boundaries:
                boundary["split"] = "train"
            manifest = root / "boundaries.auto.jsonl"
            step_1.write_jsonl(manifest, boundaries)

            stories = step_1.prepare_stories(
                input_dir,
                root / "work",
                manifest,
                min_chars=10,
                max_chars=10000,
                simhash_threshold=3,
                dry_run=False,
            )

            self.assertFalse(queue)
            self.assertEqual(len(stories), 1)
            self.assertEqual(stories[0]["boundary_status"], "auto_approved")
            self.assertEqual(stories[0]["split"], "train")

    def test_step_2_boundary_gate_blocks_incomplete_source(self):
        analysis = valid_analysis(SOURCE_ID_TRAIN)
        self.assertTrue(step_2.boundary_assessment_passes(analysis))

        analysis["boundary_assessment"]["status"] = "incomplete"
        analysis["boundary_assessment"]["issues"] = ["缺少结尾"]
        self.assertFalse(step_2.boundary_assessment_passes(analysis))

    def test_step_6_auto_approval_only_accepts_clean_training_candidate(self):
        candidate = {
            "story": story_record(SOURCE_ID_TRAIN, "train"),
            "pipeline_decision": "pass",
            "analysis": valid_analysis(SOURCE_ID_TRAIN),
            "rewrite": {
                **valid_rewrite(SOURCE_ID_TRAIN),
                "_deterministic_checks": {
                    "forbidden_markers": [],
                    "new_name_candidates": [],
                },
            },
        }

        self.assertTrue(step_6.can_auto_approve_candidate(candidate))
        candidate["story"]["split"] = "validation"
        self.assertFalse(step_6.can_auto_approve_candidate(candidate))

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
                        "split": "blind",
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
                simhash_threshold=3,
                dry_run=False,
            )

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["eligible_for_cloud"])
            self.assertEqual(records[0]["split"], "blind")
            story_text = (work_dir / records[0]["story_path"]).read_text(encoding="utf-8")
            self.assertNotIn("images/a.jpg", story_text)
            self.assertIn("结局揭晓", story_text)

    def test_prepare_stories_skips_unreviewed_template_rows_with_null_end_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "training"
            collection = input_dir / "刊物"
            collection.mkdir(parents=True)
            (collection / "一期.md").write_text(
                "# 封面\n# 完整故事\n张明听见敲门声。\n他打开门。\n真相揭晓。\n",
                encoding="utf-8",
            )
            boundaries = root / "boundaries.jsonl"
            approved = boundary_record(2, 5, "完整故事")
            step_1.write_jsonl(
                boundaries,
                [
                    {
                        "source_path": "刊物/一期.md",
                        "title": "封面",
                        "start_line": 1,
                        "end_line": None,
                        "boundary_status": "needs_review",
                        "rights_status": "unknown",
                        "split": "train",
                    },
                    approved,
                ],
            )

            records = step_1.prepare_stories(
                input_dir,
                root / "work",
                boundaries,
                min_chars=1,
                max_chars=100,
                simhash_threshold=3,
                dry_run=True,
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["title"], "完整故事")

    def test_prepare_stories_summarizes_approved_rows_without_end_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boundaries = root / "boundaries.jsonl"
            step_1.write_jsonl(
                boundaries,
                [
                    {
                        "source_path": "刊物/一期.md",
                        "title": f"错误候选{index}",
                        "start_line": index,
                        "end_line": None,
                        "boundary_status": "approved",
                        "rights_status": step_1.APPROVED_RIGHTS_STATUS,
                        "split": "train",
                    }
                    for index in (1, 2)
                ],
            )

            with self.assertRaisesRegex(
                step_1.PipelineError,
                "有 2 条 approved 记录缺少有效完整边界",
            ):
                step_1.prepare_stories(
                    root / "training",
                    root / "work",
                    boundaries,
                    min_chars=1,
                    max_chars=100,
                    simhash_threshold=3,
                    dry_run=True,
                )

    def test_codex_command_is_ephemeral_read_only_and_schema_constrained(self):
        command = step_1.codex_command(
            prompt="处理故事",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            schema_path=Path("schema.json"),
            output_path=Path("output.json"),
        )

        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertNotIn("--profile", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-terra")
        self.assertIn("--output-schema", command)
        self.assertIn('model_reasoning_effort="high"', command)

    def test_automatic_model_policy_rejects_sol_alias_fast_profiles_and_xhigh(self):
        for model in ("gpt-5.6", "gpt-5.6-sol"):
            with self.subTest(model=model), self.assertRaisesRegex(
                step_1.PipelineError, "禁止 Sol"
            ):
                step_1.codex_command(
                    prompt="测试",
                    model=model,
                    reasoning_effort="medium",
                    schema_path=Path("schema.json"),
                    output_path=Path("output.json"),
                )
        with self.assertRaisesRegex(step_1.PipelineError, "xhigh/max/pro"):
            step_1.codex_command(
                prompt="测试",
                model="gpt-5.6-luna",
                reasoning_effort="xhigh",
                schema_path=Path("schema.json"),
                output_path=Path("output.json"),
            )
        for parser in (
            step_1.build_parser(),
            step_2.build_parser(),
            step_3.build_parser(),
            step_4.build_parser(),
            step_5.build_parser(),
        ):
            self.assertNotIn("profile", vars(parser.parse_args([])))

    def test_validation_failure_is_not_retried_with_same_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "result.json"
            temporary_path = output_path.with_suffix(".json.tmp")

            class InvalidProcess:
                returncode = 0
                pid = 999998

                def communicate(self, timeout=None):
                    temporary_path.write_text("{}", encoding="utf-8")
                    return "", ""

                def poll(self):
                    return 0

            with (
                patch.object(step_1, "codex_command", return_value=["codex"]),
                patch.object(
                    step_1.subprocess,
                    "Popen",
                    return_value=InvalidProcess(),
                ) as popen,
            ):
                with self.assertRaisesRegex(step_1.PipelineTaskFailed, "已尝试 1 次"):
                    step_1.run_codex_task(
                        prompt="测试",
                        model="gpt-5.6-luna",
                        reasoning_effort="medium",
                        schema_path=Path(directory) / "schema.json",
                        output_path=output_path,
                        validator=lambda value: (_ for _ in ()).throw(
                            step_1.PipelineError("字段不匹配")
                        ),
                        retries=5,
                        timeout=30,
                    )
            self.assertEqual(popen.call_count, 1)

    def test_quality_fallback_uses_terra_high_once_then_requires_manual_sol(self):
        validation_error = step_1.PipelineTaskFailed(
            "结构校验失败",
            failure_kind="validation",
        )
        with patch.object(
            step_1,
            "run_codex_task",
            side_effect=[validation_error, {"ok": True}],
        ) as run_task:
            result, model, effort, used_fallback = (
                step_1.run_codex_task_with_quality_fallback(
                    prompt="测试",
                    model="gpt-5.6-terra",
                    reasoning_effort="medium",
                    fallback_model="gpt-5.6-terra",
                    fallback_reasoning_effort="high",
                    schema_path=Path("schema.json"),
                    output_path=Path("output.json"),
                    validator=lambda value: None,
                    retries=1,
                    timeout=30,
                )
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual((model, effort, used_fallback), ("gpt-5.6-terra", "high", True))
        self.assertEqual(run_task.call_count, 2)
        self.assertEqual(run_task.call_args_list[1].kwargs["retries"], 0)

        with patch.object(
            step_1,
            "run_codex_task",
            side_effect=[validation_error, validation_error],
        ):
            with self.assertRaisesRegex(
                step_1.PipelineManualEscalationRequired,
                "需要人工 Sol",
            ):
                step_1.run_codex_task_with_quality_fallback(
                    prompt="测试",
                    model="gpt-5.6-terra",
                    reasoning_effort="medium",
                    fallback_model="gpt-5.6-terra",
                    fallback_reasoning_effort="high",
                    schema_path=Path("schema.json"),
                    output_path=Path("output.json"),
                    validator=lambda value: None,
                    retries=1,
                    timeout=30,
                )

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

    def test_limit_caps_pending_items_and_allows_later_batches(self):
        pending_after_resume = ["story_3", "story_4", "story_5"]

        self.assertEqual(
            step_1.limit_pending_items(pending_after_resume, 2),
            ["story_3", "story_4"],
        )
        self.assertEqual(
            step_1.limit_pending_items(pending_after_resume[2:], 2),
            ["story_5"],
        )
        with self.assertRaisesRegex(step_1.PipelineError, "limit 不能小于 0"):
            step_1.limit_pending_items(pending_after_resume, -1)

    def test_parallel_runner_completes_independent_items_and_isolates_failure(self):
        completed: list[int] = []
        errors: list[tuple[int, str]] = []

        def task(item: int) -> None:
            if item == 2:
                raise step_1.PipelineError("模拟失败")
            completed.append(item)

        failures = step_1.run_parallel_tasks(
            [1, 2, 3],
            workers=2,
            heartbeat_seconds=1,
            stage_label="测试并发",
            item_label=str,
            task=task,
            on_error=lambda item, error: errors.append((item, str(error))),
            continue_on_error=True,
        )

        self.assertEqual(failures, 1)
        self.assertEqual(set(completed), {1, 3})
        self.assertEqual(errors, [(2, "模拟失败")])

    def test_codex_usage_limit_stops_without_retrying(self):
        class QuotaProcess:
            returncode = 1
            pid = 999999

            def communicate(self, timeout=None):
                return (
                    "",
                    "ERROR: You've hit your usage limit. Purchase more credits "
                    "or try again at 6:09 PM.",
                )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "result.json"
            with (
                patch.object(step_1, "codex_command", return_value=["codex"]),
                patch.object(
                    step_1.subprocess,
                    "Popen",
                    return_value=QuotaProcess(),
                ) as popen,
            ):
                with self.assertRaisesRegex(
                    step_1.PipelineQuotaExhausted,
                    "使用额度已耗尽",
                ):
                    step_1.run_codex_task(
                        prompt="测试",
                        model="test",
                        reasoning_effort="medium",
                        schema_path=Path(directory) / "schema.json",
                        output_path=output_path,
                        validator=lambda value: None,
                        retries=5,
                        timeout=30,
                    )

            self.assertEqual(popen.call_count, 1)
            self.assertFalse(output_path.with_suffix(".json.tmp").exists())

    def test_parallel_runner_stops_on_quota_and_records_resumable_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            progress_path = Path(directory) / "progress.json"
            completed: list[int] = []
            errors: list[int] = []

            def task(item: int) -> None:
                if item == 2:
                    raise step_1.PipelineQuotaExhausted("模拟额度耗尽")
                completed.append(item)

            try:
                with self.assertRaisesRegex(
                    step_1.PipelineQuotaExhausted,
                    "已停止后续任务",
                ):
                    step_1.run_parallel_tasks(
                        [1, 2, 3],
                        workers=1,
                        heartbeat_seconds=1,
                        stage_label="测试额度",
                        item_label=str,
                        task=task,
                        on_error=lambda item, error: errors.append(item),
                        continue_on_error=True,
                        progress_path=progress_path,
                        progress_stage="test_quota",
                        total_items=5,
                        completed_before=2,
                    )
            finally:
                step_1._MODEL_TASK_CANCELLED.clear()

            progress = step_1.read_json(progress_path)
            self.assertEqual(completed, [1])
            self.assertEqual(errors, [2])
            self.assertEqual(progress["status"], "quota_exhausted")
            self.assertEqual(progress["completed_items"], 3)
            self.assertEqual(progress["pending_items"], 2)
            self.assertEqual(progress["skipped_existing_items"], 2)
            self.assertEqual(progress["completed_this_run"], 1)
            self.assertEqual(progress["failed_this_run"], 1)

    def test_parallel_progress_marks_limited_successful_batch_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            progress_path = Path(directory) / "progress.json"

            failures = step_1.run_parallel_tasks(
                [3, 4],
                workers=1,
                heartbeat_seconds=1,
                stage_label="测试分批",
                item_label=str,
                task=lambda item: None,
                on_error=lambda item, error: None,
                continue_on_error=True,
                progress_path=progress_path,
                progress_stage="test_batch",
                total_items=5,
                completed_before=2,
            )

            progress = step_1.read_json(progress_path)
            self.assertEqual(failures, 0)
            self.assertEqual(progress["status"], "partial")
            self.assertEqual(progress["completed_items"], 4)
            self.assertEqual(progress["pending_items"], 1)

    def test_step_2_rejects_partial_step_1_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            manifest = work_dir / "stories.jsonl"
            step_1.write_jsonl(manifest, [])
            step_1.write_json(
                work_dir / "automatic_boundary_report.json",
                {
                    "source_count": 80,
                    "completed_source_count": 78,
                    "failed_source_count": 48,
                },
            )

            with self.assertRaisesRegex(step_1.PipelineError, "Step 1 尚未完整结束"):
                step_2.require_completed_step_1(work_dir, manifest)

            step_1.write_json(
                work_dir / "automatic_boundary_report.json",
                {
                    "source_count": 80,
                    "completed_source_count": 80,
                    "failed_source_count": 0,
                },
            )
            step_1.write_json(
                work_dir / "progress" / "step_1_boundary_review.json",
                {"status": "quota_exhausted"},
            )
            with self.assertRaisesRegex(step_1.PipelineError, "进度不是 completed"):
                step_2.require_completed_step_1(work_dir, manifest)

    def test_model_task_cancellation_terminates_active_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "result.json"
            failures: list[Exception] = []
            step_1._MODEL_TASK_CANCELLED.clear()

            def run_task() -> None:
                try:
                    step_1.run_codex_task(
                        prompt="测试",
                        model="test",
                        reasoning_effort="medium",
                        schema_path=Path(directory) / "schema.json",
                        output_path=output_path,
                        validator=lambda value: None,
                        retries=0,
                        timeout=30,
                    )
                except Exception as error:
                    failures.append(error)

            command = [sys.executable, "-c", "import time; time.sleep(30)"]
            with patch.object(step_1, "codex_command", return_value=command):
                worker = threading.Thread(target=run_task)
                worker.start()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with step_1._ACTIVE_MODEL_PROCESSES_LOCK:
                        if step_1._ACTIVE_MODEL_PROCESSES:
                            break
                    time.sleep(0.01)
                active_count = step_1.cancel_active_model_tasks()
                worker.join(timeout=5)

            self.assertGreaterEqual(active_count, 1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0], step_1.PipelineInterrupted)
            step_1._MODEL_TASK_CANCELLED.clear()

    def test_duplicate_canonical_prefers_protected_test_over_train(self):
        common = {
            "content_hash": "same",
            "simhash64": "0000000000000000",
            "duplicate_of": None,
            "duplicate_kind": None,
        }
        records = [
            {**common, "source_id": "story_train", "split": "train"},
            {**common, "source_id": "story_test", "split": "test"},
        ]

        step_1.mark_duplicates(records, threshold=3)

        by_id = {record["source_id"]: record for record in records}
        self.assertIsNone(by_id["story_test"]["duplicate_of"])
        self.assertEqual(by_id["story_train"]["duplicate_of"], "story_test")

    def test_model_stage_worker_defaults_are_conservative(self):
        self.assertEqual(step_1.build_parser().parse_args([]).boundary_workers, 3)
        self.assertEqual(step_1.build_parser().parse_args([]).boundary_review_limit, 10)
        self.assertEqual(step_2.build_parser().parse_args([]).workers, 2)
        self.assertEqual(step_2.build_parser().parse_args([]).limit, 20)
        self.assertEqual(step_2.DEFAULT_REASONING_EFFORT, "medium")
        self.assertEqual(step_2.DEFAULT_ANALYSIS_SPLITS, {"train", "validation"})
        self.assertEqual(step_3.build_parser().parse_args([]).workers, 2)
        self.assertEqual(step_3.DEFAULT_MODEL, "gpt-5.6-luna")
        self.assertEqual(step_3.DEFAULT_TEACHER_MODEL, "gpt-5.6-terra")
        self.assertEqual(step_4.build_parser().parse_args([]).workers, 2)
        self.assertEqual(step_4.DEFAULT_MODEL, "gpt-5.6-luna")
        self.assertEqual(step_5.DEFAULT_MODEL, "gpt-5.6-terra")
        self.assertEqual(step_5.build_parser().parse_args([]).reasoning_effort, "medium")
        self.assertEqual(step_3.DEFAULT_TEACHER_SPLITS, {"train", "validation"})

    def test_blind_test_defaults_to_all_frozen_stories(self):
        self.assertIsNone(step_7.build_parser().parse_args([]).count)

        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            story = story_record(SOURCE_ID_BLIND, "blind")
            step_1.write_jsonl(work_dir / "stories.jsonl", [story])
            story_path = work_dir / story["story_path"]
            story_path.parent.mkdir(parents=True)
            story_path.write_text("雨夜里的完整故事。\n", encoding="utf-8")
            for variant in step_7.DEFAULT_VARIANTS:
                write_json(
                    work_dir / "rewrites" / variant / f"{SOURCE_ID_BLIND}.json",
                    valid_rewrite(SOURCE_ID_BLIND),
                )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                exit_code = step_7.main(
                    ["--work-dir", str(work_dir), "--dry-run"]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("盲测故事：1；变体：3；音频子集：1", output.getvalue())

    def test_compact_boundary_packets_exclude_story_middle(self):
        lines = [f"第{index}行" for index in range(1, 401)]
        source_text = "\n".join(lines)
        detection = {
            "source_path": "刊物/一期.md",
            "source_sha256": step_1.sha256_text(source_text),
            "line_count": len(lines),
            "stories": [
                {
                    "title": "风险故事",
                    "start_line": 100,
                    "end_line": 300,
                    "completeness": "uncertain",
                    "content_kind": "fiction",
                    "target_genre": True,
                    "confidence": 0.6,
                    "reason": "待核对",
                }
            ],
            "document_notes": "",
        }

        review_packet = step_1.build_boundary_review_packet(
            source_text,
            detection,
            minimum_confidence=0.8,
            context_lines=10,
        )
        self.assertIn("L100\t第100行", review_packet)
        self.assertIn("L300\t第300行", review_packet)
        self.assertNotIn("L200\t第200行", review_packet)

        with tempfile.TemporaryDirectory() as directory:
            source_file = Path(directory) / "一期.md"
            source_file.write_text(source_text, encoding="utf-8")
            story = {
                "source_path": "刊物/一期.md",
                "start_line": 100,
                "end_line": 300,
            }
            context = step_2.build_story_boundary_context(
                story,
                source_file,
                context_lines=10,
            )
            self.assertIn("L100\t第100行", context)
            self.assertIn("L300\t第300行", context)
            self.assertNotIn("L200\t第200行", context)

    def test_automatic_run_only_resumes_its_own_step_1_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory)
            step_1.write_jsonl(work_dir / "boundaries.auto.jsonl", [])
            write_json(
                work_dir / "step_1_report.json",
                {"source_manifest": str(work_dir / "boundaries.auto.jsonl")},
            )

            self.assertTrue(step_1.automatic_run_can_resume(work_dir))
            write_json(
                work_dir / "step_1_report.json",
                {"source_manifest": str(work_dir / "boundaries.reviewed.jsonl")},
            )
            self.assertFalse(step_1.automatic_run_can_resume(work_dir))

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
                    work_dir / "analysis" / f"{source_id}.json",
                    valid_analysis(source_id),
                )
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


def valid_analysis(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "characters": [],
        "immutable_facts": [],
        "clues": [],
        "misdirection": [],
        "twist": "",
        "story_dna": {
            "genre": "悬疑",
            "narrative_viewpoint": "第三人称",
            "timeline": "顺叙",
            "suspense_mechanism": [],
            "audio_adaptation_risks": [],
        },
        "ocr_flags": [],
        "difficulty": "normal",
        "boundary_assessment": {
            "status": "complete",
            "confidence": 0.95,
            "issues": [],
            "suggested_start_line": None,
            "suggested_end_line": None,
        },
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
