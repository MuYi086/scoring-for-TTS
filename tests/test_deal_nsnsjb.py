"""training/script/deal_nsnsjb.py 的无网络单元测试。"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO_ROOT / "training" / "script" / "deal_nsnsjb.py"
    spec = importlib.util.spec_from_file_location("deal_nsnsjb", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DealNsnsjbTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_collect_pdf_files_is_recursive_case_insensitive_and_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            (source_dir / "b.PDF").write_bytes(b"pdf")
            nested_dir = source_dir / "nested"
            nested_dir.mkdir()
            (nested_dir / "a.pdf").write_bytes(b"pdf")
            (source_dir / "ignore.txt").write_text("not a pdf", encoding="utf-8")

            files = self.module.collect_pdf_files(source_dir)

            self.assertEqual(
                [path.relative_to(source_dir).as_posix() for path in files],
                ["b.PDF", "nested/a.pdf"],
            )

    def test_duplicate_pdf_stems_are_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            first = source_dir / "first" / "issue.pdf"
            second = source_dir / "second" / "issue.PDF"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"pdf")
            second.write_bytes(b"pdf")

            with self.assertRaisesRegex(ValueError, "同名 PDF"):
                self.module.ensure_unique_output_paths(
                    self.module.collect_pdf_files(source_dir), source_dir / "output"
                )

    def test_oversized_pdf_is_rejected_before_mineru_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "oversized.pdf"
            with pdf_path.open("wb") as output:
                output.truncate(self.module.MAX_UPLOAD_SIZE_BYTES + 1)

            with self.assertRaisesRegex(ValueError, "200 MB"):
                self.module.ensure_within_upload_size_limit([pdf_path])

    def test_markdown_from_zip_prefers_full_markdown(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("result/other.md", "other")
            archive.writestr("result/full.md", "full content")

        self.assertEqual(self.module.markdown_from_zip(archive_bytes.getvalue()), "full content")

    def test_get_batch_upload_urls_uses_mineru_v4_payload_and_data_ids(self):
        captured: dict[str, object] = {}

        def fake_request_json(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return {
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "file_urls": ["https://upload.example/1", "https://upload.example/2"],
                },
            }

        items = [
            self.module.BatchItem(
                data_id="document-000001",
                pdf_path=Path("first.pdf"),
                output_path=Path("first.md"),
            ),
            self.module.BatchItem(
                data_id="document-000002",
                pdf_path=Path("second.pdf"),
                output_path=Path("second.md"),
            ),
        ]
        original_request_json = self.module.request_json
        self.module.request_json = fake_request_json
        try:
            batch_id, upload_urls = self.module.get_batch_upload_urls(items, "test-key")
        finally:
            self.module.request_json = original_request_json

        self.assertEqual(batch_id, "batch-1")
        self.assertEqual(
            upload_urls,
            ["https://upload.example/1", "https://upload.example/2"],
        )
        self.assertEqual(captured["url"], f"{self.module.API_BASE}/file-urls/batch")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(
            captured["payload"],
            {
                "files": [
                    {"name": "first.pdf", "data_id": "document-000001"},
                    {"name": "second.pdf", "data_id": "document-000002"},
                ],
                "model_version": "vlm",
                "language": "ch",
            },
        )

    def test_split_batches_honors_mineru_fifty_file_limit(self):
        items = [
            self.module.BatchItem(
                data_id=f"document-{index:06d}",
                pdf_path=Path(f"{index}.pdf"),
                output_path=Path(f"{index}.md"),
            )
            for index in range(51)
        ]

        batches = self.module.split_batches(items, self.module.MAX_BATCH_SIZE)

        self.assertEqual([len(batch) for batch in batches], [50, 1])

    def test_match_batch_results_prefers_data_id_and_falls_back_to_filename(self):
        items = (
            self.module.BatchItem("id-1", Path("first.pdf"), Path("first.md")),
            self.module.BatchItem("id-2", Path("second.pdf"), Path("second.md")),
        )
        results = [
            {"data_id": "id-1", "file_name": "wrong.pdf", "state": "done"},
            {"file_name": "second.pdf", "state": "failed"},
        ]

        matched = self.module.match_batch_results(items, results)

        self.assertEqual(matched["id-1"]["state"], "done")
        self.assertEqual(matched["id-2"]["state"], "failed")

    def test_collect_batch_results_saves_each_done_file_before_next_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            first = self.module.BatchItem(
                "id-1", Path("first.pdf"), output_dir / "first.md"
            )
            second = self.module.BatchItem(
                "id-2", Path("second.pdf"), output_dir / "second.md"
            )
            batch = self.module.SubmittedBatch("batch-1", (first, second))
            call_count = 0

            def get_snapshot(*unused_args):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return [
                        {"data_id": "id-1", "state": "done", "full_zip_url": "zip-1"},
                        {"data_id": "id-2", "state": "running"},
                    ]
                self.assertTrue(first.output_path.exists())
                return [
                    {"data_id": "id-1", "state": "done", "full_zip_url": "zip-1"},
                    {"data_id": "id-2", "state": "done", "full_zip_url": "zip-2"},
                ]

            def write_result(item, unused_zip_url):
                item.output_path.write_text("markdown", encoding="utf-8")

            with patch.object(self.module, "get_batch_results", side_effect=get_snapshot):
                with patch.object(
                    self.module,
                    "download_and_write_result",
                    side_effect=write_result,
                ):
                    with patch.object(self.module.time, "sleep") as sleep:
                        succeeded, failed = self.module.collect_batch_results(
                            batch,
                            api_key="test-key",
                            poll_interval=5,
                            poll_timeout=30,
                            download_workers=2,
                        )

            self.assertEqual((succeeded, failed), (2, 0))
            self.assertEqual(call_count, 2)
            sleep.assert_called_once_with(5)

    def test_collect_batch_results_isolates_per_file_failures_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            first = self.module.BatchItem(
                "id-1", Path("first.pdf"), output_dir / "first.md"
            )
            second = self.module.BatchItem(
                "id-2", Path("second.pdf"), output_dir / "second.md"
            )
            batch = self.module.SubmittedBatch("batch-1", (first, second))
            results = [
                {"data_id": "id-1", "state": "done", "full_zip_url": "zip-1"},
                {"data_id": "id-2", "state": "failed", "err_msg": "bad pdf"},
            ]

            def write_result(item, unused_zip_url):
                item.output_path.write_text("markdown", encoding="utf-8")

            with patch.object(self.module, "get_batch_results", return_value=results):
                with patch.object(
                    self.module,
                    "download_and_write_result",
                    side_effect=write_result,
                ):
                    succeeded, failed = self.module.collect_batch_results(
                        batch,
                        api_key="test-key",
                        poll_interval=5,
                        poll_timeout=30,
                        download_workers=2,
                    )

            self.assertEqual((succeeded, failed), (1, 1))
            self.assertEqual(first.output_path.read_text(encoding="utf-8"), "markdown")
            self.assertIn("bad pdf", second.error_path.read_text(encoding="utf-8"))

    def test_upload_file_uses_curl_upload_file_without_network(self):
        completed = self.module.subprocess.CompletedProcess([], 0, stdout="200", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "issue.pdf"
            pdf_path.write_bytes(b"pdf")
            with patch.object(self.module.subprocess, "run", return_value=completed) as run:
                self.module.upload_file(pdf_path, "https://upload.example/signed")

        command = run.call_args.args[0]
        self.assertIn("--upload-file", command)
        self.assertEqual(command[command.index("--upload-file") + 1], str(pdf_path))
        self.assertEqual(command[-1], "https://upload.example/signed")
        self.assertNotIn("Content-Type", command)
        self.assertIn("--speed-limit", command)
        self.assertIn("--speed-time", command)

    def test_upload_file_retries_broken_connection_without_network(self):
        broken_pipe = self.module.subprocess.CompletedProcess(
            [], 55, stdout="000", stderr="curl: (55) Send failure: Broken pipe"
        )
        uploaded = self.module.subprocess.CompletedProcess([], 0, stdout="200", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "issue.pdf"
            pdf_path.write_bytes(b"pdf")
            with patch.object(
                self.module.subprocess,
                "run",
                side_effect=[broken_pipe, uploaded],
            ) as run:
                with patch.object(self.module.time, "sleep") as sleep:
                    self.module.upload_file(pdf_path, "https://upload.example/signed")

        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(self.module.UPLOAD_RETRY_DELAY_SECONDS)

    def test_upload_file_does_not_retry_http_403_without_network(self):
        forbidden = self.module.subprocess.CompletedProcess(
            [], 22, stdout="403", stderr="curl: (22) HTTP 403"
        )
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "issue.pdf"
            pdf_path.write_bytes(b"pdf")
            with patch.object(self.module.subprocess, "run", return_value=forbidden) as run:
                with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                    self.module.upload_file(pdf_path, "https://upload.example/signed")

        run.assert_called_once()

    def test_get_api_token_reads_mineu_api_key_and_removes_bearer_prefix(self):
        environment = {
            "MINEU_API_KEY": "  Bearer current-token  ",
        }

        with patch.dict(self.module.os.environ, environment, clear=True):
            self.assertEqual(self.module.get_api_token(), "current-token")

    def test_get_api_token_rejects_other_mineru_variable_names(self):
        environment = {
            "MINERU_API_TOKEN": "current-token",
            "MINERU_API_KEY": "current-token",
        }

        with patch.dict(self.module.os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "MINEU_API_KEY"):
                self.module.get_api_token()

    def test_request_json_gives_safe_401_remediation(self):
        request = self.module.Request("https://mineru.net/api/v4/file-urls/batch")
        http_error = self.module.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"msg":"user authenticate failed"}'),
        )

        with patch.object(self.module, "urlopen", side_effect=http_error):
            with self.assertRaisesRegex(self.module.MinerUAuthenticationError, "MINEU_API_KEY"):
                self.module.request_json(request, timeout=1)

    def test_request_json_reports_connectivity_errors_separately(self):
        request = self.module.Request("https://mineru.net/api/v4/file-urls/batch")
        with patch.object(self.module, "urlopen", side_effect=URLError("timed out")):
            with self.assertRaisesRegex(self.module.MinerUConnectionError, "无法连接 MinerU"):
                self.module.request_json(request, timeout=1)

    def test_dry_run_skips_existing_output_without_requiring_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory) / "source"
            output_dir = Path(directory) / "output"
            source_dir.mkdir()
            output_dir.mkdir()
            (source_dir / "2002-01.pdf").write_bytes(b"pdf")
            (output_dir / "2002-01.md").write_text("already done", encoding="utf-8")
            (source_dir / "2002-02.pdf").write_bytes(b"pdf")
            args = argparse.Namespace(
                source_dir=source_dir,
                output_dir=output_dir,
                overwrite=False,
                dry_run=True,
                poll_interval=1.0,
                poll_timeout=1.0,
                batch_size=50,
                upload_workers=4,
                download_workers=4,
            )

            summary = self.module.run(args)

            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.skipped, 1)
            self.assertEqual(summary.succeeded, 0)
            self.assertEqual(summary.failed, 0)

    def test_run_stops_after_batch_submission_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory) / "source"
            output_dir = Path(directory) / "output"
            source_dir.mkdir()
            for name in ("2002-01.pdf", "2002-02.pdf"):
                (source_dir / name).write_bytes(b"pdf")
            args = argparse.Namespace(
                source_dir=source_dir,
                output_dir=output_dir,
                overwrite=False,
                dry_run=False,
                poll_interval=1.0,
                poll_timeout=1.0,
                batch_size=50,
                upload_workers=4,
                download_workers=4,
            )

            def fail_submission(*unused_args):
                raise RuntimeError("user authenticate failed")

            with patch.object(self.module, "get_api_token", return_value="test-token"):
                with patch.object(self.module, "submit_batch", side_effect=fail_submission):
                    with self.assertRaisesRegex(RuntimeError, "user authenticate failed"):
                        self.module.run(args)

            for name in ("2002-01.md.error", "2002-02.md.error"):
                error_path = output_dir / name
                self.assertIn("user authenticate failed", error_path.read_text(encoding="utf-8"))

    def test_run_finishes_each_batch_before_submitting_the_next(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory) / "source"
            output_dir = Path(directory) / "output"
            source_dir.mkdir()
            for index in range(51):
                (source_dir / f"{index:02d}.pdf").write_bytes(b"pdf")
            args = argparse.Namespace(
                source_dir=source_dir,
                output_dir=output_dir,
                overwrite=False,
                dry_run=False,
                poll_interval=1.0,
                poll_timeout=1.0,
                batch_size=50,
                upload_workers=4,
                download_workers=4,
            )
            events: list[tuple[str, int]] = []

            def submit(items, *unused_args):
                events.append(("submit", len(items)))
                return self.module.SubmittedBatch("batch", tuple(items)), 0

            def collect(batch, *unused_args):
                events.append(("collect", len(batch.items)))
                return len(batch.items), 0

            with patch.object(self.module, "get_api_token", return_value="test-token"):
                with patch.object(self.module, "submit_batch", side_effect=submit):
                    with patch.object(
                        self.module,
                        "collect_batch_results",
                        side_effect=collect,
                    ):
                        summary = self.module.run(args)

            self.assertEqual(
                events,
                [("submit", 50), ("collect", 50), ("submit", 1), ("collect", 1)],
            )
            self.assertEqual(summary.succeeded, 51)
            self.assertEqual(summary.failed, 0)

    def test_write_text_atomically_replaces_previous_content(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "issue.md"
            output_path.parent.mkdir()
            output_path.write_text("old", encoding="utf-8")

            self.module.write_text_atomically(output_path, "new")

            self.assertEqual(output_path.read_text(encoding="utf-8"), "new")
            self.assertFalse((output_path.parent / ".issue.md.tmp").exists())
