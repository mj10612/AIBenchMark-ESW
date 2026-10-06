import io
import json
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw import cli
from aibenchmark_esw.dataset import DatasetLoader, validate_task_assets
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


class TestTaskValidation(unittest.TestCase):
    def copy_task(self, root, task_id="custom_crc"):
        original = DatasetLoader().get_task("tier1_crc16")
        destination = root / task_id
        shutil.copytree(original.task_dir, destination)
        path = destination / "task.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["id"] = task_id
        path.write_text(json.dumps(data), encoding="utf-8")
        return destination

    def test_validate_bundled_tasks_without_compiler_or_provider(self):
        args = cli.build_parser().parse_args(["validate"])
        with patch.object(cli, "ExecutionSandbox") as compiler, patch.object(cli, "LLMClient") as provider:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.cmd_validate(args), 0)
            compiler.assert_not_called()
            provider.assert_not_called()
        self.assertIn(f"{len(DatasetLoader().list_tasks())} passed, 0 failed", output.getvalue())

    def test_missing_assets_never_generate_and_are_retained_as_failed_results(self):
        for relative, diagnostic in (("prompt.md", "Missing prompt"),
                ("include/crc16.h", "Missing API header"), ("src/crc16.c", "Missing starter"),
                ("reference/crc16.c", "Missing reference"), ("tests/test_crc16.c", "Missing test source")):
            with self.subTest(relative=relative), TemporaryDirectory() as directory:
                root = Path(directory) / "tasks"
                task_dir = self.copy_task(root)
                (task_dir / relative).unlink()
                report = Path(directory) / "result.json"
                args = cli.build_parser().parse_args(["run", "--tasks-root", str(root),
                    "--model", "mock", "--output", str(report)])
                with patch.object(cli.LLMClient, "generate_solution") as generate, redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 1)
                    generate.assert_not_called()
                data = json.loads(report.read_text(encoding="utf-8"))
                results = BenchmarkReporter.from_json_dict(data)
                self.assertEqual(len(results), 1)
                self.assertEqual(data["overall_score"], 0)
                self.assertEqual(data["metadata"]["run_status"], "completed")
                self.assertIn(diagnostic, results[0].error_log)
                self.assertIsNone(results[0].generation)
                self.assertFalse(results[0].compiled)

    def test_empty_and_non_utf8_assets_are_diagnosed(self):
        for content, diagnostic in ((b" \n\t", "Empty reference"), (b"\xff", "Unreadable reference")):
            with self.subTest(content=content), TemporaryDirectory() as directory:
                root = Path(directory) / "tasks"
                task_dir = self.copy_task(root)
                (task_dir / "reference/crc16.c").write_bytes(content)
                args = cli.build_parser().parse_args(["validate", "--tasks-root", str(root)])
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(cli.cmd_validate(args), 1)
                self.assertIn(diagnostic, output.getvalue())
                run = cli.build_parser().parse_args(["run", "--tasks-root", str(root), "--model", "mock"])
                with patch.object(cli.LLMClient, "generate_solution") as generate, redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(run), 1)
                    generate.assert_not_called()

    def test_valid_tasks_continue_after_invalid_assets_without_hiding_failures(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "tasks"
            invalid = self.copy_task(root, "a_missing")
            self.copy_task(root, "z_valid")
            (invalid / "tests/test_crc16.c").unlink()
            report = Path(directory) / "result.json"
            args = cli.build_parser().parse_args(["run", "--tasks-root", str(root),
                "--model", "mock", "--output", str(report)])
            reference = DatasetLoader().get_reference_solution("tier1_crc16")
            with patch.object(cli.LLMClient, "generate_solution", return_value=reference) as generate:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 1)
                self.assertEqual(generate.call_count, 1)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(len(BenchmarkReporter.from_json_dict(data)), 2)
            self.assertEqual(data["pass_at_1_pct"], 50)
            self.assertEqual(data["overall_score"], 50)
            self.assertEqual(data["tasks"][1]["scores"]["total"], 100)

    def test_validate_obeys_task_selection_and_rejects_conflicts(self):
        args = cli.build_parser().parse_args(["validate", "--tasks", "tier1_crc16", "--tier", "1"])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.cmd_validate(args), 0)
        self.assertIn("1 passed, 0 failed", output.getvalue())
        for flags in (["--tasks", "unknown"], ["--tasks", ""], ["--tasks", "tier1_crc16", "--tier", "2"]):
            with self.subTest(flags=flags), redirect_stderr(io.StringIO()):
                self.assertEqual(cli.cmd_validate(cli.build_parser().parse_args(["validate", *flags])), 1)

    def test_validation_lists_multiple_problems_in_one_task(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "tasks"
            task_dir = self.copy_task(root)
            (task_dir / "prompt.md").write_text("", encoding="utf-8")
            (task_dir / "reference/crc16.c").unlink()
            errors = validate_task_assets(DatasetLoader(root).get_task("custom_crc"))
            self.assertEqual(len(errors), 2)
            self.assertTrue(any("Empty prompt" in error for error in errors))
            self.assertTrue(any("Missing reference" in error for error in errors))

    def test_unreadable_prompt_keeps_valid_selected_tasks_and_failed_results(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "tasks"
            invalid = self.copy_task(root, "a_invalid")
            self.copy_task(root, "z_valid")
            (invalid / "prompt.md").write_bytes(b"\xff")
            loader = DatasetLoader(root)
            self.assertEqual(len(loader.list_tasks()), 2)
            self.assertIn("Unreadable prompt", validate_task_assets(loader.get_task("a_invalid"))[0])
            args = cli.build_parser().parse_args(["validate", "--tasks-root", str(root)])
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.cmd_validate(args), 1)
            self.assertIn("Unreadable prompt", output.getvalue())
            self.assertIn("z_valid", output.getvalue())
            report = Path(directory) / "result.json"
            args = cli.build_parser().parse_args(["run", "--tasks-root", str(root),
                "--model", "mock", "--output", str(report)])
            reference = DatasetLoader().get_reference_solution("tier1_crc16")
            with patch.object(cli.LLMClient, "generate_solution", return_value=reference) as generate:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.cmd_run(args), 1)
                self.assertEqual(generate.call_count, 1)
            results = json.loads(report.read_text(encoding="utf-8"))["tasks"]
            self.assertEqual([result["task_id"] for result in results], ["a_invalid", "z_valid"])
            self.assertEqual(results[0]["scores"]["total"], 0)
            self.assertEqual(results[1]["scores"]["total"], 100)
            selected = cli.build_parser().parse_args(["run", "--tasks-root", str(root),
                "--model", "baseline", "--tasks", "z_valid"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_run(selected), 0)

    def test_prompt_read_oserror_is_reported_by_asset_validation(self):
        original_read_text = Path.read_text
        def unreadable(path, *args, **kwargs):
            if path.name == "prompt.md":
                raise PermissionError("fixture denies prompt access")
            return original_read_text(path, *args, **kwargs)
        with patch.object(Path, "read_text", unreadable):
            loader = DatasetLoader()
            self.assertEqual(loader.get_task("tier1_crc16").prompt, "")
            self.assertTrue(any("Unreadable prompt" in error for error in
                                validate_task_assets(loader.get_task("tier1_crc16"))))
